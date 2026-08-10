# dev スキル群の 4 観点評価(プロンプト・コンテキスト・ハーネス・ループ)

調査日: 2026-08-10。評価対象は本リポジトリのコミット `f33431e`(`refactor: port と拡張バンドルをグループ配下へ移す` のマージ時点)。

4 観点の定義と一次情報の所在は、workspace の調査ノート `4_artifacts/home/issues/07_claude-code-usage-slides/research/advanced-engineering.md`(調査日 2026-08-08)による。本ノートは、そこで整理された設計指針と本スキル群の現状を照合し、採用・不採用を決める材料を記録する。確定した判断は `../decisions/` の `D-###` に置く。

指針の出典は次の 8 件である。本文では表題で参照する。

- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Building agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)

## 0. 起票時に挙げた 4 つの食い違いの対応先

| 食い違い | 対応先 |
| -------- | ------ |
| 参照の深さ(1 階層に留める) | P-1(読み込み量)・P-2(深さの判定) |
| 評価の不在(3 つ以上の代表シナリオ) | `../evaluations/README.md`。本ノートは判断の材料を扱い、シナリオの定義と実行結果は評価ノートに置く |
| 強制手段(hook による決定論的強制) | H-1(対象の選定)・H-2(配布方法) |
| 反復実行の設計 | L-1〜L-8 |

## 1. プロンプト

### P-1. 「参照(必読)」の量が progressive disclosure を無効にしている

測定値(行数。`SKILL.md` 本体と、その「参照(必読)」が挙げるファイルの合計。件数はファイル数で数える。dev-implement と dev-release は複数ファイルを 1 つの箇条書きに束ねているため、箇条書きの項目数とは一致しない):

| 部品 | SKILL.md | 必読の参照(ファイル数) | 必読の合計行数 | 実効の読み込み量 |
| ---- | -------- | ---------------------- | -------------- | ---------------- |
| dev-implement | 156 | 13 | 880 | 1,036 |
| dev-release | 81 | 8 | 609 | 690 |
| dev-spec | 103 | 7 | 439 | 542 |
| dev-decompose | 105 | 5 | 344 | 449 |
| dev-check | 65 | 5 | 370 | 435 |

Skill authoring best practices は `SKILL.md` 本体を 500 行以下に保ち、毎回は必要でない内容を参照ファイルへ移すことを求める。本体はいずれも 500 行を大きく下回るが、「必読」と宣言した参照を合わせた読み込み量は dev-implement で 1,036 行になる。参照ファイルへ移しても「必読」と書けば毎回読まれるため、移した効果が出ていない。

実際には、全参照が全実行で必要になるわけではない。dev-implement の `source-driven.md` は外部ライブラリの API を使うときだけ、`durable-info.md` は恒久情報へ反映する判断が生じたときだけ、`review-perspectives.md` は最終検証パネルの観点を選ぶときだけ必要になる。これらは条件付きの参照であり、条件を書けば読む量を減らせる。

判断: 改修する。各部品の参照節を「常時参照」と「条件付き参照(発火条件つき)」に分ける。

### P-2. 参照の深さは 1 階層に収まっている

Skill authoring best practices は、参照ファイルへのリンクを `SKILL.md` から 1 階層に留めることを求める(入れ子の参照は部分読みで済まされ、内容が欠ける)。本スキル群には 2 系統の多段参照がある。

- `flow-sdd/SKILL.md` → 部品の `SKILL.md` → `dev-core/references/*.md`: これはスキル間の委譲であり、部品の `SKILL.md` はそれ自体が起点(Skill として単独起動できる)である。1 つのスキル内での入れ子ではないため、この指針の対象にしない。
- `dev-core/references/*.md` → 別の `dev-core/references/*.md`: 例として `review-perspectives.md` が `runtime-verification.md`・`notation.md`・`durable-info.md`・`contract-and-domain.md`・`static-check.md`・`ports.md` を参照する。ただしこれらはいずれも「必読」ではなく、定義の所在を示す参照である。`dev-core/references/` と `dev-core/templates/` の全ファイルを検索したが、他ファイルを「必読」として要求する記述は無い。

