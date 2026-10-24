# dev-skills

Claude Code・Codex CLI・Antigravity CLI のプラグインである。開発作業で使うスキルとサブエージェントを 3 つの CLI に提供し、Claude Code にはセッション開始時に respond を注入し、日本語 Markdown を書き込むたびに検査し、コミットと PR 本文のセッション URL を拒否する hooks も提供する。

## 1. 提供するもの

| 構成要素 | 種別 | 役割 |
| :-- | :-- | :-- |
| `develop` | スキル | 実装タスクを要件の確認から PR まで進める統括の手順。要件(目的・完了条件・対象外・品質(簡易 / プロダクト))の壁打ち、Backlog.md のタスク、GitHub flow、git hook(lefthook・husky)、planner・implementer・reviewer による実装と点検のループ、gate-reviewer によるブランチ全体の点検、push 後の CI 確認を定める。品質がプロダクトのときは secure・observe・recover を適用し、git hook と CI にシークレット検知(gitleaks)と依存監査(osv-scanner)を、CI に SAST(CodeQL か semgrep)を追加し、Claude Code ではゲートの前に `/security-review` を実行する。新しい Web の画面・フォームを作るタスクで UI モックの行が無ければ、要件の確認で UI モックを先に作るか不要かを 1 問聞き、先に作るなら design-ui の工程を示して止まる。UI モックの行は planner に渡す。planner の未確定事項のうち事実で決まるものは統括が調べて決め、本人の判断が必要なものは依存するステップの前に 1 問ずつ聞く。本人の指摘があったタスクでは、閉じる工程で retro を実行する(build の反復を除く) |
| `specify` | スキル | 曖昧な着想から、ユーザーとの対話で「何を作るか」を 1 問ずつ聞き出し、build がそのまま 1 要求 = 1 タスクで分解できる PRD(製品要求仕様書)を書く手順。PRD は雛形 `references/prd.md` から書き、要求ごとに目的・完了条件・対象外・品質の 4 行と、検証できる受け入れ条件を持たせる。PRD の 4.(制約と決定事項)には UI モックの行(brief.md のパス・`未作成`・`不要` のいずれか)を書き、新しい Web の画面・フォームを作る要求で UI モックの行が `未作成` なら、次の一手に design-ui で UI モックを作るかを示す。PRD のタスクへの分解と実装は build が行う |
| `build` | スキル | PRD から起こした複数のタスクを develop で 1 つずつ PR まで進める外側のループ。PRD を受け入れ条件つきの backlog のタスクに分解する工程と、未完了のタスクを 1 つ取って develop で PR まで進め、受け入れ条件を検証して Done にする反復を定める。新しい Web の画面・フォームを作る要求で PRD の UI モックの行が `未作成` か無ければ、分解の前に UI モックを先に作るか不要かを 1 問だけ聞き、タスク本文に UI モックの行を書く。反復ではこの問いで止まらない。状態は backlog と進捗ファイルだけに持ち、全タスクの Done・要判断・同じタスクの失敗の上限・反復の回数の上限などで止まる。`scripts/loop.py` が反復ごとに新しい `claude -p` を起動する(Claude Code) |
| `retro` | スキル | 本人とレビューの指摘を 4 分類(文言・挙動・手順・委譲)に分け、原因を 3 分類(守られなかった・無かった・矛盾)と個別で判定して根拠付きの表にし、個別を除く行を本人の承認を得て dev-skills の改善タスクとして起票する手順。表の雛形 `references/report.md` と事例 `references/example.md` を持つ。Google の SRE 本 15 章を出典とする |
| `planner`・`implementer`・`reviewer`・`gate-reviewer` | サブエージェント(`agents/`) | develop が起動する 4 つの役割。planner は計画(Write/Edit 不可)、implementer はステップ 1 つ分の実装とコミット、reviewer はステップの適合・テスト・欠陥・簡潔さの点検(Write/Edit 不可)、gate-reviewer は push 前のブランチ全体の点検(要件の充足・ステップ間の整合・残骸・PR 本文。Write/Edit 不可)。このうち planner・implementer・reviewer は起動時に ponytail を読み込み、品質がプロダクトのときは secure・observe・recover も読み込み、UI を含むタスクでは design-ui も読み込む。planner は未確定事項に決め方(事実 / 本人の判断)を付けて既定を置かずに書き、品質がプロダクトのとき入口ごとの失敗を「失敗の一覧」の表として計画に書き、UI を含むタスクで状態ごとの見出し・本文・操作を「利用者に見せる文言」の表として計画に書く。reviewer と gate-reviewer は実装の文言が「利用者に見せる文言」の表と文言の規範に合うかを点検する |
| `ponytail` | スキル | コードを最小に保つ規範。そもそも作るかを問い、標準ライブラリと既存のものを先に使い、動く最小の差分で終える。planner・implementer・reviewer が起動時に読み込む |
| `secure` | スキル | プロダクト品質のコードの安全性の規範。信頼境界での入力検証、認証・認可、シークレットと設定、依存の脆弱性、GitHub Actions の供給網(SHA 固定・最小権限)、ログへの秘密の出力、エラー応答からの情報漏えいについて、何を対策すれば十分かを定める。OWASP ASVS と OWASP Cheat Sheet Series を出典とする |
| `observe` | スキル | プロダクト品質のコードの可観測性の規範。構造化ログ、相関 ID、メトリクス、トレース、ヘルスチェック、エラーの分類、計画の完了条件に書く観測の内容を定める。OpenTelemetry のセマンティック規約、Google の SRE 本、W3C Trace Context を出典とする |
| `recover` | スキル | プロダクト品質のコードの失敗時の挙動の規範。入口ごとの失敗の列挙、タイムアウト、リトライと冪等、二重送信の防止、段階的なフォールバック、エラーページ、中間状態の露出防止、計画の完了条件に書く失敗時の挙動を定める。Google の SRE 本、Amazon Builders' Library、RFC 9110 などを出典とする |
| `write-doc` | スキル | 仕様書・手順書・調査レポート・議事録・記事などの日本語文書を書く・推敲する・リライトするときの規範。読み手・表記・文・段落・検査の規範と、検査スクリプト(`lint.py` ほか)を持つ。他者向けの文書は、本人に見せる前に、書いたエージェントと別のエージェントにレビューさせる。見出しが 10 を超える文書では `lint.py` が分担の通知を出す |
| `write-slide` | スキル | プレゼン資料・説明資料のスライド構成を作る・点検するときの規範。型の選択、メッセージライン、ページの役割分担、文体と強調を定める |
| `write-message` | スキル | issue・PR のコメント、レビューコメント、業務チャット、短いメールなど、他者へ送る短い日本語メッセージを敬語で書く・直すときの規範。宛先・場・用件を確かめ、用件から書き、定型の謝辞・結び・申し出と敬語の誤用を除く。敬語の規範(`references/keigo.md`)と場ごとの規範(`references/places.md`)を持つ |
| `respond` | スキル | 会話の応答の形を定める規範。読み手の認知負荷を下げるため、最初の行に答えを書く・最後の行に読み手の次の行動を 1 つ書く・複数手順に番号を振る・状態を毎回書き直す・調べた事実に根拠となるソースを示すなどの規則を定める |
| `draw-diagram` | スキル | `.mmd` で構造を固めてから人間が見やすい SVG を描く作図の規範。埋め込み先の幅で横スクロールを出さない寸法、辺の端点、帯の連続、軸と帯の説明、原典の工程を写す図では箱をまとめない規則、接続線の規則(水平・垂直の線分と角丸の曲がり、線を箱より先に描く。出典は diagram-design)を持つ。`render.py` で `.mmd` と SVG の対応照合・禁止要素の検査・斜めの接続線の検出・Chrome headless の PNG 出力を行う |
| `write-page` | スキル | HTML で配布する説明資料(図・表・切り替えの UI を持つ 1 ページの文書)を作る・直すときの規範と工程。構成とモックの往復、本文と図の作成、HTML の生成、検査、別のエージェントによるレビューの順に進め、本文は write-doc、図は draw-diagram、見た目は design-ui の閲読モードを参照する。HTML 固有の規則(表・一覧・切り替えの UI・折りたたみ・行幅・図の幅・前版の参照)を持つ |
| `design-ui` | スキル | Web・iOS・Android・デスクトップの画面・コンポーネント・ページを設計・実装するときの規範。題材からトークン案を書き、汎用の既定と照合してから実装し、有限回の検証で止める工程を定める。利用者向けの日本語の文言の規範(敬体で書く、利用者が行動を変えられない情報を出さない)を `references/text.md` に持つ。新しい Web の画面・フォームの実装の前に、UI モックを本人と往復して作る工程を `references/session.md` に持つ。往復は HTML のモック・headless Chrome で撮った PNG・文言の表で 1 案ずつ行い(1 往復に質問 1 つ、3 往復まで)、合意を brief.md にまとめる(既定の置き場所は `docs/ui-mock/<slug>/`)。UI モックは PRD と組で build に渡すか、単独で develop に渡す |
| `hooks/inject_respond.py` | hook(SessionStart、Claude Code のみ) | セッション開始時に `skills/respond/SKILL.md` の本文を注入する |
| `hooks/guard_session_url.py` | hook(PreToolUse、Claude Code のみ) | コミットと PR 本文に入るセッション URL を実行前に止める |
| `hooks/inspect_write.py` | hook(PostToolUse、Claude Code のみ) | 日本語 Markdown の書き込み直後に `lint.py` を実行し、検出があれば書き直しを促す警告を返す |
| `hooks/inspect_stop.py` | hook(Stop、Claude Code のみ) | セッション完了時に再検査し、重大カテゴリの検出が残るあいだ完了を差し戻す |

