#!/usr/bin/env python3
"""cli.py - AIモデルベンチマーク自動評価システムのエントリーポイント。

使い方:
    python benchmark/cli.py run --date today
    python benchmark/cli.py run --date today --models claude-sonnet,gpt-4o
    python benchmark/cli.py run --date today --category coding
    python benchmark/cli.py judge --date 20250301
    python benchmark/cli.py report --date 20250301
"""

import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

# benchmark/ ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from runner import AUTO_CATEGORIES, load_config, run_model
from judge import judge_model
from report import generate_report

console = Console()


def resolve_date(date_str: str) -> str:
    """'today' を YYYYMMDD 形式に変換する。"""
    if date_str.lower() == "today":
        return datetime.now().strftime("%Y%m%d")
    return date_str


@click.group()
def cli():
    """AIモデル性能比較 自動評価システム。"""
    pass


@cli.command()
@click.option(
    "--date",
    required=True,
    help="実行日（'today' または YYYYMMDD 形式）",
)
@click.option(
    "--models",
    default=None,
    help="実行するモデル名（カンマ区切り、例: claude-sonnet,gpt-4o）。省略時は全モデル。",
)
@click.option(
    "--category",
    default=None,
    help="実行するカテゴリ（document/planning/coding）。省略時は全カテゴリ。",
)
@click.option(
    "--skip-judge",
    is_flag=True,
    default=False,
    help="採点ステップをスキップする（run のみ）。",
)
@click.option(
    "--skip-report",
    is_flag=True,
    default=False,
    help="レポート生成ステップをスキップする。",
)
def run(date, models, category, skip_judge, skip_report):
    """テキスト系プロンプトを全モデルで実行 → 採点 → レポート生成まで一気通貫。"""
    run_date = resolve_date(date)
    config = load_config()

    # モデルリストを決定
    if models:
        model_list = [m.strip() for m in models.split(",")]
        unknown = [m for m in model_list if m not in config["models"]]
        if unknown:
            console.print(f"[red]未定義のモデル: {', '.join(unknown)}[/red]")
            console.print(f"利用可能なモデル: {', '.join(config['models'].keys())}")
            sys.exit(1)
    else:
        model_list = list(config["models"].keys())

    # カテゴリを決定
    if category:
        if category not in AUTO_CATEGORIES:
            console.print(
                f"[red]無効なカテゴリ: {category}（有効: {', '.join(sorted(AUTO_CATEGORIES))}）[/red]"
            )
            sys.exit(1)
        categories = {category}
    else:
        categories = AUTO_CATEGORIES

    console.print(
        f"\n[bold green]===== 実行開始 =====[/bold green]\n"
        f"日付: {run_date}\n"
        f"モデル: {', '.join(model_list)}\n"
        f"カテゴリ: {', '.join(sorted(categories))}\n"
    )

    # Step 1: Runner
    console.rule("[bold]Step 1: プロンプト実行[/bold]")
    for model_name in model_list:
        run_model(model_name, run_date, config, categories)

    if skip_judge:
        console.print("[yellow]採点をスキップしました（--skip-judge）[/yellow]")
        return

    # Step 2: Judge
    console.rule("[bold]Step 2: 採点[/bold]")
    for model_name in model_list:
        judge_model(model_name, run_date, config)

    if skip_report:
        console.print("[yellow]レポート生成をスキップしました（--skip-report）[/yellow]")
        return

    # Step 3: Report
    console.rule("[bold]Step 3: レポート生成[/bold]")
    generate_report(run_date)

    console.print(f"\n[bold green]===== 完了 =====[/bold green]")


@cli.command()
@click.option(
    "--date",
    required=True,
    help="採点対象の日付（'today' または YYYYMMDD 形式）",
)
@click.option(
    "--models",
    default=None,
    help="採点するモデル名（カンマ区切り）。省略時は raw/ にある全モデル。",
)
def judge(date, models):
    """手動結果を追加した後などに採点のみ再実行する。"""
    run_date = resolve_date(date)
    config = load_config()

    if models:
        model_list = [m.strip() for m in models.split(",")]
    else:
        # raw/ にある JSON ファイルからモデルリストを自動検出
        raw_dir = Path(__file__).parent.parent / "results" / run_date / "raw"
        if not raw_dir.exists():
            console.print(f"[red]実行結果が見つかりません: {raw_dir}[/red]")
            sys.exit(1)
        model_list = [
            f.stem for f in raw_dir.glob("*.json")
        ]
        if not model_list:
            console.print(f"[red]採点対象のJSONファイルが見つかりません: {raw_dir}[/red]")
            sys.exit(1)

    console.print(
        f"\n[bold green]===== 採点開始 =====[/bold green]\n"
        f"日付: {run_date}\n"
        f"モデル: {', '.join(model_list)}\n"
    )

    for model_name in model_list:
        judge_model(model_name, run_date, config)

    console.print(f"\n[bold green]===== 採点完了 =====[/bold green]")


@cli.command()
@click.option(
    "--date",
    required=True,
    help="レポート対象の日付（'today' または YYYYMMDD 形式）",
)
def report(date):
    """採点結果からMarkdown比較レポートのみを再生成する。"""
    run_date = resolve_date(date)

    console.print(
        f"\n[bold green]===== レポート生成 =====[/bold green]\n"
        f"日付: {run_date}\n"
    )

    generate_report(run_date)

    console.print(f"\n[bold green]===== 完了 =====[/bold green]")


if __name__ == "__main__":
    cli()
