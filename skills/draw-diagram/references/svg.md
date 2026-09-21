# SVG の書式

## 1. 寸法

`viewBox` で寸法を決める。`width`・`height` は `viewBox` と同じ数値を指定し、埋め込み先で拡大縮小できるようにする。箱の左上・幅・高さは 20px 単位のグリッドにそろえる。辺の端点はマーカーの余白分(2px 程度)を引いてよい。文字の基準線は箱の中央にそろえる。

## 2. 色とフォント

色トークンは `<style>` 内の `:root` に定義し、`prefers-color-scheme: dark` の内側で上書きする。

```css
:root { --fg: #1f2328; --bg: #ffffff; --accent: #0969da; --muted: #6e7781; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #e6edf3; --bg: #0d1117; --accent: #58a6ff; --muted: #8b949e; }
}
```

フォントは `system-ui, "Hiragino Sans", "Noto Sans JP", sans-serif` を指定する。文字サイズは本文が 11〜13px の範囲に収まるようにする。

## 3. 矢印マーカー

矢印の先端は `marker` 要素で定義し、`fill="context-stroke"` を指定して辺の線色を継承させる。

```xml
<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/>
  </marker>
</defs>
```

辺の要素には `marker-end: url(#arrow)` を指定する。

## 4. アクセシビリティ

ルートの `<svg>` に `role="img"` と `aria-label`(図が伝える内容を 1 文で要約したもの)を指定する。

## 5. 禁止事項

次を `render.py` が検出する。検出されると exit code が 1 になる。

- `<script>` 要素
- `<foreignObject>` 要素
- `<image>` 要素
- `href`・`xlink:href` 属性の外部参照(`http://`・`https://`)
- `style` 属性・`<style>` 要素内の `url(http://...)`・`url(https://...)`

## 6. 照合のための属性

`.mmd` と対応させるため、次の 2 種類の属性を指定する。

- ノードの図形要素に `data-id="<.mmd のノード id>"` を指定する(`<rect>`・`<circle>` など、ノードを表す図形 1 つにつき 1 つ)。
- 辺を表す要素(通常は `<path>`)に `data-edge="<src>-><dst>"` を指定する。`src`・`dst` は `.mmd` のノード id と一致させる。
- stateDiagram-v2 の開始・終了の擬似状態 `[*]` は、`data-id="_start"`(遷移元の `[*]`)・`data-id="_end"`(遷移先の `[*]`)を指定する図形で表す。辺の `data-edge` も同じ id を使う(例: `data-edge="_start->Idle"`)。

`render.py` はこの 2 種類の属性を `.mmd` から抽出した id・辺の集合と突き合わせ、過不足を報告する。

## 7. HTML 閲覧ページ

次のいずれかに当てはまるときだけ、SVG を内包した HTML 閲覧ページを作る。図そのものは、照合済みの SVG をそのまま使う。

- 拡大縮小して細部を読む必要がある。
- 複数案を切り替えて比較する必要がある。
- 複数の図を 1 ページにまとめて並べる必要がある。

複数の図を 1 ページに並べるときは、貼る前にその図の `id` と class に図ごとの接頭辞(`arrow-cache-read`・`box-cache-read` など)を付け、`<style>` の衝突を避ける。

雛形(CSS のみ、スクリプトは使わない)。

```html
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>図</title>
<style>
  body { margin: 0; padding: 24px; font-family: system-ui, "Hiragino Sans", "Noto Sans JP", sans-serif; }
  .diagram { max-width: 960px; margin: 0 auto 32px; }
  .diagram svg { width: 100%; height: auto; }
  figcaption { font-size: 13px; color: #6e7781; margin-top: 8px; }
</style>
</head>
<body>
  <figure class="diagram">
    <!-- ここに SVG の中身をそのまま貼り付ける -->
    <figcaption>キャプション</figcaption>
  </figure>
</body>
</html>
```