判断: 現状は指針を満たす。ただし規律が明文化されていないため、「必読の参照が別の必読を要求する連鎖を作らない」を参照節の書式とあわせて明記する。

### P-3. 100 行を超える参照ファイルに目次が無い

Skill authoring best practices は 100 行を超える参照ファイルに目次を付けることを求める(部分読みでも構造を把握できるようにするため)。該当は 6 件で、目次を持つものは無い。

| ファイル | 行数 |
| -------- | ---- |
| `../../writing/skills/japanese-writing/references/composition.md` | 201 |
| `../../authoring/skills/skill-authoring/references/glossary.md` | 201 |
| `../../writing/skills/japanese-writing/references/inspection.md` | 181 |
| `../../writing/skills/japanese-writing/references/sentence.md` | 142 |
| `../../dev/skills/dev-core/references/review-perspectives.md` | 115 |
| `../../dev/skills/dev-core/references/git-convention.md` | 114 |

`../../dev/skills/dev-core/references/orchestration-patterns.md`(94 行)は目次を持つ。

判断: 改修する。6 件に目次を付ける。目次は見出しの一覧であり、規範の内容を変えない。

### P-4. サブエージェント・プロンプトが指示とデータを構造で区別していない

4 本のテンプレート(`implementer-prompt.md`・`reviewer-prompt.md`・`debugger-prompt.md`・`final-review-prompt.md`)は Markdown の見出しで構成し、差し込む値を `<...>` のプレースホルダで本文に埋める。差し込む値には外部由来の文字列が含まれる。

| テンプレート | 外部由来の差し込み値 |
| ------------ | -------------------- |
| implementer-prompt | タスク説明、`## Implementation Notes` の内容、注入知識のパス列 |
| reviewer-prompt | タスク説明、実装者の `OUT_OF_BOUNDARY` 申告、注入知識のパス列 |
| debugger-prompt | 実装者の `BLOCKER`、レビュアーの `FINDINGS`、検証エラー・CI 失敗ログの要点 |
| final-review-prompt | 注入知識のパス列、ベースコミット指定 |

Prompting best practices は、内容種別ごとにタグで括って指示・データ・例の混同を防ぐことを求める。現在は見出しの語彙だけが境界であり、差し込んだ文字列が見出しを含めば指示の側に混ざる。間接プロンプトインジェクション耐性は各テンプレートの制約節が文章で課しているが、境界を構造で示す手当てが無い。

同じ出典が求める配置順(20,000 トークンを超える長文データをプロンプト先頭に置き、指示・質問を末尾に置く)は、差し込む値がいずれもその規模に達しないため適用対象にならない。返却フォーマットが末尾にある現在の並びを変えない。

同じ出典が挙げる few-shot 例示(3〜5 個の例を `<example>` タグで括る)も検討したが、採らない。各雛形は返却フォーマットをコードブロックで示しており、これが出力形式の見本として機能している。例を足すと 1 タスクあたりのプロンプトが長くなる分だけ、P-1 で削る読み込み量と相殺する。

判断: 改修する。差し込む値を XML タグで括り、タグ内の内容をデータとして扱うことを制約節と対応させる。同じ形の差し込みを持つ `doc-gate-prompt.md`(呼び出し元が転記する種別固有チェック・上流の要約)と `release-review-prompt.md`(観点カタログから転記する重点・注入知識のパス列)にも同じ改修を適用する。

### P-5. 成功基準と自由度の水準は現状で成立している

- 成功基準: implementer-prompt は検証コマンドと返却フォーマットを持つ。`VERDICT` の判定条件は、reviewer-prompt が「`[Critical]` が 1 件以上」、final-review-prompt が「`[Critical]` が 1 件以上、または `UNVERIFIED` が『なし』以外」と、それぞれ明示する。
- 自由度の水準: implementer-prompt は手順を固定する箇所(TDD の順序・返却フォーマット)と判断に委ねる箇所(実装方針・境界外変更の必要性)を分けている。Effective context engineering の right altitude(ハードコードした条件分岐の羅列と曖昧な指示の中間)に照らして妥当である。

