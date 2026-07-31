# port サンプル集

dev スキル群の port(拡張点)のサンプルと雛形。**この場所のファイルは実行時に読まれない**。利用側プロジェクトの `docs/dev/ports/` へコピーし、プロジェクトに合わせて編集して使う。

## 1. port の仕組み

部品は「port があればそれに従い、なければ部品内のデフォルトで動く」という規約を持つ。port の共通ルートは利用側プロジェクトの `docs/dev/ports/` で、**ルート以下のフォルダ構成は自由**(本サンプル集の階層は整理の一例にすぎない)。規約の正本は dev-core の [ports リファレンス](../dev/skills/dev-core/references/ports.md)。

- **識別は frontmatter の `name`**(ツリー内で一意)で行い、配置パスに意味を持たせない。各ファイルは frontmatter で注入先を宣言する: `inject` = 注入先スキル名のリスト、`condition` = `常時` または自然言語の条件。
- スキルは全ファイルの frontmatter だけを再帰的に一括走査し、自分が inject に含まれ条件に該当する port のみ本文を読む。tasks.md の `_Knowledge:` 注記は最優先の明示指定。
- port は概念上 2 種類ある(仕組みは共通): **差し替え port** = 部品のデフォルト手順・データを固定 name で置き換える(例: `hearing-questions` は dev-spec のヒアリングを差し替える)/ **知識 port** = 作業内容に応じて条件付きで注入される専門知識。

## 2. フォルダ構成

```
ports/
├── templates/     テンプレート(新規 port の雛形)
├── swappable/     差し替えポート(部品デフォルトの差し替え)
└── knowledge/     知識ポート(ジャンル別)
    ├── crosscutting/  横断・常時
    └── domain/        機能・ドメイン・手法
```

### 2.1. templates/(テンプレート)

| ファイル                    | 用途                                                       |
| --------------------------- | ---------------------------------------------------------- |
| `templates/knowledge-port.md` | 知識 port の雛形。`docs/dev/ports/<ジャンル>/<name>.md` にコピーして書く |
| `templates/swappable-port.md` | 差し替え port の雛形。固定 name は部品の SKILL.md「契約」節を見る |
| `templates/lang.md`           | 言語別知識 port の雛形(`lang-<言語>.md` に改名して使う)   |

### 2.2. swappable/(差し替えポート)

| ファイル                       | 差し替え対象                                             | 注入先(frontmatter `inject` が正本) |
| ------------------------------ | -------------------------------------------------------- | ------------------------------------ |
| `swappable/hearing-questions.md` | dev-spec の仕様化ヒアリング質問セット(Step 2)を差し替える | dev-spec(常時)                     |
| `swappable/impact-analysis.md`   | dev-check・dev-decompose・dev-implement の既定の影響範囲特定手順(読解による判断)を機械的手段に差し替える | dev-check・dev-decompose・dev-implement(常時) |

### 2.3. knowledge/(知識ポート)

| ファイル                                     | 用途                                                   | 注入先(frontmatter `inject` が正本)                              |
| -------------------------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------- |
| `knowledge/crosscutting/principles.md`         | プロジェクト原則(テスト方針・設計方針・規約・標準準拠) | dev-implement・dev-spec・dev-decompose・dev-check・dev-release(常時) |
| `knowledge/crosscutting/review-perspectives.md` | レビュー観点の追加・上書き                             | dev-implement・dev-release・dev-check(常時)                       |
| `knowledge/domain/auth-session.md`             | 認証・セッション管理(ログイン成立・リロード耐性)       | dev-spec・dev-implement(認証を含む作業のとき)                     |
| `knowledge/domain/frontend-design.md`          | GUI 作業時の視覚設計(正本への準拠と方向づけ)           | dev-implement・dev-spec(GUI を持つ作業のとき)                     |
| `knowledge/domain/motion-design.md`            | UI モーション・アニメーションの設計判断と craft         | dev-spec・dev-implement(GUI のモーションを含む Web 作業のとき)     |
| `knowledge/domain/migration.md`                | 置換・廃止・移行の規律(Strangler Fig・使用ゼロ確認)    | dev-spec・dev-implement(置換・廃止・移行を含む作業のとき)          |

## 3. カスタマイズの指針

- **本サンプル集はあくまで出発点(サンプル)である**。拡張・ワークフローが利用側プロジェクトに同名の port を生成・更新することがあり、その場合は生成された port(利用側資産)が正本になる。本サンプルとの整合を保つ必要はない。
- port はプロジェクト側の資産として Git 管理し、PR レビューの対象にする(Docs-as-Code)。
- 知識 port は簡潔に保つ(注入されるたびにコンテキストを消費する)。プロジェクトに関係しない項目は削る。
- 組織・顧客固有の内容(固有名詞・独自規約・独自質問)はコピー後にプロジェクト側で追記する。このサンプル集自体は汎用に保つ。
