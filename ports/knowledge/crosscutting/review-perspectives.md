---
name: review-perspectives
description: レビュー観点の追加・上書き(プロジェクト固有観点)
inject:
  - dev-implement
  - dev-release
  - dev-check
condition: 常時
---

# レビュー観点の追加(プロジェクト固有)

観点カタログ(dev-core の review-perspectives.md)へのプロジェクト固有観点の追加・上書きの雛形。**同名の観点があればこの port を優先する**。dev-reviewer を使う全部品(dev-implement の最終検証・dev-release の出荷可否パネル・dev-check)が参照する。

追加した観点は、呼び出し側が「1 観点 = 1 起動」で dev-reviewer に注入する。エントリの形式はカタログと同じ(対象・重点・返却契約は共通)。以下の `motion` は具体例で、`<...>` の入ったエントリは自プロジェクトの観点を書くための雛形である。

## 観点: motion(UI モーションの craft)

- 追加条件: GUI のアニメーション・モーション・ジェスチャを追加・変更するとき。
- 対象: モーション関連のコード(CSS transition / animation、spring 設定、ジェスチャ・ドラッグ処理)。
- 重点(二値で判定する): (1) キーボード起動の操作にアニメが付いていない。(2) UI に `ease-in` を使わず、弱い既定 easing でなくカスタム曲線を使う。(3) UI アニメが 300ms 未満。(4) `scale(0)` から入場していない(`scale(0.9–0.97)` + `opacity`)。(5) ポップオーバーが trigger 起点(`transform-origin`。モーダルは中央で除外)。(6) 押下要素に `:active` の即時フィードバックがある。(7) 素早く連続発火する UI が `@keyframes` でなく CSS transition(割り込み可能)。(8) アニメ対象が `transform`/`opacity` に限られる(`width`/`height`/`margin`/`top`/`left` を動かさない)。(9) `prefers-reduced-motion` と hover ゲート(`@media (hover: hover)`)がある。(10) 入退場が非対称タイミングで、spring の bounce が過剰でない。
- 根拠: `motion-design` 知識 port、[emilkowalski/skills](https://github.com/emilkowalski/skills)(MIT)。

## 観点: <観点名(例: internal-api-guideline)>

- 追加条件: <どんな作業のときにこの観点を起動するか(例: 社内 API を追加・変更するとき)>
- 対象: <検査対象(例: 変更されたエンドポイント定義とハンドラ)>
- 重点: <検査の起点となるチェック項目を列挙。測定可能・二値判定可能な形で書く>
- 根拠: <準拠する社内規約・標準の名前と所在>

## 観点: <観点名 2>

- 追加条件: ...
- 対象: ...
- 重点: ...
- 根拠: ...
