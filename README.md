# japanese-writing

日本語の技術文書を書くための規範スキルと、その検査を自動で走らせる hooks を配る Claude Code プラグイン。

## 1. 概要

配るものは 2 つある。

- **スキル `japanese-writing`**: 仕様書・手順書・調査レポート・議事録・記事などの日本語文書を書く・推敲する・リライトするときの規範。読み手・表記・文・段落の規約と、検査スクリプト(`lint.py` ほか)を持つ。
- **検査 hooks**: 日本語 Markdown の書き込み直後に `lint.py` を実行して書き直しを促し、セッション完了時に再検査して重大カテゴリの検出が残るあいだ完了を差し戻す。

スキルは Claude が必要と判断したときに読み込まれる。hooks はプラグインを有効にしたセッションで決定論的に発火する。

## 2. 構成

```
.claude-plugin/
├── plugin.json            # プラグインのマニフェスト
└── marketplace.json       # このリポジトリ自身をマーケットプレイスとして宣言する
skills/japanese-writing/
├── SKILL.md               # 規範の入口(工程と参照ファイル)
├── references/            # 読み手・表記・文・段落・検査の規範
└── scripts/               # lint.py・outline.py・terms.py・semantic.py と NG/OK カタログ
hooks/
├── hooks.json             # PostToolUse と Stop の配線
├── inspect_write.py       # PostToolUse: 書き込み直後の検査と警告
├── inspect_stop.py        # Stop: 再検査と重大カテゴリによる完了ブロック
├── inspect_lib.py         # 共通処理(設定・対象判定・lint 実行・警告文・状態)
├── inspection.config.json # 検査設定の正本
└── rewrite_guides.json    # カテゴリごとの書き直し指針・言い換え例
tests/                     # カタログと hooks の単体テスト
```

## 3. 導入

```console
$ claude plugin marketplace add mosidas/dev-skills
$ claude plugin install japanese-writing@japanese-writing
```

設定ファイルで宣言することもできる。プロジェクト単位の有効化は `.claude/settings.json` に書く。

```json
{
  "enabledPlugins": {
    "japanese-writing@japanese-writing": true
  }
}
```

マーケットプレイスの宣言(`extraKnownMarketplaces`)はユーザー設定(`~/.claude/settings.json`)に書く。ネットワーク上のマーケットプレイスはプロジェクト設定では信頼されない。

```json
{
  "extraKnownMarketplaces": {
    "japanese-writing": {
      "source": { "source": "github", "repo": "mosidas/dev-skills" }
    }
  }
}
```

hooks はセッション開始時に読み込まれる。有効化した後は、新しいセッションから発火する。

## 4. 前提

`uv` が使えること。`lint.py` は形態素解析に sudachipy を使い、依存は `uv run` がスクリプト先頭の宣言から解決する。`uv` が無い環境では hooks は検査を諦めて何もせず、スキルは規範に沿って目視で点検する。

`semantic.py` だけは torch と sentence-transformers に依存する重量級の opt-in 検出器であり、hooks からは呼ばない。

## 5. 検査 hooks

| hook | 発火 | 動作 |
| :-- | :-- | :-- |
| PostToolUse(Write / Edit / MultiEdit / NotebookEdit) | 日本語 Markdown の書き込み直後 | `lint.py` を `--json` で実行し、検出があれば警告を返す。書き込みは取り消さない |
| Stop | セッション完了時 | そのセッションで検査したファイルを再検査し、重大カテゴリの検出が残るあいだ完了をブロックする |

発火するのは、拡張子が `.md` / `.markdown` で、日本語文字が 30 文字以上あり、除外パターンに一致しないファイルへの書き込みに限る。警告には、検出の一覧・該当文を丸ごと書き直す指示・語ごとの言い換え例・カテゴリ別の指針が入る。

重大カテゴリの既定は `forbidden_phrase`(severity warn 以上)と `antithesis_repetition`(critical のみ)である。Stop のブロックは既定 3 回で打ち切り、解消しない検出で作業が封鎖され続ける事態を避ける。

設定の正本は `hooks/inspection.config.json` である。利用側の変更は `.claude/japanese-writing-inspection.json` に同じキーで書く(浅い上書き。プラグインを更新しても残る)。キーの一覧は `skills/japanese-writing/references/inspection.md` 3. にある。

次のいずれかに当たると、hooks は書き込みと完了を止めずに素通しする。

- `uv` が無い、または `lint.py` を実行できない。
- lint がタイムアウトした、または異常終了した。
- 検査対象の条件(拡張子・日本語文字数・除外パターン・文書種別)を満たさない。

検査が発火しているかは、禁止語を含む Markdown を書いて警告が返ることで確かめる。

## 6. 開発

テストは標準ライブラリの `unittest` だけで動く。

```console
$ python3 -m unittest discover -s tests -t tests
```

マニフェストの検査は次のコマンドで行う。

```console
$ claude plugin validate . --strict
```
