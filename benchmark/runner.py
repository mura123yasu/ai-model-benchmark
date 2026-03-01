"""runner.py - 各モデルAPIにプロンプトを投げて結果を保存する。"""

import json
import os
import re
from pathlib import Path
from typing import Callable, Optional

import yaml
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

ROOT = Path(__file__).parent.parent

# 全プロンプト定義
PROMPT_DEFINITIONS = [
    {
        "id": "document_create",
        "category": "document",
        "subcategory": "文書作成",
        "file": "prompts/document.md",
        "section_index": 0,
        "max_score": 10,
        "scoring_type": "judge",
    },
    {
        "id": "document_review",
        "category": "document",
        "subcategory": "文書レビュー",
        "file": "prompts/document.md",
        "section_index": 1,
        "max_score": 10,
        "scoring_type": "judge",
    },
    {
        "id": "document_summary",
        "category": "document",
        "subcategory": "要約",
        "file": "prompts/document.md",
        "section_index": 2,
        "max_score": 10,
        "scoring_type": "judge",
    },
    {
        "id": "image_generate",
        "category": "image",
        "subcategory": "画像生成",
        "file": "prompts/image.md",
        "section_index": 0,
        "max_score": 10,
        "scoring_type": "manual",
    },
    {
        "id": "video_generate",
        "category": "video",
        "subcategory": "動画生成",
        "file": "prompts/video.md",
        "section_index": 0,
        "max_score": 10,
        "scoring_type": "manual",
    },
    {
        "id": "music_generate",
        "category": "music",
        "subcategory": "音楽生成",
        "file": "prompts/music.md",
        "section_index": 0,
        "max_score": 10,
        "scoring_type": "manual",
    },
    {
        "id": "planning_requirements",
        "category": "planning",
        "subcategory": "要件定義",
        "file": "prompts/planning.md",
        "section_index": 0,
        "max_score": 10,
        "scoring_type": "judge",
    },
    {
        "id": "planning_design",
        "category": "planning",
        "subcategory": "設計支援",
        "file": "prompts/planning.md",
        "section_index": 1,
        "max_score": 10,
        "scoring_type": "judge",
    },
    {
        "id": "coding_implement",
        "category": "coding",
        "subcategory": "実装",
        "file": "prompts/coding.md",
        "section_index": 0,
        "max_score": 10,
        "scoring_type": "judge",
    },
    {
        "id": "coding_review",
        "category": "coding",
        "subcategory": "コードレビュー",
        "file": "prompts/coding.md",
        "section_index": 1,
        "max_score": 6,
        "scoring_type": "count",
    },
    {
        "id": "coding_tetris",
        "category": "coding",
        "subcategory": "テトリス",
        "file": "prompts/coding.md",
        "section_index": 2,
        "max_score": 50,
        "scoring_type": "judge",
    },
]

# 自動実行対象カテゴリ（image/video/musicはrunnerでは実行しない）
AUTO_CATEGORIES = {"document", "planning", "coding"}


def load_config() -> dict:
    """config.yaml を読み込む。"""
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_prompt_from_markdown(file_path: Path, section_index: int) -> str:
    """Markdownファイルの指定セクションからプロンプト本文を抽出する。

    Args:
        file_path: Markdownファイルパス
        section_index: セクションのインデックス（0始まり）

    Returns:
        プロンプト本文（コードブロック内のテキスト）
    """
    content = file_path.read_text(encoding="utf-8")

    # "## " で始まるセクションに分割
    sections = re.split(r"\n(?=## )", content)
    sections = [s for s in sections if s.startswith("## ")]

    if section_index >= len(sections):
        raise ValueError(
            f"section_index={section_index} が見つかりません（{file_path}、セクション数={len(sections)}）"
        )

    section = sections[section_index]

    # ### プロンプト の後のコードブロックを抽出
    match = re.search(r"### プロンプト\s*\n```\n(.*?)```", section, re.DOTALL)
    if not match:
        raise ValueError(
            f"プロンプトのコードブロックが見つかりません（{file_path}、section_index={section_index}）"
        )

    return match.group(1).strip()


