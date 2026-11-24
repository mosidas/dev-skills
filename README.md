# dev-skills

Claude Code のプラグインである。開発作業で使うスキルとサブエージェントを提供し、セッション開始時に respond を注入し、日本語 Markdown を書き込むたびに検査し、コミットと PR 本文のセッション URL を拒否し、本人への質問をまとめたフォームを出す前に止める hooks も提供する。gate-reviewer の判定を記録し、`gh pr merge` の前にゲートの記録と照合する hook もある。応答の最後の「次:」の行が記号で名付けた案を選ばせるときに完了を止める hook もある。

## 1. 提供するもの

| 構成要素 | 種別 | 役割 |
| :-- | :-- | :-- |
| `develop` | スキル | 実装タスクを要件の確認から計画・実装・点検・PR・CI の確認まで進める統括の手順 |
| `specify` | スキル | 曖昧な着想を本人との対話で聞き出し、build がタスクに分解できる PRD(製品要求仕様書)に書く手順 |
| `interview` | スキル | 着手の前に本人から「何を作るか」「誰に何を判断してもらうか」を 1 問ずつ聞き出す聞き方と問いの型 |
| `build` | スキル | PRD から起こした複数のタスクを develop で 1 つずつ PR まで進める外側のループ |
| `retro` | スキル | 本人とレビューの指摘の原因を判定し、dev-skills の改善タスクを起票する手順 |
| `explain` | スキル | コードを変えずに読み取りだけで調べ、仕組み・経緯・学び・再開の問いに答える手順 |
| `verify` | スキル | 実アプリを利用者と同じ経路で動かして証拠を取る手引き `docs/verify/` を、対象リポジトリに生成して保守する手順 |
| `planner`・`implementer`・`reviewer`・`gate-reviewer` | サブエージェント(`agents/`) | develop が起動する 4 つの役割(計画・ステップの実装・ステップの点検・push 前のブランチ全体の点検) |
| `ponytail` | スキル | そもそも作るかを問い、既存のものを先に使い、動く最小の差分で終えるコードの規範 |
| `secure` | スキル | プロダクト品質のコードで、安全のために何を対策すれば十分かを定める規範 |
| `observe` | スキル | プロダクト品質のコードで、何を計装すれば十分に観測できるかを定める可観測性の規範 |
| `recover` | スキル | プロダクト品質のコードで、失敗したときの挙動として何を決めれば十分かを定める規範 |
| `write-doc` | スキル | 日本語の開発文書・技術文書を書く・推敲する・リライトするときの規範 |
| `write-slide` | スキル | プレゼン資料・説明資料のスライド構成を作る・点検するときの入口 |
| `write-message` | スキル | 他者へ送る短い日本語メッセージを敬語で書く・直すときの規範 |
| `respond` | スキル | 会話の応答を、読み手が行動できる形に組み立てる規範 |
| `draw-diagram` | スキル | 説明のための図を、`.mmd` で構造を固めてから SVG に描く作図の規範 |
| `write-page` | スキル | HTML で配布する 1 ページの説明資料を作る・直すときの入口 |
| `design-ui` | スキル | 画面・コンポーネント・ページを設計・実装する規範と、実装の前に UI モックを本人と往復して作る工程 |
| `hooks/inject_respond.py` | hook(SessionStart) | セッション開始時に `skills/respond/SKILL.md` の本文を注入する |
| `hooks/guard_session_url.py` | hook(PreToolUse) | コミットと PR 本文に入るセッション URL を実行前に止める |
| `hooks/guard_ask_one_question.py` | hook(PreToolUse) | 本人への質問を 2 問以上まとめた AskUserQuestion を、フォームを出す前に止める |
| `hooks/inspect_write.py` | hook(PostToolUse) | 日本語 Markdown の書き込み直後に `lint.py` を実行し、検出があれば書き直しを促す警告を、見出しが 10 を超える文書では推敲の分担の通知を返す(通知は同じファイルに対して状態ファイルが削除されるまで初回だけ出す。Stop は重大カテゴリの検出が残っていない完了のときに状態ファイルを削除するので、通常は 1 回の応答につき初回だけになる。検出が残ったままブロックの上限に達すると、重大カテゴリの検出がすべて解消された完了(状態ファイルの削除)まで再び出ない) |
| `hooks/inspect_stop.py` | hook(Stop) | セッション完了時に再検査し、重大カテゴリの検出が残るあいだ完了を差し戻す |
| `hooks/guard_next_line.py` | hook(Stop) | 応答の最後の「次:」の行が記号で名付けた案を選ばせていれば完了を止め、選択肢ごとに中身を書いた「次:」の行への書き直しを求める |
| `hooks/merge_gate.py` | hook(PreToolUse・PostToolUse・SubagentStop) | gate-reviewer の判定を記録し、`gh pr merge` の前に PR の head と本文を記録と照合する |

