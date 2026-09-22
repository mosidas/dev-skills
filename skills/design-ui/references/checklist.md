# 実装の品質床

機械的に確認できる規則の一覧である。実装後に、この一覧に沿って点検する。1〜2 節は媒体を問わない共通の規則、3〜8 節は Web 固有の規則である。ネイティブアプリ固有の規則は `native.md` が定める。

## 1. アクセシビリティ(共通)

- 通常サイズの文字のコントラストは 4.5:1 以上、大きな文字(24px 通常または 18.66px 太字以上)は 3:1 以上を確保する。
- アイコンだけのボタンには、読み上げ用の名前(Web は `aria-label`)を付ける。装飾のアイコンは読み上げの対象から外す(Web は `aria-hidden="true"`)。
- 色だけで意味を示さない。アイコン・形・文言のいずれかを併用する。
- 画像には代替テキストを付ける。装飾画像は読み上げの対象から外す(Web は `alt=""`)。

## 2. 状態とモーション(共通)

- hover・focus・disabled・loading・error・empty の状態を、実装時にすべて用意する。ネイティブアプリでは hover を除く 5 状態を用意する。
- 長いコンテンツ・空の配列を想定して、レイアウトが崩れないことを確認する。
- `prefers-reduced-motion`(ネイティブアプリは OS のモーション低減設定)を尊重し、動きを抑えた代替か無効化を用意する。

## 3. Web: 操作とフォーカス

- 操作には `<button>`、ページ遷移には `<a>` を使う。`<div onClick>` を操作の代わりにしない。
- 操作対象には `:focus-visible` で可視のフォーカスを与える。
- `outline: none` を、代替のフォーカス表示を用意せずに使わない。
- 複合コントロールは `:focus-within` でグループ化する。
- 固定ヘッダー・フッター・オーバーレイが、フォーカス中の要素を覆わないようにする。

## 4. Web: タッチとフォーム

- タップ領域は 44×44px 以上を確保する。視覚上のアイコンが小さいときは、当たり判定だけ広げる。
- ラベルは常時表示にする。placeholder だけをラベルの代わりにしない。
- エラーは該当フィールドの脇に表示し、送信時に最初のエラーへフォーカスを移す。
- `onPaste` で貼り付けを止めない。
- 適切な `autocomplete`・`inputmode`・`type`(email、tel、url、number)を指定する。

## 5. Web: アニメーション

- アニメーションは `transform` と `opacity` を中心に、コンポジタで処理できる性質のプロパティに絞る。
- `transition: all` を使わず、対象のプロパティを列挙する。

## 6. Web: 記号と数字

- 省略は `...` でなく `…` を使う。
- 数値の桁をそろえる場面では `font-variant-numeric: tabular-nums` を使う。
- 単位の前には改行させたくない空白(`&nbsp;` など)を入れる。
- 日付・数値・通貨は `Intl.DateTimeFormat`・`Intl.NumberFormat` で整形し、書式を決め打ちしない。

## 7. Web: レイアウト

- 横スクロールを、意図した領域以外に発生させない。`overflow-x: hidden` で防ぐ場合は、原因側の崩れも直す。
- flex の子要素にはテキストの省略を許すため `min-width: 0` を指定する。
- ライトとダークの両方のテーマで、コントラストと境界線の視認性を個別に確認する。

## 8. Web: パフォーマンス

- 画像には `width`・`height` を明示し、読み込み中のレイアウトのずれ(CLS)を防ぐ。
- ビューポート外の画像は `loading="lazy"` にする。上部の主要な画像は先読みする。
- 50 件を超える一覧は仮想化するか、`content-visibility: auto` で描画範囲を絞る。

## 9. 出典

- [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines)(MIT。`vercel-labs/agent-skills` の `skills/web-design-guidelines` 経由)
- [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)(MIT)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)(Apache-2.0)、`skill/reference/craft-floor.md`
