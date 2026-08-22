---
name: ext-writing-inspection
description: 拡張スキル(writing グループ)。日本語 Markdown の書き込み直後に japanese-writing の lint.py を hook で自動実行し、検出した文の書き直し指示と言い換え指針をエージェントへ返す。セッション完了時には再検査し、重大カテゴリの検出が残るあいだ完了をブロックする。検査の実行をエージェントの自主性に任せず決定論的に発火させたいとき、指摘した表現が次のセッションで再び現れる状態を塞ぎたいときに導入する。
---

# ext-writing-inspection — 日本語検査の決定論的発火

japanese-writing スキルは検査スクリプト(`lint.py`)と規範を持つが、実行はエージェントの自主性に委ねられている。読み飛ばせば検査は走らず、指摘済みの表現が次のセッションで再び現れる。本バンドルは検査の**発火**を hook で決定論的にし、検出への対応(書き直しの判断)はこれまでどおりエージェントと書き手に残す。

検査の実体は導入先の `.claude/skills/japanese-writing/scripts/lint.py` である(本バンドルは検出器を持たない)。正規表現と集計で拾えない不自然さは、警告文がエージェント自身の判定(LLM 判定)として書き直し時に指示する。

## 1. 仕組み

| hook | 発火 | 動作 |
| ---- | ---- | ---- |
| PostToolUse(Write / Edit / MultiEdit / NotebookEdit) | 日本語 Markdown の書き込み直後 | lint.py を `--json` で実行し、検出があれば警告をエージェントへ返す。**処理は止めない**(書き込みは成立済み)。書き直しの結果へ再び検査がかかる |
| Stop | セッション完了時 | このセッションで検査したファイルを再検査し、**重大カテゴリ**の検出が残るあいだ完了をブロックする(上限あり。3. の `stop_max_blocks`) |

警告文は次の 4 点で構成する。

- 検出の一覧(行番号・severity・カテゴリ・該当箇所)。
- **検出箇所を含む文を丸ごと書き直す指示**。指摘された語だけを類語に置き換える対処を禁じる(語の置換では検出をすり抜けるだけの別の不自然さが残るため)。
- 語ごとの OK 言い換え例(検出された禁止語に対応。正本は導入先の `.claude/skills/japanese-writing/scripts/forbidden_phrases.json` の NG/OK カタログ)と、カテゴリごとの書き直し指針(`hooks/rewrite_guides.json`)。語を特定できない検出はカテゴリの指針だけになる。
- 機械検出に出ない不自然さ(文脈のねじれ・冗長・常体と敬体の混在)をエージェント自身が判定して直す指示。

## 2. 検査の範囲と発火条件

次のすべてを満たす書き込みで発火する。

- 拡張子が `.md` / `.markdown`。
- 日本語文字(ひらがな・カタカナ・漢字)が `min_japanese_chars`(既定 30)文字以上。
- `exclude` のパターンに一致しない。
- パスに一致した文書種別(3.)の `inspect` が `true`。

効く範囲は導入したプロジェクトの全セッションである(hook は `.claude/settings.json` に配線される)。重量級の `semantic.py`(sentence-transformers 依存)は hook から呼ばない。

## 3. 設定

正本は `hooks/inspection.config.json`。利用側の恒久的な変更は `.claude/ext-writing-inspection.config.json` に同じキーで書く(浅い上書き。バンドルの再導入でスキルディレクトリが置換されても消えない)。

| キー | 意味 |
| ---- | ---- |
| `min_japanese_chars` | 検査対象とみなす日本語文字数のしきい値(既定 30) |
| `exclude` | 検査しないパスのパターン(プロジェクト相対、fnmatch。`*` は `/` もまたぐ) |
| `blocking` | **重大カテゴリの宣言**。`{"category": ..., "min_severity": "info"/"warn"/"critical"}` の配列。該当する検出が残るあいだ Stop が完了をブロックする |
| `doctypes` | 文書種別。`paths` に最初に一致した種別の `genre`(lint.py の閾値プロファイル)・`disabled_categories`(無効化するカテゴリ)・`inspect`(false で検査自体を外す)を適用する |
| `default_doctype` | どの種別にも一致しないファイルへ適用する既定 |
| `stop_max_blocks` | Stop がブロックする回数の上限(既定 3)。超えたら検出が残っていても完了を許可する |
| `lint_timeout_seconds` / `max_findings_in_warning` | lint 実行のタイムアウト / 警告に列挙する検出の上限 |