判断: 維持する。

### P-6. description は規約に合っている

配布する 8 スキル(`SKILL.md` を持つもの。`dev-core` は持たない)の description はいずれも「何をするか」と「いつ使うか」を持つ。人称は、日本語では主語を持たない終止形(「〜する」「〜に使う」)で書かれており、一人称・二人称の指示形は含まない。Skill authoring best practices が求める三人称記述に反する記述は無い。

`trigger_check.py` は 30 ケース全通過・警告 0 件で、近接衝突の検出も無い。ただし `meta-check/SKILL.md` 3.2 が注記するとおり、通過が示すのは「意図した語彙が description に含まれる」ことだけである。判別力の根拠にはしない。

判断: 維持する。

## 2. コンテキスト

### C-1. 採用済みの手段

| 手段 | 実装箇所 | 判断 |
| ---- | -------- | ---- |
| 参照による自己完結(上流の本文を転記しない) | `../../dev/skills/dev-implement/SKILL.md` 2.、`../../dev/skills/dev-decompose/SKILL.md` 3. Step 3 | 維持 |
| サブエージェントへの探索の隔離 | `../../dev/agents/dev-explorer.md`、`../../dev/skills/dev-core/references/orchestration-patterns.md` 1. | 維持 |
| イテレーション間で 1 行サマリのみ保持 | `../../dev/skills/dev-implement/SKILL.md` 6. | 維持 |
| 必要分だけ読む(progressive disclosure) | `../../dev/skills/dev-core/references/principles.md` 3. | P-1 の改修で実効化する |

### C-2. 必要時点での取得の徹底(just-in-time)

principles.md 3. は「必要分だけ読む」を原則として定めるが、P-1 のとおり各部品の「参照(必読)」がこれと矛盾する。原則は正しく、実装が原則を満たしていない。

判断: P-1 の改修で解消する。原則の文言は変えない。

### C-3. 圧縮(compaction)後の再開手段が定義されていない

Effective context engineering は、上限に近づいた会話を要約して再開する際に、アーキテクチャ上の決定・未解決のバグ・実装詳細を残すことを求める。Best practices for Claude Code は `/compact <指示>` と CLAUDE.md の規則で要約の焦点を指定できると述べる。本スキル群には、圧縮時に何を残すかの指示も、圧縮後にどう再開するかの手順も無い。

dev-implement の自律モードは、dev-decompose 4. が定める規模上限の目安(1 作業単位のメインタスク 8 以下)まで反復するため、長い実行では圧縮が起きる。圧縮で失われる情報を性質で 3 つに分ける。

| 性質 | 該当する情報 | 対処 |
| ---- | ------------ | ---- |
| ファイルから再導出できる | 現在の状態、承認、完了・未完了のタスク、変更の履歴 | 圧縮後にファイルを読み直す |
| 再導出の入口になる | workdir のパス、`## Implementation Notes` の所在 | 要約に残す。失うと読み直す先が分からない |
| ファイルに無い | 直近の失敗の内容と原因、却下した方針 | 要約に残す。残らなければ同じ失敗を繰り返す |

判断: 採用する。ただし主たる対策は「圧縮の後は記憶ではなくファイル(`state.json`・`tasks.md`・git ログ)から現在地を再導出する」とし、これは L-2 の再開手順を同一セッション内の圧縮にも適用するものとする。この手当ては harness の圧縮挙動に依存しない。

要約に残す情報の指定(2 行目・3 行目)は補助的な位置づけとする。スキル本文に書いた指定が圧縮の要約に実際に反映されるかは、出典が挙げる手段(`/compact` の引数・CLAUDE.md の規則)には含まれておらず、本評価では確かめていない。圧縮は harness が任意の時点で起こすため決定論的に再現できず、効果を確かめる手段を現時点で持たない。評価シナリオ(`../evaluations/README.md` E-006)が確かめるのは、要約に何も残らなくてもファイルから再導出できることである。