def _make_anthropic_completer(model_id: str, api_key: str) -> Callable:
    """Anthropic用のcompletion関数を返す。"""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    def complete(prompt: str, temperature: float) -> str:
        message = client.messages.create(
            model=model_id,
            max_tokens=4096,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    return complete


def _make_openai_completer(model_id: str, api_key: str) -> Callable:
    """OpenAI用のcompletion関数を返す。"""
    import openai

    client = openai.OpenAI(api_key=api_key)

    def complete(prompt: str, temperature: float) -> str:
        response = client.chat.completions.create(
            model=model_id,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    return complete


def _make_google_completer(model_id: str, api_key: str) -> Callable:
    """Google Generative AI用のcompletion関数を返す。"""
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_id)

    def complete(prompt: str, temperature: float) -> str:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=temperature),
        )
        return response.text

    return complete


def create_completer(model_name: str, config: dict) -> Callable:
    """モデル設定からAPI呼び出し関数を生成する。"""
    model_cfg = config["models"][model_name]
    provider = model_cfg["provider"]
    model_id = model_cfg["model_id"]
    api_key = os.getenv(model_cfg["api_key_env"])

    if not api_key:
        raise EnvironmentError(
            f"環境変数 {model_cfg['api_key_env']} が設定されていません"
        )

    if provider == "anthropic":
        return _make_anthropic_completer(model_id, api_key)
    elif provider == "openai":
        return _make_openai_completer(model_id, api_key)
    elif provider == "google":
        return _make_google_completer(model_id, api_key)
    else:
        raise ValueError(f"未対応のプロバイダー: {provider}")


def run_model(
    model_name: str,
    run_date: str,
    config: dict,
    categories: Optional[set] = None,
) -> None:
    """指定モデルに対してプロンプトを実行し、結果をJSONに保存する。

    Args:
        model_name: config.yaml に定義されたモデル名
        run_date: 実行日（YYYYMMDD形式）
        config: 読み込み済みのconfig.yaml内容
        categories: 実行するカテゴリのセット（Noneの場合はAUTO_CATEGORIESすべて）
    """
    if categories is None:
        categories = AUTO_CATEGORIES

    temperature = config["runner"]["temperature"]
    runs_per_prompt = config["runner"]["runs_per_prompt"]

    console.print(f"\n[bold blue]モデル実行: {model_name}[/bold blue]")

    try:
        complete = create_completer(model_name, config)
    except Exception as e:
        console.print(f"[red]プロバイダーの初期化に失敗: {e}[/red]")
        return

    results = []

    for prompt_def in PROMPT_DEFINITIONS:
        if prompt_def["category"] not in categories:
            continue

        prompt_id = prompt_def["id"]
        file_path = ROOT / prompt_def["file"]

        try:
            prompt_text = extract_prompt_from_markdown(
                file_path, prompt_def["section_index"]
            )
        except Exception as e:
            console.print(f"  [yellow]スキップ {prompt_id}: {e}[/yellow]")
            continue

        console.print(
            f"  [cyan]{prompt_id}[/cyan] ({runs_per_prompt}回実行)..."
        )
        responses = []

        for run_num in range(runs_per_prompt):
            try:
                response = complete(prompt_text, temperature)
                responses.append(response)
                console.print(f"    Run {run_num + 1}/{runs_per_prompt} 完了")
            except Exception as e:
                console.print(f"    [red]Run {run_num + 1} 失敗: {e}[/red]")
                responses.append(None)

        results.append(
            {
                "prompt_id": prompt_id,
                "category": prompt_def["category"],
                "subcategory": prompt_def["subcategory"],
                "prompt": prompt_text,
                "responses": responses,
                "max_score": prompt_def["max_score"],
                "scoring_type": prompt_def["scoring_type"],
            }
        )

    # 結果を保存
    output_dir = ROOT / "results" / run_date / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{model_name}.json"

    output = {
        "model": model_name,
        "date": run_date,
        "results": results,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    console.print(f"[green]保存完了: {output_file}[/green]")
