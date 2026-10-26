---
name: write-page
description: HTML で配布する説明資料(図・表・切り替えの UI を持つ 1 ページの文書)を作る・直すときの規範と工程。本文は write-doc、図は draw-diagram、見た目は design-ui の閲読モードを参照し、HTML 固有の規則(表の列の並び、一覧の全件表示、操作と表示先の近接、表の面、折りたたみのラベル、行幅、図の幅)を write-doc の format/html.md から読み、本文・図・スクリプト・見た目の検査を定める。「HTML の資料を作って」「1 ページの説明資料にして」「ブラウザーで読める資料にして」「HTML で配布したい」と言われたとき、Markdown の文書を HTML の資料に組み替えるときに使う。アプリの画面は design-ui、Markdown の文書は write-doc、スライドは write-slide が扱う。
---

# HTML の説明資料の規範

## 1. 適用範囲

- 適用範囲は、HTML で配布する説明資料である。図・表・切り替えの UI(タブ・折りたたみ)を持ち、読み手がブラウザーで読む 1 ページの文書を指す。
- 次のものは対象外とする。
  - アプリの画面・フォーム・ダッシュボード。design-ui が扱う。
  - Markdown で配布する文書。write-doc が扱う。
  - スライド・プレゼン資料。write-slide が扱う。
  - 図だけの HTML 閲覧ページ。draw-diagram の `references/svg.md` 8. が扱う。
- HTML の資料は、文書であると同時に Web のページである。文書として扱って見た目を後回しにすると、実装の後に見た目の直しを何度も受ける。ページとして扱って本文を後回しにすると、推敲と検査が抜ける。本スキルは両方の工程を 1 つにまとめる。規則の正本は write-doc の references にあり、本スキルは読むファイルと HTML 固有の工程だけを定める。

## 2. 読むファイル

次の順に読む。

| ファイル | 扱う規範 | 読むとき |
| :-- | :-- | :-- |
| `../write-doc/references/process.md` | 工程の一覧、着手時の brief、骨組みの合意、疑問の一覧、肉付けの規則、レビュー役に渡す物、指摘を受けた後 | 書き始める前と、工程を進めるとき |
| `../write-doc/references/format/html.md` | 折りたたみのラベル、HTML の資料の規則(表の列の並び、一覧の全件表示、操作と表示先の近接、折りたたみの有無、表の面、行幅、図の幅、タブと節の対応、中間ファイルの参照) | 構成を決めるときと、HTML を生成するとき |
| `../write-doc/references/sentence.md` | 語の選び方、文の組み立て、動詞と語彙、事実・意見・確信度、翻訳調、表記、記号、出典 | 本文を書くとき |
| `../write-doc/references/paragraph.md` | 段落、論証、構成、接地と省略、見出し、表と図 | 節の役割を決めるときと、本文を組むとき |
| `../write-doc/references/inspection.md` | 検査スクリプト、検出への対応(文書ごとの確かめ)、別のエージェントによるレビュー | 書いた後に点検するとき |

## 3. HTML 固有の工程

- モックの往復: 骨組みの合意(`process.md` 3.)で節の表ができたら、ページの構成のモックを作り、本人と往復する。往復の形は design-ui の `../design-ui/references/session.md` の 3.1(案 1 つ・前回からの差分・質問 1 つ・往復の番号)、3.2(見せ方)、3.5(3 往復まで)に従う。3.1 の文言の表と brief は使わない。往復の記録は節の表の下に書き、合意した構成を節の表に書き足す。
- モックに入れるのは、節の並び、図と表の位置、切り替えの UI(タブ・折りたたみ)の有無と位置、本文の行幅である。本文はダミーでよい。切り替えの UI は、モックでも JavaScript で動かしてよい(session.md 3.3 の「JavaScript を使わない」は適用しない)。モックの撮影は、後述の見た目の検査と同じ手順で行う。
- 本文: 節ごとに Markdown で書き、`../write-doc/references/process.md` と `../write-doc/references/inspection.md` に従って書き、検査する。検査では、節ごとの Markdown に `../write-doc/scripts/lint.py` を実行し、`../write-doc/references/inspection.md` 4. の段落ごとの確かめ(新しく作る資料でも行う)と文書ごとの確かめを行う。HTML に直接書かない。HTML に直接書くと、lint が本文を読めない。
- 図: `../draw-diagram/SKILL.md` の工程に従い、`.mmd` と SVG の対で作る。図の寸法は、ページの本文の幅で横スクロールを出さない値にする(`../draw-diagram/references/svg.md` 1.)。表は Markdown の表で書く。
- HTML の生成: 本文の Markdown と図の SVG から HTML を組み立てるスクリプトを書く。スクリプトは、本文を変えたときに再実行できる形にし、HTML を手で直さない。
  - 見た目は design-ui の閲読モード(`../design-ui/SKILL.md` 2.)に従う。トークンは `../design-ui/SKILL.md` 4. のスケールから選び、`../design-ui/references/anti-ai.md` と照合する。トークンには、本文の背景と別に、表と折りたたみの面の色を 1 つ持つ(`format/html.md` 2. の表の面)。
  - CSS はインラインで書き、外部の資源(CDN・Web フォント)を読み込まない。配布先でネットワークが無くても読めるようにする。
  - SVG は HTML にインラインで埋め込む。複数の図を埋め込むときは、`../draw-diagram/references/svg.md` 8. の接頭辞の規則(id と class に図ごとの接頭辞を付け、要素型セレクタと `:root` を使わない)に従う。svg.md 8. の雛形の HTML は使わず、本スキルの生成スクリプトで代える。
  - JavaScript は、切り替えの UI(タブ・折りたたみ)に限って使う。本文の表示に JavaScript を要求しない。JavaScript が動かない環境でも、すべての本文と図が縦に並んで読める形にする。