### C-4. コンテキスト外への構造化メモの書き出し(採用済みと判定する)

Effective harnesses for long-running agents は進捗ファイル(`claude-progress.txt`)への定期的な書き出しを挙げる。本スキル群では、対応する情報が 4 箇所に分かれて既に存在する。ループ観点の検討事項「状態の外部化」もこの節で扱う。

| 情報 | 記録先 |
| ---- | ------ |
| 現在の状態・承認・凍結ハッシュ | `state.json`(`state.py` が書く) |
| 完了・未完了のタスク | `tasks.md` のチェックボックス |
| 作業単位を横断する知見・境界外変更の申告 | `tasks.md` の `## Implementation Notes` |
| 変更の履歴と復元点 | git のコミット履歴 |

判断: 進捗ファイルを追加しない。同じ進捗を 2 箇所に持つと正本が割れ、どちらを正とするかの規律が新たに要る。再入時の現在地は `state.json` と `tasks.md` から機械的に再導出でき、これは orchestration-patterns.md 1. の「再入時はファイルから現在地を機械的に再導出する」と一致する。

再検討条件: 自走ループ(レイヤー 3)の実装で、`state.json` と `tasks.md` から再導出できない情報(試行の履歴・却下した方針)を持ち越す必要が生じた場合。

## 3. ハーネス

### H-1. 文章で守らせている規律のうち hook で強制できるもの

Best practices for Claude Code は、文章の指示は助言であり、毎回確実に実行させる動作は hook で強制すると述べる。現在の強制手段は決定論スクリプト(`state.py`・`check.py`)だけで、hook を持つ拡張は存在しない。

| 規律 | 現在の所在 | 機械判定の可否 | 判断 |
| ---- | ---------- | -------------- | ---- |
| 破壊的な git 操作の禁止 | `git-convention.md` 6.、`dev-implement/SKILL.md` 13. | コマンド文字列の照合で判定できる | hook 化する |
| 選択的ステージング(`git add -A` / `git add .` の禁止) | 同上 | 同上 | hook 化する |
| 凍結後の中間生成物を変更しない | `principles.md` 1.、`static-check.md` 5. | 書き込み先のパスと `state.json` の `frozen` の照合で判定できる | hook 化する |
| コードに中間生成物の ID を残さない | `dev-implement/SKILL.md` 13. | 要件 ID の書式(`1.2`)はコード中の通常の数値・バージョン表記と区別できない | hook 化しない |
| テストの削除・スキップで緑にしない | `git-convention.md` 9.4、`dev-debugger.md` | 削除の検出には差分解析が要り、仕様変更に伴う正当な削除と区別できない | hook 化しない |

hook 化する 3 件は、いずれも例外を持たない絶対禁止であり、コマンド文字列とパスの照合で判定が閉じる。hook 化しない 2 件は文脈に依存する判定であり、誤って拒否すると正当な作業を止める。判定の性質でこの 2 群を分ける。

`check.py` は凍結違反を error として検出するが、検出は書き込みの後になる。hook は書き込み自体を拒否するため、検出と防止の差がある。

効く範囲の限定: hook は H-2 のとおり拡張バンドルとして配るため、バンドルを導入しない利用側では 3 件とも文章の規律のまま残る。コア側の規律文は削らず、hook は上乗せの強制手段として位置づける。

判断: 上の 3 件を hook にする。残る 2 件はレビュー(dev-reviewer)とプロンプトの規律に委ねる。

### H-2. hook の配布方法

`../../dev/extensions/README.md` 3.2 は「hooks・settings.json・MCP は本体(レイヤー 0〜2)では使用しない」と定める。理由は、コアが特定の harness の機構に依存しないこと(可搬性)である。

