"""judge.py - Claude APIを使って各モデルの回答を採点する。"""

import json
import os
import re
from pathlib import Path
from typing import Optional

import anthropic
import yaml
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

ROOT = Path(__file__).parent.parent

# coding_reviewで検出すべき脆弱性リスト（coding.mdの正解リストに準拠）
VULNERABILITIES = [
    {
        "id": "sqli",
        "label": "SQLインジェクション（get_user・create_user）",
        "keywords": ["SQLインジェクション", "sql injection", "f文字列", "f-string", "フォーマット文字列"],
    },
    {
        "id": "md5_hash",
        "label": "MD5使用（非推奨ハッシュ）",
        "keywords": ["MD5", "md5", "非推奨", "bcrypt", "argon2", "sha-256", "hashlib.md5"],
    },
    {
        "id": "plaintext_password",
        "label": "平文パスワード比較（get_user）",
        "keywords": ["平文", "ハッシュ化されていない", "パスワード比較", "user[2] == password", "password比較"],
    },
    {
        "id": "connection_leak",
        "label": "コネクションリーク（with文未使用）",
        "keywords": ["コネクションリーク", "connection leak", "with文", "クローズ", "close", "リーク", "コンテキストマネージャ"],
    },
    {
        "id": "password_exposure",
        "label": "パスワードハッシュ露出（get_all_users）",
        "keywords": ["パスワード", "ハッシュ", "露出", "get_all_users", "全カラム", "機密情報"],
    },
    {
        "id": "missing_commit",
        "label": "コミット漏れ（create_user で commit() 未呼び出し）",
        "keywords": ["commit", "コミット", "書き込み", "確定", "conn.commit"],
    },
]

VULN_JUDGE_PROMPT = """以下のコードレビュー回答を読んで、次の6つの脆弱性・問題点それぞれが「指摘されているか」を判定してください。

コードレビュー回答：
---
{response}
---

判定する問題点：
1. SQLインジェクション（get_user・create_user 両方のf文字列によるSQL組み立て）※どちらか一方の言及でもよい
2. MD5の使用（非推奨ハッシュアルゴリズム）
3. get_user関数でのパスワード平文比較（ハッシュ化されていないパスワードとDBのハッシュを直接比較）
4. with文未使用によるコネクションリーク
5. get_all_usersでパスワードハッシュを含む全カラムを返している（機密情報の露出）
6. create_user で conn.commit() が呼ばれていない（書き込みが確定しない）

各問題が回答内で指摘されているか判定し、以下のJSON形式のみで返してください：
{
  "detections": {
    "sqli": true,
    "md5_hash": true,
    "plaintext_password": true,
    "connection_leak": true,
    "password_exposure": true,
    "missing_commit": true
  },
  "detected_count": 6,
  "notes": "補足コメント（省略可）"
}
"""


def load_config() -> dict:
    """config.yaml を読み込む。"""
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_judge_system_prompt() -> str:
    """judge_prompt.md とスコアシートを組み合わせてシステムプロンプトを生成する。"""
    judge_prompt_path = Path(__file__).parent / "judge_prompt.md"
    scoresheet_path = ROOT / "evaluation" / "scoresheet.md"

    judge_template = judge_prompt_path.read_text(encoding="utf-8")
    scoresheet = scoresheet_path.read_text(encoding="utf-8")

    return judge_template.replace("{scoresheet_content}", scoresheet)


def create_judge_client(config: dict) -> anthropic.Anthropic:
    """採点用Claudeクライアントを生成する。"""
    judge_cfg = config["judge"]
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY が設定されていません")
    return anthropic.Anthropic(api_key=api_key)


