# evals の結果

`claude plugin eval` の実行結果を、新しい回を上にして 1 回ずつ記録する。ケースの内容と表の読み方は README の「7. 評価」にある。

## 2026-10-01(1 回目): 全ケース(claude plugin eval、Claude Code 2.1.284)

- 実行コマンド: `claude plugin eval . --trust-plugin --allow-tools Write Edit -j 4 --max-cost-usd 5 --no-publish`
- 規模: 18 回の実行(3 ケース × プラグインあり・なし × 3 回)、152 秒、$3.01
- 判定モデル: haiku(既定)
- 結果: `evals/results/2026-10-01T01-54-13-044Z/`(git 管理外)

### ケースごとのスコア

| ケース | あり | なし | Δ |
| :-- | --: | --: | --: |
| `respond-next-action` | 1.00 | 0.67 | **+0.33** |
| `write-doc-report` | 0.83 | 0.33 | **+0.50** |
| `one-liner-control` | 1.00 | 1.00 | 0 |

全体の overallScore は 0.94、meanDelta は +0.28 だった。exit code は 1 になった。`--threshold` の既定値 1.0 を下回るケースがあるためで、実行の失敗ではない。

### grader ごとの通過数

| ケース | grader | 判定 | あり | なし |
| :-- | :-- | :-- | :-- | :-- |
| `respond-next-action` | `action-first` | regex。返答が `git commit --amend` で始まるか | 3/3 | 0/3 |
| `respond-next-action` | `no-preamble` | regex。返答が相づち・前置きで始まっていないか | 3/3 | 3/3 |
| `respond-next-action` | `no-closing` | regex。返答が締めの定型句で終わっていないか | 3/3 | 3/3 |
| `write-doc-report` | `fired` | tool_used。Skill の呼び出しに write-doc があるか。arm 指定なしのため Δ に入らない | 3/3 | — |
| `write-doc-report` | `no-author-voice` | regex。`docs/report.md` に「筆者」「私は」などが無いか | 3/3 | 2/3 |
| `write-doc-report` | `reader-checked` | llm。最後の返答で読み手の仮定を明示したか | 2/3 | 0/3 |
| `one-liner-control` | `correct` | llm。`//` を床除算として正しく述べ、資料の形(想定読者の欄・理解度チェック・ファイルへの書き出し)をとっていないか | 3/3 | 3/3 |
| `one-liner-control` | `no-skill` | tool_used。Skill の呼び出しが 0 回か | 3/3 | 3/3 |
| `one-liner-control` | `short` | regex。返答が 1,000 文字以内か | 3/3 | 3/3 |

1 ケースを 3 回ずつしか実行していないため、差は傾向として読む。

### 読み方

`respond-next-action` の差は、すべて `action-first` から生じた。ありは 3 回とも、実行するコマンドから返答を始めた。なしは 3 回とも別の書き出しだった。regex の grader は返答の本文を結果に残さないため、なしが何から書き始めたかは記録に無い。`no-preamble` と `no-closing` は、なしも定型句を使わなかったため、この回は差を生んでいない。

`write-doc-report` の差は、`reader-checked` と `no-author-voice` から生じた。

- `reader-checked`: ありの 2 回は、返答で読み手の仮定を明示した。run2 は「読み手は社内のチームなど、経緯を知らない人と想定した」、run3 は「読み手: 経緯を知らない他者向けと想定した」と書いた。run1 は「自分で判断して置いた前提」を列挙したが、読み手には触れず、3 票とも FAIL だった。なしの 3 回は読み手に一切触れず、どれも「レポートを `docs/report.md` に書きました。結論は B 案の採用です」の形で始まった。
- `no-author-voice`: なしの 1 回が FAIL した。どの語に一致したかは結果に記録されない。
- 費用と手数: ありは 19〜23 ターンで 3 回分 $1.64、なしは 2〜3 ターンで $0.53 だった。ターンが増えたのは、規範の読み込みと lint の実行のためと考えられる。run1 の返答は lint の結果に触れている。トレースは残っていないため、ターンの内訳は確かめていない。

