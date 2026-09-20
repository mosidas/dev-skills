# スクリプトの単体テスト

プラグインが同梱する動詞カタログ(NG/OK 対)と検査 hooks に対する単体テスト。標準ライブラリの `unittest` だけを使い、追加インストールなしで実行できる(hooks が標準ライブラリのみで動く規律と揃える)。

## 1. 実行

リポジトリのルートで実行する。

```sh
python3 -m unittest discover -s tests -t tests
```

個別のファイルだけを走らせるときは次のようにする。

```sh
python3 -m unittest discover -s tests -t tests -p test_phrase_catalog.py
```

## 2. 構成

| ファイル | 対象 | 主な検査 |
| :-- | :-- | :-- |
| `helpers.py` | — | 一時ディレクトリとサブプロセス実行の共通処理 |
| `test_phrase_catalog.py` | `skills/write-doc/scripts/forbidden_phrases.json` | 動詞カタログの整合(型が 3 つ・重複・包含・OK 例の必須・severity 方針)と lint.py の検出語・severity の導出 |
| `test_inspection_hooks.py` | `hooks/` | 検査対象の判定・重大カテゴリの絞り込み・設定の上書き・警告文・完了ブロックと上限、検査できない環境での素通し |
| `test_respond_hook.py` | `hooks/inject_respond.py` | frontmatter の除去(CRLF・本文中の区切り線を含む)・本文の出力・スキルが無い環境での素通し |

lint.py の実行は環境変数 `WRITING_INSPECTION_LINT_CMD` でスタブへ差し替える。テストは `uv` と sudachipy に依存しない。

## 3. 書き方の規律

- **一時ディレクトリで自己決着させる**。リポジトリ内のファイルを書き換えるテストを書かない。
- **exit code とエラーメッセージはサブプロセスで確かめる**。hook は `sys.exit` を呼ぶため、関数を直接呼ぶと処理が中断する。
- **検出できることと誤検出しないことを対で書く**。違反を入れて検出を確かめるだけでは、常に検出する実装(偽陽性)を通してしまう。
- テスト名は日本語で、何が成り立つべきかを書く(`test_状態が無ければ何もしない`)。Python の識別子に使えない記号(半角スペース・括弧)を含めない。