判断: 拡張バンドルとして配る。バンドル群 `guardrails`、バンドル `ext-dev-guardrails` を新設し、`install.py ext` で導入する。

却下した選択肢: コアの一部にして `install.py core` で配線する。理由は 2 点ある。

- コアが harness の機構(Claude Code の hooks と `settings.json`)に依存することになり、`extensions/README.md` 3.2 の規律に反する。`install.py` の実装も、`settings.snippet.json` のマージを拡張の導入経路にだけ持たせている。
- `install.py core` の役割は用途グループの `skills/`・`agents/` のハードコピーであり、利用側の `settings.json` の書き換えはその範囲を超える。core の導入という 1 つの操作に、範囲の異なる変更を抱き合わせることになる。

### H-3. 検証手段の 3 方式が 1 箇所で対応づけられていない

Building agents with the Claude Agent SDK は検証を (1) ルールベース(lint・型検査・明示的なエラーチェック)、(2) 視覚フィードバック(スクリーンショット)、(3) LLM as judge の 3 方式に分ける。本スキル群の対応は次のとおりで、3 方式の対応表が 1 箇所に無い。

| 方式 | 本スキル群での実装 | 正本 |
| ---- | ------------------ | ---- |
| ルールベース | `check.py`・`state.py`・タスクの検証コマンド(テスト・ビルド・リント) | `static-check.md` |
| 視覚フィードバック | 実行時検証の手段 1(ブラウザ自動化)。環境にある場合のみ | `runtime-verification.md` 3. |
| LLM as judge | dev-reviewer の観点別パネル | `review-perspectives.md` |

判断: 改修する。`principles.md` に 1 節を足し、3 方式と適用対象・正本の所在を対応させる。3 方式は代替関係ではなく適用対象が違うことを明示する(ルールベースの緑を実行時成立の根拠にしない、という既存規律と同じ構図)。

### H-4. `disable-model-invocation` は D-008 の判断を維持する

D-008 は配布物をモデル自動起動の対象に置いたままとし、再検討条件を「意図しない commit / push・本番操作の発生」または「description の近接衝突の実測」とした。いずれも観測していない(`trigger_check.py` の近接衝突検出は 0 件)。

判断: 維持する。

### H-5. 権限設定とサンドボックスは配布しない

`install.py` は拡張の `settings.snippet.json` から hooks と `permissions.deny` のみをマージし、`permissions.allow` は対象外として警告を出す。

判断: この範囲を維持する。`permissions.allow` とサンドボックス設定は利用側のリスク許容度・CI 構成で決まるため、配布側が決めると利用側の判断を上書きする。`deny` は方向が逆で、配布側の規律を足すだけなので既存どおり許す。

### H-6. ツール設計は追加の改修をしない

Writing effective tools for agents の要点と本スキル群の決定論スクリプトの対応:

| 要点 | 現状 |
| ---- | ---- |
| 複数操作を統合する | `state.py` が init / set-state / approve / show / status / scan を 1 つのエンジンに統合する |
| 関連ツールを名前空間でまとめる | スキル群自体を扱うスクリプトは `meta_` 接頭辞、成果物を扱うスクリプトは用途別のファイル名で分かれる |
| レスポンスのトークン量を制限する | `--json` で形式を切り替える。既定は重大度つきの要約 |
| エラーは次の行動が分かる文にする | 日本語で違反内容と対処を書く(例: 「`--baseline` の形式が `meta_check.py --json` の出力でない」) |
| 評価タスクを作って実行ログからツールを改善する | 未実施。評価シナリオ(`../evaluations/README.md`)が部分的に相当する |

判断: 維持する。スクリプトの改修はしない。

## 4. ループ

### L-1. 1 反復の単位・終了条件・評価者の分離は現状で成立している