`one-liner-control` は対照ケースである。両アームとも全 grader を 3/3 で通過し、Skill の呼び出しはどちらも 0 回だった。1 文で済む質問にスキルが余計に発火していないことを、この回で確かめた。

### 本実行の前の試行で直した grader

本実行の前に、同じ日に 2 回試した。どちらの回でも grader の誤判定が見つかり、本実行の前に直した。

試行 1 は本実行のコマンドに `--runs 1` を付け、`--max-cost-usd` を 1 にして全ケースを実行した。全ケース 6 回の実行で、109 秒、$1.13 だった。費用の上限 $1 を超えたが、実行のスキップは無かった。ただし `write-doc-report` のありの `reader-checked` は、費用の上限のため判定されなかった。誤判定は次の 3 件である。

- `one-liner-control/correct`: 見出しと表を含む正しい答えを、「見出しの多い構成」として両アームとも FAIL にした。
- `one-liner-control/short`: 当時の上限 400 文字を、自然な正しい答え(あり 575 文字、なし 549 文字)が超えた。
- `respond-next-action/action-first`: 当時は llm の grader で、コードフェンスの直後に `git commit --amend …` を書いた正しい答えを 3 票とも FAIL にした。

同じ試行で、`respond-next-action` のなしは作業ディレクトリでリポジトリを探し、「コミットが無い」と答えた。これらを受けて、コミット e52e472 で 4 点を直した。`correct` の FAIL 条件を限定し、`short` の上限を 1,000 文字にし、`action-first` を regex に替えた。依頼文には「このセッションからはリポジトリに触れない。手元で実行するコマンドを教えてほしい」を追記した。

試行 2 は本実行のコマンドに `--tag cheap --runs 1` を付け、`--max-cost-usd` を 0.6 にして実行した。tag `cheap` の 2 ケースで、4 回の実行、$0.27 だった。`respond-next-action` はあり 1.00、なし 0.67 で、本実行と同じだった。`one-liner-control` はあり 0.67、なし 1.00 となった。`correct` が、ありの返答の末尾の 1 行「次: Python の REPL で `-7 // 2` と `int(-7 / 2)` を実行し、結果の違いを確かめる」を理解度チェックと読み、FAIL にしたためである。この行は respond スキルが定める次の行動の 1 行である。haiku に同じ基準と返答を渡して理由を出させ、この読み方を確認した。コミット 928f955 で、`correct` の基準に「次: 〜」の 1 行を FAIL の理由にしないと明記し、`action-first` の regex を行内コードと `$` 付きの書き出しにも広げた。

2 回の試行から得た教訓は、explainer の評価で得たものに近い。

- llm の grader は基準の読み方で誤判定するため、基準が固まったら regex に替える。
- 依頼文で grader の PASS 条件をそのまま指示しない。指示すると、Δ がスキルの効果でなく依頼文の効果になる。`write-doc-report` の初稿の依頼文は「仮定を返答に書け」と指示しており、コミット前のレビューで外した。

### 次に試すこと

- 各ケースをもう 1 回実行し、Δ が回をまたいで再現するかを確かめる。
- `respond-next-action` の `no-preamble` と `no-closing` は差を生んでいない。`--keep-temp` でなしの返答を確かめてから、pattern を見直す。
- `write-doc-report` の `reader-checked` は、ありでも 3 回中 1 回が FAIL した。非対話で実行したときに読み手の仮定を明示することを、write-doc の規範(`references/readers.md`)が定めているかを確かめる。スキル本文の改善は別のタスクで扱う。
- `no-author-voice` で一致した語を知るため、対象のファイルを結果に残す方法を調べる。
- `action-first` を regex に替えたため、コマンドの文言が正しいかは検査していない。
