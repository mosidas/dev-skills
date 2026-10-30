# dev-skills

Claude Code・Codex CLI・Antigravity CLI のプラグインである。開発作業で使うスキルとサブエージェントを 3 つの CLI に提供し、Claude Code にはセッション開始時に respond を注入し、日本語 Markdown を書き込むたびに検査し、コミットと PR 本文のセッション URL を拒否する hooks も提供する。

## 1. 提供するもの

| 構成要素 | 種別 | 役割 |
| :-- | :-- | :-- |
| `develop` | スキル | 実装タスクを要件の確認から PR まで進める統括の手順。要件(目的・完了条件・対象外・品質(簡易 / プロダクト))の壁打ち、Backlog.md のタスク、GitHub flow、git hook(lefthook・husky)、planner・implementer・reviewer による実装と点検のループ、gate-reviewer によるブランチ全体の点検、push 後の CI 確認を定める。品質がプロダクトのときは secure・observe・recover を適用し、git hook と CI にシークレット検知(gitleaks)と依存監査(osv-scanner)を、CI に SAST(CodeQL か semgrep)を追加し、Claude Code ではゲートの前に `/security-review` を実行する。新しい Web の画面・フォームを作るタスクで UI モックの行が無ければ、要件の確認で UI モックを先に作るか不要かを 1 問聞き、先に作るなら design-ui の工程を示して止まる。UI モックの行は planner に渡す。計画の未確定事項のうち事実で決まるものは統括が調べて決め、調べても決まらないものと本人の判断が必要なものは依存するステップの前に 1 問ずつ聞く。本人の指摘があったタスクでは、閉じる工程で retro を実行する(build の反復を除く) |
| `specify` | スキル | 曖昧な着想から、ユーザーとの対話で「何を作るか」を 1 問ずつ聞き出し、build がそのまま 1 要求 = 1 タスクで分解できる PRD(製品要求仕様書)を書く手順。PRD は雛形 `references/prd.md` から書き、要求ごとに目的・完了条件・対象外・品質の 4 行と、検証できる受け入れ条件を持たせる。PRD の 4.(制約と決定事項)には UI モックの行(brief.md のパス・`未作成`・`不要` のいずれか)を書き、新しい Web の画面・フォームを作る要求で UI モックの行が `未作成` なら、次の一手に design-ui で UI モックを作るかを示す。PRD のタスクへの分解と実装は build が行う |
| `build` | スキル | PRD から起こした複数のタスクを develop で 1 つずつ PR まで進める外側のループ。PRD を受け入れ条件つきの backlog のタスクに分解する工程と、未完了のタスクを 1 つ取って develop で PR まで進め、受け入れ条件を検証して Done にする反復を定める。新しい Web の画面・フォームを作る要求で PRD の UI モックの行が `未作成` か無ければ、分解の前に UI モックを先に作るか不要かを 1 問だけ聞き、タスク本文に UI モックの行を書く。反復ではこの問いで止まらない。状態は backlog と進捗ファイルだけに持ち、全タスクの Done・要判断・同じタスクの失敗の上限・反復の回数の上限などで止まる。`scripts/loop.py` が反復ごとに新しい `claude -p` を起動する(Claude Code) |
| `retro` | スキル | 本人とレビューの指摘を 4 分類(文言・挙動・手順・委譲)に分け、原因を 3 分類(守られなかった・無かった・矛盾)と個別で判定して根拠付きの表にし、個別を除く行を本人の承認を得て dev-skills の改善タスクとして起票する手順。原因が「無かった」で直す場所が文書の規範なら、規範にするか(案件の記録・宛先プロファイルに残すか)と、write-doc のどの束に加えるかを判定する。本人の指摘の回数と往復の回数を記録する。表の雛形 `references/report.md` と事例 `references/example.md` を持つ。Google の SRE 本 15 章を出典とする |
| `planner`・`implementer`・`reviewer`・`gate-reviewer` | サブエージェント(`agents/`) | develop が起動する 4 つの役割。planner は計画(Write/Edit 不可)、implementer はステップ 1 つ分の実装とコミット、reviewer はステップの適合・テスト・欠陥・簡潔さの点検(Write/Edit 不可)、gate-reviewer は push 前のブランチ全体の点検(要件の充足・ステップ間の整合・残骸・PR 本文。Write/Edit 不可)。このうち planner・implementer・reviewer は起動時に ponytail を読み込み、品質がプロダクトのときは secure・observe・recover も読み込み、UI を含むタスクでは design-ui も読み込む。planner は未確定事項に決め方(事実 / 本人の判断)を付けて既定を置かずに書き、品質がプロダクトのとき入口ごとの失敗を「失敗の一覧」の表として計画に書き、UI を含むタスクで状態ごとの見出し・本文・操作と、管理画面の項目名・選択肢の値と並びを「利用者に見せる文言」の表として計画に書く。reviewer と gate-reviewer は実装の文言が「利用者に見せる文言」の表と文言の規範に合うかを点検する。planner は計画に設計の節(中核のデータの形・呼び出し側の使い方・関数境界を越える変更の 2 案・要求が最初からあったら作る形)と順序の節(先行する作業・最小の分解)を書く。4 つの役割は判断を変えた原則を報告に名指しする。reviewer と gate-reviewer は名指しした判断が差分にあるかを点検する |
| `ponytail` | スキル | コードを最小に保つ規範。そもそも作るかを問い、標準ライブラリと既存のもの、利用する外部サービスの組み込み機能を先に使い、動く最小の差分で終える。原則の名前と規則の所在の索引を持つ。設計の原則と設計の赤信号を参照ファイル `references/design.md` に持つ。planner・implementer・reviewer が起動時に読み込む |
| `secure` | スキル | プロダクト品質のコードの安全性の規範。信頼境界での入力検証、認証・認可、シークレットと設定、依存の脆弱性、GitHub Actions の供給網(SHA 固定・最小権限)、ログへの秘密の出力、エラー応答からの情報漏えいについて、何を対策すれば十分かを定める。OWASP ASVS と OWASP Cheat Sheet Series を出典とする |
| `observe` | スキル | プロダクト品質のコードの可観測性の規範。構造化ログ、相関 ID、メトリクス、トレース、ヘルスチェック、エラーの分類、計画の完了条件に書く観測の内容を定める。OpenTelemetry のセマンティック規約、Google の SRE 本、W3C Trace Context を出典とする |
| `recover` | スキル | プロダクト品質のコードの失敗時の挙動の規範。入口ごとの失敗の列挙、タイムアウト、リトライと冪等(移行・投入のスクリプトを空の環境から 1 回の実行で最終状態にし、再実行で変えないことを含む)、二重送信の防止、段階的なフォールバック、エラーページ、中間状態の露出防止、計画の完了条件に書く失敗時の挙動を定める。Google の SRE 本、Amazon Builders' Library、RFC 9110 などを出典とする |
| `write-doc` | スキル | 仕様書・手順書・調査レポート・議事録・記事などの日本語文書を書く・推敲する・リライトするときの規範。`references/` を 4 つの束(言語・読み手と工程・形式・種類)に分け、SKILL.md は束と参照ファイルの表だけを持つ。工程の規範 `process.md` に、着手時の brief、骨組みの合意、レビュー役に渡す物を定める。形式の束は `format/`(Markdown・HTML・スライド)、種類の束は `types/` の手順書・仕様書と規約・議事録・調査レポート・技術記事・企画書と PRD の 6 種類のファイルである。検査スクリプト(`lint.py` ほか)を持つ。他者向けの文書は、本人に見せる前に、書いたエージェントと別のエージェントにレビューさせる。見出しが 10 を超える文書では `lint.py` が分担の通知を出す |
| `write-slide` | スキル | プレゼン資料・説明資料のスライド構成を作る・点検するときの入口。読む write-doc のファイル(`format/slide.md` と言語の束)と、型の確認・ページ単位の骨組み・スケルトン通読の工程を定める |
| `write-message` | スキル | issue・PR のコメント、レビューコメント、業務チャット、短いメールなど、他者へ送る短い日本語メッセージを敬語で書く・直すときの規範。宛先・場・用件を確かめ、用件から書き、定型の謝辞・結び・申し出と敬語の誤用を除く。敬語の規範(`references/keigo.md`)と場ごとの規範(`references/places.md`)を持つ |
| `respond` | スキル | 会話の応答の形を定める規範。読み手の認知負荷を下げるため、最初の行に答えを書く・最後の行に読み手の次の行動を 1 つ書く・複数手順に番号を振る・状態を毎回書き直す・調べた事実に根拠となるソースを示すなどの規則を定める |
| `draw-diagram` | スキル | `.mmd` で構造を固めてから人間が見やすい SVG を描く作図の規範。埋め込み先の幅で横スクロールを出さない寸法、辺の端点、帯の連続、軸と帯の説明、原典の工程を写す図では箱をまとめない規則、接続線の規則(水平・垂直の線分と角丸の曲がり、線を箱より先に描く。出典は diagram-design)を持つ。`render.py` で `.mmd` と SVG の対応照合・禁止要素の検査・斜めの接続線の検出・Chrome headless の PNG 出力を行う |
| `write-page` | スキル | HTML で配布する説明資料(図・表・切り替えの UI を持つ 1 ページの文書)を作る・直すときの入口。読む write-doc のファイル(HTML 固有の規則を持つ `format/html.md` と、工程・言語の束)と、モックの往復・本文と図の作成・HTML の生成・検査の HTML 固有の工程を定める。図は draw-diagram、見た目は design-ui の閲読モードを参照する |
| `design-ui` | スキル | Web・iOS・Android・デスクトップの画面・コンポーネント・ページを設計・実装するときの規範。題材からトークン案を書き、汎用の既定と照合してから実装し、有限回の検証で止める工程を定める。利用者向けの日本語の文言の規範(敬体で書く、利用者が行動を変えられない情報を出さない、管理画面の項目名・選択肢は利用者の画面の見出しと同じ語を既定にする)を `references/text.md` に持つ。新しい Web の画面・フォームの実装の前に、UI モックを本人と往復して作る工程を `references/session.md` に持つ。往復は HTML のモック・headless Chrome で撮った PNG・文言の表で 1 案ずつ行い(1 往復に質問 1 つ、3 往復まで)、合意を brief.md にまとめる(既定の置き場所は `docs/ui-mock/<slug>/`)。UI モックは PRD と組で build に渡すか、単独で develop に渡す |
| `hooks/inject_respond.py` | hook(SessionStart、Claude Code のみ) | セッション開始時に `skills/respond/SKILL.md` の本文を注入する |
| `hooks/guard_session_url.py` | hook(PreToolUse、Claude Code のみ) | コミットと PR 本文に入るセッション URL を実行前に止める |
| `hooks/inspect_write.py` | hook(PostToolUse、Claude Code のみ) | 日本語 Markdown の書き込み直後に `lint.py` を実行し、検出があれば書き直しを促す警告を返す |
| `hooks/inspect_stop.py` | hook(Stop、Claude Code のみ) | セッション完了時に再検査し、重大カテゴリの検出が残るあいだ完了を差し戻す |