スキルは Claude Code が用途を判断して自動で読み込む。`/dev-skills:<スキル名>` で明示的に呼んでもよい。サブエージェントは `dev-skills:planner` のように plugin 名つきで起動する。respond は SessionStart hook が常時適用する。hooks に呼び出しの操作はない。プラグインを有効にしたセッションでは、次のときに自動で発火する。

- セッション開始
- `git commit`・`gh pr create`・`gh pr edit`・`gh pr merge` の実行前
- AskUserQuestion の実行前
- gate-reviewer の報告の受け取り
- 日本語 Markdown の書き込み
- セッション完了

依頼は次のように書く。統括は依頼を要件の 4 行にまとめて確認する。4 行の形式は `skills/develop/references/requirements.md` にある。

- 目標と確かめ方を自分の言葉で書く。確かめ方は合否が付く形(実行するコマンド・見る値・開く画面)にする。「良くして」には合否が付かない。
- 見たい証拠を書く(コマンドの出力・画面の撮影・変更の前後の数値)。書かないとビルドが通ったという報告だけで終わることがある。
- 既に知っていることと制約を書く。症状・再現の手順・ログの行・リンクは調べ直しを減らす。「先に再現する」「コードはまだ変えない」「挙動を変えない」のような制約は工程を変える。
- どう作るかと原因の仮説は最初に書かない。仮説を書くと調べる範囲がそこに狭まる。仮説は統括が 4 行と期待する最小の変更を示した後で伝える。
- スキル名を並べて手順を指図しない。工程の順序は develop が持つ。スキル名は特定の判断を変えたいときだけ書く。
- 話題を変えたら「新しいタスク」と書く。書かないと前のタスクの続きとして扱われることがある。

本人は原則の名前で軌道修正を指示でき、名前の一覧・適用する場面・規則の所在は ponytail 6.(原則の索引)にある。

## 2. 前提

- `uv` が使えること。`lint.py` は形態素解析に sudachipy を使い、依存は `uv run` がスクリプト先頭の宣言から解決する。`uv` が無い環境では hooks は検査を行わず、スキルは規範に沿って目視で点検する。
- `semantic.py`(文埋め込みで話題の平板さを検出する opt-in の検出器)だけは torch と sentence-transformers に依存し、初めて実行するときにモデル約 1GB をダウンロードする。hooks からは呼ばない。
- `draw-diagram` の `render.py` による PNG 出力は Google Chrome を必要とする(パスは環境変数 `CHROME_BIN` で変更できる)。Chrome が無い環境では `--png` を付けずに実行し、照合と検査だけを行う。Claude Code のサンドボックス内では Chrome が起動できないため、PNG 出力はサンドボックス外で実行する。`design-ui` の UI モックの撮影も `render.py` で Chrome を使い、撮れないときは PNG の代わりに mock.html のパスを示して往復を続ける。
- `build` の反復は `backlog`(Backlog.md の CLI)・`gh` と、`claude` を使う。

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

## 4. hooks

