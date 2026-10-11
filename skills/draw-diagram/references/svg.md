# SVG の書式

## 1. 寸法と配置

`viewBox` で寸法を決める。`width`・`height` は `viewBox` と同じ数値を指定し、埋め込み先で拡大縮小できるようにする。箱の左上・幅・高さは 20px 単位のグリッドにそろえる。辺の端点はマーカーの余白分(2px 程度)を引いてよい。文字の基準線は箱の中央からフォントサイズの約 3 分の 1 だけ下げる。

- 図の要素と凡例を合わせた範囲を `viewBox` の中央に置き、上下の余白どうし・左右の余白どうしをそろえる。
- 凡例と図の要素の間を 40px(グリッド 2 つ)以上空ける。
- 始点のノードは、流れの上流の端(LR なら左、TB なら上)に配置する。

## 2. 色とフォント

色トークンは `<style>` 内の `:root` に定義し、`prefers-color-scheme: dark` の内側で上書きする。

```css
:root { --fg: #1f2328; --bg: #ffffff; --accent: #0969da; --muted: #6e7781; --panel: #f6f8fa; --hot-bg: #ddf4ff; --old-bg: #e7ebef; --danger: #cf222e; --danger-bg: #ffebe9; }
@media (prefers-color-scheme: dark) {
  :root { --fg: #e6edf3; --bg: #0d1117; --accent: #58a6ff; --muted: #8b949e; --panel: #161b22; --hot-bg: #0f2a4d; --old-bg: #2a2f36; --danger: #f85149; --danger-bg: #3c1618; }
}
```

フォントは `system-ui, "Hiragino Sans", "Noto Sans JP", sans-serif` を指定する。文字サイズは本文が 11〜13px の範囲に収まるようにする。

文字幅は次の目安で見積もる。system-ui 13px の本文は全角 1 文字が約 13px、半角が約 7px である。11px の補足は全角が約 11px、半角が約 6px である。半角の目安は小文字の場合であり、大文字・数字は全角の約 3 分の 2(13px で約 9px、11px で約 7px)で見積もる。枠の題(`.title`、12px)は全角を 12px、半角を 6px で見積もる。見積もった幅が箱の幅を超えたら、次の順に対処する。

- 主ラベルと補足(`.label`)の 2 行に分ける。
- 箱を 20px グリッドの単位で広げる。
- PNG で目視する。

見積もりと箱の幅の差が片側 1 文字分未満のときは、PNG で目視して判断する。辺のラベルと枠の題も、ほかの箱や線に重ならないかを同じ手順で確かめる。

## 3. 塗り分け

要素の区別は枠線の色でなく塗りで付ける。枠線の色だけを変える区別はしない。

塗りは 4 種までにする。

- 既定は `--bg` で塗る。説明の対象となる要素に使う。
- 強調は `--hot-bg` で塗り、枠線を `--accent` にする。図の主張が指す要素に使う。
- 退役・外部は `--old-bg` で塗る。置き換え対象や図の外側にある要素に使う。
- 脅威は `--danger-bg` で塗り、枠線を `--danger` にする。攻撃者・攻撃・障害など、図の対象を脅かす要素に使う。

脅威を表す辺は線色を `--danger` にする。

塗りどうしの差は小さい(`--hot-bg` と `--bg` は 1.14:1、`--danger-bg` と `--hot-bg` は 1.01:1)ので、強調と脅威は塗りと枠線色(`--accent`・`--danger`)を必ず併用する。塗りだけで区別しない。

ノード名の文字は塗りに関わらず `--fg` にする。`--muted` は辺のラベルと補足の行(`.label`)に限る。

グループ枠(`subgraph` に対応する枠)は `--panel` の薄い塗りに点線の枠、または塗り無しの点線にする。グループが並ぶ・入れ子になるときは、片方を塗り無しにして区別する。

ファイル・DB は塗りや色でなく円筒の形で示す。円筒は `<path class="box" data-id="…">` で描く。箱を (x, y, w, h)、楕円の縦半径を r=10 とすると、パスの雛形は次のとおりである。build の `../../build/references/flow.svg` の `state` が同じ形である。

```
M x,y+r v h-2r a w/2,r 0 0 0 w,0 v -(h-2r) a w/2,r 0 0 0 -w,0 a w/2,r 0 0 0 w,0
```

凡例は、塗り・線色に意味を持たせた図にだけ付ける。主体を枠、処理をノードで描く形式では、主体を枠の題が示すため、塗りに意味を持たせず凡例も付けない。グループ枠の塗りと点線は隣り合う枠を見分けるためのものであり、凡例の対象に含めない。

凡例を付ける図では、次の規則で書く。

- 凡例の各項目は、見本の小さな図形と、その要素が何であるかを述べる 1 文の対にする。
- 文には、見本を見れば分かること(塗り・線種・形・色名)を書かない。「塗り(青):」「点線の枠:」「(赤)」のような前置きや補足も書かない。
  - Before: 「塗り: 読み取りがここで完結する要素」
  - After: 「読み取りがここで完結する要素」
- 括弧の補足(「(当社の SNS)」)は、削除しても図から読み取れるなら付けない。ノードのラベル・キャプションも同じ。
- 項目は、類似の要素(同じ塗りの種類、同じ役割)を隣り合わせて並べる。

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
