# dev-skills

Claude Code のプラグインである。開発作業で使うスキルと、日本語 Markdown を書き込むたびに検査する hooks を提供する。

## 1. 提供するもの

| 構成要素 | 種別 | 役割 |
| :-- | :-- | :-- |
| `write-doc` | スキル | 仕様書・手順書・調査レポート・議事録・記事などの日本語文書を書く・推敲する・リライトするときの規範。読み手・表記・文・段落・検査の規範と、検査スクリプト(`lint.py` ほか)を持つ |
| `write-slide` | スキル | プレゼン資料・説明資料のスライド構成を作る・点検するときの規範。型の選択、メッセージライン、ページの役割分担、文体と強調を定める |
| `hooks/inspect_write.py` | hook(PostToolUse) | 日本語 Markdown の書き込み直後に `lint.py` を実行し、検出があれば書き直しを促す警告を返す |
| `hooks/inspect_stop.py` | hook(Stop) | セッション完了時に再検査し、重大カテゴリの検出が残るあいだ完了を差し戻す |

スキルは Claude が用途を判断して自動で読み込む。`/dev-skills:write-doc`・`/dev-skills:write-slide` で明示的に呼んでもよい。hooks に呼び出しの操作はない。プラグインを有効にしたセッションで、日本語 Markdown の書き込みとセッション完了のたびに自動で発火する。

## 2. 前提

- `uv` が使えること。`lint.py` は形態素解析に sudachipy を使い、依存は `uv run` がスクリプト先頭の宣言から解決する。`uv` が無い環境では hooks は検査を行わず、スキルは規範に沿って目視で点検する。
- `semantic.py`(文埋め込みで話題の平板さを検出する opt-in の検出器)だけは torch と sentence-transformers に依存し、初回実行時にモデル約 1GB をダウンロードする。hooks からは呼ばない。

## 3. 導入

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

## 4. 検査 hooks

| hook | 発火 | 動作 |
| :-- | :-- | :-- |
| PostToolUse(Write / Edit / MultiEdit / NotebookEdit) | 日本語 Markdown の書き込み直後 | `lint.py` を `--json` で実行し、検出があれば警告を返す。書き込みは取り消さない |
| Stop | セッション完了時 | そのセッションで検査したファイルを再検査し、重大カテゴリの検出が残るあいだ完了をブロックする |

発火するのは、拡張子が `.md` / `.markdown` で、日本語文字が 30 文字以上あり、除外パターンに一致しないファイルへの書き込みに限る。警告には、検出の一覧、該当文を丸ごと書き直す指示、語ごとの言い換え例、カテゴリ別の指針が入る。

重大カテゴリとは、Stop が完了をブロックする検出カテゴリの宣言で、既定は `forbidden_phrase`(severity warn 以上。動詞カタログのうち空虚な動詞 4 語)と `antithesis_repetition`(critical のみ)である。ブロックは既定 3 回で打ち切るため、解消できない検出があっても完了できない状態は続かない。

設定の正本は `hooks/inspection.config.json` である。利用側の変更は `.claude/write-doc-inspection.json` に同じキーで書く。浅い上書きなので、プラグインを更新しても残る。キーの一覧は `skills/write-doc/references/inspection.md` 3. にある。

次のいずれかに当たると、hooks は書き込みと完了を止めずに素通しする。

- `uv` が無い、または `lint.py` を実行できない。
- lint がタイムアウトした、または異常終了した。
- 検査対象の条件(拡張子・日本語文字数・除外パターン・文書種別)を満たさない。

検査が発火しているかは、カタログに登録した動詞を含む Markdown を書いて警告が返ることで確かめる。

## 5. 構成

```
.claude-plugin/
├── plugin.json            # プラグインのマニフェスト
└── marketplace.json       # このリポジトリ自身をマーケットプレイスとして宣言する
skills/write-doc/
├── SKILL.md               # 規範の入口(工程と参照ファイル)
├── references/            # 読み手・表記・文・段落・検査の規範
└── scripts/               # lint.py・outline.py・terms.py・semantic.py と動詞の NG/OK カタログ
skills/write-slide/
└── SKILL.md               # スライド構成の規範
hooks/
├── hooks.json             # PostToolUse と Stop の配線
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

プラグインの内容を変更したら、`.claude-plugin/plugin.json` の `version` を上げる。`claude plugin update` は version が同じだと最新と判定し、変更を取り込まない。

マニフェストの検査は次のコマンドで行う。

```console
$ claude plugin validate . --strict
```