スキルは各 CLI が用途を判断して自動で読み込む。Claude Code では `/dev-skills:develop`・`/dev-skills:specify`・`/dev-skills:build`・`/dev-skills:retro`・`/dev-skills:ponytail`・`/dev-skills:secure`・`/dev-skills:observe`・`/dev-skills:recover`・`/dev-skills:write-doc`・`/dev-skills:write-slide`・`/dev-skills:write-message`・`/dev-skills:draw-diagram`・`/dev-skills:design-ui`・`/dev-skills:write-page`、Codex CLI では `$dev-skills:develop`、Antigravity CLI では `/develop` で明示的に呼んでもよい。サブエージェントは Claude Code では `dev-skills:planner` のように plugin 名つきで起動する。Codex CLI と Antigravity CLI はサブエージェントを起動しないため、develop では統括が 4 つの役割を順に受け持つ。respond は Claude Code では SessionStart hook が常時適用し、Codex CLI・Antigravity CLI ではスキルとして読み込む。hooks に呼び出しの操作はない。プラグインを有効にした Claude Code のセッションで、セッション開始、`git commit`・`gh pr create`・`gh pr edit` の実行前、日本語 Markdown の書き込み、セッション完了のたびに自動で発火する。hooks の stdin の形式は CLI ごとに異なるため、Codex CLI と Antigravity CLI では hooks を提供しない。

