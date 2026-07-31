# dev スキル群 構成(DESIGN)

> 現状の構造を表す生成物。`meta-doc` がスキルの定義(SSoT)から生成し、更新時は全上書きする。設計判断の根拠・履歴は [decisions/](./decisions/README.md)(`D-###`)にある。構成の詳細の正本は各 SKILL.md・スクリプトの docstring・`workflow.json` であり、本書と差異がある場合はそれらを正とする。

## 概要

`dev-skills` は汎用の開発スキル群である。SSoT をソースコードに置き(コードが SSoT、仕様は実装までの中間生成物)、単機能の部品スキルと、それを状態機械で束ねる composition で構成する。依存はオニオン型に外側から内側への一方向に限る(Layer 0: foundation 〜 Layer 3: extension)。SDD はこの部品群から組み立てる composition の一つ(flow-sdd)である。

これと直交する軸として、スキル群**自体**を構成するドキュメント(SKILL・references・templates・agents・scripts・`.meta`)の品質を担保する meta 分類(`meta-*`)を持つ。配布するスキルは用途グループ(`dev`・`writing`・`authoring`)に置き、配布しない `meta-*` は `.claude/skills` に置く(D-011)。利用側はグループを選んで導入できる(D-012)。meta 分類も同じくレイヤー構造をとる(レイヤー 0: meta-core / レイヤー 1: meta-check・meta-review・meta-doc)。

導入・削除は展開スクリプト `install.py` が用途グループの `skills/*`・`agents/*` を利用側の `.claude/` へハードコピーして行う(グループ外の `meta-*` は配布しない。グループ名を指定すればその群だけを導入する。利用側の明示操作)。設計判断の根拠は D-000(初版設計の全体像)・D-001(スキル群自体の品質と DESIGN 2 層分離)・D-004(本書のテンプレート化と全上書き方針)・D-005(品質の対象の呼称)・D-006(導入をハードコピーにし meta-* を配布しない)・D-007(多段オーケストレーションの禁止対象をエージェント主導に限定)・D-008(配布する部品をモデル自動起動の対象に置いたままにする)・D-009(恒久情報の配置に用語集を追加)・D-010(スクリプトの単体テストを tests/ に置き配布しない)・D-011(配布するスキルを `.claude` の外の用途グループへ置く)・D-012(汎用スキルを用途ごとのグループへ置き、グループ単位で導入する)を参照。

## 原則

スキル群自体の品質担保の設計原則。正本は [principles.md](../.claude/skills/meta-core/references/principles.md) で、本節はその要約である。

- **2 つの品質の対象(対象レベル / メタレベル)**: 生成する成果物(spec.md 等 = 成果物の品質)と、スキル群自体を構成するドキュメント(SKILL・references・templates・scripts・`.meta` 等 = スキル群自体の品質)を分けて担保する。前者は dev 分類(check.py・文書ゲート)、後者は meta 分類(`meta-*`)が担う。後者は前者のメタレベル(同じ品質哲学の自己適用)。層 0/1/2 とは別軸(D-005)。
- **SSoT はスキルの定義**: 実際に実行される定義(各グループの `skills/`・`agents/` と `workflow.json`)がスキル群の唯一の正本。DESIGN.md 等の俯瞰文書はその導出物で、食い違えばスキルの定義を正とする(「コードが SSoT、説明は導出」の自己適用)。
- **DESIGN の 2 層分離**: 現状の構造は DESIGN.md(生成・全上書き)、判断の根拠・履歴は `decisions/`(手書き)。DESIGN.md は判断を持たず `D-###` で参照する(D-004)。
- **依存規律(一方向)**: `dev-*`/`flow-*`/`ext-*` は `meta-*` を参照しない。`meta-*` が対象を走査・検査・生成するのは一方向(`meta-*` → 対象)。スキル群自体の品質に固有の観点は `meta-core` に置き `dev-core` に混ぜない。
- **`meta-*` の構成**: `meta-core`(原則・観点・スクリプトの正本)+ `meta-check`(機械検査)+ `meta-review`(観点レビュー)+ `meta-doc`(DESIGN 生成)。

## 構成要素

