# D-033: タスク間のインターフェースを分解で明示し、スキルの記述に形式の選択と検証を課す(2026-08-22)

## 背景

home/035 の調査(obra/superpowers)で採用と判断した要素のうち、文書生成側の 2 件を反映する。D-031 が実装ループの消費量、D-032 がデバッグとレビューの規律を扱ったのに続く 3 本目である。

`../../dev/skills/dev-implement/SKILL.md` 2. は、実装者が読む範囲をタスク固有情報と仕様の参照先に限る。この限定は判断のドリフトを抑えるが、隣接するタスクが使う名前と型を実装者が知る経路も同時に断つ。`../../dev/skills/dev-decompose/SKILL.md` は `_Depends:` で依存の有無を示すものの、共有するシグネチャを書く欄を持たない。Step 4 の「契約先行」(並行タスクが共有する契約を確定するタスクを先行依存に置く)は順序の規定であり、確定した契約を後続タスクへ渡す記述場所を定めていない。

プロジェクト全体に掛かる制約(言語・ランタイムのバージョンの下限、依存の制限、命名と表記の規則、プラットフォーム要件)は spec.md にあるが、実装者は spec.md のうち自分の要件 ID と該当節しか読まない。全体制約は要件 ID を持たないため、参照の対象から外れる。

`../../authoring/skills/skill-authoring/SKILL.md` は設計規範(predictability・invocation・information hierarchy・pruning・leading word・失敗モード)を定めるが、書いた記述が効いているかを確かめる手順を持たない。失敗モード negation は「禁止による操縦は裏目に出る」と一律に述べるが、superpowers の writing-skills は、規律違反(規則を知っていて圧力下で破る)に対しては禁止と反駁表が正しい形であり、出力の形の崩れに対してのみ禁止が逆効果になる(実測で無指示の対照群より悪い)と型を分ける。

## 決定

- **タスク固有情報に `_Interfaces:` を加える**。Consumes(先行タスクから使う名前と型)と Produces(後続タスクが依存する関数名・引数と戻り値の型)を書く。`_Depends:` を持つタスクと `(P)` のタスクに書き、共有が無いタスクには書かない。記法は `../../dev/skills/dev-core/references/notation.md` の注記表を正本とする。
- **`_Interfaces:` の整合を内蔵ゲートで見る**。先行タスクの Produces と後続タスクの Consumes が名前・引数・戻り値の型で一致するかを、dev-decompose Step 6 の種別固有チェックに加える。片方にしか現れないシグネチャは、どちらかの記述の誤りとして扱う。
- **tasks.md に `## Global Constraints` を置く**。spec.md の全体制約を逐語で写し、要約・言い換えをしない。全タスクの要件に暗黙に含まれるものとし、実装者とレビュアーの双方へ渡す。
- **skill-authoring に「形式の選択」を置く**。観測した失敗を 4 つの型(規律違反・出力の形の崩れ・要素の欠落・条件依存)へ分類し、型ごとに採る形式と裏目に出る形式を対応づける。失敗モード negation から本節へ参照を張る。
- **skill-authoring に「検証」を置く**。ベースライン取得(スキル無しで失敗を誘う課題を実行させ、言い分を逐語で記録する。対照群が失敗を示さないなら書かない)・記述・再検証の順序と、文言のマイクロテスト(実際に置かれる文脈を与える・記述なしの対照群を必ず置く・5 回以上反復する・一致箇所を目視で読む・ばらつきを指標にする)を定める。

## 却下した選択肢

- **`_Interfaces:` を `check.py` の機械検査へ入れる**: シグネチャの一致は文字列の比較では判定できない(引数名の別名・型の別表記・言語ごとの記法が同じ意味を持つ)。機械検査に載せると、正しい記述を error にするか、無意味に緩い一致で通すかのどちらかになる。意味の判定を要するため内蔵ゲート(dev-reviewer)へ置いた。
- **`_Interfaces:` を全タスクに必須とする**: 共有の無いタスクに空欄を書かせることになり、記入欄が形骸化する。`check.py` のタスク固有情報の検査にも加えない(必須項目にすると既存の tasks.md が一斉に warning になる)。
- **全体制約を各タスクの `_Requirements:` へ展開する**: 要件 ID は spec.md の受け入れ基準に対応する識別子であり、ID を持たない全体制約に割り当てると、前方・後方トレースの検査が壊れる。
- **全体制約を知識 port で渡す**: port はプロジェクトを跨いで再利用する知識の置き場であり(`../../dev/skills/dev-core/references/ports.md`)、単一の作業単位に閉じる制約の置き場ではない。port へ入れると作業単位の終了後も残る。
- **skill-authoring の negation を書き換える**: negation の記述自体は誤っていない(肯定でプロンプトする既定は維持する)。型による分岐は追加であり、置き換えではない。既存の記述を残したまま 9. への参照を足した。
- **検証手順を独立したスキルへ切り出す**: skill-authoring を読む場面と検証する場面が同じであり、`../../authoring/skills/skill-authoring/SKILL.md` 5. の分割の判断(独立した発火の必要がない切断は payoff が無い)に照らして切らない。

## 帰結

- `../../dev/skills/dev-core/references/notation.md` の注記表へ `_Interfaces:` を追加した。
- `../../dev/skills/dev-decompose/SKILL.md` の Step 2 へ Global Constraints の写しを、Step 3 のタスク固有情報へ `_Interfaces:` を、Step 6 の種別固有チェックへ 2 行(Produces と Consumes の一致、Global Constraints の逐語性)を追加した。description も更新した。
- `../../dev/skills/dev-decompose/templates/tasks-template.md` に `## Global Constraints` の節と `_Interfaces:` の記入例、注記表の行、ルールの 1 行を追加した。
- `../../dev/skills/dev-implement/templates/implementer-prompt.md`・`../../dev/skills/dev-implement/templates/reviewer-prompt.md` に `<global_constraints>` タグと `<task>` のインターフェース欄を追加した。`../../dev/skills/dev-implement/SKILL.md` 9. の受け渡しの記述を追随させた。
- `../../authoring/skills/skill-authoring/SKILL.md` に 9.(形式の選択)と 10.(検証)を新設し、旧 9.(用語集)を 11. へ繰り下げ、8. の negation から 9. への参照を張り、description を更新した。

## 再検討条件

netdiver の次の作業単位で、`_Interfaces:` を書いたタスクの実装が隣接タスクの名前と型を取り違える事例が続く場合(記述場所ではなく渡し方の問題であるため、実装者へ先行タスクの差分を渡す形を検討する)。または `## Global Constraints` が空の作業単位が続く場合(spec.md が全体制約を持たない構造であるため、写す先ではなく spec.md 側の節構成を見直す)。