| hook | 発火 | 動作 |
| :-- | :-- | :-- |
| SessionStart(すべての source) | セッション開始時 | `skills/respond/SKILL.md` の本文を frontmatter を除いて注入する |
| PreToolUse(Bash) | `git commit`・`gh pr create`・`gh pr edit` の実行前 | セッション URL か `Claude-Session:` の行があれば exit 2 で止め、理由を 1 行で返す |
| PreToolUse(Bash) | `gh pr merge` の実行前 | PR の head と本文を gate-reviewer の判定の記録と照合する。記録どおりなら何も返さずに通し、ゲートの後に本文を変えたかコミットを追加したなら deny し、記録が無いか照合できなければ本人の確認(ask)を求める |
| PreToolUse(AskUserQuestion) | AskUserQuestion の実行前 | `questions` が 2 問以上なら deny し、1 問ずつ聞くよう理由を返す |
| PostToolUse(SubagentHandback) | gate-reviewer が SubagentHandback で報告を返した直後 | 報告の「## 判定」を読み、「マージ可」なら記録を書き、「差し戻し」なら同じ SHA の記録を削除する |
| PostToolUse(Write / Edit / MultiEdit / NotebookEdit) | 日本語 Markdown の書き込み直後 | `lint.py` を `--json` で実行し、検出があるか、`lint.py` が分担の通知を出したとき(見出しが 10 を超える文書)に警告を返す。通知は同じファイルに対して状態ファイルが削除されるまで初回だけ出す。Stop は重大カテゴリの検出が残っていない完了のときに状態ファイルを削除するので、通常は 1 回の応答につき初回だけになる。検出が残ったままブロックの上限に達すると、重大カテゴリの検出がすべて解消された完了(状態ファイルの削除)まで再び出ない。書き込みは取り消さない |
| Stop | セッション完了時 | そのセッションで検査したファイルを再検査し、重大カテゴリの検出が残るあいだ完了をブロックする |
| Stop | 応答の完了時 | 最後の「次:」の行が記号で名付けた案を選ばせていれば、1 ターンに 1 回だけ完了をブロックし、中身を書いた「次:」の行への書き直しを求める |
| SubagentStop(gate-reviewer) | gate-reviewer の終了時 | PostToolUse(SubagentHandback)と同じく判定を記録する。同じ判定を 2 回読んでも記録は 1 つである |

`guard_session_url.py`(PreToolUse(Bash))の対象は、`git commit`(`git -C <path> commit` を含む)・`gh pr create`・`gh pr edit` を含む Bash のコマンドである。`claude.ai/code/session_` の URL と `Claude-Session:` の行(大文字と小文字を区別しない)を、コマンド文字列全体と、`-F`・`--file`・`--body-file` で渡した本文ファイルから探す。相対パスは `cwd` から解決し、`-` は読まない。`Co-Authored-By` と `Generated with` の行は止めない。再利用するメッセージ(`--amend --no-edit`・`-C <commit>`)と、中身がコマンド文字列に現れない `--body "$(cat body.md)"`・`-m "$(cat msg.txt)"` は検査しない。

`guard_session_url.py` は、対象と判定したコマンドを、本文が読めないときや検査に失敗したときも止める(fail-closed)。同じコマンドで作ったファイルや `cd` のあとの相対パスも止まるため、先に作って絶対パスで渡す。

PreToolUse(AskUserQuestion)は、止めた直後に同じ内容で呼び直した 1 回だけを通す。ほかのプラグインの手順が複数の問いを 1 回で聞くと定めている場合のためである。止めた内容を一時ディレクトリに記録できないときや、記録を消せないときは、呼び直しも止める。入力を読めないときは止めずに通す。

`merge_gate.py` の照合は、ゲートの後の変更を判定の取り直しなしにマージすることを止める。対象は Bash のコマンドの中の `gh pr merge` である。PR は URL・番号・ブランチ名で指定するか、指定を省いて作業ツリーのブランチで決める。URL・`-R`・`GH_REPO` でリポジトリを示さない指定は、hook の `cwd` とコマンドの `cd`・`pushd` の行き先の作業ツリーで PR を引く。hook は `gh pr view` で PR の head・本文・コミットを取り、(リポジトリ, head) の記録と次のように照らす。

| 判定 | 条件 |
| :-- | :-- |
| 通す | 今の head に記録があり、PR の本文のハッシュ(行の全体が `🤖 Generated with [Claude Code](https://claude.com/claude-code)` の形の帰属の行を除く。絵文字は任意、リンク先は `https://claude.com/claude-code` か `https://claude.ai/code`)が記録と一致する |
| 通す(main の取り込み) | 記録の head から今の head までが、PR の base(通常は main)を競合なしで取り込んだマージコミットだけ(20 回まで)で、本文のハッシュが記録と一致する |
| deny(本文の変更) | 上の 2 つで本文のハッシュが記録と違う |
| deny(コミットの追加) | 今の head に記録が無く、PR の古いコミットに記録があり、その後が main の取り込みだけと確かめられない |
| ask(本人の確認) | 記録が無い、PR を特定できない(行き先を追えない `cd`・`$` を含む指定・シェルや起動役(`sh -c`・`xargs` など)に渡したマージなど)、URL・`-R`・`GH_REPO`・`GH_HOST` で示した host が github.com でない、`gh pr view` が失敗した、照合が途中で失敗した |

1 つのコマンドに複数のマージがあれば、deny > ask > 通すの強いほうにする。URL・`-R`・`GH_REPO`・`GH_HOST` で示した host が github.com でなければ `gh pr view` を走らせない。gh の認証情報をその host へ送らないためである。権限の確認に答える人がいない `claude -p`(build のループ)では ask は拒否になる。