## 2. 前提

- `uv` が使えること。`lint.py` は形態素解析に sudachipy を使い、依存は `uv run` がスクリプト先頭の宣言から解決する。`uv` が無い環境では hooks は検査を行わず、スキルは規範に沿って目視で点検する。
- `semantic.py`(文埋め込みで話題の平板さを検出する opt-in の検出器)だけは torch と sentence-transformers に依存し、初回実行時にモデル約 1GB をダウンロードする。hooks からは呼ばない。
- `draw-diagram` の `render.py` による PNG 出力は Google Chrome を必要とする(パスは環境変数 `CHROME_BIN` で変更できる)。Chrome が無い環境では `--png` を付けずに実行し、照合と検査だけを行う。Claude Code のサンドボックス内では Chrome が起動できないため、PNG 出力はサンドボックス外で実行する。`design-ui` の UI モックの撮影も `render.py` で Chrome を使い、撮れないときは PNG の代わりに mock.html のパスを示して往復を続ける。
- `build` の反復は `backlog`(Backlog.md の CLI)・`gh` と、反復を起動する CLI(Claude Code では `claude`)を使う。

## 3. 導入

### 3.1. Claude Code

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

### 3.2. Codex CLI

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

### 3.3. Antigravity CLI

マニフェストはリポジトリ直下の `plugin.json` である。クローンのパスを指定して導入する。

```console
$ agy plugin install <クローンのパス>
```

導入先は `~/.gemini/config/plugins/dev-skills/`(コピー)である。クローンを更新したら同じコマンドで導入し直す。スキルは `/develop`・`/specify`・`/build`・`/retro`・`/ponytail`・`/secure`・`/observe`・`/recover`・`/write-doc`・`/write-slide`・`/write-message`・`/respond`・`/draw-diagram`・`/design-ui`・`/write-page` のスラッシュコマンドにもなる。

## 4. hooks