- 1 反復の単位: `dev-implement/SKILL.md` 6. の「1 イテレーション = 1 サブタスクのみ」。flow-sdd は 1 作業単位 = 仕様 → 分解 → 実装。Effective harnesses for long-running agents の「1 セッション = 1 機能」と同じ粒度である。
- 終了条件: 状態機械の `completed` 到達と凍結。dev-implement は全タスク完了かつ最終検証 GO。
- 評価者の分離: Harness design for long-running application development は、実装者が自分の成果物を過大評価する傾向への抑止として、実装者と別の評価者を置くことを挙げる。本スキル群は dev-implementer と dev-reviewer を別文脈で起動し(`dev-reviewer.md` の制約節)、最終検証を観点別の独立文脈のパネルで行う。採用済みとして維持する。
- 状態の外部化: C-4 で扱う。

判断: 維持する。

### L-2. セッション開始手順が固定されていない

Effective harnesses for long-running agents は、開始手順を「pwd → 進捗ファイルと git ログの読了 → `init.sh` 実行 → 基本機能のテスト → 未完了機能を 1 つ選択」の順で毎回実行することを求める。開始時のテストは前セッションが残した破損を早期に検出する目的を持つ。

`flow-sdd/SKILL.md` Step 0 は「`state.json` があれば `status` で現在地を復元し、状態に対応するフェーズから続行する」と定めるが、順序を持つ手順ではなく、開始時の検証コマンド実行が無い。

判断: 改修する。Step 0 を順序付きの再開手順にし、リポジトリと作業ブランチの確認・`state.json` と git ログの読了・検証コマンドの実行・次の作業の選択の順に固定する。

条件の分岐: 検証コマンドは `tasks.md` のタスク固有情報に書かれるため、`tasks.md` が生成される前の状態(`initialized`・`spec-generated`・`spec-approved`)では実行対象が存在しない。この 3 状態では検証コマンドの実行を省き、その旨を手順に書く。`init.sh` に相当する起動スクリプトの作成はプロジェクト側の資産のため、コアでは要求しない。

### L-3. 巻き戻し手段が定義されていない

`git-convention.md` 1. は「誤った変更が起きても直前の状態へ復帰できる」ことを commit の目的に挙げるが、復帰の手順は書いていない。同 6. が `git reset --hard`・`git checkout .` を禁止しているため、禁止だけがあって復帰の実行手段が定義されていない状態になっている。

判断: 改修する。`git-convention.md` に巻き戻しの手順を足す。方針は、コミット済みの変更は `git revert` で打ち消す(履歴を残す)、未コミットの変更は捨てずに `git stash` で退避する、とする。禁止と手段を対にする。

### L-4. 反復上限はコアに追加しない

現在の有界リトライは、レビュー却下に対する再投入 2 回・デバッガ 2 ラウンド・検証失敗の修復 3 ラウンド(`dev-implement/SKILL.md` 10.)、CI 修正 3 ラウンド(`git-convention.md` 9.3)である。ループ全体(作業単位の数・フェーズの往復回数)の上限は無い。

flow-sdd の承認ゲート(ルーティング・roadmap・spec・tasks)はすべて人間承認であり(`flow-sdd/SKILL.md` 4.)、実装フェーズは承認ゲートを持たず自走するが、そこへ入る前に必ず tasks の承認を通る。承認の停止点が実質の上限として働く。

判断: コアに全体の反復上限を追加しない。自走するレイヤー 3 の拡張が、反復上限・コスト監視・権限の限定を定める。この境界を flow-sdd の「対応しないこと」に明記する。

### L-5. 完了判定の偽陽性への対策が実装者側に無い

Effective harnesses for long-running agents は「進捗を根拠にした早すぎる完了宣言」を典型的な失敗に挙げ、機能リストの改変禁止と「テストの削除・編集は許容しない」の明示で対処する。Ralph ループの記事は「実装済みを装うスタブ」を失敗モードに挙げる。

本スキル群の現状の対策は 3 箇所に分かれている。

| 対策 | 所在 |
| ---- | ---- |
| 判定基準を緩めて緑にしない(CI) | `git-convention.md` 9.4 |
| テストの削除・スキップで通すことの禁止 | `../../dev/agents/dev-debugger.md` |
| リファクタが振る舞いを変えていないか(既存テストの書き換えを疑う) | `../../dev/skills/dev-implement/templates/reviewer-prompt.md` |

