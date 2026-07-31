---
name: skill-authoring
description: スキル(.claude/skills 配下の SKILL.md とその参照ファイル)を新規作成・編集・リファクタするときの設計規範。predictability(毎回同じ手続きを踏むこと)を根本の徳に、invocation(model-invoked / user-invoked と context load / cognitive load)、information hierarchy(step / reference / disclosed reference と progressive disclosure)、description の書き方、分割の判断、pruning、leading word、失敗モード(premature completion・duplication・sediment・sprawl・no-op・negation)を references/glossary.md の語彙で定める。スキルを書く・直すとき、SKILL.md や description を設計するとき、スキルが「毎回挙動が違う」「長すぎる」「呼ばれない/呼ばれすぎる」といった問題を示すときに使う。
---

# スキル作成規範

## 1. はじめに

スキルは、確率的なシステムから決定性を引き出すために存在する。根本の徳は **predictability**(予測可能性)である。毎回のrunで同じ「出力」を出すことではなく、同じ「プロセス」を踏むことを指す。以下のレバーはすべてこの徳に奉仕する。

本ファイルは原則を要約する。用語の完全な定義は `references/glossary.md` に置く(必要時に読む disclosed reference)。**太字語** は用語集の見出し語である。

対象は `.claude/skills/` 配下の自作スキル。運用は Claude Code を前提とする。

## 2. Invocation(呼び出し)

異なるコストを払う 2 択がある。

- **model-invoked**: **description** を残す。エージェントが自律的に発火でき、他のスキルからも到達できる(人間が名前を打つこともできる)。代わりに毎ターン **context load** を払う(description が文脈に載り続け、トークンと注意を消費する)。機構: frontmatter で `disable-model-invocation` を書かず、トリガー語を豊富に含むモデル向け description を書く。
- **user-invoked**: **description** をエージェントの到達から外す。人間が名前を打ったときだけ発火でき、他のどのスキルからも呼べない。context load はゼロだが **cognitive load** を払う(人間がスキルの存在と使いどころを覚える)。機構: frontmatter に `disable-model-invocation: true` を書き、description は人間向けの一行要約にする。

エージェント自身がスキルへ到達する必要があるとき、または他のスキルが到達する必要があるときだけ model-invocation を選ぶ。手動でしか発火しないなら user-invoked にし、context load を払わない。

user-invoked スキルが覚えきれないほど増えたら、積もった cognitive load は **router skill**(他の user-invoked スキルとその使いどころを名指しする 1 つの user-invoked スキル)で治す。

## 3. description の書き方

model-invoked の **description** は 2 つの仕事をする。スキルが何かを述べ、発火すべき **branch** を列挙する。どの語も context load を増やすため、本文よりさらに強く刈り込む。

- **先頭に leading word を置く**。description は呼び出しの仕事をする場所である。
- **1 つの branch に 1 つのトリガー**。1 つの branch を言い換えた同義語は **duplication** である。まとめ、真に別々の branch だけを残す。
- **本文にある同一性は削る**。description はトリガーと、必要なら「他のスキルが必要とするとき」の到達句に絞る。

## 4. Information hierarchy(情報の階層)

スキルは 2 種の内容——**steps** と **reference**——から成り、自由に混ざる(all steps でも all reference でも両方でもよい)。核心の判断は、どちらを使い、各要素を階段のどこに置くかである。階段は、エージェントがどれだけ即座に必要とするかで順位づける。

1. **In-file step**——`SKILL.md` 内の順序づけられた動作。一次の段。各 step は **completion criterion**(完了基準)で終わる。チェック可能(done と not-done を区別できる)にし、要る場所では網羅的(「変更したモデルをすべて計上」であって「変更リストを作る」ではない)にする。曖昧な基準は **premature completion** を招く。
2. **In-file reference**——`SKILL.md` 内の定義・ルール・事実。必要時に参照する。正当にフラットな並列集合であることが多い。
3. **External / disclosed reference**——`SKILL.md` の外へ出し、**context pointer** で到達する reference。ポインタが発火したときだけ読み込む。