- 図の検査: `../draw-diagram/scripts/render.py` で `.mmd` と SVG の対応を照合する。
- スクリプトの検査: 生成スクリプトを `node --check <script>`(Node.js)か `python3 -m py_compile <script>`(Python)で構文検査する。生成した HTML の `<script>` の中身も、ファイルに抜き出して `node --check` にかける。生成スクリプトが通っても、埋め込んだ JavaScript の構文誤りは検出されない。
- 切り替えの UI の検査: JavaScript を無効にした表示(全本文と図が縦に並ぶ形)を撮り、すべての節・表・図があることを確かめる。headless の撮影ではタブを押せないため、タブごとの表示は、本人に見せる前に統括がブラウザーで開き、各タブを順に押して表示先が変わることを確かめる。ブラウザーを開けない環境では、その旨を本人に伝える。
- 見た目の検査: `../design-ui/references/session.md` 3.4. の手順で、生成した HTML を frames.html の iframe(幅 1280 と幅 390)に入れ、`render.py` の `screenshot()` でウィンドウ幅 1700 で 1 枚に撮る。headless Chrome はウィンドウを 500px 未満に縮めないため、幅 390 を直接は撮れない。高さは、ページ全体が入る値を引数で渡し、PNG の下端で本文が切れていたら上げて撮り直す。Claude Code では統括が Read で PNG を開いて点検し、画像を表示できない CLI では PNG のパスを示して本人に確かめてもらう。見るのは、横スクロール、図の縮小による文字の潰れ、表の面と背景の区別、切り替えの UI と表示先の位置である。design-ui の `../design-ui/SKILL.md` 3. の 5 と同じく、1 巡の確認、見つかった欠陥の一括修正、確認の 1 巡で止める。
- 別のエージェントによるレビュー: `process.md` 6. の物に加えて、生成した HTML、PNG、`../write-doc/references/format/html.md` を渡す。

## 4. 他スキルとの関係

| 規範 | 参照する範囲 | 参照しない範囲 |
| :-- | :-- | :-- |
| `../draw-diagram/` | 図の判断・工程・`.mmd`・SVG・`render.py`(SKILL.md と references の全部)。`references/svg.md` 8. は接頭辞の規則を参照する | `references/svg.md` 8. の雛形の HTML(本スキルの生成スクリプトで代える) |
| `../design-ui/` | 閲読モード(SKILL.md 2.)、スケール(4.)、階層と強調(5.)、構造は情報(6.)、`references/anti-ai.md`、`references/checklist.md` の共通と Web の節、`references/session.md` 3.1・3.2・3.4・3.5 | 操作・説得・体験のモード、`references/text.md`(利用者向けの敬体の文言。資料の本文は write-doc の常体)、`references/native.md`、`references/brief.md`、`references/session.md` 3.3 |

- 資料の中に画面のモックを載せるときも、モックの作り方は design-ui に従う。
- 往復での指摘は、retro の「本人の指摘」に含めない(`../design-ui/references/session.md` 6.)。実装の後に受けた見た目の指摘は含める。