実装者(最も強い誘因を持つ役)へ渡すプロンプトには、REFACTOR の段に限った「テストの書き換えを要する整理はしない」があるだけで、GREEN にするためのテストの削除・スキップ・アサーション弱体化を禁じる記述は無い。未実装のスタブを完了として返さない旨も無い。タスク定義(`tasks.md`)からタスクを削って完了に見せることの禁止も、どこにも無い。

判断: 改修する。implementer-prompt の既存の REFACTOR 限定の制約を、段に依存しない禁止へ拡張し、「未実装のスタブを `READY_FOR_REVIEW` で返さない」を足す。reviewer-prompt の確認手順にテストの削除・弱体化の検出を足し、`dev-implement/SKILL.md` に「`tasks.md` のタスクを削除・改変して完了に見せない」を足す。

### L-6. headless 実行と Stop hook はコアの対象外とする

`flow-sdd` は `AskUserQuestion` と明示承認に依存するため、`claude -p` の非対話実行では承認待ちで停止する。承認を省く改変を加えれば動くが、それは flow-sdd の設計(承認ゲートはすべて人間承認)を壊す。

Best practices for Claude Code は Stop hook で検証スクリプトが通るまでターン終了をブロックする手法を挙げる。これも同じ理由で採らない。承認ゲートに到達したターンの終了は「ユーザーの応答を待つ」ための正しい停止であり、Stop hook はこの停止をブロック対象と区別できない。

判断: コアの部品・composition は headless で回さず、Stop hook も使わない。headless と自走はレイヤー 3 のワークフローの領域とし、その拡張が反復上限・`--allowedTools` による権限の限定・コスト監視(`--output-format json` の `total_cost_usd`)を定める。この境界を flow-sdd の「対応しないこと」に明記する。

### L-7. dev-author は起動経路を持たない

`dev/agents/dev-author.md` は「composition が自走ループでサブ部品の成果物生成を隔離委譲するときにのみ起動される」と定める。自走ループはレイヤー 3 の拡張に委ねられており、その拡張は存在しない。本リポジトリ全体を検索したところ、`dev-author` を起動する記述は無く、言及は `orchestration-patterns.md` 5.(役割の説明)・`DESIGN.md`・`D-000` の 3 箇所だけである。

`install.py core` は `<グループ>/agents/*.md` をすべて配布するため、利用側では起動経路を持たないエージェント定義が 1 件常駐する。エージェントの description はサブエージェント起動時の候補一覧に載るため、読み込み量を払って何も返さない状態になる。

判断: 改修する。`dev-author` をコアから外す。自走ループを実装する拡張バンドルが `<バンドル名>-author` として同梱する(`extensions/README.md` 3.1 の同梱エージェント規約に合う)。`orchestration-patterns.md` 5. の記述をこの方針へ改める。

この判断は D-000 8.1 の役割エージェント 5 体構成を部分的に覆すため、`D-###` 化の際に `../decisions/README.md` の規約(新エントリで supersede し、旧エントリへ更新先を追記する)に従って D-000 を supersede 対象として扱う。あわせて dev-skills/004(並列実装の拡張バンドル)の前提を変えるため、004 のログへ記録する。

### L-8. 差し戻し遷移は維持する

状態機械は `tasks-generated → spec-generated`・`implementing → tasks-generated` の差し戻し遷移を持ち、飛び越し遷移を定義しない(`flow-sdd/SKILL.md` 5. の補足)。上流の欠陥が見つかったときに 1 段ずつ戻る形は、戻り先で何を作り直すかを状態が示すため維持する。

判断: 維持する。

## 5. 構造の棚卸し

Harness design for long-running application development の「ハーネスの各構成要素は、モデルが単独ではできないことについての仮定を符号化している」に沿って、各構成要素が符号化する仮定と、その仮定の成立根拠を判定する。

