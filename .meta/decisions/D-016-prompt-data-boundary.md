# D-016: サブエージェント・プロンプトで指示とデータを構造で区別する(2026-08-10)

## 背景

[Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) は、内容種別ごとにタグで括って指示・データ・例の混同を防ぐことを求める。

サブエージェント・プロンプトの雛形 4 本は Markdown の見出しで構成し、差し込む値を `<...>` のプレースホルダで本文へ直接埋める(`../notes/2026-08-10-engineering-lenses.md` P-4)。差し込む値には外部由来の文字列が含まれる。

| 雛形 | 外部由来の差し込み値 |
| ---- | -------------------- |
| implementer-prompt | タスク説明、`## Implementation Notes` の内容、注入知識のパス列 |
| reviewer-prompt | タスク説明、実装者の `OUT_OF_BOUNDARY` 申告、注入知識のパス列 |
| debugger-prompt | 実装者の `BLOCKER`、レビュアーの `FINDINGS`、検証エラー・CI 失敗ログの要点 |
| final-review-prompt | 注入知識のパス列、ベースコミット指定 |

間接プロンプトインジェクション耐性は各雛形の制約節が文章で課しているが、境界を構造で示す手当てが無い。差し込んだ文字列が見出しを含めば、指示の側に混ざる。

## 決定

- 差し込む値を **XML タグで括る**。タグ名は内容種別で付け、雛形ごとに次のとおりとする。

| 雛形 | タグ |
| ---- | ---- |
| implementer-prompt | `task`(タスク固有情報)・`spec_refs`(仕様の参照先)・`injected_knowledge`(注入知識のパス列)・`implementation_notes`(これまでの学習)・`verify_commands`(検証コマンド) |
| reviewer-prompt | `task`・`out_of_boundary`(実装者の境界外変更の申告)・`test_changes`(実装者のテスト変更の申告。D-021)・`spec_refs`・`injected_knowledge` |
| debugger-prompt | `situation`(タスクと起動理由)・`attempts`(これまでの試行と結果)・`spec_refs`・`verify_commands` |
| final-review-prompt | `target`(対象と成果物の所在)・`aspect`(担当観点と観点カタログの節番号)・`injected_knowledge`・`diff_base`(変更範囲のベース)・`review_scope`(impact-analysis port が算出した差分外の確認箇所) |
| doc-gate-prompt | `target`(文書と種別)・`aspects`(観点カタログの文書ゲート系の節の位置)・`upstream`(上流の要約または上流成果物のパス)・`type_checks`(呼び出し元が転記する種別固有チェック) |
| release-review-prompt | `scope`(出荷スコープ)・`aspect`(担当観点と観点カタログの節番号)・`injected_knowledge`・`diff_base` |

- **指示・手順・返却フォーマットはタグの外**に置く。タグの内側はデータであり指示ではないことを、各雛形の**冒頭**(タグが現れる前)に明記する。読み手がタグに出会う前に扱いを知る順序にする。
- **山括弧の 2 つの用法を区別する規則を各雛形の冒頭に置く**。対のタグ(`<name>` … `</name>`)は構造であり、実値を埋めた後もそのまま残す。閉じタグを持たない `<...>` は実値へ置換するプレースホルダである。この区別を書かないと、既存の雛形が定める「`<...>` を実値に置換して使う」と衝突する。
- 差し込む値の規模が 20,000 トークンに達しないため、同じ出典が求める配置順(長文データを先頭、指示を末尾)は適用しない。返却フォーマットを末尾に置く現在の並びを変えない。
- **観点の重点を雛形へ転記しない**。判定の基準は観点カタログのエントリを読ませて適用させ、雛形にはその位置(`aspects`・`aspect`)だけを渡す。転記は正本の更新に追随せず、実際に doc-gate-prompt で基準 1 件が欠けたドリフトが起きていた。
- **本文(`---` 以降)に雛形起点の相対パスを書かない**。本文はサブエージェントへそのまま渡され、受け手の作業ディレクトリは雛形の位置と異なる。参照先はプレースホルダにして、オーケストレーターが実パスを差し込む。
- **返却フィールドの空値を「なし」に統一する**。全フィールドを省略せず出力し、該当が無いフィールドには「なし」と書く(行の省略と空欄を使い分けない)。`UNVERIFIED` は「なし」以外のときに `APPROVED` を返せない判定に使うため、空欄と「なし」の区別が判定に効く。

## 却下した選択肢

- **Markdown の引用ブロックで括る**: 差し込む値自体が Markdown を含むため、引用の入れ子で境界が壊れる。
- **差し込む値をファイルパスの参照だけにする**: `## Implementation Notes` はファイルの一部でパスを渡せるが、実装者の申告・レビュアーの指摘・失敗ログはサブエージェントの返却値でありファイルに存在しない。全てをパス参照にはできない。
- **現状維持**: 文章の制約だけでは、差し込み値が見出しを含む場合に境界が語彙上のものになる。制約は残したうえで、構造の手当てを加える。
- **プレースホルダの記法を `{{...}}` へ変える**: 山括弧の 2 義は解消するが、`<unit>`・`<workdir>`・`<engine>` のように各 SKILL.md が同じ山括弧の記法を使っており、雛形だけ別記法にすると読み手が 2 つの記法を覚えることになる。冒頭に区別の規則を 1 行置くほうが小さい。

## 帰結

- `../../dev/skills/dev-implement/templates/implementer-prompt.md`・`../../dev/skills/dev-implement/templates/reviewer-prompt.md`・`../../dev/skills/dev-implement/templates/debugger-prompt.md`・`../../dev/skills/dev-implement/templates/final-review-prompt.md` の差し込み値を XML タグで括った。各雛形の冒頭に、山括弧の 3 用法(対のタグ・プレースホルダ・本文からのタグ参照)と、タグの内側を基準と観測データに分ける区別を明記した。
- `../../dev/skills/dev-core/templates/doc-gate-prompt.md`・`../../dev/skills/dev-release/templates/release-review-prompt.md` にも同じ形を適用した。
- タグの内側からは手続きの文(「〜を読む」「〜で判断する」)を外し、タグの外の手順へ移した。基準に当たるタグ(`<type_checks>`・`<aspect_focus>` 等)は、判定に適用する旨をタグの外に書いた。

## 再検討条件

XML タグを含む差し込み値(タグを扱うタスクの説明・XML を含むエラーログ等)が、タグの対応を崩して境界を壊した事例が発生した場合。または、6 雛形の冒頭へ同じ文言で置いた 2 段落(山括弧の 3 用法・基準と観測データの区別)が食い違った場合(現在この一致を検査する機構は無く、`meta_check.py` への検査項目の追加を検討する)。