スキルは各 CLI が用途を判断して自動で読み込む。Claude Code では `/dev-skills:develop`・`/dev-skills:specify`・`/dev-skills:build`・`/dev-skills:retro`・`/dev-skills:ponytail`・`/dev-skills:secure`・`/dev-skills:observe`・`/dev-skills:recover`・`/dev-skills:write-doc`・`/dev-skills:write-slide`・`/dev-skills:write-message`・`/dev-skills:draw-diagram`・`/dev-skills:design-ui`・`/dev-skills:write-page`、Codex CLI では `$dev-skills:develop`、Antigravity CLI では `/develop` で明示的に呼んでもよい。サブエージェントは Claude Code では `dev-skills:planner` のように plugin 名つきで起動する。Codex CLI と Antigravity CLI はサブエージェントを起動しないため、develop では統括が 4 つの役割を順に受け持つ。respond は Claude Code では SessionStart hook が常時適用し、Codex CLI・Antigravity CLI ではスキルとして読み込む。hooks に呼び出しの操作はない。プラグインを有効にした Claude Code のセッションで、セッション開始、`git commit`・`gh pr create`・`gh pr edit` の実行前、日本語 Markdown の書き込み、セッション完了のたびに自動で発火する。hooks の stdin の形式は CLI ごとに異なるため、Codex CLI と Antigravity CLI では hooks を提供しない。

本人は次の原則の名前で軌道修正を指示できる。原則ごとの適用する場面と規則の所在は ponytail の「原則の索引」にある。

| 英語名 | 日本語名 |
| :-- | :-- |
| Laziness Protocol | 怠ける作法 |
| Foundational Thinking | 土台から考える |
| Redesign from First Principles | 一から設計し直す |
| Attack the Premise | 前提を疑う |
| Subtract Before You Add | 足す前に削る |
| Minimize Reader Load | 読み手の負荷を減らす |
| Outcome-Oriented Execution | 最終の形を目指す |
| Experience First | 体験を先に |
| Build the Lever | 道具を作る |
| Model the Domain | ドメインを構造で表す |
| Boundary Discipline | 境界で守る |
| Type System Discipline | 型で守る |
| Make Operations Idempotent | 操作を冪等にする |
| Migrate Callers Then Delete Legacy APIs | 呼び出し元を移して旧 API を削除する |
| Separate Before Serializing Shared State | 直列化の前に共有をなくす |
| Prove It Works | 動くと示す |
| Fix Root Causes | 根本原因を直す |
| Sequence Work into Verifiable Units | 確かめられる単位で刻む |
| Test Behavior, Not Implementation | 実装でなく挙動をテストする |
| Guard the Context Window | コンテキストを守る |
| Never Block on the Human | 人を待たない |
| Encode Lessons in Structure | 教訓を構造にする |

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
├── SKILL.md               # 規範の入口(束と参照ファイルの表)
├── references/            # 4 つの束。言語: sentence.md・paragraph.md(文と表記・段落と見出し)、読み手と工程: readers.md・process.md・inspection.md(読み手・brief と骨組みの合意とレビュー役に渡す物・検査)
│   ├── format/            # 形式の束: markdown.md・html.md・slide.md
│   └── types/             # 種類の束: procedure.md・spec.md・minutes.md・report.md・article.md・proposal.md と一覧の README.md
└── scripts/               # lint.py・outline.py・terms.py・semantic.py と動詞・名詞の NG/OK カタログ
skills/write-slide/
└── SKILL.md               # スライド構成の規範の入口(読むファイルの表とスライド固有の工程)
skills/write-message/
├── SKILL.md               # 短いメッセージの規範の入口(工程・構成・書式・AI らしさの抑制・検査)
└── references/            # keigo.md・places.md(敬語の規範・場ごとの規範)
skills/respond/
└── SKILL.md               # 会話の応答の形を定める規範(本人の特性を前提に、最初の行に答え・最後の行に次の行動を書く規則群)
skills/ponytail/
├── SKILL.md               # コードを最小に保つ規範(はしご・規則・単純にしないもの・原則の索引)
└── references/design.md   # 設計の原則(ドメインを構造で表す・型で守る・境界の内側の構造・直列化の前に共有をなくす)と設計の赤信号
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
└── SKILL.md               # HTML の説明資料の規範の入口(読むファイルの表と HTML 固有の工程)
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
- 上流の資料を取り込んだときは、出典(資料名・URL・ライセンス・版とコミット SHA・取り込んだ範囲)をスキルの `SKILL.md` と `references/` に書かず、README の 9. に書く。CLI がスキルを読み込むたびに出典の文面もコンテキストに入るためである。
- 規則を具体的な手段の禁止や指示の列挙だけで書かない。列挙に無い場面でも判定を導ける考え(何を守るためか・判定の問い)を書く。手段は考えの例として書く。lint で検出する禁止語の登録はこの規則から除く。例は ponytail の「テストの判定」(2 つの想像上の編集で判定する)である。規則が無くてもエージェントが同じに振る舞う文は書かない。そうした文を見つけたら削る。

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

## 9. 出典

この節は、各スキルが取り込んだ上流の資料の出典をまとめる。版とコミットは取り込んだ時点の値であり、上流の更新を調べるときは、この値からの差分を見る。この節は、取り込んだ資料のライセンスが求める帰属表示も兼ねる。9.3 以降の各小節で文中と括弧内に出る節番号は、ファイルを示した小節ではそのファイルの節を、示していない小節では `skills/<スキル名>/SKILL.md` の節を指す。

### 9.1. 一覧

ライセンスの列の「明示なし」は資料にライセンスの表記が無いことを、「未確認」はライセンスを確かめていないことを示す。

