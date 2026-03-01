"""report.py - 採点結果からMarkdown比較レポートを生成する。"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()

ROOT = Path(__file__).parent.parent

# レポートの行定義（表示順・ラベル）
REPORT_ROWS = [
    {"category": "document", "subcategory": "文書作成", "prompt_id": "document_create", "display_category": "文書", "display_sub": "作成"},
    {"category": "document", "subcategory": "文書レビュー", "prompt_id": "document_review", "display_category": "文書", "display_sub": "レビュー"},
    {"category": "document", "subcategory": "要約", "prompt_id": "document_summary", "display_category": "文書", "display_sub": "要約"},
    {"category": "image", "subcategory": "画像生成", "prompt_id": "image_generate", "display_category": "画像", "display_sub": "生成"},
    {"category": "video", "subcategory": "動画生成", "prompt_id": "video_generate", "display_category": "動画", "display_sub": "生成"},
    {"category": "music", "subcategory": "音楽生成", "prompt_id": "music_generate", "display_category": "音楽", "display_sub": "生成"},
    {"category": "planning", "subcategory": "要件定義", "prompt_id": "planning_requirements", "display_category": "検討", "display_sub": "要件定義"},
    {"category": "planning", "subcategory": "設計支援", "prompt_id": "planning_design", "display_category": "検討", "display_sub": "設計支援"},
    {"category": "coding", "subcategory": "実装", "prompt_id": "coding_implement", "display_category": "コーディング", "display_sub": "実装"},
    {"category": "coding", "subcategory": "コードレビュー", "prompt_id": "coding_review", "display_category": "コーディング", "display_sub": "レビュー"},
    {"category": "coding", "subcategory": "テトリス", "prompt_id": "coding_tetris", "display_category": "コーディング", "display_sub": "テトリス"},
]


def _fmt_score(score: Optional[float], max_score: int) -> str:
    """スコアを表示用文字列にフォーマットする。"""
    if score is None:
        return "-"
    return f"{score:.0f}/{max_score}"


def load_scores(date: str) -> dict:
    """scores/ ディレクトリの全JSONを読み込み、モデル→プロンプトID→スコアのマップを返す。

    Returns:
        {model_name: {prompt_id: score_entry_dict}}
    """
    scores_dir = ROOT / "results" / date / "scores"
    model_scores: dict = {}

    if not scores_dir.exists():
        return model_scores

    for json_file in sorted(scores_dir.glob("*.json")):
        model_name = json_file.stem
        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)
            model_scores[model_name] = {
                entry["prompt_id"]: entry for entry in data.get("scores", [])
            }
        except Exception as e:
            console.print(f"[yellow]スコアファイルの読み込みエラー {json_file}: {e}[/yellow]")

    return model_scores


def generate_summary_table(models: list, model_scores: dict) -> str:
    """サマリーテーブルのMarkdown文字列を生成する。"""
    header = "| 観点 | サブ項目 | " + " | ".join(models) + " |"
    separator = "|------|---------|" + "|".join(["---"] * len(models)) + "|"

    rows = [header, separator]

    for row_def in REPORT_ROWS:
        prompt_id = row_def["prompt_id"]
        cells = [row_def["display_category"], row_def["display_sub"]]

        for model in models:
            entry = model_scores.get(model, {}).get(prompt_id)
            if entry is None:
                cells.append("-")
            else:
                avg = entry.get("average_score")
                max_s = entry.get("max_score", 10)
                cells.append(_fmt_score(avg, max_s))

        rows.append("| " + " | ".join(cells) + " |")

    # 合計行
    totals = []
    for model in models:
        scores = model_scores.get(model, {})
        total = sum(
            e["average_score"]
            for e in scores.values()
            if e.get("average_score") is not None
        )
        max_total = sum(e["max_score"] for e in scores.values())
        totals.append(f"**{total:.0f}/{max_total}**")

    rows.append("| **合計** | | " + " | ".join(totals) + " |")

    return "\n".join(rows)


def generate_detail_section(models: list, model_scores: dict) -> str:
    """観点別詳細セクションのMarkdown文字列を生成する。"""
    lines = ["## 観点別詳細\n"]

    for row_def in REPORT_ROWS:
        prompt_id = row_def["prompt_id"]
        lines.append(f"### {row_def['display_category']} / {row_def['display_sub']}\n")

        for model in models:
            entry = model_scores.get(model, {}).get(prompt_id)
            if entry is None:
                lines.append(f"**{model}**: データなし\n")
                continue

            avg = entry.get("average_score")
            max_s = entry.get("max_score", 10)
            score_str = _fmt_score(avg, max_s)
            comment = entry.get("overall_comment", "")
            scoring_type = entry.get("scoring_type", "")
            notes = entry.get("notes", "")

            lines.append(f"**{model}**: {score_str}")

            if scoring_type == "manual" and notes:
                lines.append(f"  - 手動評価: {notes}")
            elif scoring_type == "count":
                # 脆弱性検出の内訳
                breakdown = entry.get("breakdown", {})
                detected = [k for k, v in breakdown.items() if v.get("detected")]
                missed = [k for k, v in breakdown.items() if not v.get("detected")]
                if detected:
                    lines.append(f"  - 検出: {', '.join(detected)}")
                if missed:
                    lines.append(f"  - 未検出: {', '.join(missed)}")
            elif comment:
                lines.append(f"  - {comment}")

            lines.append("")

        lines.append("")

    return "\n".join(lines)


def generate_ranking(models: list, model_scores: dict) -> str:
    """総合ランキングセクションを生成する。"""
    ranking = []

    for model in models:
        scores = model_scores.get(model, {})
        total = sum(
            e["average_score"]
            for e in scores.values()
            if e.get("average_score") is not None
        )
        max_total = sum(e["max_score"] for e in scores.values())
        ranking.append((model, total, max_total))

    ranking.sort(key=lambda x: x[1], reverse=True)

    lines = ["## 総合ランキング\n"]
    lines.append("| 順位 | モデル | 合計スコア | 達成率 |")
    lines.append("|------|--------|-----------|--------|")

    for rank, (model, total, max_total) in enumerate(ranking, 1):
        pct = (total / max_total * 100) if max_total > 0 else 0
        lines.append(f"| {rank} | {model} | {total:.0f}/{max_total} | {pct:.1f}% |")

    return "\n".join(lines)


def generate_highlights(models: list, model_scores: dict) -> str:
    """注目ポイント（最も差が開いた観点など）を生成する。"""
    lines = ["## 注目ポイント\n"]

    # 観点ごとにモデル間の差を計算
    spread_data = []

    for row_def in REPORT_ROWS:
        prompt_id = row_def["prompt_id"]
        label = f"{row_def['display_category']} / {row_def['display_sub']}"

        valid_scores = []
        for model in models:
            entry = model_scores.get(model, {}).get(prompt_id)
            if entry and entry.get("average_score") is not None:
                max_s = entry["max_score"]
                normalized = entry["average_score"] / max_s * 10
                valid_scores.append((model, entry["average_score"], max_s, normalized))

        if len(valid_scores) >= 2:
            normalized_vals = [s[3] for s in valid_scores]
            spread = max(normalized_vals) - min(normalized_vals)
            best_model = max(valid_scores, key=lambda x: x[3])
            worst_model = min(valid_scores, key=lambda x: x[3])
            spread_data.append((spread, label, best_model, worst_model))

    if spread_data:
        # 最も差が開いた観点（上位3件）
        spread_data.sort(reverse=True)
        lines.append("### モデル間で最も差が開いた観点（正規化スコア10点換算）\n")
        lines.append("| 観点 | 差（10点換算） | 最高モデル | 最低モデル |")
        lines.append("|------|--------------|-----------|-----------|")

        for spread, label, best, worst in spread_data[:3]:
            best_str = f"{best[0]}: {best[1]:.1f}/{best[2]}"
            worst_str = f"{worst[0]}: {worst[1]:.1f}/{worst[2]}"
            lines.append(f"| {label} | {spread:.1f} | {best_str} | {worst_str} |")

        lines.append("")

        # 最も差が少なかった観点
        spread_data.sort()
        least_spread = spread_data[0]
        lines.append(
            f"### 最も拮抗した観点: {least_spread[1]}"
            f"（差 {least_spread[0]:.1f}点）\n"
        )

    return "\n".join(lines)


def generate_report(date: str) -> None:
    """指定日付の採点結果からMarkdownレポートを生成・保存する。

    Args:
        date: 実行日（YYYYMMDD形式）
    """
    model_scores = load_scores(date)

    if not model_scores:
        console.print(f"[red]採点結果が見つかりません: results/{date}/scores/[/red]")
        return

    models = sorted(model_scores.keys())
    console.print(f"\n[bold blue]レポート生成: {date}（モデル: {', '.join(models)}）[/bold blue]")

    # 日付フォーマット変換（YYYYMMDD → YYYY-MM-DD）
    display_date = f"{date[:4]}-{date[4:6]}-{date[6:8]}" if len(date) == 8 else date

    lines = [
        f"# AIモデル性能比較レポート",
        f"",
        f"**実行日**: {display_date}  ",
        f"**評価モデル**: {', '.join(models)}  ",
        f"**生成日時**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"---",
        f"",
        f"## サマリーテーブル",
        f"",
        generate_summary_table(models, model_scores),
        f"",
        f"---",
        f"",
        generate_detail_section(models, model_scores),
        f"---",
        f"",
        generate_ranking(models, model_scores),
        f"",
        f"---",
        f"",
        generate_highlights(models, model_scores),
    ]

    report_content = "\n".join(lines)

    # レポートを保存
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_file = reports_dir / f"{date}.md"

    output_file.write_text(report_content, encoding="utf-8")
    console.print(f"[green]レポート生成完了: {output_file}[/green]")
