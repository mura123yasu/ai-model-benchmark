# AIモデル性能比較プロンプト集

新しいAIモデルが登場するたびに、同一プロンプトで性能を比較・記録するためのプロンプト集です。
毎回同じプロンプトを使用することで、モデル間の性能差を定量的に比較できます。

---

## 評価観点一覧

| カテゴリ | ファイル | サブ項目 |
|---|---|---|
| 文書 | [prompts/document.md](prompts/document.md) | 文書作成・文書レビュー・要約 |
| 画像生成 | [prompts/image.md](prompts/image.md) | 画像生成 |
| 動画生成 | [prompts/video.md](prompts/video.md) | 動画生成 |
| 音楽生成 | [prompts/music.md](prompts/music.md) | 音楽生成 |
| 検討・計画 | [prompts/planning.md](prompts/planning.md) | 要件定義・設計支援 |
| コーディング | [prompts/coding.md](prompts/coding.md) | 実装・レビュー・テトリス |
| 評価シート | [evaluation/scoresheet.md](evaluation/scoresheet.md) | 全観点の採点表 |

---

## 評価時の注意事項

- **temperatureは統一する**：比較するモデル間で同じtemperature（推奨：0.0〜0.3）を使用する
- **3回平均を推奨**：生成のばらつきを吸収するため、同じプロンプトを3回実行して平均点を記録する
- **プロンプトは一字一句変えない**：モデル比較の公平性を保つため、プロンプトを改変しない
- **システムプロンプトなし**：特別なシステムプロンプトを追加せず、デフォルト状態で評価する
- **コンテキストをリセットする**：プロンプトごとに新しいセッション（会話）で実行する

---

## 評価シートの使い方

1. [evaluation/scoresheet.md](evaluation/scoresheet.md) を開く
2. 比較するモデル名を「モデルA」「モデルB」欄に記入する
3. 各プロンプトをモデルに入力し、評価基準に従って10点満点で採点する
4. テトリスのみ50点満点（詳細配点はscoresheet.md参照）
5. 合計点（150点満点）でモデルを比較する

---

## スコア構成

| カテゴリ | 配点 |
|---|---|
| 文書（作成・レビュー・要約） | 各10点 × 3 = 30点 |
| 画像生成 | 10点 |
| 動画生成 | 10点 |
| 音楽生成 | 10点 |
| 検討（要件定義・設計支援） | 各10点 × 2 = 20点 |
| コーディング（実装・レビュー） | 各10点 × 2 = 20点 |
| コーディング（テトリス） | 50点 |
| **合計** | **150点** |

---

## 自動評価システムの使い方

プロンプトの実行・採点・レポート生成を自動化する `benchmark/` システムを利用できます。

### セットアップ

```bash
# 依存ライブラリをインストール
pip install -r requirements.txt

# APIキーを設定（.env.example をコピーして編集）
cp .env.example .env
# .env にAPIキーを記入
```

### 実行方法

```bash
# テキスト系を全モデルで実行 → 採点 → レポート生成（一気通貫）
python benchmark/cli.py run --date today

# モデルを絞って実行
python benchmark/cli.py run --date today --models claude-sonnet,gpt-4o

# カテゴリを絞って実行
python benchmark/cli.py run --date today --category coding

# 手動結果を追加後に採点だけ再実行
python benchmark/cli.py judge --date 20250301

# レポートだけ再生成
python benchmark/cli.py report --date 20250301
```

### 手動評価（画像・動画・音楽）の登録方法

1. `results/YYYYMMDD/raw/manual/` ディレクトリを作成する
2. 以下の形式でJSONファイルを置く（例: `image_generate_dalle3.json`）

```json
{
  "model": "dalle3",
  "category": "image",
  "prompt_id": "image_generate",
  "result_file": "image_001.png",
  "manual_score": 8,
  "max_score": 10,
  "notes": "日本語テキストの再現が不完全"
}
```

3. `python benchmark/cli.py judge --date YYYYMMDD` で採点を再実行する

### 出力ファイル

| パス | 内容 |
|------|------|
| `results/YYYYMMDD/raw/{model}.json` | 各モデルの生の回答 |
| `results/YYYYMMDD/raw/manual/` | 手動評価結果を置く場所 |
| `results/YYYYMMDD/scores/{model}.json` | 採点結果 |
| `reports/YYYYMMDD.md` | Markdown比較レポート |
