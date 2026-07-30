---
name: motion-design
description: UI モーション・アニメーションの設計判断と craft(いつ・なぜ・どう動かすか)
inject:
  - dev-spec
  - dev-implement
condition: GUI のアニメーション・モーション・ジェスチャを含む Web フロントエンド作業のとき
---

# UI モーション設計(motion-design)

GUI のモーション(アニメーション・トランジション・ジェスチャ)を扱う作業で dev-spec・dev-implement に注入する知識 port。`frontend-design`(静的な視覚設計)の姉妹となる、動きの設計判断と craft。出典: [emilkowalski/skills](https://github.com/emilkowalski/skills)(MIT。apple-design・emil-design-eng・review-animations の要約)、Apple WWDC「Designing Fluid Interfaces」(2018)。値は Web(CSS)前提。

## 1. まず「動かすべきか」(頻度で決める)

- 頻度で判断する: 100 回/日以上(キーボード操作・コマンドパレット)= 動かさない / 数十回/日(hover・一覧移動)= 削るか最小化 / 時々(モーダル・ドロワー・トースト)= 標準 / まれ(オンボーディング・祝祭)= delight 可。
- **キーボード起動の操作はアニメしない**(何百回も繰り返すため、遅く・切断されて感じる)。
- 目的の無いモーション(「かっこいいから」で頻出)は入れない。有効な目的: 空間的一貫性・状態表示・説明・フィードバック・急変の緩和。

## 2. 設計判断(easing / duration)

- easing: 入退場 → `ease-out`(出だしが速く応答的) / 画面内の移動・モーフ → `ease-in-out` / hover・色 → `ease` / 定速(マーキー・進捗) → `linear`。**UI に `ease-in` を使わない**(出だしが遅れ、最も見られる瞬間に鈍く感じる)。既定の CSS easing は弱いので、強いカスタム曲線を使う(例: `cubic-bezier(0.23, 1, 0.32, 1)`)。
- duration の目安: ボタン押下 100–160ms / ツールチップ 125–200ms / ドロップダウン 150–250ms / モーダル・ドロワー 200–500ms。**UI アニメは 300ms 未満**に収める。
- **非対称タイミング**: 利用者が判断する所(押下・hold)は遅く、システムが応答する所(離す)は速く。

## 3. 物理と割り込み(springs)

- 利用者が触れる要素は spring(固定 duration でなく物理で収束)。パラメータは damping(減衰・overshoot の量)と response(到達の速さ)で考える。既定は critically damped(bounce なし)、勢いを伴うジェスチャ(フリック・スワイプ解放)にだけ弱い bounce(0.1–0.3)。
- **割り込み可能にする(最重要)**: 動作中に掴んで反転できること。アニメは常に**現在の表示値**から始める(目標値から始めると割り込み時に跳ぶ)。ジェスチャ駆動に CSS transition / `@keyframes` を使わない(掴んで滑らかに反転できない)。
- **速度の受け渡し**: ジェスチャ終了時、指の速度でアニメを継続し継ぎ目を消す。運動量の投射: 離した点でなく、速度から着地点を予測してスナップ先を選ぶ(スクロール減速と同じ)。

## 4. craft のルール

- **`scale(0)` から動かさない**(無から現れて見える)。`scale(0.9–0.97)` + `opacity: 0` から。
- ポップオーバーは trigger 起点で拡大する(`transform-origin` を trigger に。**モーダルは中央のまま**=特定 trigger に紐づかない)。
- ボタン等の押下要素は `:active` で `transform: scale(0.97)`(即時フィードバック)。
- 素早く連続発火する UI(トースト追加・トグル)は `@keyframes` でなく CSS transition(keyframes は 0 から再スタートし割り込めない)。入場は `@starting-style`。
- crossfade が二重像で濁るときは遷移中に軽い `filter: blur(2px)`(20px 未満。重い blur は Safari で高コスト)。
- 群の入場は stagger(要素間 30–80ms。装飾なので操作を止めない)。

## 5. パフォーマンス

- **`transform` と `opacity` だけをアニメする**(layout/paint を飛ばし GPU で走る)。`width`/`height`/`margin`/`top`/`left` は描画 3 段すべてを起こす。
- 親の CSS 変数で子の transform を駆動しない(全子のスタイル再計算を起こす)。要素の `transform` を直接更新する。
- 予定されたモーションは CSS(メインスレッド外で走る)、動的・割り込みは JS。アニメーションライブラリの `x`/`y` ショートハンドはハードウェア加速されないことがある(full の `transform` 文字列を使う)。

## 6. アクセシビリティ

- `prefers-reduced-motion: reduce`: 移動・spring・パララックスを短い opacity クロスフェードに置き換える(ゼロにはしない。理解を助ける opacity・色は残す)。
- hover 由来のモーションは `@media (hover: hover) and (pointer: fine)` で囲う(タッチはタップで hover を誤発火する)。

## 7. 検証(feel の確認)

- スローモーション(duration を 2–5 倍)・フレーム単位(DevTools の Animations パネル)で、色のクロスフェードの滑らかさ・easing の当たり・`transform-origin`・複数プロパティの同期を確認する。ジェスチャは実機で確認する。
- 翌日に新鮮な目で見直す(当日は気づかない timing の粗が見える)。モーションはコンポーネントの personality に合わせる(遊びは弾ませ、業務ダッシュボードは速く硬質に)。