| hook | 発火 | 動作 |
| :-- | :-- | :-- |
| SessionStart(すべての source) | セッション開始時 | `skills/respond/SKILL.md` の本文を frontmatter を除いて注入する |
| PreToolUse(Bash) | `git commit`・`gh pr create`・`gh pr edit` の実行前 | セッション URL か `Claude-Session:` の行があれば exit 2 で止め、理由を 1 行で返す |
| PostToolUse(Write / Edit / MultiEdit / NotebookEdit) | 日本語 Markdown の書き込み直後 | `lint.py` を `--json` で実行し、検出があれば警告を返す。書き込みは取り消さない |
| Stop | セッション完了時 | そのセッションで検査したファイルを再検査し、重大カテゴリの検出が残るあいだ完了をブロックする |

PreToolUse の対象は、`git commit`(`git -C <path> commit` を含む)・`gh pr create`・`gh pr edit` を含む Bash のコマンドである。`claude.ai/code/session_` の URL と `Claude-Session:` の行(大文字と小文字を区別しない)を、コマンド文字列全体と、`-F`・`--file`・`--body-file` で渡した本文ファイルから探す。相対パスは `cwd` から解決し、`-` は読まない。`Co-Authored-By` と `Generated with` の行は止めない。再利用するメッセージ(`--amend --no-edit`・`-C <commit>`)と、中身がコマンド文字列に現れない `--body "$(cat body.md)"`・`-m "$(cat msg.txt)"` は検査しない。

対象と判定したあとは、本文が読めないときや検査の失敗でも止める(fail-closed)。同じコマンドで作ったファイルや `cd` のあとの相対パスも止まるため、先に作って絶対パスで渡す。

PostToolUse と Stop は日本語文書の検査を行う。発火するのは、拡張子が `.md` / `.markdown` で、日本語文字が 30 文字以上あり、除外パターンに一致しないファイルへの書き込みに限る。警告には、検出の一覧、該当文を丸ごと書き直す指示、語ごとの言い換え例、カテゴリ別の指針が入る。

重大カテゴリとは、Stop が完了をブロックする検出カテゴリの宣言で、既定は `forbidden_phrase`(severity warn 以上。動詞カタログのうち空虚な動詞 4 語と、比喩語 5 語(`壊れる`・`静かに`・`黙って`・`沈黙`・`逃がす`))と `antithesis_repetition`(critical のみ)である。ブロックは既定 3 回で打ち切るため、解消できない検出があっても完了できない状態は続かない。

設定の正本は `hooks/inspection.config.json` である。利用側の変更は `.claude/write-doc-inspection.json` に同じキーで書く。浅い上書きなので、プラグインを更新しても残る。キーの一覧は `skills/write-doc/references/inspection.md` 3. にある。

次のいずれかに当たると、検査と注入の hooks は書き込みと完了を止めずに素通しする。

- `uv` が無い、または `lint.py` を実行できない。
- lint がタイムアウトした、または異常終了した。
- 検査対象の条件(拡張子・日本語文字数・除外パターン・文書種別)を満たさない。
- `skills/respond/SKILL.md` が読めない(SessionStart は何も注入しない)。

検査が発火しているかは、カタログに登録した語を含む Markdown を書いて警告が返ることで確かめる。

## 5. 構成

