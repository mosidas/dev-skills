# dev-skills

Claude Code・Codex CLI・Antigravity CLI のプラグインである。開発作業で使うスキルとサブエージェントを 3 つの CLI に提供し、Claude Code にはセッション開始時に respond を注入し、日本語 Markdown を書き込むたびに検査する hooks も提供する。

## 1. 提供するもの

| 構成要素 | 種別 | 役割 |
| :-- | :-- | :-- |
| `develop` | スキル | 実装タスクを要件の確認から PR まで進める統括の手順。要件(目的・完了条件・対象外)の壁打ち、Backlog.md のタスク、GitHub flow、git hook(lefthook・husky)、planner・implementer・reviewer による実装と点検のループ、gate-reviewer によるブランチ全体の点検、push 後の CI 確認を定める |
| `planner`・`implementer`・`reviewer`・`gate-reviewer` | サブエージェント(`agents/`) | develop が起動する 4 つの役割。planner は計画(Write/Edit 不可)、implementer はステップ 1 つ分の実装とコミット、reviewer はステップの適合・テスト・欠陥・簡潔さの点検(Write/Edit 不可)、gate-reviewer は push 前のブランチ全体の点検(要件の充足・ステップ間の整合・残骸・PR 本文。Write/Edit 不可)。このうち planner・implementer・reviewer は起動時に ponytail を読み込む |
| `ponytail` | スキル | コードを最小に保つ規範。そもそも作るかを問い、標準ライブラリと既存のものを先に使い、動く最小の差分で終える。planner・implementer・reviewer が起動時に読み込む |
| `write-doc` | スキル | 仕様書・手順書・調査レポート・議事録・記事などの日本語文書を書く・推敲する・リライトするときの規範。読み手・表記・文・段落・検査の規範と、検査スクリプト(`lint.py` ほか)を持つ |
| `write-slide` | スキル | プレゼン資料・説明資料のスライド構成を作る・点検するときの規範。型の選択、メッセージライン、ページの役割分担、文体と強調を定める |
| `respond` | スキル | 会話の応答の形を定める規範。読み手を ADHD と想定し、次の行動から書く・複数手順に番号を振る・状態を毎回書き直す・調べた事実に根拠となるソースを示すなどの規則を定める |
| `hooks/inject_respond.py` | hook(SessionStart、Claude Code のみ) | セッション開始時に `skills/respond/SKILL.md` の本文を注入する |
| `hooks/inspect_write.py` | hook(PostToolUse、Claude Code のみ) | 日本語 Markdown の書き込み直後に `lint.py` を実行し、検出があれば書き直しを促す警告を返す |
| `hooks/inspect_stop.py` | hook(Stop、Claude Code のみ) | セッション完了時に再検査し、重大カテゴリの検出が残るあいだ完了を差し戻す |

スキルは各 CLI が用途を判断して自動で読み込む。Claude Code では `/dev-skills:develop`・`/dev-skills:ponytail`・`/dev-skills:write-doc`・`/dev-skills:write-slide`、Codex CLI では `$dev-skills:develop`、Antigravity CLI では `/develop` で明示的に呼んでもよい。サブエージェントは Claude Code では `dev-skills:planner` のように plugin 名つきで起動する。Codex CLI と Antigravity CLI はサブエージェントを起動しないため、develop では統括が 3 つの役割を順に担う。respond は Claude Code では SessionStart hook が常時適用し、Codex CLI・Antigravity CLI ではスキルとして読み込む。hooks に呼び出しの操作はない。プラグインを有効にした Claude Code のセッションで、セッション開始・日本語 Markdown の書き込み・セッション完了のたびに自動で発火する。hooks の stdin の形式は CLI ごとに異なるため、Codex CLI と Antigravity CLI では hooks を提供しない。

## 2. 前提

- `uv` が使えること。`lint.py` は形態素解析に sudachipy を使い、依存は `uv run` がスクリプト先頭の宣言から解決する。`uv` が無い環境では hooks は検査を行わず、スキルは規範に沿って目視で点検する。
- `semantic.py`(文埋め込みで話題の平板さを検出する opt-in の検出器)だけは torch と sentence-transformers に依存し、初回実行時にモデル約 1GB をダウンロードする。hooks からは呼ばない。

## 3. 導入

### Claude Code

```console
$ claude plugin marketplace add mosidas/dev-skills
$ claude plugin install dev-skills@mosidas
```

設定ファイルで宣言してもよい。マーケットプレイスの宣言はユーザー設定(`~/.claude/settings.json`)に書く。ネットワーク上のマーケットプレイスはプロジェクト設定では信頼されないためである。

```json
{
  "extraKnownMarketplaces": {
    "mosidas": {
      "source": { "source": "github", "repo": "mosidas/dev-skills" }
    }
  }
}
```

プロジェクト単位の有効化は `.claude/settings.json` に書く。

```json
{
  "enabledPlugins": {
    "dev-skills@mosidas": true
  }
}
```

hooks はセッション開始時に読み込まれるため、有効化した後は新しいセッションから発火する。

### Codex CLI

マニフェストは `.codex-plugin/plugin.json` である。Codex CLI はマーケットプレイス経由でプラグインを導入するため、個人マーケットプレイス `~/.agents/plugins/marketplace.json`(ルートはホームディレクトリ。自動で発見される)にこのリポジトリのクローンを登録し、`codex plugin add` で導入する。