記録は次のすべてが成り立つときだけ `${CLAUDE_PLUGIN_DATA}/merge-gate/` に保存する。

- 作業ツリーの HEAD が判定の SHA と一致する。
- origin が host/owner/name に直せる。
- 本文案が読める。

照合と記録の結果は同じディレクトリの `events.jsonl` に 1 行ずつ追記し、本文・報告の中身・origin の URL は書かない。

次は照合の範囲の外である。

- `gh api` でのマージ
- Web の画面からのマージ
- `--auto` を有効にした後の変更
- URL・`-R`・`GH_REPO`・`GH_HOST` の無いマージで gh が cwd の git remote から決める host
- 偽造(記録のファイルを直接書く・追跡 ref を書き換える・hook を避けて組んだコマンド)

`guard_next_line.py`(Stop)は、respond 3.2(最後の行に次の行動を 1 つ書く)の「次:」の行を検査する。検査するのは、コードフェンスの外にある最後の空でない行が「次:」で始まるときだけである。止めるのは「案 A」「B 案」「第 2 案」「(a) か (b)」のように記号で名付けた案を選ばせる形である。記号は前の本文を読んだ読み手にしか意味が通らないため、選択肢ごとに中身を書いた「次:」の行を返し直させる。インラインコード・URL・パス・ファイル名の中の記号と、「案 3 件」のように数の後に助数詞が続く語は止めない。

止めるのは 1 ターンに 1 回だけである。hook は Stop の入力の `stop_hook_active` が true なら検査せずに通し、止めた応答の書き直しを再び止めない。`stop_hook_active` はターン全体の値であり、ほかの Stop の hook が先に止めたターンでも true になる。そのため、`inspect_stop.py` などが先に止めたターンでは、書き直した応答の「次:」の行を検査しない。

入力が UTF-8 の JSON の dict として読めないときと、`last_assistant_message` が文字列でないときは、何も書かずに通す。hook の解析の失敗で止めると、すべての応答の完了が止まるためである。hook 自身が想定外の例外で終わるときは、exit 1 を返し標準エラーに例外の型名だけを書く。Claude Code は exit 2 以外の 0 でない終了をブロックしないエラーとして扱う。そのため、応答の完了は止まらない。

`inspect_write.py`(PostToolUse)と `inspect_stop.py`(Stop)は日本語文書の検査を行う。発火するのは、拡張子が `.md` / `.markdown` で、日本語文字が 30 文字以上あり、除外パターンに一致しないファイルへの書き込みに限る。警告には、検出の一覧、検出箇所を含む文をカテゴリ別の指針に従って直す指示(指針が残すとする文は残す)、語ごとの言い換え例、カテゴリ別の指針と、見出しが 10 を超える文書では分担の通知が入る。通知は同じファイルに対して状態ファイルが削除されるまで初回だけ出す。Stop は重大カテゴリの検出が残っていない完了のときに状態ファイルを削除するので、通常は 1 回の応答につき初回だけになる。検出が残ったままブロックの上限に達すると、重大カテゴリの検出がすべて解消された完了(状態ファイルの削除)まで再び出ない。

重大カテゴリとは、Stop が完了をブロックする検出カテゴリの宣言で、既定は `forbidden_phrase`(severity warn 以上。動詞カタログのうち空虚な動詞 4 語と、比喩語 5 語(`壊れる`・`静かに`・`黙って`・`沈黙`・`逃がす`))と `antithesis_repetition`(critical のみ)である。ブロックは既定 3 回で打ち切るため、解消できない検出があっても完了できない状態は続かない。

設定の正本は `hooks/inspection.config.json` である。利用側の変更は `.claude/write-doc-inspection.json` に同じキーで書く。浅い上書きなので、プラグインを更新しても残る。キーの一覧は `skills/write-doc/references/inspection.md` 3. にある。

次のいずれかに当たると、検査と注入の hooks と `guard_next_line.py` は書き込みと完了を止めずに素通しする。

- `uv` が無い、または `lint.py` を実行できない。
- lint がタイムアウトした、または異常終了した。
- 検査対象の条件(拡張子・日本語文字数・除外パターン・文書種別)を満たさない。
- `skills/respond/SKILL.md` が読めない(SessionStart は何も注入しない)。
- `guard_next_line.py` が Stop の入力を読めない、または想定外の例外で終了した。

検査が発火しているかは、カタログに登録した語を含む Markdown を書いて警告が返ることで確かめる。

