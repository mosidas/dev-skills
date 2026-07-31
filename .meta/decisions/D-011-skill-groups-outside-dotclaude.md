# D-011: 配布するスキルを `.claude` の外の用途グループへ置く(2026-07-31)

## 背景

配布元のスキル本体は `.claude/skills/`(`dev-*` 6 件・`flow-sdd`・`meta-*` 4 件)、エージェント定義は `.claude/agents/`(5 件)に置いていた。この `.claude/` は 3 つの役割を兼ねていた。

- Claude Code が dev-skills リポジトリで読み込む場所(`meta-*` を自リポジトリで使うための場所)
- `install.py core` が利用側へコピーする配布元
- 上記 2 つの区別を名前のプレフィックス(`dev-`・`flow-`・`meta-`)だけで表す場所

この構成では、配布対象の切り分けが `install.py` の `CORE_EXCLUDE_PREFIX = "meta-"` という名前判定に依存する(D-006 で導入)。開発以外の用途のスキル群を追加すると、配布したい群と配布したくない群の区別も、群ごとのまとまりも、すべて名前の規約に載る。

## 決定

- **配布対象のスキルとエージェントを用途グループのディレクトリへ移す**。グループは配布ルート直下に置き、`<グループ>/skills/`・`<グループ>/agents/` を持つ。現状のグループは `dev/`(`dev-*` 6 件・`flow-sdd`・エージェント 5 件)。
- **`meta-*` は `.claude/skills/` に残す**。`meta-*` は dev-skills 自身のスキル群を検査・生成する保守用の道具で、利用側へは配布しない(D-006)。この性質は `.claude/` の役割「このリポジトリで Claude Code が使うスキル」と一致する。用途グループの外に置くことで配布対象から外れ、リポジトリを開けばそのまま使える状態も変わらない。
- **配布対象は「配布ルート直下で `skills/` を持つ、ドットで始まらないディレクトリ」で決める**。`install.py core` はこの規約でグループを走査し、名前による除外(`CORE_EXCLUDE_PREFIX`)を持たない。配布先の配置(`.claude/skills/`・`.claude/agents/`)は変えない。
- **導入先は名前が平坦なため、スキル名・エージェント名がグループ間で衝突する場合は停止する**(後のグループが先のグループを上書きすることを防ぐ)。
- **`meta-*` スクリプトの走査は `meta_lib` に集約する**。グループの列挙・スキルの列挙・エージェントの列挙・ルート探索を `meta_lib` の関数にまとめ、`meta_check.py`・`meta_extract.py`・`meta_loc.py`・`trigger_check.py` が共有する。抽出の分類(`family`)はスキル名ではなくグループ名から決める(`.claude` は `meta`)。
- **`flow-sdd` は `dev/` に含める**。`flow-*` は分類ではなくレイヤー(composition)を表すプレフィックスで、`flow-sdd` が束ねるのは `dev-*` の部品である。

## 却下した選択肢

- **`meta-*` も用途グループ(`meta/skills/`)へ移す**: 自リポジトリで `meta-*` を呼び出す手段が失われるため、`install.py` に自リポジトリ向けの展開サブコマンドを足すか、`.claude/skills/` からシンボリックリンクを張る必要がある。いずれも「配布しないものを配布の仕組みで置く」ための追加機構で、`.claude/` に置けば不要になる。
- **グループをマニフェスト(`groups.json` 等)に列挙する**: 配置とマニフェストの二重管理になり、追加のたびに両方を更新する。ディレクトリの形(`skills/` を持つか)で決めれば実体が唯一の正本になる。
- **配置は変えず、配布対象の指定を `install.py` の引数(`--include`)にする**: 群のまとまりがディレクトリに現れないため、スキルが増えるほど引数の指定が長くなり、群の境界がコマンドの呼び出し側にしか存在しない状態になる。
- **グループごとに配布先も分ける(`.claude/skills/<グループ>/<スキル>`)**: Claude Code はスキルをディレクトリ名で解決するため、配布先の階層を増やすと解決できない。配布先は平坦のまま維持する。

## 帰結

- `.claude/skills/{dev-check,dev-core,dev-decompose,dev-implement,dev-release,dev-spec,flow-sdd}` を `dev/skills/` へ、`.claude/agents/*.md` を `dev/agents/` へ移した。`.claude/skills/` には `meta-*` 4 件が残る。
- `install.py`: `cmd_core` をグループ走査へ変え、`core_groups()` を追加した。`CORE_EXCLUDE_PREFIX` を削除し、名前衝突の検出を加えた。配布結果(スキル 7 件・エージェント 5 件・`meta-*` を含まない)は再編前と一致する。
- `meta_lib.py`: `distributed_groups`・`groups`・`skill_dirs`・`agent_files`・`group_docs`・`family_of`・`group_of`・`is_root`・`find_root` を追加した。`meta_check.py`・`meta_extract.py`・`meta_loc.py`・`trigger_check.py` の `.claude` 直指定をこれらへ置き換えた。`trigger_check.py` の既定の仕様ファイルは自スクリプトの位置から解決する形にした。
- `meta_loc.py` の領域は、スキルは名前そのもの、エージェントは `<グループ>/agents` にした。
- ドキュメント間の相対参照(`meta-*` から `dev-core` へ、`.meta/decisions/` と `ports/README.md` から `dev-core` へ)を新しい配置へ更新した。`principles.md` §2 の原則名を「SSoT は `.claude`」から「SSoT はスキルの定義」へ改めた。
- `tests/test_install.py` を新設し(配布対象・名前衝突・廃止分の削除・dry-run・実リポジトリ)、`test_meta_lib.py` に配置の走査のテストを加えた。既存テストのフィクスチャを新しい配置へ移した。全 211 件が通る。
- `.prettierignore` に `*/skills/*/templates/` を追加した。

## 再検討条件

グループ間でスキル名の衝突が常態化し、配布先を平坦に保てなくなった場合。または Claude Code がスキルの探索範囲を変更し、`.claude/skills/` 以外の配置を直接読めるようになった場合(`meta-*` の置き場所を再考する)。
