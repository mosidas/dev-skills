# D-014: port と拡張バンドルをグループ配下へ移す(2026-07-31)

## 背景

`ports/`(知識 port のサンプル 12 ファイル)と `extensions/`(拡張バンドルの置き場所。収録済みのバンドルは無く README のみ)はリポジトリ直下にあった。どちらも dev グループの機構である。

- 拡張バンドル: `extensions/README.md` §3.2 が依存先を「Layer 0〜1(dev-core・部品)」と定め、命名を `ext-*`・`flow-*` に限る。`.meta/DESIGN.md` のレイヤー構造図にも `dev・レイヤー 3 — extension` として現れる。
- port: 機構の正本が `dev/skills/dev-core/references/ports.md`、走査スクリプトが `dev/skills/dev-core/scripts/ports.py` で、frontmatter の `inject` の宛先は `dev-*`・`flow-*`・`ext-*` に限られる(ports.md §2)。
- D-012 で追加した `writing`・`authoring` のグループは、どちらの機構も使わない。

一方、両者がリポジトリ直下にあるため、`meta-*` の走査がグループの外を直接指していた。D-013 の棚卸しでは、参照実在検査の走査対象(`.meta`・`ports`・`extensions`・`tests`)と inject 実在検査(`ports/` を走査)を「リポジトリ構成に依存」と分類していた。この分類は「`ports/` の有無で決まり、グループ差ではない」という理由に立つが、実際にはどちらの機構も dev グループの構造の一部であり、グループ差がないのではなく dev グループしか使っていないだけだった。

## 決定

- **グループの機構はグループ配下に置く**。`ports/` を `dev/ports/` へ、`extensions/` を `dev/extensions/` へ移す。バンドル群の階層(`extensions/<バンドル群>/<バンドル名>/`)は維持する。どちらも `skills/`・`agents/` の外にあるため、`install.py core` の配布対象にならない点は変わらない。
- **`meta-*` は固定パスではなく各グループ配下を走査する**。走査対象の列挙を `meta_lib.group_subdirs()` に集約し、機構を持たないグループは走査対象を持たないだけで成立する。D-013 の「特定のグループの前提を `meta-*` のスクリプト・テンプレートに直接書かない」規律を、規約の宣言だけでなく機構の配置にも適用する。
- **D-013 の分類を 2 項目だけ改める**。「inject 実在」と「走査対象ディレクトリ」のうち `ports`・`extensions` を「リポジトリ構成に依存」から「グループ固有」へ再分類する。`.meta`・`tests` はリポジトリ全体の資産のため「リポジトリ構成に依存」のまま直下に残す。
- **`install.py ext` の指定は末尾から照合する**。指定を `<用途グループ>/extensions/<バンドル群>/<バンドル名>` の末尾から順に照合し、`<バンドル名>`・`<バンドル群>/<バンドル名>`・`<用途グループ>/<バンドル群>/<バンドル名>` の 3 通りを受け付ける。複数一致したときはエラーにし、前の階層を足して絞らせる。用途グループの判定は core と同じ関数(`skills/` を持つルート直下のディレクトリ)を使うため、拡張バンドルの置き場所も用途グループ配下に限られる。判断の観点は issue が定めた 2 点(指定の短さ・同名バンドルを一意へ解決できること)であり、最短の指定を保ったまま、3 階層すべてを書けば必ず一意になる形を選んだ。
- **行数集計の領域はグループ込みの名前にする**。`dev/ports`・`dev/extensions` を領域名とし、エージェント(`dev/agents`)と同じ形にする。どのグループの分量かを区別できる。

## 却下した選択肢

- **用途グループを常に明示させる(`install.py ext dev/<バンドル名>`)**: 指定が常に 1 階層長くなるうえ、同じ用途グループ内の別バンドル群に同名バンドルがある場合は一意に解決できず、結局バンドル群の指定も要る。末尾からの照合は、短い指定を既定にしたまま、必要なときだけ前の階層を足せば必ず一意にできる。
  - 再検討条件: 用途グループごとに同名バンドルを意図的に用意する運用になり、既定の探索が常にエラーで止まる場合。
