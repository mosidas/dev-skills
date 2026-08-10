# D-015: 参照を常時と条件付きに分け、100 行超の参照に目次を付ける(2026-08-10)

## 背景

[Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) は、`SKILL.md` 本体を 500 行以下に保つこと、毎回は必要でない内容を参照ファイルへ移すこと、100 行を超える参照ファイルに目次を付けることを求める。

測定の結果(`../notes/2026-08-10-engineering-lenses.md` P-1・P-3)、本体はいずれも 500 行を大きく下回るが、「参照(必読)」が挙げるファイルを合わせた読み込み量は dev-implement で 1,036 行(本体 156 行 + 必読 13 ファイル 880 行)になる。参照ファイルへ移しても「必読」と書けば毎回読まれるため、移した効果が出ていない。`principles.md` 3.「必要分だけ読む」とも矛盾する。

実際には全参照が全実行で必要になるわけではない。dev-implement の `source-driven.md` は外部ライブラリの API を使うときだけ、`durable-info.md` は恒久情報へ反映する判断が生じたときだけ、`review-perspectives.md` は最終検証パネルの観点を選ぶときだけ必要になる。

100 行を超える参照ファイルは 6 件あり、いずれも目次を持たない。

## 決定

- 各部品の参照節を **常時参照** と **条件付き参照** に分ける。分類の基準は、常時参照が「その部品のどの実行経路でも読む必要があるもの」、条件付き参照が「特定の分岐でだけ読むもの」とする。条件付き参照には発火条件を 1 行で書く。
- **必読の参照が別ファイルの必読を要求する連鎖を作らない**。現状は満たしている(`dev-core/references/`・`dev-core/templates/` に他ファイルを必読として要求する記述は無い)ため、規律の明文化のみを行う。
- **100 行を超える参照ファイルに目次(見出しの一覧)を付ける**。閾値は上記の出典に合わせて 100 行とする。

## 却下した選択肢

- **参照ファイルを統合して数を減らす**: 参照は複数の部品が共有する正本であり、統合すると部品ごとに不要な内容まで含む正本になる。レイヤー 0 に共通のリファレンス群を置く構成(D-000 2.1)と逆行する。
- **「必読」の表記のまま量だけ削る**: どの参照が必要かは実行経路で決まるため、量を削ると経路によっては必要な参照が失われる。条件を書くほうが情報を保てる。
- **目次を付けず、参照ファイルを 100 行以下へ分割する**: ファイル数が増え、各部品の参照の数も増える。目次は 5〜10 行で済み、分割より読み込み量の増分が小さい。
- **`writing`・`authoring` グループの参照ファイルを目次の対象から外す**: 目次は見出しの一覧であり、両スキルが定める規範の内容を変えない。同じ規約を適用しない理由がない。

## 帰結

- `dev-spec`・`dev-decompose`・`dev-implement`・`dev-release`・`dev-check` の参照節を常時参照と条件付き参照に分け、条件付き参照に発火条件を書いた。
- `../../dev/skills/dev-core/references/git-convention.md`・`../../dev/skills/dev-core/references/review-perspectives.md`・`../../authoring/skills/skill-authoring/references/glossary.md`・`../../writing/skills/japanese-writing/references/sentence.md`・`../../writing/skills/japanese-writing/references/inspection.md`・`../../writing/skills/japanese-writing/references/composition.md` に目次を追加した。
- `../../dev/skills/dev-core/references/principles.md` 3. に、参照節の書式(常時 / 条件付きの分割・必読の連鎖の禁止)と目次の閾値を追加した。

## 再検討条件

条件付き参照の条件判定を誤り、必要な参照を読まないまま作業が進んだ事例が観測された場合(その参照を常時参照へ戻す)。または Skill authoring best practices が閾値・方針を改めた場合。