```
.claude-plugin/
├── plugin.json            # Claude Code 向けのマニフェスト
└── marketplace.json       # このリポジトリ自身をマーケットプレイスとして宣言する
.codex-plugin/
└── plugin.json            # Codex CLI 向けのマニフェスト
plugin.json                # Antigravity CLI 向けのマニフェスト
lefthook.yml                # git hook(pre-commit: plugin validate、pre-push: unittest)
.github/workflows/ci.yml   # CI(ubuntu-latest で unittest と plugin validate --strict、gitleaks)
.github/dependabot.yml     # GitHub Actions の SHA を週次で更新する
LICENSE                    # MIT ライセンスの全文
agents/
├── planner.md             # 計画(opus、Write/Edit 不可、ponytail 読み込み。品質がプロダクトのとき secure・observe・recover も、UI を含むタスクでは design-ui も読み込む)
├── implementer.md         # 実装とコミット(opus、ponytail 読み込み。品質がプロダクトのとき secure・observe・recover も、UI を含むタスクでは design-ui も読み込む)
├── reviewer.md            # ステップの点検と判定(opus、Write/Edit 不可、ponytail 読み込み。品質がプロダクトのとき secure・observe・recover も、UI を含むタスクでは design-ui も読み込む)
└── gate-reviewer.md       # push 前のブランチ全体の点検(opus、Write/Edit 不可)
skills/develop/
├── SKILL.md               # 統括の工程(要件・タスク・ブランチ・計画・実装と点検のループ・ゲート・PR・完了)
└── references/            # requirements.md(要件の 4 行と UI モックの行の形式・聞く範囲・品質の決め方)、git-flow.md(ブランチ・PR・CI・マージ)、hooks.md(lefthook・husky・シークレット検知・依存監査・CI での監査・SAST)
skills/specify/
├── SKILL.md               # 着想から PRD を書く工程(聞く・PRD を書く・確かめて終える)
└── references/prd.md      # PRD の雛形(節ごとの書き方は各節の直下のコメント)
skills/build/
├── SKILL.md               # 外側のループの工程(進捗ファイル・分解・反復・停止と再開・反復の回し方)
└── scripts/loop.py        # 反復ごとに新しい `claude -p` を起動し、停止条件を判定する
skills/retro/
├── SKILL.md               # 指摘からの規範の改善の工程(集める・分類する・原因を判定する・表にして起票する)
└── references/            # report.md・example.md(表と起票案の雛形・2026-10-14 の事例)
skills/write-doc/
├── SKILL.md               # 規範の入口(工程と参照ファイル)
├── references/            # 読み手・表記・文・段落・検査の規範
└── scripts/               # lint.py・outline.py・terms.py・semantic.py と動詞・名詞の NG/OK カタログ
skills/write-slide/
└── SKILL.md               # スライド構成の規範
skills/write-message/
├── SKILL.md               # 短いメッセージの規範の入口(工程・構成・書式・AI らしさの抑制・検査)
└── references/            # keigo.md・places.md(敬語の規範・場ごとの規範)
skills/respond/
└── SKILL.md               # 会話の応答の形を定める規範(本人の特性を前提に、最初の行に答え・最後の行に次の行動を書く規則群)
skills/ponytail/
└── SKILL.md               # コードを最小に保つ規範(はしご・規則・単純にしないもの)
skills/secure/
└── SKILL.md               # コードの安全性の規範(入力検証・認証認可・シークレット・依存・ログ・エラー応答)
skills/observe/
└── SKILL.md               # コードの可観測性の規範(構造化ログ・相関 ID・メトリクス・トレース・ヘルスチェック・エラーの分類・完了条件)
skills/recover/
└── SKILL.md               # 失敗時の挙動の規範(失敗の列挙・タイムアウト・リトライと冪等・二重送信の防止・フォールバック・エラーページ・中間状態の露出防止・完了条件)
skills/draw-diagram/
├── SKILL.md               # 作図の規範の入口
├── references/            # mermaid.md・svg.md・examples/(`.mmd` の書き方・SVG の書式と寸法・サンプル)
└── scripts/render.py      # `.mmd` と SVG の対応照合・禁止要素の検査・斜めの接続線の検出・Chrome headless の PNG 出力
skills/write-page/
└── SKILL.md               # HTML の説明資料の規範(適用範囲・工程・HTML 固有の規則・参照する規範)
skills/design-ui/
├── SKILL.md               # UI 設計規範の入口(モードの選択・工程・スケール)
└── references/            # anti-ai.md・text.md・checklist.md・native.md・session.md・brief.md(汎用の既定の一覧・UI テキストの最小化と利用者向けの文言の規範・実装の品質床・ネイティブアプリ固有の規範・UI モックを作る工程・UI モックの brief の雛形)
hooks/
├── hooks.json             # SessionStart・PreToolUse・PostToolUse・Stop の配線
├── guard_session_url.py   # PreToolUse: コミットと PR 本文のセッション URL を拒否する
├── inject_respond.py      # SessionStart: respond スキルの本文を注入する
├── inspect_write.py       # PostToolUse: 書き込み直後の検査と警告
├── inspect_stop.py        # Stop: 再検査と重大カテゴリによる完了ブロック
├── inspect_lib.py         # 共通処理(設定・対象判定・lint 実行・警告文・状態)
├── inspection.config.json # 検査設定の正本
└── rewrite_guides.json    # カテゴリごとの書き直し指針・言い換え例
tests/                     # カタログと hooks の単体テスト、test_render.py(draw-diagram の render.py)、test_build_loop.py(build の loop.py)、test_manifest_version.py(2 つのマニフェストの version の一致)、corpus/(境界値コーパス)
evals/                     # claude plugin eval のケース(prompt.md と graders/)。結果の出力先 results/ は git 管理外
```

