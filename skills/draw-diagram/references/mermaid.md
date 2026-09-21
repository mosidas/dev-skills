# `.mmd` の書き方

## 1. 基本規則

- ノード id は英数字と `_` だけで構成する(`render.py` が `[A-Za-z0-9_]+` を id として抽出する)。
- ラベルは日本語で短く記述する。ノードは `id[ラベル]`・`id(ラベル)`・`id{ラベル}`・`id([ラベル])` のいずれかの形で宣言する。
- 関連するノードは `subgraph 名前 ... end` でグループ化する。
- コメントは `%%` で記述する。

## 2. 種類ごとの構図

### flowchart

流れは左から右へ書く。`flowchart LR` を使い、処理の段階が複数あるときは、同じ段の要素を縦にそろえる。

```
flowchart LR
    Client[クライアント] -->|読み取り| Cache[キャッシュ]
    Cache -->|ミス時のみ| DB[DB]
```

矢印は `-->`・`---`・`==>`・`-.->`・`-.-` のいずれかを使う。ラベルは `-->|ラベル|` の形で辺に付ける。複数のノードから同じ辺を引くときは `A & B --> C` の並列記法を使う。

### sequenceDiagram

参加者を `participant id as ラベル` で宣言し、メッセージを `A->>B: ラベル` の形で書く。矢印は `->`・`-->`・`->>`・`-->>` を使う。

```
sequenceDiagram
    participant Client as クライアント
    participant API as API サーバー
    Client->>API: リクエスト送信
    API-->>Client: レスポンス返却
```

### stateDiagram-v2

状態遷移は `A --> B` の形で書き、遷移条件は `A --> B: 条件` のようにコロンの後に記述する。開始・終了の擬似状態は `[*]` で書く。

```
stateDiagram-v2
    [*] --> Idle
    Idle --> Running: 開始
    Running --> Done: 完了
    Done --> [*]
```

`render.py` は `[*]` を、左端(遷移元)なら id `_start`、右端(遷移先)なら id `_end` として扱う。対応する SVG 側は `data-id="_start"`・`data-id="_end"` を指定する(`svg.md` の「照合のための属性」参照)。

### classDiagram・erDiagram

`render.py` の照合対象外である。整形式検査と禁止要素の検査だけを行い、ノード・辺の対応は照合しない。

## 3. アーキテクチャ図・ポンチ絵

構造だけを `flowchart` と `subgraph` で書く。配置(座標)と装飾(色・影・アイコン)は SVG 側で決める。`.mmd` には「何がある」「何につながる」だけを書き、見た目を書き込まない。

```
flowchart LR
    subgraph Frontend
        Web[Web クライアント]
    end
    subgraph Backend
        API[API サーバー]
        DB[(DB)]
    end
    Web -->|HTTPS| API
    API -->|SQL| DB
```

## 4. ノード数の目安

1 つの図のノード数が 12 を超えたら、図を分ける。分けられないほど密な図は、読み手が構造を追えない図である。

## 5. render.py が拾う記法の範囲

- ノード宣言: `id[...]`・`id(...)`・`id{...}`・`id([...])`(`participant id as ラベル`・`actor id as ラベル` は sequenceDiagram のみ)。sequenceDiagram では `participant`・`actor` 行以外の角括弧(メッセージ本文の `A->>B: fetch data[1]` など)はノード宣言として扱わない。
- 辺: flowchart は `-->`・`---`・`==>`・`-.->`・`-.-`(途中の `|ラベル|` は無視して両端の id だけを見る)。stateDiagram-v2 と sequenceDiagram は `-->`・`->`・`->>`・`-->>` のあとのコロン区切りラベルを含めて見る。1 行に `A --> B --> C` のように辺が連なるときは、そのすべてを辺として拾う。
- flowchart の `A & B --> C`(または `A --> B & C`)の並列記法は、`&` で結ばれた各ノードと反対側のノードとの直積を辺として拾う。
- stateDiagram-v2 の `[*]` は、遷移元なら id `_start`、遷移先なら id `_end` として辺・ノードに登録する。
- `flowchart`・`graph`・`stateDiagram-v2`・`subgraph`・`end`・`direction` で始まる行と `%%` のコメント行は、ノード宣言・辺の抽出の対象から外れる(図の種類の判定と読み飛ばしにだけ使う)。
