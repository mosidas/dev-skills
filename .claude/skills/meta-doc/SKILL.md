---
name: meta-doc
description: DESIGN.md(`.meta/DESIGN.md`)をスキルの定義(SSoT)から生成する(メタレベル)。DESIGN.md は現状の構造のみを表す生成物で、更新時は既存記述を全上書きする(履歴・判断は decisions/ に残す)。テンプレート(design-template.md)に沿い、構成要素・レイヤー構造・DFD・処理シーケンスを meta_extract.py の抽出と一致させる。スキルの追加・改名・状態機械の変更を DESIGN.md へ反映したいときに使う。
---

# meta-doc — DESIGN.md の生成(スキルの定義 → DESIGN)

人間向けの俯瞰ドキュメント `.meta/DESIGN.md` を、SSoT であるスキルの定義から生成するメタ部品。「コードが SSoT、説明は導出」(`../../../dev/skills/dev-core/references/source-driven.md`)をスキル群自身へ再帰適用したもの(principles.md §2)。

## 1. 方針(D-004)

- **DESIGN.md は現状の構造のみを表す**。設計判断の根拠・却下案・経緯・履歴は書かない。それらは `.meta/decisions/`(`D-###`)が正本で、DESIGN.md からは `D-###` で参照するだけ。
- **更新は全上書き**(差分追記をしない)。スキルの定義の現状を都度まるごと反映する。
- 構成はテンプレート `./templates/design-template.md` を正とする(概要 / 構成要素 / 相関図〔レイヤー構造・DFD〕/ 処理シーケンス)。図は Mermaid で書く。

## 2. 契約

- **入力**: dev-skills のルート(`--root`。省略時は自動探索)。
- **出力**: `.meta/DESIGN.md`(全上書き。差分を提示し、コミットはしない)。
- **不可侵**: `.meta/decisions/` を生成・改変しない(判断層は人間が手書きする)。

## 3. 参照(必読)

- 生成テンプレート(構成の正本): `./templates/design-template.md`
- スキル群自体の品質の設計原則(2 層分離): `../meta-core/references/principles.md` §2–3
- 判断層の正本(参照のみ): `../../../.meta/decisions/README.md`(索引。各 `D-###` の実体は同ディレクトリ)
- 自己適用の根拠: `../../../dev/skills/dev-core/references/source-driven.md`

## 4. ステップ

### Step 1: 構造的事実の抽出

```console
$ python3 ../meta-core/scripts/meta_extract.py [--root <ルート>]
```

- 出力 JSON(`parts`・`state_machines`・`inject_graph`・`agents`)が構成の素材の正本。DESIGN.md の記述は、この JSON と一致させる(食い違ったら JSON = スキルの定義を正とする)。

### Step 2: 判断参照の把握

- `.meta/decisions/` を読み、各判断の `D-###` と表題を把握する。概要で根拠に触れる箇所には、判断本文を転記せず `D-###` で参照を張る。

### Step 3: テンプレートに沿って全上書き生成

- `./templates/design-template.md` の節構成に沿って DESIGN.md をまるごと生成し、既存の DESIGN.md を全上書きする。
  - **概要**: スキル群の位置づけ・レイヤー構成・SSoT を文章で(根拠は `D-###` 参照)。
  - **原則**: `../meta-core/references/principles.md` の要約(2 つの品質の対象〔成果物の品質 / スキル群自体の品質〕・SSoT はスキルの定義・DESIGN の 2 層分離・依存規律・meta-* の構成)。正本へリンクし、要約である旨を明記する。
  - **構成要素**: 表(分類 / レイヤー / 種別 / 名前 / 役割)。Step 1 の JSON の `parts`・`scripts`・`agents`(・hook)を列挙する。分類 = dev/meta(family)、レイヤー = 0/1/2(layer)、種別 = スキル/エージェント/スクリプト/フック(kind)。基盤・コア・サブ・オプション等の位置づけは役割に自由記述する。
  - **相関図 / レイヤー構造**: Mermaid。dev 分類・meta 分類の**どちらもレイヤー構造**としてネスト subgraph で描き(dev: 3⊃2⊃1⊃0、meta: 1⊃0)、外→内の一方向依存を内包で示す。meta は dev と直交し、走査・生成を破線で結ぶ。
  - **相関図 / DFD**: Mermaid flowchart。プロセス(部品)は矩形、ドキュメント/成果物(spec.md・tasks.md・コード等)は平行四辺形のエンティティ、データストア(port・state.json)はシリンダ、外部(依頼・出荷)はスタジアムで区別する。ドキュメントは矢印ラベルでなくノードとして置く。**すべての矢印に説明文を付け**、**凡例を Mermaid 図の中に置く**(`subgraph LEGEND["凡例"]`)。
  - **処理シーケンス**: Mermaid sequenceDiagram を flow-*(composition)ごとに 1 つ。状態遷移・承認ゲート・部品呼び出しを示す。
- 命名・状態名・部品名・inject 先は JSON のとおりにする(手書きの推測で埋めない)。判断の根拠・履歴は書かない(D-004)。

### Step 4: 検証

- `../meta-core/scripts/meta_check.py` を実行し、参照切れ・状態名の取り違え・部品名の不実在が無いことを確認する(error 0)。
- 抽出 JSON と DESIGN.md の突合を目視で確認する(構成要素・状態・inject の件数一致、Mermaid のノード名が JSON と一致)。

### Step 5: 提示

- 変更差分をユーザーに提示して停止する。**コミットしない**(コミットはユーザーの明示操作)。

## 5. 規律(厳守)

- `decisions/` を生成・改変しない(判断層は人間の手書き)。
- DESIGN.md に判断・根拠・履歴を書かない。現状の構造だけを書き、根拠は `D-###` 参照にする(D-004)。
- 構成はスキルの定義(= meta_extract.py の JSON)を正とし、乖離は再生成(全上書き)で解消する。
- コミットはユーザーの明示操作。本部品は差分提示で停止する。