| 構成要素 | 符号化している仮定 | 成立根拠 | 判断 |
| -------- | ------------------ | -------- | ---- |
| 用途グループの分割(dev / writing / authoring) | 利用側は必要な群だけを導入したい(D-012) | モデルの能力とは独立の配布要求。`install.py` のグループ指定がこの要求に対応する | 維持 |
| オニオン型レイヤー(0〜3) | 依存の向きを宣言しないと、拡張が本体を書き換える形の依存が生じる | 依存規律違反の観測実績は無い(`meta_check.py` の検出 0 件)。仮定の真偽は本評価では判定できない。ただしレイヤーは検査以外にも、`install.py` の配布境界と `extensions/README.md` 3.2 の拡張の依存規律を記述する語彙として使われており、削ると両方の記述先が無くなる | 維持。レイヤー 3 に実体(hook 拡張)を入れる |
| `meta-*` の 4 スキル構成 | 副作用の有無が異なる操作を 1 つの description に束ねると、read-only を意図した依頼で副作用のある操作が走る | `meta-check`・`meta-review` は read-only、`meta-doc` は `DESIGN.md` を全上書きする。副作用の非対称は実装上の事実である(束ねた場合の誤起動そのものは未観測) | 維持 |
| flow-sdd の 7 状態 | セッションをまたぐと現在地を失う | Effective harnesses for long-running agents が長時間エージェントの中心課題として挙げる。コンテキストが有限である限り成立する | 維持 |
| `dev-author` | 自走ループが生成の隔離委譲を必要とする | 自走ループが未実装のため、現時点で起動経路が無い | コアから外す(L-7) |

flow-sdd の状態数については、`spec-approved`・`tasks-approved` が `state.json` の `approvals` フラグと重複するように見えるため個別に検討した。両状態を削ると、再開時の分岐が「状態」1 つではなく「状態と `approvals` の組」になり、Step 0 の再開判定が複雑になる。L-2 で Step 0 を固定手順にする方針と逆行するため、削らない。

`meta-core` は `SKILL.md` を持たない参照専用のため、起動対象の `meta-*` は 3 つである。この非対称は `dev-core` と同型で、意図した構成である。

## 6. 改修しない項目の一覧

判断の根拠を後から引けるように、採用しないと決めた項目をまとめる。

| 項目 | 採用しない理由 | 根拠の所在 |
| ---- | -------------- | ---------- |
| 進捗ファイル(`claude-progress.txt` 相当)の追加 | 進捗の正本が `state.json`・`tasks.md`・git と重複し、正本が割れる | C-4 |
| コードへの中間生成物 ID の混入を hook で検出する | 要件 ID の書式がコード中の通常の数値と区別できず、誤検出が正当な作業を止める | H-1 |
| テストの削除を hook で検出する | 仕様変更に伴う正当な削除と区別できない | H-1 |
| `permissions.allow`・サンドボックス設定の配布 | 利用側のリスク許容度と CI 構成で決まる判断を配布側が上書きする | H-5 |
| コアへの全体反復上限の追加 | 承認の停止点が上限として働く。自走はレイヤー 3 の責務 | L-4 |
| コアの headless 対応 | 承認ゲートの設計を壊す。レイヤー 3 の責務 | L-6 |
| Stop hook による自走 | 承認ゲートでの正しい停止と、検証未達での停止を区別できない | L-6 |
| `disable-model-invocation` の採用 | D-008 の再検討条件を満たす観測が無い | H-4 |
| flow-sdd の状態数の削減 | 再開判定が「状態と `approvals` の組」になり、固定手順化と逆行する | 5. |
| サブエージェント・プロンプトへの few-shot 例示の追加 | 返却フォーマットのコードブロックが出力形式の見本として機能しており、例を足すと 1 タスクあたりのプロンプトが長くなる | P-4 |
| 決定論スクリプトの改修 | Writing effective tools for agents の要点に対応が付いている | H-6 |