既定の重大カテゴリは `forbidden_phrase`(severity warn 以上。info の弱いシグナルは除く)と `antithesis_repetition`(critical のみ)である。決定論的に直せて誤検知が少ないカテゴリに限り、集計統計系(文長の分散・語彙多様性等)は判断を要するためブロックしない(警告のみ)。

## 4. 契約と収録物

```
ext-writing-inspection/
├── SKILL.md
├── hooks/
│   ├── inspect_write.py       # PostToolUse: 書き込み直後の検査と警告
│   ├── inspect_stop.py        # Stop: 再検査と重大カテゴリによる完了ブロック
│   ├── inspect_lib.py         # 共通処理(設定・対象判定・lint 実行・警告文・状態)
│   ├── inspection.config.json # 検査設定(重大カテゴリ・文書種別の宣言)
│   └── rewrite_guides.json    # カテゴリごとの書き直し指針・言い換え例
└── settings.snippet.json
```

- **参照**: 導入先の japanese-writing の lint.py(検査の実体)と NG/OK カタログ(語ごとの言い換え例)。カタログが読めない場合は言い換え例を省いて警告する。
- **入力**: PostToolUse / Stop の JSON(標準入力)。`tool_name`・`tool_input` のファイルパス・`cwd`・`session_id`・`stop_hook_active` を読む。
- **出力**: 指摘なしは exit 0(何も出力しない)。指摘ありは `{"decision": "block", "reason": ...}` の JSON(PostToolUse では警告のフィードバック、Stop では完了の差し戻し)。
- **状態**: 検査したファイルの一覧とブロック回数を、一時ディレクトリ配下(`claude-ext-writing-inspection/<プロジェクトのハッシュ>-<セッション ID>.json`)に持つ。リポジトリには何も書かない。
- hook 自身は Python 3 標準ライブラリのみで動作する。lint.py の実行は `uv run`(sudachipy 依存の解決)に委ねる。

## 5. 導入と削除

```console
$ python3 <dev-skills のパス>/install.py ext ext-writing-inspection --target <利用側プロジェクト>
$ python3 <dev-skills のパス>/install.py remove ext-writing-inspection --target <利用側プロジェクト>
```

- 前提: 導入先に japanese-writing スキルが導入済みであること(`install.py core --target <利用側プロジェクト> writing`)と、`uv` が使えること。どちらが欠けても hook はエラーを出さず、検査を諦めて素通しになる(6.)。
- 導入は `.claude/skills/ext-writing-inspection/` へのコピーと、`settings.snippet.json` の `.claude/settings.json` への冪等マージで行う。`remove` はマージ分だけを取り消す。
- hooks の配線はセッション開始時に読み込まれるため、導入後は新しいセッションから有効になる。

## 6. 判定の限界

- **検査できない環境では素通しになる**。uv が無い・japanese-writing が未導入・lint.py の実行失敗・タイムアウトのいずれでも、hook は書き込み・完了を止めない(hook 自身の不具合や環境差で作業を封鎖しない)。検査が効いているかは、禁止語を含む Markdown を書いて警告が返ることで確かめる。
- **検出は lint.py の表層検出に限る**。意味の単調さ(semantic.py)は hook から呼ばない。機械検出に出ない不自然さの書き直しは警告文の指示によるため、助言の域を出ない。
- **Stop のブロックは `stop_max_blocks` 回で打ち切る**。書き直しても解消しない検出(固有名詞由来・文脈上必要)で完了が封鎖され続ける事態を避ける。打ち切り後の残検出は、japanese-writing の収束ループ(`references/inspection.md` 6.)で人が判断する。
- **発火の粒度はファイル単位**である。Edit で 1 行だけ変えても全文を再検査する(検出は編集箇所に限らない)。
- 検査と修正の収束ループ・判断台帳・診断モードは本バンドルの対象外であり、japanese-writing の自主実行(`references/inspection.md`)で行う。hook は「書いた直後の警告」と「完了前のゲート」だけを担う。