各グループのスキル・スクリプト・エージェント(役割の正本は各 SKILL.md の frontmatter・スクリプトの docstring)。hook を持つ拡張(Layer 3)は現在なし。

| 分類 | レイヤー | 種別 | 名前 | 役割 |
| ---- | -------- | ---- | ---- | ---- |
| dev | 0 | スキル | dev-core | 基盤。記法規約・恒久情報配置・オーケストレーション等の共有リファレンス群 + 決定論スクリプト(参照専用) |
| dev | 1 | スキル | dev-spec | サブ部品。壁打ちで公開インターフェース・データ構造の契約と EARS 受け入れ基準を spec.md 1 本に確定 |
| dev | 1 | スキル | dev-decompose | サブ部品。spec.md を実装タスク(tasks.md)へ分解し File Structure Plan を立てる |
| dev | 1 | スキル | dev-implement | コア部品。tasks.md をもとに TDD 実装(implementer/reviewer/debugger 協調) |
| dev | 1 | スキル | dev-release | コア部品。出荷可否判定(GO/NO-GO)とリリース計画 |
| dev | 1 | スキル | dev-check | オプション部品。read-only の整合性検査 |
| dev | 2 | スキル | flow-sdd | composition。SDD ワークフロー(spec→decompose→implement を承認ゲート付き状態機械で駆動。状態機械定義は workflow.json) |
| dev | 0 | エージェント | dev-implementer | 役割エージェント。1 タスクの TDD 実装 |
| dev | 0 | エージェント | dev-debugger | 役割エージェント。失敗タスクの根本原因の切り分けと最小修正 |
| dev | 0 | エージェント | dev-reviewer | 役割エージェント。敵対的判定器(文書ゲート・コード検証。観点別に並列起動) |
| dev | 0 | エージェント | dev-explorer | 役割エージェント。read-only 調査(ダイジェストのみ返す) |
| dev | 0 | エージェント | dev-author | 役割エージェント。中間生成物生成の隔離実行(自走ループ時) |
| dev | 0 | スクリプト | dev-core/scripts/state.py | 汎用状態機械エンジン(init/set-state/approve/show/status/scan・凍結) |
| dev | 0 | スクリプト | dev-core/scripts/check.py | 成果物の静的チェッカ(状態・spec.md・tasks.md の規約検査) |
| dev | 0 | スクリプト | dev-core/scripts/lib.py | state.py・check.py 共通ロジック(定義検証・パース・凍結) |
| dev | 0 | スクリプト | dev-core/scripts/ports.py | 知識 port の frontmatter 走査(inject 判定) |
| writing | 1 | スキル | japanese-writing | 日本語の開発ドキュメント・技術文書の作成規範(層別の references + 検査スクリプト) |
| authoring | 1 | スキル | skill-authoring | スキル(SKILL.md と参照ファイル)を新規作成・編集・リファクタするときの設計規範 |
| meta | 0 | スキル | meta-core | 基盤(メタ)。スキル群自体の品質担保の設計原則(principles.md)・観点カタログ(doc-perspectives.md)+ スクリプト(参照専用) |
| meta | 1 | スキル | meta-check | スキル群の機械的整合検査(read-only) |
| meta | 1 | スキル | meta-review | 観点カタログによる意味レビュー(read-only) |
| meta | 1 | スキル | meta-doc | 本書(DESIGN.md)をスキルの定義から生成 |
| meta | 0 | スクリプト | meta-core/scripts/meta_check.py | スキル群自体の機械的整合検査(参照実在・依存規律・状態整合等) |
| meta | 0 | スクリプト | meta-core/scripts/meta_lib.py | meta-* スクリプトの共通ロジック(frontmatter の YAML サブセット解析・スキル群の配置の走査) |
| meta | 0 | スクリプト | meta-core/scripts/meta_extract.py | DESIGN.md 生成用の構造抽出(部品・状態機械・inject・エージェント) |
| meta | 0 | スクリプト | meta-core/scripts/meta_loc.py | スキル群のコード行数の集計(領域ごと・種別ごと・read-only) |
| meta | 0 | スクリプト | meta-core/scripts/trigger_check.py | description のトリガ検査(肯定例・near-miss 否定例・近接衝突・read-only) |

## 相関図

