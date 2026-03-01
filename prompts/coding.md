# コーディングプロンプト集

---

## 1. 実装（FastAPI）

### プロンプト

```
FastAPIを使用してタスク管理APIを実装してください。

【エンドポイント仕様】
- POST   /tasks       タスク作成
- GET    /tasks       タスク一覧取得
- GET    /tasks/{id}  タスク取得
- PUT    /tasks/{id}  タスク更新
- DELETE /tasks/{id}  タスク削除

【データ構造】
タスクオブジェクトは以下のフィールドを持つこと：
- id          : UUID（自動採番）
- title       : 文字列（1〜100文字、必須）
- description : 文字列（任意）
- status      : 列挙型（"todo" / "in_progress" / "done"）
- priority    : 整数（1〜5）
- created_at  : 作成日時（datetime）
- updated_at  : 更新日時（datetime）
- due_date    : 期限日（date、任意）

【実装要件】
- バリデーションエラーは422を返す（FastAPIデフォルト動作）
- 存在しないIDへのアクセスは404を返す
- ストレージはインメモリ（辞書型）で実装する（DBは不要）
- 型ヒントをすべてのコードに付与すること
- すべての関数・クラスにdocstringを記述すること

【出力形式】
1. 完全な実装コード（そのままコピーして実行できる状態）
2. 動作確認用curlコマンド例（作成・取得・更新・削除の各操作）
```

### 評価ポイント

- **Pydanticの活用度**：入力バリデーション・レスポンスモデルの定義にPydanticが適切に使われているか
- **エラーハンドリング網羅性**：404・422の返却、バリデーション範囲（文字数・enumの値）が適切に実装されているか
- **型の正確さ**：`due_date`が`date`型（`datetime`ではなく）で定義されているか等、型の使い分けが正確か
- **実際に動くか**：コピーして`uvicorn main:app`で起動し、提示されたcurlコマンドが正常に動作するか

---

## 2. レビュー（セキュリティ脆弱性）

### プロンプト

```
以下のPythonコードをレビューしてください。

【レビュー対象コード】
---
import sqlite3
import hashlib


def get_db_connection():
    conn = sqlite3.connect("users.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT
        )
    """)
    return conn


def get_user(username: str, password: str):
    conn = get_db_connection()
    cursor = conn.execute(
        f"SELECT * FROM users WHERE username = '{username}'"
    )
    user = cursor.fetchone()
    if user and user[2] == password:
        return user
    return None


def create_user(username: str, password: str):
    conn = get_db_connection()
    hashed = hashlib.md5(password.encode()).hexdigest()
    conn.execute(
        f"INSERT INTO users (username, password) VALUES ('{username}', '{hashed}')"
    )
    return True


def get_all_users():
    conn = get_db_connection()
    cursor = conn.execute("SELECT * FROM users")
    return cursor.fetchall()
---

【出力形式】
以下の5観点で問題点を指摘し、各問題に重大度（High / Medium / Low）を付けてください。
また、各問題に対して修正コード例を示してください。

観点：
1. バグ
2. セキュリティ
3. パフォーマンス
4. 可読性
5. 設計
```

### 評価ポイント（正解リスト）

以下の6点を何個検出できたかで定量評価する（各1点、最大6点）：

1. **SQLインジェクション**：`get_user`・`create_user`両方のf文字列によるSQL組み立て
2. **非推奨ハッシュアルゴリズム**：MD5の使用（bcrypt・argon2等の推奨アルゴリズムへの指摘）
3. **平文パスワード比較**：`get_user`でハッシュ化されていないパスワードとDBのハッシュを直接比較している
4. **コネクションリーク**：`with`文を使用していないためコネクションが確実にクローズされない
5. **機密情報の露出**：`get_all_users`がパスワードハッシュを含む全カラムを返している
6. **コミット漏れ**：`create_user`で`conn.commit()`が呼ばれていないため書き込みが確定しない

---

## 3. 自律要件補完（テトリス）

### プロンプト

```
テトリスを作ってください。
```

### 評価観点

このプロンプトは意図的に要件を明示していません。モデルが自律的に要件を補完し、完成度の高いテトリスを実装できるかを評価します。

#### 要件補完力（20点）

モデルが自律的に実装した機能の数で評価する（各3点、合計21点→20点に正規化）：

| 機能 | 配点 |
|---|---|
| 7種類のテトリミノ（I・O・T・S・Z・J・L）| 3点 |
| ライン消去 | 3点 |
| スコア表示 | 3点 |
| レベルシステム（消去数に応じてスピードアップ） | 3点 |
| ゲームオーバー判定 | 3点 |
| NEXTピースプレビュー | 3点 |
| ポーズ機能 | 2点 |

#### コード品質（20点）

| 観点 | 配点 | 基準 |
|---|---|---|
| コピペ即動作 | 8点 | コードを貼り付けて即座に実行できるか |
| 関数・クラス分割 | 5点 | 適切にモジュール化されているか |
| ゲームループの実装 | 4点 | 適切なゲームループが実装されているか |
| 定数化 | 3点 | マジックナンバーが定数として定義されているか |

#### 技術選択（10点）

| 観点 | 配点 | 基準 |
|---|---|---|
| 実行環境の明示 | 5点 | 動作に必要な環境・コマンドが明記されているか |
| 依存ライブラリの最小化 | 5点 | 不必要な外部ライブラリを使用していないか |

#### ボーナス（各+2点）

- ホールド機能の実装：+2点
- ゴーストピース（落下予測位置の表示）の実装：+2点