| 出典 | ライセンス | 取り込んだ版・コミット | 反映先 |
| :-- | :-- | :-- | :-- |
| [cursor/plugins](https://github.com/cursor/plugins) の pstack | MIT | コミット 997ffc7(2026-10-12 時点。specify)・0.15.36(コミット 1ba91fc、2026-10-28) | specify・develop・build・ponytail・recover・retro・respond・agents(`planner.md`・`implementer.md`・`reviewer.md`・`gate-reviewer.md`)・README 6.2 |
| [mattpocock/skills](https://github.com/mattpocock/skills) | MIT | コミット 49dd158(2026-10-12 時点) | specify |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | MIT | v5.1.0 | ponytail |
| [coji/natural-japanese](https://github.com/coji/natural-japanese) | MIT | v1.5.0(9a78a42)・v1.6.0(03bc944)・v1.6.2(a88b8e9) | write-doc(`inspection.md`・`paragraph.md`・`readers.md`・`sentence.md`・`format/slide.md`・`types/report.md`)・write-slide・write-message(`SKILL.md`) |
| [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu) | MIT | v1.1.1(373356e)・v2.0.1(84e1f5b)・v2.3.0(15244a1) | write-doc(`inspection.md`・`paragraph.md`・`readers.md`・`sentence.md`・`types/minutes.md`)・write-message(`SKILL.md`・`keigo.md`) |
| [mizchi/explainer](https://github.com/mizchi/explainer) | MIT | 版の記載なし | write-doc(`paragraph.md`・`readers.md`) |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | Apache-2.0 | 版の記載なし | write-doc(`paragraph.md`・`readers.md`。explainer を経由) |
| [carnot-tech/consulting-pptx-skill](https://github.com/carnot-tech/consulting-pptx-skill) | MIT | コミット bc9a587 | write-doc(`format/slide.md`・`paragraph.md`・`sentence.md`・`process.md`・`inspection.md`)・write-slide・draw-diagram(`SKILL.md`) |
| [iKora128/stop-ai-slop-jp](https://github.com/iKora128/stop-ai-slop-jp) | MIT | コミット e09d327 | write-message(`SKILL.md`) |
| [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd) | MIT | 版の記載なし | respond |
| [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | MIT | v2.6.115(f2f4d49) | draw-diagram(`svg.md`・`render.py`) |
| [anthropics/skills frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | Apache-2.0 | 版の記載なし | design-ui(`SKILL.md`・`anti-ai.md`・`text.md`) |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Apache-2.0 | 版の記載なし | design-ui(`SKILL.md`・`anti-ai.md`・`checklist.md`・`native.md`・`text.md`) |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | MIT | 版の記載なし | design-ui(`SKILL.md`・`checklist.md`) |
| [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) | MIT | 版の記載なし | design-ui(`SKILL.md`・`checklist.md`) |
| `vercel-labs/agent-skills` の `skills/web-design-guidelines` | 未確認 | 版の記載なし | design-ui(`SKILL.md`・`checklist.md`。web-interface-guidelines の経由先) |
| [s0xDk/refactoring-ui-skill](https://github.com/s0xDk/refactoring-ui-skill) | MIT | 版の記載なし | design-ui(`SKILL.md`・`text.md`) |
| [misskey-dev/misskey のバグ報告テンプレート](https://github.com/misskey-dev/misskey/blob/develop/.github/ISSUE_TEMPLATE/01_bug-report.yml) | AGPL-3.0 | 版の記載なし | write-message(`places.md`) |
| [asciidwango/js-primer](https://github.com/asciidwango/js-primer) | CC BY 4.0 | 版の記載なし | write-message(`places.md`) |
| [vim-jp/vimdoc-ja](https://github.com/vim-jp/vimdoc-ja) | 未確認 | 版の記載なし | write-message(`places.md`。コメントの集計) |
| [textlint-ja/textlint-rule-preset-ja-technical-writing](https://github.com/textlint-ja/textlint-rule-preset-ja-technical-writing) | 未確認 | 版の記載なし | write-message(`places.md`。コメントの集計) |
| [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/) | Apache-2.0 | 1.44.0 | observe |
| Google『Site Reliability Engineering』 | CC BY-NC-ND 4.0 | 2017 年版の第 6 章・第 15 章・第 22 章 | observe・recover・retro |
| [W3C Trace Context Level 1](https://www.w3.org/TR/trace-context/) | W3C Software and Document License | W3C 勧告(2021-11-23) | observe |
| [Kubernetes の liveness/readiness probe](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) | 未確認 | 版の記載なし | observe |
| [Amazon Builders' Library "Timeouts, retries, and backoff with jitter"](https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter) | 明示なし | 版の記載なし | recover |
| [RFC 9110 HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) | IETF Trust Legal Provisions | 2022-06(STD 97) | recover |
| [RFC 6585 Additional HTTP Status Codes](https://www.rfc-editor.org/rfc/rfc6585.html) | IETF Trust Legal Provisions | 2012-04 | recover |
| [Stripe API Reference "Idempotent requests"](https://docs.stripe.com/api/idempotent_requests) | 明示なし | 版の記載なし | recover |
| [Google Search Central "How HTTP status codes, and network and DNS errors affect Google Search"](https://developers.google.com/search/docs/crawling-indexing/http-network-errors) | CC BY 4.0 | 2026-02-04 更新 | recover |
| Michael T. Nygard『Release It! Second Edition』 | 未確認 | 2018 年 | recover |
| [OWASP Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/) | CC BY-SA 4.0 | 5.0.0(2025-05-30 公開) | secure |
| [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/) | CC BY-SA 4.0 | 版番号なし | secure |
| 木下是雄『理科系の作文技術』 | 未確認 | 版の記載なし | write-doc(`paragraph.md`・`sentence.md`) |
| 結城浩『数学文章作法 基礎編・推敲編』 | 未確認 | 版の記載なし | write-doc(`paragraph.md`) |
| Wathan & Schoger『Refactoring UI』 | 未確認 | 版の記載なし | design-ui(`SKILL.md`・`text.md`。refactoring-ui-skill の原典) |
| [敬語の指針](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/keigo_tosin.pdf) | 未確認 | 平成 19 年 2 月 2 日 | write-message(`keigo.md`) |
| [公用文作成の考え方](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/93651301_01.pdf) | 未確認 | 令和 4 年 1 月 7 日 | write-message(`keigo.md`) |
| [分かり合うための言語コミュニケーション(報告)](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/wakariau/pdf/r1403493_01.pdf) | 未確認 | 平成 30 年 3 月 2 日 | write-message(`keigo.md`) |
| [平成 25 年度「国語に関する世論調査」報告書](https://www.bunka.go.jp/tokei_hakusho_shuppan/tokeichosa/kokugo_yoronchosa/pdf/92701201_06.pdf) | 未確認 | 平成 25 年度 | write-message(`keigo.md`) |
| [洞澤伸・岡江里子「「バイト敬語」を使う若者たち」](https://gifu-u.repo.nii.ac.jp/record/68522/files/reg_030019001.pdf) | 未確認 | 2006 年 | write-message(`keigo.md`) |
| [ビジネスメールの基本構成(マイナビニュース)](https://news.mynavi.jp/article/businessmail-6/) | 明示なし | 版の記載なし | write-message(`places.md`) |
| [メールの書き方について(神田外語大学 学生課)](https://www.kandagaigo.ac.jp/kuis/cms/wp-content/uploads/2020/04/c7fa5f7a72fa9eb5d79262912a336d08.pdf) | 明示なし | 版の記載なし | write-message(`places.md`) |
| [Slack 公式ブログのチャットのエチケット](https://slack.com/intl/ja-jp/blog/collaboration/etiquette-tips-in-slack) | 明示なし | 版の記載なし | write-message(`places.md`) |
| [ITmedia NEWS の Slack マナーの記事](https://www.itmedia.co.jp/news/articles/2001/09/news073.html) | 明示なし | 版の記載なし | write-message(`places.md`) |
| [How to Report Bugs Effectively(Simon Tatham)](https://www.chiark.greenend.org.uk/~sgtatham/bugs.html) | OpenContent License | 版の記載なし | write-message(`places.md`) |
| [OSS Issue投稿ガイド(Zenn)](https://zenn.dev/immedio/articles/15c1b953696841) | 明示なし | 版の記載なし | write-message(`places.md`) |
| [OSS に Issue 報告する際の作法(DevelopersIO)](https://dev.classmethod.jp/articles/issue-report-to-oss/) | 明示なし | 版の記載なし | write-message(`places.md`) |
| [How to write code review comments(Google Engineering Practices)](https://google.github.io/eng-practices/review/reviewer/comments.html) | CC BY 3.0 | 版の記載なし | write-message(`places.md`) |
| [Conventional Comments](https://conventionalcomments.org/) | CC BY 3.0 | 版の記載なし | write-message(`places.md`) |
| [レビューコメントで頻繁に使うプレフィックス(DevelopersIO)](https://dev.classmethod.jp/articles/prefixes-for-frequently-used-review-comments/) | 明示なし | 版の記載なし | write-message(`places.md`) |
| [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) | CC BY-SA 4.0 | 版の記載なし | write-message(`SKILL.md`) |
| [大西夢「AI 生成文からみた「自然な日本語」についての研究」(広島大学文学部、卒業論文)](https://home.hiroshima-u.ac.jp/jshira/papers/AI生成文からみた「自然な日本語」についての研究（大西夢）.pdf) | 明示なし | 令和 7 年度 | write-message(`SKILL.md`) |
| [マナーべるの記事](https://mannerbell.com/ai-email-revise-manner/) | 明示なし | 2026-04-17 の記事 | write-message(`SKILL.md`) |
| [KDDI のコラム](https://biz.kddi.com/content/column/smb/making-of-sentence/) | 明示なし | 版の記載なし | write-message(`SKILL.md`) |
| [プレジデントオンラインの記事](https://news.yahoo.co.jp/articles/032bcc2f342a768b8ff275e43fa98dbc14febb1a) | 明示なし | 版の記載なし | write-message(`SKILL.md`) |
| [NN/g](https://www.nngroup.com/articles/) の記事(Tooltip Guidelines・Icon Usability・Progressive Disclosure・Error-Message Guidelines) | 未確認 | 版の記載なし | design-ui(`SKILL.md`・`text.md`) |
| [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/) | 未確認 | 版の記載なし | design-ui(`SKILL.md`・`native.md`・`text.md`) |
| [Material Design 3](https://m3.material.io/) と developer.android.com の文書 | 未確認 | 版の記載なし | design-ui(`SKILL.md`・`native.md`・`text.md`) |
| [Flutter: Platform adaptations](https://docs.flutter.dev/platform-integration/platform-adaptations) | 未確認 | 版の記載なし | design-ui(`native.md`) |
| [React Native: Platform-specific code](https://reactnative.dev/docs/platform-specific-code) | 未確認 | 版の記載なし | design-ui(`native.md`) |
| [developersdigest](https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it)・[925studios](https://www.925studios.co/blog/ai-slop-design-tells)・[mania.design](https://www.mania.design/blog/spot-the-slop-a-ui-designers-guide-to-fixing-ai-defaults/)・[dev.to](https://dev.to/james_anderson_h/the-purple-gradient-problem-why-ai-ui-all-looks-alike-and-how-to-fix-it-3j65) の記事 | 未確認 | 版の記載なし | design-ui(`anti-ai.md`) |

### 9.2. specify

specify は、次の 2 つのリポジトリにある 3 つの手法(grill-me、to-spec と to-tickets、pstack)を参考にした。取り込んだのは dev-skills のコミット 59cac98 であり、手法を specify の文体で書き直した。

- cursor/plugins の pstack(MIT ライセンス、Copyright (c) 2026 Lauren Tan、https://github.com/cursor/plugins)。2026-10-12 時点のコミット 997ffc7 の `pstack/skills/figure-it-out/SKILL.md` と `pstack/skills/poteto-mode/playbooks/multi-phase-plan.md` を参考にした。
- mattpocock/skills(MIT ライセンス、Copyright (c) 2026 Matt Pocock、https://github.com/mattpocock/skills)。2026-10-12 時点のコミット 49dd158 の `skills/productivity/grill-me/SKILL.md`・`skills/engineering/to-spec/SKILL.md`・`skills/engineering/to-tickets/SKILL.md` を参考にした。

取り込んだ範囲は次の 8 点である。文中と括弧内の節番号は `skills/specify/SKILL.md` の節を指す。

- 調べて分かることは、聞かずに先に調べる(2.)。
- 要求一覧は、1 件ずつ深さ優先で聞く(2.)。
- 問いを 5 つの型から選ぶ(2.)。
- 5〜8 問ごとに、埋まった節と未決の問いをユーザーに示す(2.)。
- 1 つの要求を、単独で確かめられる縦の一切れにする(3.)。
- 依存の制約を満たす範囲で、不確かさの大きい要求を先に並べる(3.)。
- 承認の前に、要求の粒度・依存・分割と統合の 3 点を聞く(4.)。
- PRD の雛形 `references/prd.md` に、制約と決定事項の節を設ける。

### 9.3. retro

retro は次の資料を参照し、要点を自分の言葉でまとめた。文面は転載していない。2026-10-15 に公式ページで版とライセンスを確かめた。

- Google『Site Reliability Engineering』(2017)第 15 章 "Postmortem Culture: Learning from Failure"(John Lunney・Sue Lueder)。CC BY-NC-ND 4.0。https://sre.google/sre-book/postmortem-culture/ 。参照した要点と、retro で対応する箇所は次の 3 つである。
  - ふりかえりを実施する条件を、事前に決めておく。retro では 1. の「本人の指摘が 1 回以上」にあたる。
  - 個人を責めず、仕組みと工程を直す。retro では 1. の指摘の扱いと、5.6 の対処の型にあたる。
  - 再発を防ぐ対策を記録に含める。retro では 6. の起票にあたる。

4\. の分類と 5. の原因の分類は外部の出典を持たず、2026-10-14 の事例(`references/example.md`)に基づく。ただし 5.6 の表の後の段落(規則を加える前の確認と考えで書くこと)は pstack を元にする(9.14)。

### 9.4. ponytail

ponytail は ponytail(MIT ライセンス、Copyright (c) 2026 DietrichGebert、https://github.com/DietrichGebert/ponytail)v5.1.0 の `skills/ponytail/SKILL.md` を元にする。強度の切り替え(lite・ultra)は取り込まず、既定の強度の規範だけを残した。テストの判定(5.)と根本原因の段落(2.)の一部は pstack を元にする(9.14)。

### 9.5. secure

secure は次の資料を参照し、要点を自分の言葉でまとめた。文面は転載していない。いずれも 2026-10-11 に公式ページで版とライセンスを確かめた。

- OWASP Application Security Verification Standard(ASVS)5.0.0(2025-05-30 公開)。CC BY-SA 4.0。https://owasp.org/www-project-application-security-verification-standard/
- OWASP Cheat Sheet Series(版番号なし)。CC BY-SA 4.0。https://cheatsheetseries.owasp.org/ 。参照したのは次の 7 本である。
  - Input Validation・Authentication・Authorization・Secrets Management・Logging・Error Handling・Vulnerable Dependency Management(各 `cheatsheets/<名前>_Cheat_Sheet.html`)

### 9.6. observe

observe は次の資料を参照し、要点を自分の言葉でまとめた。文面は転載していない。いずれも 2026-10-11 に公式ページで版とライセンスを確かめた。

- OpenTelemetry Semantic Conventions 1.44.0。Apache-2.0(リポジトリ open-telemetry/semantic-conventions)。https://opentelemetry.io/docs/specs/semconv/
- Google『Site Reliability Engineering』(2017)第 6 章 "Monitoring Distributed Systems"。CC BY-NC-ND 4.0。https://sre.google/sre-book/monitoring-distributed-systems/
- W3C Trace Context Level 1(W3C 勧告、2021-11-23)。W3C Software and Document License。https://www.w3.org/TR/trace-context/

2.5 は Kubernetes の liveness/readiness probe の慣習に基づく。https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/

### 9.7. recover

recover は次の資料を参照し、要点を自分の言葉でまとめた。文面は転載していない。Release It! を除き、いずれも 2026-10-14 に公式ページで版とライセンスを確かめた。

- Google『Site Reliability Engineering』(2017)第 22 章 "Addressing Cascading Failures"。CC BY-NC-ND 4.0。https://sre.google/sre-book/addressing-cascading-failures/
- Amazon Builders' Library "Timeouts, retries, and backoff with jitter"(Marc Brooker)。ライセンスの明示は無い(© Amazon Web Services, Inc.)ため、要点の要約にとどめた。https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter
- RFC 9110 HTTP Semantics(2022-06、STD 97)。IETF Trust Legal Provisions。https://www.rfc-editor.org/rfc/rfc9110.html 。参照した節は 9.2.2(冪等なメソッド)・10.2.3(Retry-After)・15.5.5(404)・15.5.6(405 と Allow)・15.6.1(500)・15.6.4(503。Retry-After は MAY)である。
- RFC 6585 Additional HTTP Status Codes(2012-04)。IETF Trust Legal Provisions。https://www.rfc-editor.org/rfc/rfc6585.html 。参照した節は 4.(429)である。
- Stripe API Reference "Idempotent requests"。ライセンスの明示は無いため、要点の要約にとどめた。https://docs.stripe.com/api/idempotent_requests
- Google Search Central "How HTTP status codes, and network and DNS errors affect Google Search"(2026-02-04 更新)。CC BY 4.0。https://developers.google.com/search/docs/crawling-indexing/http-network-errors
- Michael T. Nygard『Release It! Second Edition』(Pragmatic Bookshelf、2018)。Timeouts・Fail Fast の背景として書名だけを挙げる。

2.6 の noindex と 2.7 は外部の出典を持たない。2.7 は、結果ページを直接開くと置換前の印がそのまま見えたという実装の事例に基づき、2.6 の noindex は、エラーページを独立した URL で配信すると直接開いたときに 200 で返るという本文の理由に基づく。

2.3 の再実行される操作の箇条は pstack を元にする(9.14)。

NN/g Error-Message Guidelines は design-ui の `references/text.md` の出典(README 9.13.5)にある。

### 9.8. write-doc

#### 9.8.1. `skills/write-doc/references/inspection.md`

- [coji/natural-japanese](https://github.com/coji/natural-japanese)(MIT ライセンス): スクリプト 5 本(textcore.py・lint.py・outline.py・terms.py・semantic.py)と、検査手順・判断台帳・収束条件の原典。write-doc の構成に合わせて再構成した。v1.6.0(コミット 03bc944)からは、文末の打ち消しの多用の検出器(`negation_repetition`)、文中の太字の多用の既定化と行頭のラベルの除外、誤検出の削減(語の境目・文頭の反復・段落の具体性・画像と URL とタグの除外・英字だけの行の除外)、BOM 付きファイルの読み込み、段落ごとの確かめの一覧と、読み手の手間を増やす 5 種(4.)を取り込んだ。段落の分割は、上流の `scripts/paragraphs.py` を持ち込まず、lint.py の中に書いた。v1.6.1 に含まれるコミット b2d1d34 の `skills/natural-japanese/scripts/calques.py` の `MOTION_VERBS` からは、`sentence.md` 3. に例のある 3 語(吐く・死ぬ・育つ)を NG/OK カタログ(`forbidden_phrases.json`、info)へ取り込んだ。残りの語と、候補を並べるスクリプト本体は取り込んでいない。
- [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)(MIT ライセンス): v2.0.1(コミット 84e1f5b)の `references/rephrase-test.md`・`references/fact-recovery.md` からは、言い直しテストの 6 点と削る案の比べ方、補いと訂正の根拠の範囲(4.)を取り込んだ。同じ版の `references/lists/fact-gaps.txt` の程度の語・比喩の語と、`references/slop-catalog.md` の定型導入・文末の付け足し・定型の結びは、lint の NG/OK カタログと前置フィラーの検出へ取り込んだ。同じ版の `references/slop-catalog.md` の仮置きの残り(4.)を取り込んだ。【要確認】を仮置きとして扱う部分は、確信度ラベルと衝突するため取り込んでいない。v2.1.0(コミット 8be3ef6)の `skills/yomiyasu/SKILL.md`・`references/review-points.md` からは、段落ごとの確かめの目的語と主題と、言い直しテストの許可・能力・義務・保証の強さ(4.)を取り込んだ。v2.1.1(コミット fbe02c9)の `scripts/yomiyasu_diff.py`・`references/review-points.md` からは、言い直しテストの範囲の語と因果の例(4.)を取り込んだ。v2.2.0(コミット a34d94f)の `references/lists/thin-evaluation.txt`・`references/slop-catalog.md` 5 章からは、中身の薄い評価の文の検出器(`thin_evaluation`、info)と技術文書向けの 15 組を lint.py へ取り込んだ。製品レビュー向けの 20 組(〜心地・質感・携帯性・保温性など)は取り込んでいない。同じ版の `references/slop-catalog.md` 6 章からは、翻訳調の「と言えるでしょう」を lint.py へ取り込んだ。上流の除外の条件(直前が体言・「に当たる」)と、`calque`・`cleft_list_ending` の検出器は取り込んでいない。上流は v2.3.0(コミット 15244a1)まで確かめた。
- lint の閾値・severity は、原典が 2026-07 に実施したコーパス校正(人間 103 文書 + AI 81 文書)の結果を引き継いでいる。

#### 9.8.2. `skills/write-doc/references/paragraph.md`

- 木下是雄『理科系の作文技術』中公新書: パラグラフとトピックセンテンスの一次出典。
- 結城浩『数学文章作法 基礎編・推敲編』ちくま学芸文庫: 読者の負荷を下げる原則の一次出典。
- [coji/natural-japanese](https://github.com/coji/natural-japanese)(MIT ライセンス): トピックセンテンス・箇条書きの扱い、節の濃淡、前置きの禁止、スケルトン通読、接地の原典。write-doc の書式に合わせて再構成した。v1.6.0(コミット 03bc944)の `SKILL.md` からは冒頭の要約の条件と要約の節(3.)を取り込んだ。
- [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)(MIT ライセンス): v2.0.1(コミット 84e1f5b)の `skills/yomiyasu/SKILL.md`・`references/slop-catalog.md` から、AI への指示の残り(3.)と、括弧の中の手順(4.)を取り込んだ。v2.1.1(コミット fbe02c9)の `references/review-points.md` からは、関連・相関・時の前後を因果に強めない規則(2.)を取り込んだ。v2.2.0(コミット a34d94f)・v2.2.1(コミット 91964cd)の `references/calques.md` からは、見出しのたとえの語と見出しの目的(6.)を取り込んだ。上流は v2.3.0(コミット 15244a1)まで確かめた。
- [mizchi/explainer](https://github.com/mizchi/explainer)(MIT ライセンス): `skills/explainer/SKILL.md`・`skills/explainer/references/writing.md` が、伝えたいことの 1 文・節の役割の表・削除テストの原典。explainer はこれらを [HyperFrames](https://github.com/heygen-com/hyperframes)(Apache-2.0)の `story-spine.md`・`brief-contract.md` を参考に書いた。write-doc の書式に合わせて再構成した。

#### 9.8.3. `skills/write-doc/references/readers.md`

- [mizchi/explainer](https://github.com/mizchi/explainer)(MIT ライセンス): `skills/explainer/SKILL.md`・`skills/explainer/references/persona.md` が、確認できないときに依頼文にあったことと推測したことを分けて書く規則の原典。explainer はこれを [HyperFrames](https://github.com/heygen-com/hyperframes)(Apache-2.0)の `brief-contract.md` を参考に書いた。write-doc の書式に合わせて再構成した。
- [coji/natural-japanese](https://github.com/coji/natural-japanese)(MIT ライセンス): v1.6.1(コミット ee007f5)の `skills/natural-japanese/SKILL.md`・`references/doctypes/memo.md` から、素材の作業用の名前(3.)を取り込んだ。上流は v1.6.2(コミット a88b8e9)まで確かめた。
- [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)(MIT ライセンス): v2.0.1(コミット 84e1f5b)の `references/audience.md`・`references/persona.md` から、説明の無い用語を書き手に返す規則(3.)を取り込んだ。v2.1.0(コミット 8be3ef6)の `skills/yomiyasu/SKILL.md` の「書き手に確かめたい点」からは、問いの選び方(3.)を取り込んだ。問いの上限の数(3 点)は上流の雛形の都合のため、取り込んでいない。上流は v2.3.0(コミット 15244a1)まで確かめた。

#### 9.8.4. `skills/write-doc/references/sentence.md`

- 木下是雄『理科系の作文技術』中公新書: 事実と意見の峻別の一次出典。
- [coji/natural-japanese](https://github.com/coji/natural-japanese)(MIT ライセンス): 読みやすさの原則・悪文の型・カタログと例文の原典。write-doc の書式に合わせて再構成した。v1.5.0 までの references は、v1.6.0 で `SKILL.md`・`references/manual-checklist.md`・`references/diagnose.md`・`references/doctypes/` に再編された。v1.6.0(コミット 03bc944)の `SKILL.md`・`references/manual-checklist.md` からは、先回りの打ち消しと残す打ち消しの 3 種(2.)、演出の語、読み手が何のことか取れない言い回しの型と確かめ方、比喩の読み方の報告(3.)、英語の逐語訳(5.)を取り込んだ。硬い漢語への置き換えを避ける規則は漢語基調(3.)と衝突し、技術の言い方として定着した比喩(「キャッシュが効く」)を直さない例外は 3. の比喩の規則(「効く」)とカタログの語と衝突するため、どちらも取り込んでいない。同じ版の `SKILL.md` からは文を分けるときの接続語(2.)と、数字・引用と改行(4.)を、`references/doctypes/memo.md` からは対象外の範囲(4.)を取り込んだ。v1.6.1(コミット ee007f5)の `skills/natural-japanese/SKILL.md` からは、新しい呼び名の規則(1.)を取り込んだ。v1.6.1(コミット 70e6e6a・717d8e0)の `skills/natural-japanese/SKILL.md` からは、読み手の分野の呼び名にそろえる規則(1.)を取り込んだ。v1.6.2(コミット 9d3fd3b)の `skills/natural-japanese/SKILL.md` からは、lint の指摘の有無で直すかを判断しない規則と、好みで言い換えない規則(3.)を取り込んだ。上流は v1.6.2(コミット a88b8e9)まで確かめた。
- [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)(MIT ライセンス): 要請と機能説明の書き分け、リライト時の情報増補の禁止、質感・認知を装う語と比喩動詞のカタログ、前置フィラー・定型クロージングの原典。write-doc の書式に合わせて再構成した。v1.1.1(コミット 373356e)の `skills/yomiyasu/SKILL.md`・`references/slop-catalog.md` からは、条件付きの比喩動詞(うち `壊れる`・`静かに`・`黙って`・`沈黙`・`逃がす` は、カタログの禁止語にした)、定着した慣用句、大げさな名詞、文末の立場、言い直しの締め、文頭の「もちろん、」、否定対比の条件を取り込んだ。同じ版の見出しの規則は、`paragraph.md` 6. へ取り込んだ。v2.0.1(コミット 84e1f5b)の `skills/yomiyasu/SKILL.md`・`references/rephrase-test.md`・`references/fact-recovery.md` からは、2 文に分けた否定対比(2.)、文の種類の保持と、リライトで使ってよい根拠の範囲(4.)を取り込んだ。本文に【要確認】を挟まない規則は、確信度ラベル(4.)と衝突するため取り込んでいない。同じ版の `skills/yomiyasu/SKILL.md`・`references/slop-catalog.md`・`references/domains/business.md` からは、`paragraph.md` の見出しの括弧と「〜について」・短い動作の見出し・題(6.)と `types/minutes.md` の議事録の推敲(3.)、`sentence.md` の補助動詞と形式名詞のひらがな(6.)と読点とラベルのコロン(7.)を取り込んだ。読点の規則は 2026-10-28 に本人の指示(接続詞の後にだけ使い、ほかの箇所は文を分ける)で置き換え、上流の読点の規則は残っていない。同じ 3 ファイルからは、「〜するには」・詰めた漢語の句・使役・前後の語での補い・指示語・予定を述べる結び(2.)、確度の語(3.)、論文調と「これにより」(5.)も取り込んだ。v2.1.0(コミット 8be3ef6)の `skills/yomiyasu/SKILL.md`・`references/gemini-syntax.md`・`references/review-points.md` からは、他動詞の目的語、主題の掛かり先、許可・能力・義務・保証、「〜のは」の強調(2.)と、RFC 2119 の表との関係(`types/spec.md` 3.)を取り込んだ。v2.2.0(コミット a34d94f)・v2.2.1(コミット 91964cd)の `references/calques.md`・`references/slop-catalog.md`・`skills/yomiyasu/SKILL.md` からは、場所のたとえの型と直し方、中身の薄い評価(3.)と、「〜と言えるでしょう」(4.)を取り込んだ。lint の `thin_evaluation` と「と言えるでしょう」の検出の出典は 9.8.1 に書いた。上流の lint の検出器 `calque` は取り込んでいない。上流は v2.3.0(コミット 15244a1)まで確かめた。

#### 9.8.5. `skills/write-doc/references/types/minutes.md`

- [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)(MIT ライセンス): v2.0.1(コミット 84e1f5b)の `references/domains/business.md` から、議事録の推敲で話題の順と見出しを変えない規則(3.)を取り込んだ。この規則は `paragraph.md` 6. から移した。

#### 9.8.6. `skills/write-doc/references/types/report.md`

- [coji/natural-japanese](https://github.com/coji/natural-japanese)(MIT ライセンス): 結びの再統合と、v1.6.0(コミット 03bc944)の `references/doctypes/report.md` からの調査の結びの検証と選択肢(3.)の原典。いずれも `paragraph.md` 3. から移した。

### 9.9. write-slide

write-slide の規則は write-doc の `references/format/slide.md` と言語の束(`sentence.md`・`paragraph.md`)・工程の束(`process.md`・`inspection.md`)へ移した。以下の出典は、移した先のファイルと節で示す。

プレゼン型の原型は [coji/natural-japanese](https://github.com/coji/natural-japanese)(MIT ライセンス)にある。v1.6.0(コミット 03bc944)の `references/doctypes/slide.md` からは `format/slide.md` 2. のメッセージラインの長さと 6. のラベルの太字を、`references/doctypes/memo.md` からは `paragraph.md` 7. の当てはまらないマスを取り込んだ。

`format/slide.md` 1.・2.・4.〜6. と、`sentence.md`・`paragraph.md` に移した項(1.〜4.・7.)、`process.md`・`inspection.md` の一部は [consulting-pptx-skill](https://github.com/carnot-tech/consulting-pptx-skill)(MIT ライセンス)の `references/slide-rules.md`(コミット bc9a587 時点)を元にする。同じ版の `references/slide-rules.md` からは、社外の資料の敬称(`sentence.md` 6.)、「できる」と「行う」の区別(`sentence.md` 4.)、表紙・タイトル・章名の略語と同じ見せ方の連続(`format/slide.md` 5.)、見出しの種類を指すだけの語・2 軸マトリクス・図の選び方・操作画面とロゴ(`paragraph.md` 7.)、定型ページ(`process.md` 5.)、ページの増減後の番号の照合(`inspection.md` 4.)、消した要素の全ページでの確かめ(`process.md` 7.)を、`SKILL.md` の手順 9 からは見たページの番号の報告(`process.md` 7.)を取り込んだ。同じ版の `references/slide-rules.md` の §8 からは、draw-diagram §2 の括弧・矢印・三角の向きと矢尻の目視も取り込んだ。

### 9.10. write-message

#### 9.10.1. `skills/write-message/SKILL.md`

- [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)(MIT ライセンス): v2.0.1(コミット 84e1f5b)の `references/slop-catalog.md` から、チャット応答の名残(謝辞・同意・申し出)、数の宣言、定型の結びの分類を取り込んだ。同じ版の `references/doc-types/mail.md` から、頼みごとの分割と期限の掛かり先(3.)、詫び・礼を減らす条件(5.)を取り込み、`references/persona.md`・`docs/usage.md` から `references/keigo.md` の規則を取り込んだ。
- [coji/natural-japanese](https://github.com/coji/natural-japanese)(MIT ライセンス): v1.5.0(コミット 9a78a42)の `references/forbidden-patterns.md` から、同意の演出の例を取り込んだ。
- [iKora128/stop-ai-slop-jp](https://github.com/iKora128/stop-ai-slop-jp)(MIT ライセンス): コミット e09d327 の `references/phrases.md` から、ヘッジを 1 段落に 1 つまでとする上限を、1 つのメッセージに 1 つまでとして取り込んだ。
- [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)(CC BY-SA 4.0): コメントに特有の兆候(見出し付きの長いコメント、事実のない謝罪、確認したことの主張、装飾の絵文字)を、文面を訳さずに規則として取り込んだ。日本語の表現への対応づけは write-message の判断である。
- [AI 生成文からみた「自然な日本語」についての研究(大西夢、広島大学文学部、令和 7 年度卒業論文)](https://home.hiroshima-u.ac.jp/jshira/papers/AI生成文からみた「自然な日本語」についての研究（大西夢）.pdf)(ライセンス表記なし): 柔らかい文体ほど AI らしさに気付かれやすいという結果を、5. の理由として使った。査読を経ていないため、規則の根拠にはしていない。
- 次の記事は、テンプレート的な構成と固有の一文の欠如を AI らしさとして挙げている。ライセンス表記が無いため文面は取り込まず、URL だけを示す: [マナーべる(2026-04-17 の記事)](https://mannerbell.com/ai-email-revise-manner/)、[生成AIの文章はなぜ「バレる」？ 自然に仕上げるテクニックを解説(KDDI)](https://biz.kddi.com/content/column/smb/making-of-sentence/)、[｢～ことを示している｣と書いた瞬間にバレる…(プレジデントオンライン)](https://news.yahoo.co.jp/articles/032bcc2f342a768b8ff275e43fa98dbc14febb1a)
- 出典の無い設計上の判断: 依頼の前置きの上限(1 つ)、長さの目安(3 文・10 文)、固有の語を含める規則、検出を残す範囲は、write-message の設計で決めた。

#### 9.10.2. `skills/write-message/references/keigo.md`

- [敬語の指針(文化審議会答申、平成 19 年 2 月 2 日)](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/keigo_tosin.pdf)(ライセンス表記は未確認): 二重敬語と定着した例(p.30)、相手の動作への謙譲語の誤用(【10】【11】)、自分側と物を尊敬語で立てる誤用(【16】【34】)、「させていただく」の 2 条件(【18】)、依頼の表現(【31】【33】)、「御苦労様」(【27】)を取り込んだ。
- [公用文作成の考え方(文化審議会建議、令和 4 年 1 月 7 日)](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/93651301_01.pdf)(ライセンス表記は未確認): 敬体の文末の基準と、「(ら)れる」程度を標準とする基準を、1. へ転用した。
- [分かり合うための言語コミュニケーション(報告)(文化審議会国語分科会、平成 30 年 3 月 2 日)](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/wakariau/pdf/r1403493_01.pdf)(ライセンス表記は未確認): 曖昧な断り、期限のある依頼の「幸いです」「助かります」、目上への評価、疑問符を取り込んだ。
- [平成 25 年度「国語に関する世論調査」報告書(文化庁文化部国語課)](https://www.bunka.go.jp/tokei_hakusho_shuppan/tokeichosa/kokugo_yoronchosa/pdf/92701201_06.pdf)(ライセンス表記は未確認): 二重敬語と謙譲語の誤用の例を、3. と 2. の確認に使った。
- [洞澤伸・岡江里子「「バイト敬語」を使う若者たち: 話し手の心理と聞き手の印象」(岐阜大学地域科学部研究報告 第 19 号、2006)](https://gifu-u.repo.nii.ac.jp/record/68522/files/reg_030019001.pdf)(ライセンス表記は未確認): 「〜になります」「〜のほう」を気になるとした割合(平成 14 年度の世論調査からの二次引用)を、5. の根拠にした。敬語の指針には、この 2 つの表現の記述が無い。
- [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu)(MIT ライセンス): v2.0.1(コミット 84e1f5b)の `references/persona.md`・`docs/usage.md` から、重い依頼の組み立て(1.)、読み手の行為への謙譲語(3.)、「教えてください」と「〜し直してください」(6.)、お詫びと約束の言い回し(10.)を取り込んだ。
- Before と After の例文は、出典の例文を参考に write-message で作った。

#### 9.10.3. `skills/write-message/references/places.md`

- [ビジネスメールの基本構成(日本ビジネスメール協会、マイナビニュース)](https://news.mynavi.jp/article/businessmail-6/)と[メールの書き方について(神田外語大学 学生課)](https://www.kandagaigo.ac.jp/kuis/cms/wp-content/uploads/2020/04/c7fa5f7a72fa9eb5d79262912a336d08.pdf)(どちらもライセンス表記なし): メールの宛名・挨拶・名乗り・要旨・詳細・結び・署名の構成と、挨拶・結びの定型句を 1. と 2. に取り込んだ。文面は転載していない。
- [Slack 公式ブログのチャットのエチケット](https://slack.com/intl/ja-jp/blog/collaboration/etiquette-tips-in-slack)と[ネットで叩かれている「Slackマナー」は本当にアホらしいのか?(ITmedia NEWS)](https://www.itmedia.co.jp/news/articles/2001/09/news073.html)(どちらもライセンス表記なし): チャットで挨拶だけのメッセージを送らないこと、宛名・所属・署名を書かないことを取り込んだ。文面は転載していない。
- [How to Report Bugs Effectively(Simon Tatham)](https://www.chiark.greenend.org.uk/~sgtatham/bugs.html)(OpenContent License)、[misskey-dev/misskey のバグ報告テンプレート](https://github.com/misskey-dev/misskey/blob/develop/.github/ISSUE_TEMPLATE/01_bug-report.yml)(AGPL-3.0)、[asciidwango/js-primer のバグ報告テンプレート](https://github.com/asciidwango/js-primer/blob/master/.github/ISSUE_TEMPLATE/bug_report.md)(CC BY 4.0): バグ報告の項目と、症状と推測を分けることを取り込んだ。テンプレートの文面は取り込んでいない。
- 次の記事から、1 つの issue に 1 つの話題、賛同はリアクションで示すこと、公開してよい情報だけを書くことを取り込んだ。ライセンス表記が無いため URL だけを示す: [OSS Issue投稿ガイド(Zenn)](https://zenn.dev/immedio/articles/15c1b953696841)、[OSS に Issue 報告する際の作法(DevelopersIO)](https://dev.classmethod.jp/articles/issue-report-to-oss/)
- [How to write code review comments(Google Engineering Practices)](https://google.github.io/eng-practices/review/reviewer/comments.html)(CC BY 3.0)と [Conventional Comments](https://conventionalcomments.org/)(CC BY 3.0): コードについて書くこと、理由を書くこと、重大度のラベル、確信が無いときは質問にすることを取り込んだ。Before の例文は Google の悪い例を日本語にした。
- [レビューコメントで頻繁に使うプレフィックス(DevelopersIO)](https://dev.classmethod.jp/articles/prefixes-for-frequently-used-review-comments/)(ライセンス表記なし): 日本のチームのラベル(`[must]` `[imo]`)の例として URL だけを示す。
- 出典の無い設計上の判断: issue・PR のコメントで宛名・挨拶・名乗り・結びを書かない規則は、日本語の OSS 3 リポジトリ([vim-jp/vimdoc-ja](https://github.com/vim-jp/vimdoc-ja)、[asciidwango/js-primer](https://github.com/asciidwango/js-primer)、[textlint-ja/textlint-rule-preset-ja-technical-writing](https://github.com/textlint-ja/textlint-rule-preset-ja-technical-writing))のコメント 106 件を数えた結果から一般化した。チャットの結びを 1 回までとする規則と、ラベルの慣習が読み取れないときに確かめる規則も、write-message の判断である。

### 9.11. respond

respond は i-have-adhd(MIT ライセンス、Copyright (c) 2026 Ayoub Ghriss、https://github.com/ayghri/i-have-adhd)の規則を元にする。冒頭の段落・1.・2. の 1〜2・3.1・3.3・3.5・5. は、本人の特性(複数の作業を並行し、最後の行から読む)に合わせて 2026-10-20 に書き換えた。3.11〜3.13 は workspace の `AGENTS.md` の原則を、3.14 は workspace の運用で得た指摘を反映する。

### 9.12. draw-diagram

#### 9.12.1. `skills/draw-diagram/references/svg.md`

9\. の規則は、[cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design)(MIT ライセンス、Copyright (c) 2025 Cathryn Lavery)v2.6.115(コミット f2f4d49)の `skills/diagram-design/references/primitives-core.md` にある接続線の規則 6 項目と、`SKILL.md` 6. にある描く順序の 1 項目を元にする。draw-diagram の語と書式(CSS で矢尻を付ける、ラベルに背景を付けない)に合わせて書き直した。`render.py` の斜めの線分の検出は、同リポジトリの `scripts/verify-geometry.py` の検出項目の 1 つを参考にし、`data-edge` を持つ要素を対象として書き直した。

### 9.13. design-ui

#### 9.13.1. `skills/design-ui/SKILL.md`

スケール(4.)は Refactoring UI(Wathan & Schoger)を出典とする。

- [anthropics/skills frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design)(Apache-2.0)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)(Apache-2.0)
- [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)(MIT)
- [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines)(MIT。`vercel-labs/agent-skills` の `skills/web-design-guidelines` 経由)
- [s0xDk/refactoring-ui-skill](https://github.com/s0xDk/refactoring-ui-skill)(MIT。原典 Wathan & Schoger, *Refactoring UI*)
- [NN/g](https://www.nngroup.com/articles/)、[Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)、[Material Design 3](https://m3.material.io/)

#### 9.13.2. `skills/design-ui/references/anti-ai.md`

- [anthropics/skills frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design)(Apache-2.0)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)(Apache-2.0)、`skill/reference/craft-floor.md`
- [developersdigest: AI design slop and how to spot it](https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it)
- [925studios: AI slop design tells](https://www.925studios.co/blog/ai-slop-design-tells)
- [mania.design: spot the slop](https://www.mania.design/blog/spot-the-slop-a-ui-designers-guide-to-fixing-ai-defaults/)
- [dev.to: the purple gradient problem](https://dev.to/james_anderson_h/the-purple-gradient-problem-why-ai-ui-all-looks-alike-and-how-to-fix-it-3j65)

#### 9.13.3. `skills/design-ui/references/checklist.md`

- [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines)(MIT。`vercel-labs/agent-skills` の `skills/web-design-guidelines` 経由)
- [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)(MIT)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)(Apache-2.0)、`skill/reference/craft-floor.md`

#### 9.13.4. `skills/design-ui/references/native.md`

- [Apple Human Interface Guidelines: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)、[Typography](https://developer.apple.com/design/human-interface-guidelines/typography)、[Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)、[VoiceOver](https://developer.apple.com/design/human-interface-guidelines/voiceover)、[Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)、[Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars)、[Modality](https://developer.apple.com/design/human-interface-guidelines/modality)、[Sheets](https://developer.apple.com/design/human-interface-guidelines/sheets)、[Alerts](https://developer.apple.com/design/human-interface-guidelines/alerts)、[Privacy](https://developer.apple.com/design/human-interface-guidelines/privacy)、[Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)、[Playing haptics](https://developer.apple.com/design/human-interface-guidelines/playing-haptics)、[Virtual keyboards](https://developer.apple.com/design/human-interface-guidelines/virtual-keyboards)、[Offering help](https://developer.apple.com/design/human-interface-guidelines/offering-help)
- Material Design 3(developer.android.com での裏取り)。[Accessibility for apps](https://developer.android.com/guide/topics/ui/accessibility/apps)、[Use window size classes](https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes)、[Navigation bar](https://developer.android.com/develop/ui/compose/components/navigation-bar)、[Predictive back gesture](https://developer.android.com/guide/navigation/custom-back/predictive-back-gesture)、[Edge to edge](https://developer.android.com/develop/ui/views/layout/edge-to-edge)、[Tooltips](https://developer.android.com/develop/ui/compose/components/tooltip)、[Dynamic color](https://developer.android.com/develop/ui/views/theming/dynamic-colors)
- [Flutter: Platform adaptations](https://docs.flutter.dev/platform-integration/platform-adaptations)
- [React Native: Platform-specific code](https://reactnative.dev/docs/platform-specific-code)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)(Apache-2.0)、`skill/reference/ios.md`・`android.md`・`adapt.native.md`

#### 9.13.5. `skills/design-ui/references/text.md`

- [NN/g: Tooltip Guidelines](https://www.nngroup.com/articles/tooltip-guidelines/)
- [NN/g: Icon Usability](https://www.nngroup.com/articles/icon-usability/)
- [NN/g: Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)
- [NN/g: Error-Message Guidelines](https://www.nngroup.com/articles/error-message-guidelines/)
- [Apple Human Interface Guidelines: Offering help](https://developer.apple.com/design/human-interface-guidelines/offering-help)
- [Material Design 3: Tooltips](https://m3.material.io/components/tooltips)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)(Apache-2.0)、`skill/reference/clarify.md`
- [s0xDk/refactoring-ui-skill](https://github.com/s0xDk/refactoring-ui-skill)(MIT。原典 Wathan & Schoger, *Refactoring UI*)
- [anthropics/skills frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design)(Apache-2.0)

### 9.14. pstack(develop・ponytail・build・recover・retro・agents・respond)

次の箇所は cursor/plugins の pstack(MIT ライセンス、Copyright (c) 2026 Lauren Tan、https://github.com/cursor/plugins)0.15.36(2026-10-28 時点のコミット 1ba91fc)を元にする。パスは上流のリポジトリ内のものである。specify の出典は 9.2 にある。

- ponytail 5. のテストの判定、`agents/reviewer.md` のテストの観点、`agents/implementer.md` の進め方 2: `pstack/skills/principle-test-behavior-not-implementation/SKILL.md`
- ponytail 2. の状態の正当性の問い: `pstack/skills/principle-fix-root-causes/SKILL.md`
- recover 2.3 の再実行される操作: `pstack/skills/principle-make-operations-idempotent/SKILL.md`
- develop 6. の手順 4 の前提の書き出し: `pstack/skills/principle-attack-the-premise/SKILL.md`
- `agents/planner.md` の未確定事項、develop 5.、build の要判断の節の判断依頼の形: `pstack/skills/ketchup/SKILL.md`
- develop 6. の推論の強さ: `pstack/skills/poteto-mode/SKILL.md` の「Match the model to the job」
- README 6.2 と retro 5.6 の規則を考えで書くこと: 上流が 4 つの原則を書き直したコミット e5136d8・99743e9(2026-10-15)
- ponytail 6. の原則の索引、ponytail 4. と agents 4 本の原則の行、`agents/reviewer.md`・`agents/gate-reviewer.md` の名指しの点検: `pstack/skills/poteto-mode/SKILL.md` の「Non-negotiables」と「Principles」
- ponytail 3. の決定の集約: `pstack/skills/principle-laziness-protocol/SKILL.md`
- ponytail 3. の素通しの層・`agents/reviewer.md` の簡潔さの 30 秒の問い: `pstack/skills/principle-minimize-reader-load/SKILL.md`
- ponytail 3. の仕様を超える検証の規則・`agents/planner.md` の進め方 3 の削除の順: `pstack/skills/principle-subtract-before-you-add/SKILL.md`
- ponytail 3. の旧 API の削除: `pstack/skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md`
- ponytail 3. の境界の内側の検証・`skills/ponytail/references/design.md` 2.3: `pstack/skills/principle-boundary-discipline/SKILL.md`
- `skills/develop/references/requirements.md` の目的の行の利用者・`skills/develop/references/git-flow.md` の PR 本文の冒頭: `pstack/skills/principle-experience-first/SKILL.md`
- `agents/planner.md` の変更の種類ごとの実物・`agents/implementer.md` の進め方 3 の観測の方法: `pstack/skills/principle-prove-it-works/SKILL.md`
- `agents/planner.md` の進め方 3 の並べ方の型: `pstack/skills/principle-sequence-verifiable-units/SKILL.md`
- develop 6. の手順 2 の大きな出力: `pstack/skills/principle-guard-the-context-window/SKILL.md`
- develop 5. と `agents/planner.md` の事実の範囲(試作・計測): `pstack/skills/poteto-mode/SKILL.md` の「Non-negotiables」
- ponytail 3. の一括の作業のスクリプト・`agents/planner.md` の再実行できる検査・retro 3. の収集のスクリプトの理由: `pstack/skills/principle-build-the-lever/SKILL.md`
- `agents/implementer.md` の進め方 2 の実装前の失敗の確認と報告の実装前の行: `pstack/skills/tdd/SKILL.md`
- ponytail 3. の残してよいコメントと抑止コメント・`agents/reviewer.md` の簡潔さのコメントの点検: `pstack/skills/no-comments/SKILL.md`・`pstack/agents/comment-sicko.md`
- ponytail 3. の検証スクリプトの工程のコメント: `pstack/skills/poteto-mode/SKILL.md` の「Comments」
- `skills/ponytail/references/design.md` 2.1・ponytail 3. の抽象化に数えない構造・`agents/reviewer.md` の簡潔さの 2 つの兆候: `pstack/skills/principle-model-the-domain/SKILL.md`
- `skills/ponytail/references/design.md` 2.2: `pstack/skills/principle-type-system-discipline/SKILL.md`
- `skills/ponytail/references/design.md` 2.4: `pstack/skills/principle-separate-before-serializing-shared-state/SKILL.md`
- `skills/ponytail/references/design.md` 3.・`agents/planner.md` の進め方 2 の呼び出し側の使い方と 2 案・`agents/reviewer.md` の簡潔さの赤信号・`agents/implementer.md` の進め方 3 の回避策で止まる条件・develop 6. の手順 4 の設計を捨てる条件: `pstack/skills/architect/SKILL.md`・`pstack/skills/architect/references/design-red-flags.md`・`pstack/skills/poteto-mode/SKILL.md` の「Code crossing a function boundary」の行
- `agents/planner.md` の進め方 2 のデータの形・ponytail 3. の足場の区別: `pstack/skills/principle-foundational-thinking/SKILL.md`・`pstack/skills/poteto-mode/SKILL.md` の「Any code」の行
- `agents/planner.md` の進め方 2 の最初からあったらの問い: `pstack/skills/principle-redesign-from-first-principles/SKILL.md`
- `agents/planner.md` の進め方 3 の移行の例外・`agents/gate-reviewer.md` のテストの観点: `pstack/skills/principle-outcome-oriented-execution/SKILL.md`
- `agents/planner.md` の出力形式の順序の節: `pstack/skills/poteto-mode/playbooks/feature.md` の手順 3
- respond 3.15: `pstack/skills/poteto-mode/SKILL.md` の「Autonomy」の「No is an acceptable answer」
- respond 4. の 2 のデプロイと他者へ送るメッセージ: `pstack/skills/poteto-mode/SKILL.md` の「Autonomy」の「Always pause」
- respond 3.9 の未決の判断とトレードオフ・3.11 のラベルと読み手に頼まない確認・3.14 の完全な URL・5. の冒頭: `pstack/skills/poteto-mode/SKILL.md` の「Writing the reply」
- respond 3.11 の見つからなかった事項: `pstack/docs/guide/03-understand.md`
- respond 4. の 7: `pstack/skills/bro/SKILL.md`
