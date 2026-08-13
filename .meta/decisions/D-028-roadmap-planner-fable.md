# D-028: unit 分解のエージェントを Claude Fable 5 の high effort に割り当てる(2026-08-13)

## 背景

D-026 は 7 つの役割エージェントに `model` と `effort` を割り当て、`dev-roadmap-planner` を opus / xhigh とした。理由は「最上流の分解。後続の全工程の区切りを決める」である。

[Introducing Claude Fable 5 and Claude Mythos 5](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5) は Claude Fable 5 を「最も要求の厳しい推論と長期的なエージェント作業のために作られた、Anthropic の最も高性能な広く提供されているモデル」と位置づける。仕様は 1M トークンの文脈窓・1 リクエストあたり最大 128k の出力トークン、価格は入力 100 万トークンあたり $10・出力 100 万トークンあたり $50 である(Claude Opus 5 の $5 / $25 の 2 倍)。thinking は常時オンで `thinking: {"type": "disabled"}` を受け付けず、深度の制御は effort パラメータが担う。

[Prompting Claude Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5) は effort について「ほとんどのタスクでは `high` を既定とし、最も能力要求の高いワークロードに `xhigh`、日常的な作業に `medium` か `low` を使う。Claude Fable 5 の低い effort の設定でも十分な性能を示し、以前のモデルの `xhigh` の性能を上回ることが多い」と定める。同ドキュメントは「日常的な作業で effort を高くすると、Claude Fable 5 はタスクが必要とする以上に文脈を集めて熟考することがある」とも記す。

同ドキュメントは、Claude Fable 5 が攻撃的なサイバーセキュリティ・生物学と生命科学・モデル自身の要約された思考の抽出を対象とする安全分類器を実行し、これらに当たるリクエストが `stop_reason: "refusal"` を返すことも記す。

unit 分解は、依頼の全体を読んで後続の全工程の区切りを決める工程である(D-026)。ここでの分解の誤りは、仕様・タスク分解・実装のすべてに波及する。

## 決定

- **`dev-roadmap-planner` の `model` を `fable`、`effort` を `high` にする**。unit 分解は後続の全工程の区切りを決めるため、分解の誤りによるやり直しの範囲が 7 つの役割の中で最も大きい。最上位のモデルを充てる利得がこの工程では他より大きい。
- **effort は `high` を採る**。公式ガイドが `high` を既定とし、`xhigh` を最も能力要求の高いワークロードに限るためである。
- **family alias で指定する規律を維持する**。`fable` は family alias であり、完全なモデル ID(`claude-fable-5`)は使わない(D-026 の「配布するエージェントにモデルを固定してよい。ただし family alias に限る」をそのまま適用する)。
- **他の 6 定義の割り当ては変えない**。D-026 の表のうち `dev-roadmap-planner` の行だけを更新する。

## 却下した選択肢

- **`model` を `fable` にし、`effort` は `xhigh` のまま残す**: 公式ガイドが `xhigh` を最も能力要求の高いワークロードに限り、`high` を既定とする。Claude Fable 5 の低い effort が以前のモデルの `xhigh` を上回る水準にある以上、`xhigh` を保って出力トークン(100 万トークンあたり $50)を増やす分に見合う利得を示せない。
- **`model` を opus のまま `effort` だけ下げる**: effort の推奨値は Claude Fable 5 に対するものであり、Claude Opus 5 の割り当てを変える根拠にならない。unit 分解に最上位のモデルを充てるという判断も残らない。
- **7 定義すべてを `fable` にする**: Claude Fable 5 の価格は Claude Opus 5 の 2 倍である。`dev-explorer` の read-only の抽出と要約のように、モデルの能力が成果を左右しない工程では価格に見合わない。D-026 の「役割ごとの費用と能力の割り当て(調査は haiku、判定は opus)」を維持する。

## 帰結

- `../../dev/agents/dev-roadmap-planner.md` の frontmatter を `model: fable` / `effort: high` にした。
- D-026 の割り当て表の `dev-roadmap-planner` の行に「→ D-028 で更新」を追記した。

## 再検討条件

unit 分解の依頼で `stop_reason: "refusal"` が観測された場合(サイバーセキュリティ・生命科学の領域を扱う依頼の分解で起きうる。`model` の差し戻し、または委譲先の切り替えを検討する)。または `high` で生成した分解案に対するユーザーの差し戻しが繰り返された場合(`xhigh` への引き上げを検討する)。