- **`extensions/` だけを移し `ports/` は直下に残す**: port の機構の正本(`ports.md`)・走査スクリプト(`ports.py`)・`inject` の宛先はいずれも dev グループにあり、拡張バンドルと扱いを変える理由がない。2 つの機構で置き場所の規則が分かれると、新しい機構を足すときの判断基準が無くなる。
- **`tests/`・`.meta/` も同じ規則でグループ配下へ移す**: どちらも特定のグループの機構ではない。`tests/` は `install.py` と全グループのスクリプトを対象にし(D-010)、`.meta/` はリポジトリ全体の設計文書である。グループ配下へ移すと、どのグループに属するかを決められない。
- **移動せず、`meta-*` 側で「直下の `ports/`・`extensions/` は dev グループのものとして扱う」と実装する**: 走査対象は変わらないまま、リポジトリ直下の名前と特定グループの結びつきを `meta-*` のコードに書くことになり、D-013 で外へ出した規律に反する。
- **バンドルのまとまりの呼称を「グループ」のまま残す**: 移動後は 1 つ上の階層にも用途グループが現れ、`extensions/README.md` の「グループ」がどちらを指すか読み手が判別できない。呼称を「バンドル群」に改め、用途グループと区別した。

## 帰結

- `ports/` を `dev/ports/` へ、`extensions/` を `dev/extensions/` へ移した(`git mv`。バンドル群の階層は維持)。
- `meta_lib.py`: 定数 `PORTS_SUBDIR`・`EXTENSIONS_SUBDIR` と、各グループ直下の当該ディレクトリを列挙する `group_subdirs()` を追加した。
- `meta_check.py`: `all_docs()` の走査対象を「スキル群 + グループ配下の `ports`・`extensions` + `.meta`・`tests` + ルート直下の md」にし、`check_inject_targets()` を全グループの `ports/` の走査にした。リポジトリ直下に残す対象を定数 `ROOT_DOC_DIRS` に置いた。
- `meta_extract.py`: `extract_inject_graph()` を全グループの `ports/` の走査にした。
- `meta_loc.py`: 領域の割り当てを `ROOT_AREAS`(`.meta`)と `GROUP_AREAS`(`agents`・`ports`・`extensions`)に分け、`dev/ports`・`dev/extensions` を dev グループの領域として集計する。
- `install.py`: `resolve_ext()` を末尾からの照合に変え、定数 `EXTENSIONS_SUBDIR` を置いた。用途グループの列挙は `core_groups()` を共有する。
- `principles.md` §6 に「グループの機構はグループ配下に置く」を追加した。
- `README.md`・`.meta/DESIGN.md`・`dev/extensions/README.md`・`dev/ports/README.md`・`meta-check/SKILL.md`・`tests/README.md`・`.prettierignore` を新しい配置に合わせた。`dev/extensions/README.md` はバンドルのまとまりの呼称を「バンドル群」に統一した。
- `tests/test_install.py` に拡張バンドルの解決・導入・削除・表示のテスト(`ExtTest` 9 件)を、`tests/test_meta_lib.py` に `group_subdirs()` のテストを、`tests/test_meta_check.py` に他グループの `ports/` の走査・グループの機構の文書の参照検査・直下の `ports/` を走査しないテストを、`tests/test_meta_extract.py` に直下の `ports/` を抽出しないテストを追加し、`tests/test_meta_loc.py` の領域のテストを新しい割り当てに更新した。全 254 件が通る(変更前は 238 件)。
- 検証: 変更前の `meta_check.py --json` を基準に取り、変更後の実行で error 0 件・warning 0 件・新規の指摘 0 件を確認した。`trigger_check.py` は 30/30 通過。`meta_extract.py` の出力は、`meta-check` の description を更新したことによる role の文言の違いを除き変更前と一致する(inject グラフ 8 件は完全に一致)。

## 再検討条件

`writing`・`authoring` 等のグループが独自の port・拡張バンドルを持ち、バンドル名の解決や走査でグループ間の衝突が常態化した場合。または、リポジトリ直下に残した `tests/`・`.meta/` にグループ固有の内容が生じ、同じ規則で分ける必要が出た場合。
