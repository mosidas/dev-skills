# dev-skills

Claude Code 向けの汎用スキル群。開発の部品(dev-spec: 壁打ちで契約と受け入れ基準を確定 / dev-decompose / dev-implement / dev-release)とそれらを束ねる SDD ワークフロー(flow-sdd)、拡張バンドル(dev/extensions/)に加えて、日本語の技術文書の作成規範(japanese-writing)とスキルの設計規範(skill-authoring)を用途ごとのグループで持つ。

設計思想・レイヤー構成・規律は [.meta/DESIGN.md](.meta/DESIGN.md) を参照。

## 構成

スキルは用途グループごとのディレクトリに置く。`install.py core` は配布ルート直下で `skills/` を持つディレクトリを用途グループとみなし、その配下だけを配布する(D-011)。利用側はグループ名を指定して必要な群だけを導入できる(D-012)。

```
dev-skills/
├── CLAUDE.md                    # 言語規約など最小限のプロジェクト指示
├── install.py                   # 導入スクリプト(コアのコピー・拡張バンドルの展開)
├── .meta/                       # 設計文書
├── dev/                         # 用途グループ: 開発スキル(配布する)
│   ├── group.json               # このグループの検査規約(meta-* が読む。配布しない)
│   ├── agents/                  # 役割エージェント(Layer 0)
│   ├── skills/
│   │   ├── dev-core/            # Layer 0: 共有リファレンス + スクリプト
│   │   ├── dev-<部品名>/        # Layer 1: 各部品(SKILL.md + templates/)
│   │   └── flow-<ワークフロー名>/ # Layer 2: composition(SKILL.md + 状態機械定義)
│   ├── ports/                   # 知識 port のサンプル(配布しない)
│   └── extensions/              # Layer 3: 拡張バンドル(<バンドル群>/ 配下に ext-*・flow-*)
│       └── guardrails/          #   安全制約を hook で強制するバンドル群(ext-dev-guardrails)
├── writing/                     # 用途グループ: 文書作成(配布する)
│   └── skills/japanese-writing/ # 日本語の開発ドキュメント・技術文書の作成規範
├── authoring/                   # 用途グループ: スキル作成(配布する)
│   └── skills/skill-authoring/  # スキルの設計規範
├── .claude/
│   └── skills/
│       └── meta-<部品名>/       # スキル群自体の検査・生成(配布しない。D-006)
└── tests/                       # 同梱スクリプトの単体テスト(配布しない。D-010)
```

`meta-*` は dev-skills 自身のスキル群を検査・生成する保守用の道具で、利用側へは配布しない。Claude Code がこのリポジトリで読み込む場所である `.claude/skills/` に置き、用途グループの外に出すことで配布対象から外す。

グループごとに異なる前提(部品名らしさ・状態名らしさ・レイヤーの割り当て)は、グループ直下の `group.json` が宣言する。宣言を持たないグループは既定で成立し、`meta-*` は特定のグループの構造を前提にしない(D-013)。

port(`ports/`)と拡張バンドル(`extensions/`)はグループの機構であり、グループ配下に置く。どちらも dev グループの仕組みで、`writing`・`authoring` は持たない。`skills/`・`agents/` の外にあるため配布されず、`meta-*` はグループ配下を走査する(D-014)。

## 導入

利用側プロジェクトへの導入・削除は `install.py` で行う(Python 3 標準ライブラリのみで動作)。

```sh
# コア(skills・agents)をハードコピーで導入・更新する
# 初回は全用途グループ、導入済みなら lock が記録するグループを配る
python3 install.py core --target /path/to/project

# 用途グループを選んで導入する(複数指定できる)
python3 install.py core --target /path/to/project writing authoring

# 導入済みのターゲットへ全用途グループを配布する
python3 install.py core --target /path/to/project --all

# 拡張バンドルを導入する
python3 install.py ext <name> --target /path/to/project

# 導入済み拡張を削除する
python3 install.py remove <name> --target /path/to/project

# 導入状態を表示する
python3 install.py status --target /path/to/project
```

各コマンドは `--dry-run` で変更せずに実行内容を確認できる(status を除く)。

拡張バンドルは hooks を持つことがあり、その場合は `settings.snippet.json` の内容を利用側の `.claude/settings.json` へ冪等マージする(`remove` でマージ分だけを取り消す)。現在収録しているのは `ext-dev-guardrails`(安全制約の決定論的強制。D-018)である。

導入はハードコピー方式である(シンボリックリンクを使わない。devcontainer 等でホスト側パスが解決できない環境でも動き、利用側は導入物を自リポジトリに Git 管理できる。D-006)。更新は `install.py core` の再実行で行い、廃止されたスキル・エージェント(前回コピーして今回の配布元に無いもの)は自動で削除される。配布対象は用途グループ配下に限るため、`.claude/skills/` に置く `meta-*` は配布されない。グループ名を指定した実行は、そのグループの廃止分だけを削除し、指定しなかったグループの導入物には触らない。グループ名を省いた実行は、導入済みの記録(`.claude/dev-core.lock.json`)があればそのグループだけを配る(更新のつもりの再実行で未導入のグループを新規に入れないため)。記録が無い初回導入と、グループ名を持たない旧形式の記録では全グループを配る。導入済みのターゲットへ全グループを入れるには `--all` を付ける。