下げなさすぎれば上が肥大し、下げすぎれば必要な素材を隠す。この緊張が判断のすべてである。**progressive disclosure**(`SKILL.md` から別ファイルへ下ろすこと)で上を読みやすく保つ。分割のテストは **branch** である。すべての branch が必要とするものをインラインにし、一部の branch だけが到達するものをポインタの陰へ下ろす。ポインタの「文言」が(向き先ではなく)到達のタイミングと確実さを決める。

階段が「どこまで下がるか」を決めるのに対し、**co-location**(共置)は下がった先で「隣に何が来るか」を決める。概念の定義・ルール・注意点を 1 つの見出しの下にまとめ、散らさない。

## 5. 分割の判断

**granularity**(粒度)は各切断で 2 つの負荷のどちらかを払うため、切断が見合うときだけ分割する。

- **invocation による切断**——それを単独で発火させる固有の **leading word** があるとき、または他のスキルが到達する必要があるとき、model-invoked スキルを切り出す。新しい description の常時 context load を払うため、その独立到達が見合う必要がある。
- **sequence による切断**——先の **steps**(ある step の post-completion steps)が、目の前の step を急がせる(**premature completion**)なら、steps の連なりを切る。見えなくすることで、目の前の作業により多くの **legwork** を促す。

## 6. Pruning(剪定)

- 各意味を **single source of truth**(単一の真実の源)に保つ。挙動の変更が 1 か所の編集で済むようにする。
- 各行の **relevance**(関連性)を確かめる。スキルの働きにまだ関わるか。
- **no-op** を文単位で狩る。各文を単独で no-op テスト(既定に対し挙動を変えるか)にかけ、落ちたら語を削るのではなく文ごと消す。積極的に。落ちる散文はほとんど、書き直すのではなく消す。

## 7. Leading word(先導語)

**leading word** は、モデルの事前学習にすでに宿るコンパクトな概念(例: _lesson_、_fog of war_、_tracer bullets_)で、スキル実行中にエージェントがそれで考える。文ではなくトークンとして繰り返され、分散した定義を蓄積し、行動の一領域を最小のトークンで固定する。造語は prior を呼び起こさないため、まず既存の語へ手を伸ばす。

2 度奉仕する。本文では **実行** を固定し(概念が現れるたび同じ挙動へ手を伸ばす)、description では **呼び出し** を固定する(同じ語がプロンプト・ドキュメント・コードに宿るとき、より確実に発火する)。3 か所で書き下した三つ組(**duplication**)や、1 つの考えを一文で示唆する description は、1 トークンへ **collapse**(圧縮)する好機である。

## 8. 失敗モード

ユーザーがスキルで抱える問題の診断に使う。定義は `references/glossary.md`。

- **premature completion**——step を本当に終わる前に終える。注意が done へ滑る。防御は順に。まず completion criterion を鋭くする(安価・局所的)。基準が本質的に曖昧で、かつ急ぎを観測したときだけ、sequence を切って post-completion steps を隠す。
- **duplication**——同じ意味が 2 か所以上にある。保守とトークンのコストを払い、階段上の順位を過大にする。
- **sediment**——剪定の規律がなく、古い層が沈着する。足すのは安全で除くのは危険に感じるための既定の運命。
- **sprawl**——全行が生きて一意でも、単に長すぎる。処方箋は階層。reference をポインタの陰へ下ろし、branch か sequence で分割する。
- **no-op**——モデルが既定で従う行。負荷を払って何も言わない。弱い leading word(既にそこそこ徹底しているのに _be thorough_)は no-op で、直し方はより強い語(_relentless_)であって別の技法ではない。
- **negation**——禁止による操縦は裏目に出る。_象を思い浮かべるな_ は象を名指しして利用しやすくする。**肯定** でプロンプトし(すべき挙動を述べ、禁じた側を口に出さない)、肯定で言い換えられないハードなガードレールのときだけ禁止を残し、それでもすべきことと対にする。

## 9. 用語集

上記の太字語の完全な定義(_避ける語_ を含む)は `references/glossary.md` に置く。用語は Invocation・Information hierarchy・Steering・Pruning の軸でまとめ、各失敗モードはそれを治すレバーの隣に置く。