### レイヤー構造

dev 分類・meta 分類はともにオニオン型のレイヤー構造をとり、依存は外側から内側への一方向(ネストした subgraph が内包 = 外側が内側を知り、内側は外側を知らないことを表す)。writing 分類・authoring 分類は単独のスキルで、レイヤー構造も相互の依存も持たない。meta 分類は配布する分類と直交し、対象を一方向に走査・生成する(破線)。

```mermaid
flowchart TD
    subgraph D3["dev・レイヤー 3 — extension(拡張スキル ext-* / 拡張 flow-* / port / hooks 配線)"]
        subgraph D2["dev・レイヤー 2 — composition(flow-sdd)"]
            subgraph D1["dev・レイヤー 1 — parts(dev-spec / dev-decompose / dev-implement / dev-release / dev-check)"]
                D0["dev・レイヤー 0 — foundation(dev-core + 役割エージェント)"]
            end
        end
    end
    W1["writing・レイヤー 1 — parts(japanese-writing)"]
    A1["authoring・レイヤー 1 — parts(skill-authoring)"]
    subgraph M1["meta・レイヤー 1 — parts(meta-check / meta-review / meta-doc)"]
        M0["meta・レイヤー 0 — foundation(meta-core)"]
    end
    M1 -. 走査・生成(一方向) .-> D3
    M1 -. 走査・生成(一方向) .-> W1
    M1 -. 走査・生成(一方向) .-> A1
```

### DFD

依頼から出荷までのデータの流れ。図形と線種の意味は図中の凡例に示す。

```mermaid
flowchart LR
    subgraph LEGEND["凡例"]
        direction LR
        lp["プロセス(部品スキル)"]
        ld[/"ドキュメント・成果物"/]
        ls[("データストア")]
        le(["外部エンティティ"])
        lf1["起点"] -->|実線: 成果物が流れる| lf2["終点"]
        lg1["起点"] -. 破線: 注入・駆動する .-> lg2["終点"]
    end

    req(["依頼"]) -->|依頼内容を渡す| spec["dev-spec"]
    spec -->|契約と受け入れ基準を書く| specmd[/"spec.md"/]
    specmd -->|仕様を読む| dec["dev-decompose"]
    dec -->|タスクと File Structure Plan を書く| tasksmd[/"tasks.md"/]
    tasksmd -->|タスクを読む| impl["dev-implement"]
    impl -->|実装とテストを書く| code[/"コード + テスト"/]
    code -->|出荷可否を判定する| rel["dev-release"]
    rel -->|リリース手順を書く| plan[/"リリース計画"/]
    plan -->|人間の承認を経て出す| out(["出荷"])

    port[("knowledge port<br/>docs/dev/ports")] -. 条件に合う知識を注入する .-> spec
    port -. 条件に合う知識を注入する .-> dec
    port -. 条件に合う知識を注入する .-> impl
    flow["flow-sdd"] -. 承認ゲート付きで部品を駆動する .-> spec
    flow -. 承認ゲート付きで部品を駆動する .-> dec
    flow -. 承認ゲート付きで部品を駆動する .-> impl
    flow -. 状態を読み書きする .-> state[("state.json")]
```

## 処理シーケンス

### flow-sdd

依頼を経路判定して作業単位に分け、各単位を仕様→分解→実装の順に承認ゲート付きで駆動する。承認はすべて人間。

```mermaid
sequenceDiagram
    actor U as ユーザー
    participant F as flow-sdd
    participant S as dev-spec
    participant D as dev-decompose
    participant I as dev-implement
    U->>F: SDD 開始(依頼)
    F->>F: 経路判定(作業単位へ分割)
    loop 各作業単位
        F->>S: 仕様化
        S-->>F: spec.md(spec-generated)
        F-->>U: spec.md 提示
        U->>F: 承認(gate spec → spec-approved)
        F->>D: タスク分解
        D-->>F: tasks.md(tasks-generated)
        F-->>U: tasks.md 提示
        U->>F: 承認(gate tasks → tasks-approved)
        F->>I: 実装(implementing)
        I-->>F: コード + テスト(completed)
    end
    F->>F: PR 作成・CI 追従(マージは人間)
```