def judge_response_with_claude(
    client: anthropic.Anthropic,
    judge_model: str,
    system_prompt: str,
    prompt_id: str,
    prompt_text: str,
    response_text: str,
    max_score: int,
) -> dict:
    """Claudeを使って1つの回答を採点する。

    Args:
        client: Anthropicクライアント
        judge_model: 採点に使うモデルID
        system_prompt: 採点システムプロンプト
        prompt_id: プロンプトID
        prompt_text: 元のプロンプト
        response_text: 採点対象の回答
        max_score: 満点

    Returns:
        採点結果の辞書
    """
    user_message = f"""プロンプトID: {prompt_id}
満点: {max_score}点

【元のプロンプト】
{prompt_text}

【採点対象の回答】
{response_text}
"""

    message = client.messages.create(
        model=judge_model,
        max_tokens=1024,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()

    # JSONブロックを抽出
    json_match = re.search(r"```json\s*(.*?)```", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1).strip()
    else:
        # コードブロックなしの場合はそのまま試みる
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        console.print(f"  [yellow]JSONパース失敗。スコア0として処理: {raw[:100]}[/yellow]")
        result = {
            "score": 0,
            "max_score": max_score,
            "breakdown": {},
            "overall_comment": f"採点エラー: JSONパース失敗",
        }

    return result


def count_vulnerabilities_with_claude(
    client: anthropic.Anthropic,
    judge_model: str,
    response_text: str,
) -> dict:
    """Claudeを使ってコードレビュー回答の脆弱性検出数をカウントする。

    Args:
        client: Anthropicクライアント
        judge_model: 採点に使うモデルID
        response_text: コードレビュー回答テキスト

    Returns:
        {"score": int, "max_score": 6, "breakdown": {...}, "overall_comment": str}
    """
    prompt = VULN_JUDGE_PROMPT.format(response=response_text)

    message = client.messages.create(
        model=judge_model,
        max_tokens=512,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(0)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        console.print(f"  [yellow]脆弱性カウントのJSONパース失敗: {raw[:100]}[/yellow]")
        return {
            "score": 0,
            "max_score": 6,
            "breakdown": {},
            "overall_comment": "採点エラー: JSONパース失敗",
        }

    detections = result.get("detections", {})
    count = sum(1 for v in detections.values() if v)

    breakdown = {
        vuln["label"]: {
            "detected": detections.get(vuln["id"], False),
            "score": 1 if detections.get(vuln["id"], False) else 0,
            "max": 1,
        }
        for vuln in VULNERABILITIES
    }

    return {
        "score": count,
        "max_score": 6,
        "breakdown": breakdown,
        "overall_comment": result.get("notes", f"{count}/6件の脆弱性を検出"),
    }


def load_manual_results(date: str) -> dict:
    """手動評価結果JSONをモデル×プロンプトIDのマップとして読み込む。

    Returns:
        {model_name: {prompt_id: manual_result_dict}}
    """
    manual_dir = ROOT / "results" / date / "raw" / "manual"
    manual_map: dict = {}

    if not manual_dir.exists():
        return manual_map

    for json_file in manual_dir.glob("*.json"):
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            model = data.get("model")
            prompt_id = data.get("prompt_id")

            if model and prompt_id:
                if model not in manual_map:
                    manual_map[model] = {}
                manual_map[model][prompt_id] = data
        except Exception as e:
            console.print(f"  [yellow]手動結果の読み込みエラー {json_file}: {e}[/yellow]")

    return manual_map


def judge_model(
    model_name: str,
    run_date: str,
    config: dict,
) -> None:
    """指定モデルの全回答を採点してスコアJSONを保存する。

    Args:
        model_name: モデル名
        run_date: 実行日（YYYYMMDD形式）
        config: config.yaml内容
    """
    raw_file = ROOT / "results" / run_date / "raw" / f"{model_name}.json"

    if not raw_file.exists():
        console.print(
            f"[yellow]生データが見つかりません: {raw_file}（runコマンドを先に実行してください）[/yellow]"
        )
        return

    with open(raw_file, encoding="utf-8") as f:
        raw_data = json.load(f)

    judge_cfg = config["judge"]
    judge_model_id = judge_cfg["model"]

    console.print(f"\n[bold blue]採点開始: {model_name}[/bold blue]")

    client = create_judge_client(config)
    system_prompt = load_judge_system_prompt()
    manual_map = load_manual_results(run_date)

    scores = []

    for item in raw_data["results"]:
        prompt_id = item["prompt_id"]
        scoring_type = item["scoring_type"]
        max_score = item["max_score"]
        responses = item["responses"]
        prompt_text = item["prompt"]

        console.print(f"  採点中: [cyan]{prompt_id}[/cyan] (scoring_type={scoring_type})")

        if scoring_type == "manual":
            # 手動評価結果があれば採用
            model_manual = manual_map.get(model_name, {})
            if prompt_id in model_manual:
                manual = model_manual[prompt_id]
                score_entry = {
                    "prompt_id": prompt_id,
                    "category": item["category"],
                    "subcategory": item["subcategory"],
                    "scoring_type": "manual",
                    "score": manual.get("manual_score", 0),
                    "max_score": manual.get("max_score", max_score),
                    "notes": manual.get("notes", ""),
                    "run_scores": [],
                    "average_score": manual.get("manual_score", 0),
                }
            else:
                console.print(f"    [dim]手動評価未実施（スキップ）[/dim]")
                score_entry = {
                    "prompt_id": prompt_id,
                    "category": item["category"],
                    "subcategory": item["subcategory"],
                    "scoring_type": "manual",
                    "score": None,
                    "max_score": max_score,
                    "notes": "手動評価未実施",
                    "run_scores": [],
                    "average_score": None,
                }
            scores.append(score_entry)
            continue

        # 自動採点：各runを採点して平均
        run_scores = []

        for run_idx, response in enumerate(responses):
            if response is None:
                console.print(f"    Run {run_idx + 1}: スキップ（回答なし）")
                continue

            try:
                if scoring_type == "count":
                    result = count_vulnerabilities_with_claude(
                        client, judge_model_id, response
                    )
                else:
                    result = judge_response_with_claude(
                        client,
                        judge_model_id,
                        system_prompt,
                        prompt_id,
                        prompt_text,
                        response,
                        max_score,
                    )

                run_scores.append(result)
                console.print(
                    f"    Run {run_idx + 1}: {result['score']}/{result['max_score']}"
                )

            except Exception as e:
                console.print(f"    [red]Run {run_idx + 1} 採点エラー: {e}[/red]")

        if run_scores:
            avg_score = sum(r["score"] for r in run_scores) / len(run_scores)
        else:
            avg_score = None

        score_entry = {
            "prompt_id": prompt_id,
            "category": item["category"],
            "subcategory": item["subcategory"],
            "scoring_type": scoring_type,
            "max_score": max_score,
            "run_scores": run_scores,
            "average_score": avg_score,
            # 最後のrunのbreakdownを代表として保持
            "breakdown": run_scores[-1].get("breakdown", {}) if run_scores else {},
            "overall_comment": run_scores[-1].get("overall_comment", "") if run_scores else "",
        }
        scores.append(score_entry)

    # 採点結果を保存
    output_dir = ROOT / "results" / run_date / "scores"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{model_name}.json"

    output = {
        "model": model_name,
        "date": run_date,
        "judge_model": judge_model_id,
        "scores": scores,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(
        s["average_score"] for s in scores if s["average_score"] is not None
    )
    console.print(
        f"[green]採点完了: {output_file}（合計 {total:.1f}点）[/green]"
    )