## 6. 開発

### 6.1. プラグインの変更手順

テストは標準ライブラリの `unittest` だけで動く。lefthook の pre-push と GitHub Actions(`.github/workflows/ci.yml`)が同じコマンドを実行する。

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

### 6.2. スキルを書くときの規則

スキルの `SKILL.md` と `references/` のファイルを書くときは、次の規則に従う。

- 雛形は、コピーするとそのまま下書きになる形で提供する。節ごとの書き方の説明は各節の見出しの直下に HTML コメントで書き、使う人は、すべての節を書き終えてからコメントを削除する。write-doc の lint は HTML コメントを検査しないため、説明の文面は検出の対象にならない。例は `skills/specify/references/prd.md` である。
- 節番号での参照は節を追加・削除すると別の節を指すため、複数のスキルが同じ規則を「develop 2.」のような節番号で参照するときは、その規則を、参照される側のスキルの `references/<name>.md` に抜き出す。参照する側は、そのファイル名で参照する。抜き出すのは規則の定義だけにし、手順(誰が・いつ確かめるか)は元のスキルに残す。例は `skills/develop/references/requirements.md`(要件の 4 行の形式)である。
- 上流の資料(yomiyasu など)にある条件付きの規則(文脈で言い換え先が変わる比喩動詞など)を write-doc へ取り込むときは、語ごとに、システム開発の文書で字義どおりの正当な用法があるかを確かめる。条件付きの規則は lint が検出しないため、正当な用法が無い語は `skills/write-doc/scripts/forbidden_phrases.json` に禁止語として登録し、lint で検出する。開発文書でも正当な用法と言い換えるべき用法の両方がある語(引き返す・契約・正本など)だけを、`skills/write-doc/references/sentence.md` に条件付きの規則として書く。

## 7. 評価

`evals/` には `claude plugin eval` のケースがある。各ケースはプラグインあり・なしの 2 アームで同じ依頼を実行し、`graders/` の採点結果の差(Δ)でスキルの効果を測る。

| ケース | 測るもの |
| :-- | :-- |
| `respond-next-action` | 短い作業依頼に、前置きと締めの定型句を付けず、答え(実行するコマンド)から始め、最後の行に読み手の次の行動を書くか(respond) |
| `write-doc-report` | 調査レポートの依頼で write-doc が発火し、読み手の仮定を明示し、書き手の人称を使わないか |
| `one-liner-control` | 1 文で済む質問に、スキルを呼ばず短く正しく答えるか(対照ケース) |

リポジトリのルートで次のコマンドを実行する。1 ケースだけ回すときは `--case <name>` を付ける。Claude Code のサンドボックス内からは実行できないため、通常の端末で実行する。`--max-cost-usd 5` は実績($3.01)に基づく値である。

```console
$ claude plugin eval . --trust-plugin --allow-tools Write Edit -j 4 --max-cost-usd 5 --no-publish
$ claude plugin eval . --trust-plugin --allow-tools Write Edit -j 4 --max-cost-usd 5 --no-publish --case write-doc-report
```

結果は `evals/results/<timestamp>/` に `aggregate-result.json` と HTML レポートとして出力される。このディレクトリは git 管理外である。`evals/RESULTS.md` は eval が生成するファイルではなく、実行ごとに人が手で書く記録である。実行のたびに、`aggregate-result.json` と HTML レポートの値から RESULTS.md の表に 1 回分を書き足す。RESULTS.md の表は次の観点で読む。

- スコアは、あり・なしの各アームの値と、その差(Δ)を見る。Δ が正で、回をまたいで再現するなら、プラグインが採点項目を改善していると判断できる。
- `arm` を指定しない `tool_used: Skill` の grader(`write-doc-report` の `fired`)は、ありアームの発火指標であり、Δ には入らない。`arm: both` を付けた `one-liner-control` の `no-skill` はスコアに入る。
- 1 ケースを 2〜3 回しか実行しないため、Δ の小さな差は誤差の範囲にある。差は傾向として読む。

## 8. ライセンス

MIT ライセンスで公開する。全文は `LICENSE` にある。
