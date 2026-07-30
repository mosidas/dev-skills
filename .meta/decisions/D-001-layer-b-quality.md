# D-001: レイヤー B 品質のため `.claude` を SSoT とし、DESIGN を 2 層分離、`meta-*` を導入(2026-07-14)

## 背景

スキル群自体を構成するドキュメント(レイヤー B。principles.md §1)の品質を担保する機構がなかった。SSoT 分散 + ファイル契約という設計のため、局所的に正しくても全体で不整合が起きるのが最大の失敗モードで、上流工程を spec 構成へ再編した際の状態名・ゲート名・参照の追随でこのリスクが顕在化した。

## 決定

1. `.claude/` 配下の実体を SSoT とし、人間向けの `.meta/DESIGN.md` はそこからの導出物とする。
2. `DESIGN.md` を構造層(`.claude` から導出。`meta-doc` が生成)と判断層(手書き SSoT。本記録)に分ける。
3. レイヤー B 用スキル `meta-*`(`meta-core` / `meta-check` / `meta-review` / `meta-doc`)を新設する。まず `meta-core/references` に原則(`principles.md`)と観点カタログ(`doc-perspectives.md`)を定義する。
4. `dev-*` は `meta-*` を参照しない。レイヤー B 固有の観点は `meta-core` 側に持ち、`dev-core` に混ぜない。

## 却下した選択肢

- **`DESIGN.md` 全体を生成物にする**: 設計判断の根拠(トレードオフ・見送り)は `.claude` の手順本文から導出できず、生成物化すると失われる。2 層分離で回避した。
- **判断根拠を各 SKILL に埋め込む**: SKILL が肥大化し、手順(頻繁に更新)と意思決定(安定)の寿命の違いで管理が混線する。別 SSoT(本記録)に分離した。
- **レイヤー B 観点を `dev-core/review-perspectives.md` に相乗りさせる**: `dev-*` が inject・参照で読めてしまい混線する。`meta-core` に分離した。

## 帰結

- `meta-core/references/principles.md`(設計原則)と `doc-perspectives.md`(種別別レビュー観点)を定義した。
- `meta-check`(機械整合検査)・`meta-doc`(DESIGN 構造層の生成)・`meta-review`(観点レビュー)の SKILL は後続で実装する。
- `DESIGN.md` の判断記述(マイルストーンの経緯等)を判断層へ移設し、`DESIGN.md` を構造層に絞る作業は `meta-doc` 導入時に行う(それまで暫定的に現状維持)。

## 再検討条件

`meta-*` の維持コストが担保効果を上回る場合、または `.claude` からの `DESIGN.md` 生成が構造層だけでは人間の理解に不足すると判明した場合。