```json
{
  "name": "personal",
  "plugins": [
    {
      "name": "dev-skills",
      "source": { "source": "local", "path": "./repos/dev-skills" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

```console
$ codex plugin add dev-skills@personal
```

導入先は `~/.codex/plugins/cache/personal/dev-skills/<version>/` である。クローンを更新したら同じコマンドで導入し直す。スキルは `$dev-skills:write-doc` の名前で読み込まれる。Codex CLI のプラグインは hooks を扱わない(`codex features list` の `plugin_hooks` は removed)。

### Antigravity CLI

マニフェストはリポジトリ直下の `plugin.json` である。クローンのパスを指定して導入する。

```console
$ agy plugin install <クローンのパス>
```

導入先は `~/.gemini/config/plugins/dev-skills/`(コピー)である。クローンを更新したら同じコマンドで導入し直す。スキルは `/develop`・`/ponytail`・`/write-doc`・`/write-slide`・`/respond` のスラッシュコマンドにもなる。

## 4. hooks

| hook | 発火 | 動作 |
| :-- | :-- | :-- |
| SessionStart(すべての source) | セッション開始時 | `skills/respond/SKILL.md` の本文を frontmatter を除いて注入する |
| PostToolUse(Write / Edit / MultiEdit / NotebookEdit) | 日本語 Markdown の書き込み直後 | `lint.py` を `--json` で実行し、検出があれば警告を返す。書き込みは取り消さない |
| Stop | セッション完了時 | そのセッションで検査したファイルを再検査し、重大カテゴリの検出が残るあいだ完了をブロックする |

PostToolUse と Stop は日本語文書の検査を行う。発火するのは、拡張子が `.md` / `.markdown` で、日本語文字が 30 文字以上あり、除外パターンに一致しないファイルへの書き込みに限る。警告には、検出の一覧、該当文を丸ごと書き直す指示、語ごとの言い換え例、カテゴリ別の指針が入る。

重大カテゴリとは、Stop が完了をブロックする検出カテゴリの宣言で、既定は `forbidden_phrase`(severity warn 以上。動詞カタログのうち空虚な動詞 4 語)と `antithesis_repetition`(critical のみ)である。ブロックは既定 3 回で打ち切るため、解消できない検出があっても完了できない状態は続かない。

設定の正本は `hooks/inspection.config.json` である。利用側の変更は `.claude/write-doc-inspection.json` に同じキーで書く。浅い上書きなので、プラグインを更新しても残る。キーの一覧は `skills/write-doc/references/inspection.md` 3. にある。

次のいずれかに当たると、hooks は書き込みと完了を止めずに素通しする。

- `uv` が無い、または `lint.py` を実行できない。
- lint がタイムアウトした、または異常終了した。
- 検査対象の条件(拡張子・日本語文字数・除外パターン・文書種別)を満たさない。
- `skills/respond/SKILL.md` が読めない(SessionStart は何も注入しない)。

検査が発火しているかは、カタログに登録した動詞を含む Markdown を書いて警告が返ることで確かめる。

## 5. 構成

```
.claude-plugin/
├── plugin.json            # Claude Code 向けのマニフェスト
└── marketplace.json       # このリポジトリ自身をマーケットプレイスとして宣言する
.codex-plugin/
└── plugin.json            # Codex CLI 向けのマニフェスト
plugin.json                # Antigravity CLI 向けのマニフェスト
lefthook.yml                # git hook(pre-commit: plugin validate、pre-push: unittest)
agents/
├── planner.md             # 計画(opus、Write/Edit 不可、ponytail 読み込み)
├── implementer.md         # 実装とコミット(sonnet、ponytail 読み込み)
├── reviewer.md            # ステップの点検と判定(opus、Write/Edit 不可、ponytail 読み込み)
└── gate-reviewer.md       # push 前のブランチ全体の点検(opus、Write/Edit 不可)
skills/develop/
├── SKILL.md               # 統括の工程(要件・タスク・ブランチ・計画・実装と点検のループ・ゲート・PR・完了)
└── references/            # git-flow.md(ブランチ・PR・CI・マージ)、hooks.md(lefthook・husky)
skills/write-doc/
├── SKILL.md               # 規範の入口(工程と参照ファイル)
├── references/            # 読み手・表記・文・段落・検査の規範
└── scripts/               # lint.py・outline.py・terms.py・semantic.py と動詞の NG/OK カタログ
skills/write-slide/
└── SKILL.md               # スライド構成の規範
skills/respond/
└── SKILL.md               # 会話の応答の形を定める規範(ADHD 想定の読み手、次の行動から書く規則群)
skills/ponytail/
└── SKILL.md               # コードを最小に保つ規範(はしご・規則・単純にしないもの)
hooks/
├── hooks.json             # SessionStart・PostToolUse・Stop の配線
├── inject_respond.py      # SessionStart: respond スキルの本文を注入する
├── inspect_write.py       # PostToolUse: 書き込み直後の検査と警告
├── inspect_stop.py        # Stop: 再検査と重大カテゴリによる完了ブロック
├── inspect_lib.py         # 共通処理(設定・対象判定・lint 実行・警告文・状態)
├── inspection.config.json # 検査設定の正本
└── rewrite_guides.json    # カテゴリごとの書き直し指針・言い換え例
tests/                     # カタログと hooks の単体テスト
```

## 6. 開発

テストは標準ライブラリの `unittest` だけで動く。

```console
$ python3 -m unittest discover -s tests -t tests
```

プラグインの内容を変更したら、`.claude-plugin/plugin.json` と `.codex-plugin/plugin.json` の `version` を同じ値に上げる。`claude plugin update` は version が同じだと最新と判定し、変更を取り込まない。

マニフェストの検査は次のコマンドで行う。Codex CLI の検査スクリプトは同梱スキル `plugin-creator` のもので、`interface` の 5 項目と `defaultPrompt` を必須とする。

```console
$ claude plugin validate . --strict
$ uv run --with pyyaml python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
$ agy plugin validate .
```
