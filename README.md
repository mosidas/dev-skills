# dev-skills

Claude Code 向けの汎用開発スキル群。仕様(dev-spec: 壁打ちで契約と受け入れ基準を確定)・タスク分解(dev-decompose)・実装(dev-implement)・リリース(dev-release)などの部品と、それらを束ねる SDD ワークフロー(flow-sdd)、および拡張バンドル(extensions/)で構成する。

設計思想・レイヤー構成・規律は [.meta/DESIGN.md](.meta/DESIGN.md) を参照。

## 構成

```
dev-skills/
├── CLAUDE.md                    # 言語規約など最小限のプロジェクト指示
├── install.py                   # 導入スクリプト(コアのリンク・拡張バンドルの展開)
├── .meta/                       # 設計文書
├── .claude/
│   ├── agents/                  # 役割エージェント(Layer 0)
│   └── skills/
│       ├── dev-core/            # Layer 0: 共有リファレンス + スクリプト
│       ├── dev-<部品名>/        # Layer 1: 各部品(SKILL.md + templates/)
│       └── flow-<ワークフロー名>/ # Layer 2: composition(SKILL.md + 状態機械定義)
├── extensions/                  # Layer 3: 拡張バンドル(<グループ名>/ 配下に ext-*・flow-*)
├── ports/                       # 知識 port のサンプル
└── tests/                       # 同梱スクリプトの単体テスト(配布しない。D-010)
```

## 導入

利用側プロジェクトへの導入・削除は `install.py` で行う(Python 3 標準ライブラリのみで動作)。

```sh
# コア(dev-* / flow-* の skills・agents)をハードコピーで導入する(meta-* は配布しない)
python3 install.py core --target /path/to/project

# 拡張バンドルを導入する
python3 install.py ext <name> --target /path/to/project

# 導入済み拡張を削除する
python3 install.py remove <name> --target /path/to/project

# 導入状態を表示する
python3 install.py status --target /path/to/project
```

各コマンドは `--dry-run` で変更せずに実行内容を確認できる(status を除く)。

導入はハードコピー方式である(シンボリックリンクを使わない。devcontainer 等でホスト側パスが解決できない環境でも動き、利用側は導入物を自リポジトリに Git 管理できる。D-006)。更新は `install.py core` の再実行で行い、廃止されたスキル・エージェント(前回コピーして今回の配布元に無いもの)は自動で削除される。`meta-*` は dev-skills 自身の保守用のため配布されない。
