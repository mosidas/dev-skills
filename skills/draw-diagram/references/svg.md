# SVG の書式

## 1. 寸法

`viewBox` で寸法を決める。`width`・`height` は `viewBox` と同じ数値を指定し、埋め込み先で拡大縮小できるようにする。箱の左上・幅・高さは 20px 単位のグリッドにそろえる。辺の端点はマーカーの余白分(2px 程度)を引いてよい。文字の基準線は箱の中央からフォントサイズの約 3 分の 1 だけ下げる。

## 2. 色とフォント

色トークンは `<style>` 内の `:root` に定義し、`prefers-color-scheme: dark` の内側で上書きする。

```css
:root { --fg: #1f2328; --bg: #ffffff; --accent: #0969da; --muted: #6e7781; --panel: #f6f8fa; --hot-bg: #ddf4ff; --old-bg: #e7ebef; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #e6edf3; --bg: #0d1117; --accent: #58a6ff; --muted: #8b949e; --panel: #161b22; --hot-bg: #0f2a4d; --old-bg: #2a2f36; }
}
```

フォントは `system-ui, "Hiragino Sans", "Noto Sans JP", sans-serif` を指定する。文字サイズは本文が 11〜13px の範囲に収まるようにする。

## 3. 塗り分け

要素の区別は枠線の色でなく塗りで付ける。枠線の色だけを変える区別はしない。

塗りは 3 種までにする。

- 既定は `--bg` で塗る。説明の対象となる要素に使う。
- 強調は `--hot-bg` で塗り、枠線を `--accent` にする。図の主張が指す要素に使う。
- 退役・外部は `--old-bg` で塗る。置き換え対象や図の外側にある要素に使う。

塗りどうしの差は小さい(`--hot-bg` と `--bg` は 1.14:1)ので、強調は塗りと枠線色(`--accent`)を必ず併用する。塗りだけで区別しない。

ノード名の文字は塗りに関わらず `--fg` にする。`--muted` は辺のラベルと補足の行(`.label`)に限る。

グループ枠(`subgraph` に対応する枠)は `--panel` の薄い塗りに点線の枠、または塗り無しの点線にする。グループが並ぶ・入れ子になるときは、片方を塗り無しにして区別する。

既定以外の塗りを使ったら、凡例に塗りの意味を書く。塗りの見本の小さな `rect` と 1 文を付記する。

意味の無い塗り(飾り)は使わない。

## 4. 矢印マーカー

矢印の先端は `marker` 要素で定義し、`fill="context-stroke"` を指定して辺の線色を継承させる。

```xml
<defs>
  <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
    <path d="M0,0 L10,5 L0,10 z" fill="context-stroke"/>
  </marker>
</defs>
```

辺の要素には `marker-end: url(#arrow)` を指定する。

## 5. アクセシビリティ

ルートの `<svg>` に `role="img"` と `aria-label`(図が伝える内容を 1 文で要約したもの)を指定する。

## 6. 禁止事項

次を `render.py` が検出する。検出されると exit code が 1 になる。

- `<script>` 要素
- `<foreignObject>` 要素
- `<image>` 要素
- `href`・`xlink:href` 属性の外部参照(`http://`・`https://`)
- `style` 属性・`<style>` 要素内の `url(http://...)`・`url(https://...)`

## 7. 照合のための属性

`.mmd` と対応させるため、次の 2 種類の属性を指定する。

- ノードの図形要素に `data-id="<.mmd のノード id>"` を指定する(`<rect>`・`<circle>` など、ノードを表す図形 1 つにつき 1 つ)。
- 辺を表す要素(通常は `<path>`)に `data-edge="<src>-><dst>"` を指定する。`src`・`dst` は `.mmd` のノード id と一致させる。
- stateDiagram-v2 の開始・終了の擬似状態 `[*]` は、`data-id="_start"`(遷移元の `[*]`)・`data-id="_end"`(遷移先の `[*]`)を指定する図形で表す。辺の `data-edge` も同じ id を使う(例: `data-edge="_start->Idle"`)。

`render.py` はこの 2 種類の属性を `.mmd` から抽出した id・辺の集合と突き合わせ、過不足を報告する。

## 8. HTML 閲覧ページ

次のいずれかに当てはまるときだけ、SVG を内包した HTML 閲覧ページを作る。図そのものは、照合済みの SVG をそのまま使う。

- 拡大縮小して細部を読む必要がある。
- 複数案を切り替えて比較する必要がある。
- 複数の図を 1 ページにまとめて並べる必要がある。

複数の図を 1 ページに並べるときは、貼る前にその図の `id` と class に図ごとの接頭辞(`arrow-cache-read`・`box-cache-read` など)を付け、`<style>` の衝突を避ける。要素型セレクタ(`text`・`svg`)と `:root` は使わず、接頭辞付きの class と図のルート要素(`#fig-<basename>`)へのセレクタに置き換える。

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
  <figure class="diagram" id="fig-cache-read">
    <!-- ここに SVG の中身をそのまま貼り付ける -->
    <figcaption>キャプション</figcaption>
  </figure>
</body>
</html>
```
