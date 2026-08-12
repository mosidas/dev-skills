# D-025: specs を roadmap ごとの 2 階層にし、roadmap.md を状態機械で凍結する(2026-08-13)

## 背景

D-024 は workdir を `docs/specs/NNN-<unit>/` と定め、`docs/specs/` 直下で連番を採番することにした。その再検討条件の 1 つは「`docs/specs/` 直下に作業単位以外のディレクトリを置く運用が生じ、採番の対象がルート直下のディレクトリ全体では定まらなくなった場合」であり、本判断はこれに該当する。

`docs/specs/` の直下に unit が平らに並ぶ構成は、roadmap が 1 本のうちは成立する。2 本目の roadmap を立てた時点で、どの unit がどの roadmap に属するかがディレクトリ名から定まらなくなる。roadmap は unit の一覧・順序・依存を持つ中間生成物であり(`../../dev/skills/flow-sdd/SKILL.md` 2.1)、対応が読めないと再開時に次の unit を選べない。

あわせて `roadmap.md` の扱いが unit と揃っていなかった。unit の中間生成物は完了状態への到達で凍結され以後は参照専用になる(D-000 6.4)が、`roadmap.md` には凍結の機構がなく、全 unit の完了後も編集できる状態が続いていた。

## 決定

- **specs の構成を `docs/specs/NNN-<roadmap 名>/NNN-<unit>/` の 2 階層にする**。roadmap の連番は `docs/specs/` 直下、unit の連番は roadmap のディレクトリ直下で採番する。採番はルート直下で閉じるというエンジンの既存の性質(D-024)をそのまま使うため、**unit の連番は roadmap ごとに閉じる**。
- **unit が 1 つでも roadmap を立てる**。ルーティングの経路 C(新規の作業 1 単位)でも `roadmap.md` を生成し、unit 一覧に 1 行を書く。承認は経路判定のゲートに含め、roadmap 単独の承認ゲートを置かない(経路 C を重くしないため)。
- **unit 名は roadmap を跨いで一意とする**。連番と違い名前の一意性は閉じない。unit 名は作業ブランチ名でもあり(`flow-sdd/SKILL.md` 3.)、roadmap ごとに閉じると `git branch` の一覧と PR の題名で区別できなくなるためである。強制は `init` の新しい引数 `--unique-root` が行う。
- **`roadmap.md` の凍結を第 2 の状態機械定義で実現する**。`flow-sdd/roadmap.json`(`initialized → roadmap-generated →(gate: roadmap)→ roadmap-approved → frozen`、差し戻し `roadmap-approved → roadmap-generated`)を新設し、roadmap のディレクトリ直下に `state.json` を置く。凍結・承認ゲート・差し戻しはすべて既存のエンジンが処理する。
- **凍結は恒久情報への移動の後に行う**。全 unit が `completed` に達したら、恒久情報への移動 → `roadmap.md` の編集 → `frozen` への遷移の順とする。移動が `roadmap.md` の編集を伴うため、先に凍結すると移動のたびに凍結違反になる。凍結は「移し終えて参照専用になった」状態を記録する操作であり、移動を禁じる操作ではない。
- **エンジンは階層の深さを前提にしない**。`state.json` の位置と `workflow` の値だけで対象を判定する規則を `static-check.md` 3.1.1 に明文化し、階層を分けた複数ワークフローの併用を一般の機能として定めた。flow-sdd はその 1 例になる。

## 却下した選択肢

- **roadmap のディレクトリだけを作り `roadmap.md` を置かない(経路 C)**: ディレクトリ名の出所が文書に無くなる。また凍結の機構が `roadmap.md` の有無で分岐し、経路ごとの特例が構成に残る。
- **unit 名の一意性も roadmap ごとに閉じる**: 作業ブランチ名を `<roadmap>/<unit>` に変える必要が生じ、`flow-sdd/SKILL.md` 3.・Step 4 と `git-convention.md` のブランチ命名へ波及する。得られるのは同名 unit を別 roadmap に置ける自由だけで、その同名は `git branch` の一覧で人間にも区別できない。
- **`roadmap.md` の凍結を unit の `state.json` に載せる**: `roadmap.md` は unit の workdir の外にあり、凍結の照合が「`state.json` と同じディレクトリで閉じる」性質を壊す。この性質は `check.py` と hook の両方が依存している。
- **roadmap 用に `state.json` とは別名の状態ファイルを置く**: 凍結の照合が `state.json` を探す実装のため、別名にすると照合の対象から外れる。ファイル名を揃えることで `check.py` を変更せずに済ませた。
- **`init` に roadmap 専用のサブコマンドを足す**: 採番・ゲート・凍結はいずれも既存の `init` / `approve` / `set-state` で足りる。定義データを差し替えるだけで済むものにコマンドを増やさない。
- **`scan` の `--def` を 1 つに保ち、roadmap の `state.json` を `others` に出す**: 出力上は「対象外」と読め、構成の一部である roadmap が異常として並ぶ。`--def` を複数指定できるようにし、各行が属する定義を `workflow` として持つ形にした。

## 帰結

- `../../dev/skills/flow-sdd/roadmap.json` を新設した。
- `../../dev/skills/dev-core/scripts/lib.py`: `find_unit_dir` に `recursive` 引数を足した(既定は従来どおりルート直下のみ)。
- `../../dev/skills/dev-core/scripts/state.py`: `init` に `--unique-root` を足した(既定は `--root`。指定するとその配下の全階層を走査する)。`scan` の `--def` を複数指定できるようにし、出力の各行に `workflow` を足した。出力の最上位の `workflow` は `workflows`(配列)に変えた。
- `../../dev/skills/dev-core/references/static-check.md`: 3.1 の採番規則に検査範囲と階層の入れ子を追記し、3.1.1(階層を分けた複数ワークフローの併用)を新設した。
- `../../dev/skills/flow-sdd/SKILL.md`: 1.(契約)・2.(ルーティング表)・2.1(構成と凍結)・3.(ブランチ運用)・5.(Step R の新設、Step 0 の手順 2 と 4、Step 4)・6.(規律)を新しい構成に合わせた。
- `../../dev/skills/dev-release/SKILL.md` と `../../dev/skills/dev-release/templates/release-review-prompt.md` の workdir のパス表記を 2 階層に揃えた。
- `check.py` と `../../dev/extensions/guardrails/ext-dev-guardrails/` の hook は、どちらも階層を参照せず `state.json` と同じディレクトリで判定が閉じるため変更しなかった。
- `../../.claude/skills/meta-core/scripts/meta_extract.py`: `extract_state_machines` がファイル名 `workflow.json` を決め打ちしていたため、1 つのスキルが持つ複数の定義データを抽出できなかった。スキル直下の `*.json` を走査し、必須キー(`name`・`states`・`initial`・`transitions`)の有無で定義データかを判定する形に変えた。抽出結果に `file`(定義データのファイル名)を足した。スキル直下には定義データ以外の JSON も置かれるため(`trigger-cases.json`)、ファイル名ではなく中身の形で選り分けている。
- `../../tests/test_lib.py` に再帰走査の 3 件、`../../tests/test_state.py` に階層ごとの採番・`--unique-root`・`scan` の複数定義の 6 件と、配布物の定義データをそのまま駆動する `FlowSddDefinitionTest`(5 件)を追加した。

## 再検討条件

roadmap をさらに束ねる階層(製品・リリース列など)が要求され、2 階層では対応が定まらなくなった場合。または unit 名を roadmap を跨いで一意にする制約が、実運用で命名の衝突を頻繁に起こした場合(その場合はブランチ命名の変更とあわせて一意性の範囲を見直す)。