## 5. 構成

```
.claude-plugin/   # Claude Code 向けのマニフェストと marketplace.json
skills/           # スキル(1 スキル 1 ディレクトリ。SKILL.md と references/・scripts/)
agents/           # develop が起動する 4 つのサブエージェント
hooks/            # hooks.json の配線・hook のスクリプト・検査の設定
tests/            # unittest の単体テストと境界値コーパス
evals/            # claude plugin eval のケース。結果の出力先 results/ は git 管理外
.github/          # CI・Dependabot・CODEOWNERS
lefthook.yml      # git hook(pre-commit: plugin validate、pre-push: unittest)
AGENTS.md         # このリポジトリで作業するエージェント向けの言語規約
LICENSE           # MIT ライセンスの全文
CREDITS.md        # 取り込んだ外部の資料の出典
```

## 6. 開発

### 6.1. プラグインの変更手順

テストは標準ライブラリの `unittest` だけで動く。lefthook の pre-push と GitHub Actions(`.github/workflows/ci.yml`)が同じコマンドを実行する。

```console
$ python3 -m unittest discover -s tests -t tests
```

プラグインの内容を変更したら、`.claude-plugin/plugin.json` の `version` を上げる。`claude plugin update` は version が同じだと最新と判定し、変更を取り込まない。

マニフェストの検査は次のコマンドで行う。

```console
$ claude plugin validate . --strict
```

### 6.2. スキルを書くときの規則

スキルの `SKILL.md` と `references/` のファイルを書くときは、次の規則に従う。

- 雛形は、コピーするとそのまま下書きになる形で提供する。節ごとの書き方の説明は各節の見出しの直下に HTML コメントで書き、使う人は、すべての節を書き終えてからコメントを削除する。write-doc の lint は HTML コメントを検査しないため、説明の文面は検出の対象にならない。例は `skills/specify/references/prd.md` である。
- 別のスキルの `SKILL.md` の節か `README.md` の節を番号で指すときは、その節をファイルの中で最初に指す箇所に、「develop 6.(実装と点検のループ)」のように節の見出しを並記する。節を追加・削除すると、番号は別の節を指す。見出しを並記しておくと、番号と見出しの食い違いを `tests/test_section_references.py` が検出する。読み手も、指す先を開かずにどの節を指すかが分かる。`references/` のファイルの節を指すときと、同じスキルの中の節を指すときは、並記しなくてよい。
- 上流の資料(yomiyasu など)にある条件付きの規則(文脈で言い換え先が変わる比喩動詞など)を write-doc へ取り込むときは、語ごとに、システム開発の文書で字義どおりの正当な用法があるかを確かめる。条件付きの規則は lint が検出しないため、正当な用法が無い語は `skills/write-doc/scripts/forbidden_phrases.json` に禁止語として登録し、lint で検出する。開発文書でも正当な用法と言い換えるべき用法の両方がある語(引き返す・契約・正本など)だけを、`skills/write-doc/references/sentence.md` に条件付きの規則として書く。上流の lint が前後の語・同じ文の語の条件で字義どおりの用法を外している語は、その条件を写した正規表現でカタログに登録する(書き方はカタログの `_comment`)。
- 上流の資料の出典は `CREDITS.md` の表に 1 行で書く。書く項目は表の列(出典・ライセンス・著作権者・版とコミット・反映先のスキル)である。スキルの `SKILL.md` と `references/` には書かない。CLI がスキルを読み込むたびに出典の文面もコンテキストに入るためである。`CREDITS.md` は帰属表示と上流の差分の起点である。文面の転載の扱いと取り込んだ範囲の追い方は `CREDITS.md` の前書きに書いた。
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

ケースを加える・直すときと結果を読むときは観測者効果を避ける。評価されていると分かったエージェントは普段と違う振る舞いをするためである。

- `prompt.md` の依頼文に評価の場と分かる語(「評価」「テスト」)を書かない。普段の依頼と同じ文面にする。
- llm の grader の PASS の条件にどのアームの出力かが分かる語(アームの名前・評価対象のモデル名)を書かない。採点者がどちらのアームの出力かを知ると採点が偏る。
- 採点の値だけで判断しない。各アームの出力を自分で読む。採点と読んだ結果が食い違うときは採点基準を先に疑う。

## 8. ライセンス

MIT ライセンスで公開する。全文は `LICENSE` にある。

## 9. 出典

取り込んだ資料の出典・ライセンス・著作権者・版は [CREDITS.md](CREDITS.md) にある。
