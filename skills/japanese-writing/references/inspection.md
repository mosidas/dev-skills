# 検査の規範

## 1. 原則

- 検出は機械が行い、直すかどうかは書き手(または AI)が文脈で判断する。検出は疑いの提示であって、機械的に全部直せという指示ではない。
- 検出件数で作業を止めない。各スクリプトは入力エラー(ファイル不在等)のときだけ exit code 1 を返し、検出件数に関わらず exit code 0 で終わる。

## 2. 検査スクリプト

スクリプトはプラグインの `skills/japanese-writing/scripts/` にある。コマンド例の `<スキルのディレクトリ>` には、Claude Code がスキル読み込み時に示す本スキルの絶対パスを入れる(シェルの cwd はプロジェクト側のままである)。

```sh
uv run <スキルのディレクトリ>/scripts/lint.py <file.md> [--json]
```

禁止語・翻訳調・否定肯定対比の反復・文長の均質さ・体言止め率・語彙多様性・英語統語の疑い・段落の具体性を機械検出する。禁止語の正本は NG/OK カタログ(`../scripts/forbidden_phrases.json`)にある。

- `--genre essay|tech|business`: コーパス校正済みの閾値プロファイルに切り替え、誤検知を減らす。
- `--baseline <前回のjson>`: 今回の検出を resolved / new / persisting に仕分ける。台帳(4.)へ追記するのは new と persisting だけでよい。
- `--experimental`: 定量校正が済んでいない実験的検出器も出力する。信頼度が低い前提で扱う。

```sh
uv run <スキルのディレクトリ>/scripts/outline.py <file.md> [--json]
```

見出し・各段落の先頭文・箇条書きプレースホルダを行番号付きで抽出する。スケルトン通読(`paragraph.md` 5.)への入力に使う。

```sh
uv run <スキルのディレクトリ>/scripts/terms.py <file.md> [--json]
```

カタカナ複合語・ASCII 略語・固有名詞らしき語を、初出行・出現回数・説明マーカーの有無つきで列挙する。用語が初出で説明されているか(`sentence.md` 1.)の確認材料になる。

```sh
uv run <スキルのディレクトリ>/scripts/semantic.py <file.md> [--json] [--genre essay|tech|business]
```

文埋め込みで話題の平板さを検出する opt-in の検出器で、既定の検査ループには組み込まない。初回実行時にモデル約 1GB のダウンロードが発生するため、実行前にユーザーへ一言断る。文数 10 未満の文書はスキップする。

## 3. hooks

検査 hooks はプラグインに同梱されており、プラグインを有効にすると自動で発火する。追加の導入作業はない。

| hook | 発火 | 動作 |
| :-- | :-- | :-- |
| PostToolUse(Write / Edit / MultiEdit / NotebookEdit) | 日本語 Markdown の書き込み直後 | lint.py を `--json` で実行し、検出があれば警告をエージェントへ返す。処理は止めない(書き込みは成立済み)。書き直しの結果へ再び検査がかかる |
| Stop | セッション完了時 | このセッションで検査したファイルを再検査し、重大カテゴリの検出が残るあいだ完了をブロックする(`stop_max_blocks` 回が上限) |

発火するのは、拡張子が `.md` / `.markdown` で、日本語文字が `min_japanese_chars`(既定 30)文字以上あり、`exclude` に一致せず、文書種別の `inspect` が `true` の書き込みに限る。設定の正本はプラグインの `hooks/inspection.config.json` である。利用側プロジェクトの恒久的な変更は `.claude/japanese-writing-inspection.json` に同じキーで書く(浅い上書き。プラグインを更新しても残る)。

| キー | 意味 |
| :-- | :-- |
| `min_japanese_chars` | 検査対象とみなす日本語文字数のしきい値(既定 30) |
| `exclude` | 検査しないパスのパターン(プロジェクト相対、fnmatch。`*` は `/` もまたぐ) |
| `blocking` | 重大カテゴリの宣言。`{"category": ..., "min_severity": "info"/"warn"/"critical"}` の配列。該当する検出が残るあいだ Stop が完了をブロックする |
| `doctypes` | 文書種別。`paths` に最初に一致した種別の `genre`・`disabled_categories`・`inspect`(false で検査自体を外す)を適用する |
| `default_doctype` | どの種別にも一致しないファイルへ適用する既定 |
| `stop_max_blocks` | Stop がブロックする回数の上限(既定 3)。超えたら検出が残っていても完了を許可する |
| `lint_timeout_seconds` / `max_findings_in_warning` | lint 実行のタイムアウト / 警告に列挙する検出の上限 |

既定の重大カテゴリは `forbidden_phrase`(severity warn 以上)と `antithesis_repetition`(critical のみ)である。判断の限界は次の 4 点になる。

- `uv` が無い・lint.py の実行失敗・タイムアウトのいずれでも、hook は書き込みと完了を止めず素通しする。
- 検出は lint.py の表層検出に限り、重量級の `semantic.py` は hook から呼ばない。
- Stop のブロックは `stop_max_blocks` 回で打ち切るため、残検出は収束ループ(5.)で人が判断する。
- 発火の粒度はファイル単位であり、1 行だけ変えても全文を再検査する。

## 4. 検出への対応

- カテゴリごとの書き直し指針の正本は `hooks/rewrite_guides.json` にあり、hook の警告に同梱される。指針が指す規範の節をそのつど読み直してから、文脈に照らして「直す/直さない」を判断する。
- 禁止語カテゴリ(`forbidden_phrase`)の対象は NG/OK カタログ(`../scripts/forbidden_phrases.json`)に登録した語であり、言い換え例は各語の `ok` にある。
- 構造レビューは `outline.py` の出力でスケルトン通読(`paragraph.md` 5.)を行う。事実レビューは `sentence.md` 4. に従い、要約・記憶で書いた箇所と仕様変更を述べた箇所を優先して原典に当てる。
- 検出とレビューで見つけた項目は、一つひとつ「直した」か「残す(理由)」かを記録しながら進める。レビューで見つけた問題も同じ台帳へ 1 行として起こす。

```
- [直した] paragraph_lead_conjunction: 3段落目冒頭「しかし、」を削除し前段落と地続きにした
- [残す/定型の連語] forbidden_phrase「置く」: 「前提を置く」は操作でなく論述の行為なので変更不可
- [残す/文脈上必要] antithesis_repetition: この段落の対比は論旨の核なので残す
```

## 5. 収束

- 改稿を一律に適用しない。着手前に見出し・節へ keep / change を割り振り、デフォルトは keep とする。元版が既に良い箇所は触らない。
- ループは回数でなく状態で終える。出口は、台帳上すべての項目が「直した」か「残す(理由つき)」に仕分けられ、かつ直した修正が新しい検出を生んでいない(lint 再実行で新規発生がない)ときに限る。
- 同じ検出が 2 周連続で「直しては再発」するなら、機械的な修正では収束しない。理由を明記して「残す」に倒すか、文・段落の構造そのものを書き直す。
- 台帳・lint の JSON・下書きのバックアップなどの中間ファイルはスクラッチパッドか一時ディレクトリに置き、完了したら削除する。

## 6. 参考文献

- [coji/natural-japanese](https://github.com/coji/natural-japanese)(MIT ライセンス): スクリプト 5 本(textcore.py・lint.py・outline.py・terms.py・semantic.py)と、検査手順・判断台帳・収束条件の原典。本スキルの構成に合わせて再構成した。
- lint の閾値・severity は、原典が 2026-07 に実施したコーパス校正(人間 103 文書 + AI 81 文書)の結果を引き継いでいる。
