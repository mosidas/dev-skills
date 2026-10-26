# スクリプトの単体テスト

プラグインが同梱する動詞・名詞のカタログ(NG/OK 対)と検査 hooks に対する単体テスト。標準ライブラリの `unittest` だけを使い、追加インストールなしで実行できる(hooks が標準ライブラリのみで動く規律と揃える)。

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
| `test_phrase_catalog.py` | `skills/write-doc/scripts/forbidden_phrases.json` | 動詞・名詞のカタログの整合(型が 4 つ・重複・包含・OK 例の必須・severity 方針)と lint.py の検出語・severity の導出 |
| `test_lint_detectors.py` | `skills/write-doc/scripts/lint.py`・`textcore.py` | 前処理(画像・地の文の URL・HTML タグの空白化、かな・漢字を含まない行の除外と行数の保持)、BOM 付きファイルの読み込み・不正な UTF-8 のエラー、禁止語の語の境目の判定と 1 行内の全出現の計数、翻訳調(`という点で` を検出し `することができる` を正規表現では検出しない)、文頭の反復の 1 件への集約と数詞始まりの除外、英字の識別子の抽出、文末の打ち消しの反復(4 文で検出・3 文と問いかけ・推量は数えない)、文中の太字の密度(行頭のラベルを数えない・既定で有効)、見出し・箇条書き・表・段落の単位分割(コード・フロントマター・英字だけの段落を出さない) |
| `test_inspection_hooks.py` | `hooks/` | 検査対象の判定・重大カテゴリの絞り込み・設定の上書き・警告文・完了ブロックと上限、検査できない環境での素通し |
| `test_respond_hook.py` | `hooks/inject_respond.py` | frontmatter の除去(CRLF・本文中の区切り線を含む)・本文の出力・スキルが無い環境での素通し |
| `test_session_url_hook.py` | `hooks/guard_session_url.py` | コマンド文字列と本文ファイル(`-F`・`--file`・`--body-file`、空白を含むパス)にあるセッション URL と `Claude-Session:` の行の拒否、本文ファイルが読めないときの拒否、`Co-Authored-By`・`Generated with`・`git log --grep`・`-F -`・Bash 以外のツール・不正な JSON の素通し |
| `test_render.py` | `skills/draw-diagram/scripts/render.py` | `.mmd` と SVG の id・辺の対応照合、禁止要素(`script`・`foreignObject`・`image`・外部参照)・整形式の検査、`data-edge` を持つ path・line の斜めの線分の検出、`classDiagram`/`erDiagram` の照合対象外扱い |
| `test_build_loop.py` | `skills/build/scripts/loop.py` | 進捗ファイルの解析(見出し・区切りの行と `失敗(解決済み)` を数えない、停止の行と失敗の上限の検証)、停止の判定(全 Done で 0・要判断で起動しない・同一タスクの失敗が上限に達したら止まり別タスクの合計では止まらない)、進捗ファイルが更新されないとき・非 0 終了・反復の上限での停止、`--` より後ろの引数の受け渡し |
| `test_yomiyasu_edge_cases.py` | `tests/corpus/yomiyasu_edge_cases/` | yomiyasu 由来の語と定型句(前置フィラー・定型クロージング)が、日常語の境界値 48 本のうち字義どおりの `壊れる` を含む 5 本では `壊れ` だけを検出し、残りの 43 本には発火しないこと |
| `test_skill_references.py` | `skills/`・`agents/`・`hooks/`・`README.md`・`tests/README.md`・`evals/` | `write-doc/references/` へのパスと、全スキルの SKILL.md・references/ と write-doc の scripts/ にある相対参照(`sentence.md`・`references/format/html.md` など)が実在すること。write-doc 内の相対参照は write-doc の中だけで解決する |
| `test_manifest_version.py` | `.claude-plugin/plugin.json`・`.codex-plugin/plugin.json` | version が両方にあり一致すること |
| `corpus/yomiyasu_edge_cases/` | — | 境界値コーパス 48 本(出典 nanaism/yomiyasu の `tests/corpus/edge_cases`、MIT、`LICENSE` 同梱) |

lint.py の実行は環境変数 `WRITING_INSPECTION_LINT_CMD` でスタブへ差し替える。テストは `uv` と sudachipy に依存しない。

## 3. 書き方の規律

- **一時ディレクトリで自己決着させる**。リポジトリ内のファイルを書き換えるテストを書かない。
- **exit code とエラーメッセージはサブプロセスで確かめる**。hook は `sys.exit` を呼ぶため、関数を直接呼ぶと処理が中断する。
- **検出できることと誤検出しないことを対で書く**。違反を入れて検出を確かめるだけでは、常に検出する実装(偽陽性)を通してしまう。
- テスト名は日本語で、何が成り立つべきかを書く(`test_状態が無ければ何もしない`)。Python の識別子に使えない記号(半角スペース・括弧)を含めない。
