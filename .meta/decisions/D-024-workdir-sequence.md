# D-024: workdir のディレクトリ名に連番を付け、採番をエンジンが行う(2026-08-12)

## 背景

`flow-sdd/SKILL.md` 1. は workdir を `docs/specs/<unit>/` と定め、`<unit>` は小文字ケバブケースのスラッグとしていた。ディレクトリ名がスラッグだけのため、次の 2 点が成立していなかった。

- **作成順が名前から定まらない**。`docs/specs/` の一覧はアルファベット順に並び、どの作業単位が先に始まったかを名前から読めない。
- **番号で一意に参照できない**。会話・コミットログ・issue から特定の作業単位を指すとき、スラッグ全体を書く以外の手段がない。

中間生成物のライフサイクル(D-000 6.4)は、workdir が作業単位ごとに増え、完了状態への到達で凍結されて以後は参照専用になることを定める。累積して凍結される点は、workspace 側でタスクを記録する issue(`1_issues/<area>/NNN-<task-name>/`。area ごとに 3 桁の連番を採番し、欠番を振り直さない)と同じ性質であり、issue はこの性質に対して連番で作成順と参照を与えている。

## 決定

- **workdir のディレクトリ名を `NNN-<unit>` にする**。`NNN` はルート(flow-sdd では `docs/specs/`)直下で採番する 3 桁の 0 埋め連番とする。`spec.md`・`tasks.md`・`state.json`・`research.md` の配置は変えない。
- **採番はエンジン(`state.py init`)が行う**。`--root <ルート> --unit <名前>` を与えると、ルート直下の `NNN-` から始まるディレクトリの最大番号 + 1 を採番してディレクトリを作り、そのパスを `workdir:` 行に出力する。スキル本文が既存ディレクトリを数える手順を持たない。
- **連番を持たない既存の workdir を受け入れる**。採番の対象は `NNN-` で始まるディレクトリに限り、連番を持たないディレクトリは数に入れない。`--workdir <パス>` を与える従来の形式は採番せず、既存の挙動のまま残す。
- **同じ unit の workdir が既にあれば `init` を拒否する**。連番の有無を問わず照合する。番号違いの重複を作らせず、既存の workdir で再開させる。
- **`unit` は連番を含まない**。`state.json` の `unit` と作業ブランチ名はどちらもスラッグのままとする。連番はディレクトリ名だけが持つ。
- **既存 workdir のパスは `scan` で特定する**。unit 名だけではパスが決まらないため、`flow-sdd` の再開手順(Step 0)とルーティング経路 A は `scan --root docs/specs` の一覧から workdir を特定する。

## 却下した選択肢

- **`spec.md` のファイル名に連番を付ける(`NNN-<name>.md`)**: 単独利用時(既定 workdir `docs/dev/`)に spec が累積して見えるが、`tasks.md`・`state.json` との対応付けを別に定める必要が生じる。ディレクトリ名に付ければ 1 作業単位のファイル群がまとめて番号を持つ。
- **ディレクトリ名とファイル名の両方に連番を付ける**: 同じ番号が 2 か所に現れ、改名時に食い違う余地が増える。番号の所在を 1 か所に限る。
- **スキル本文の手順として採番する(既存ディレクトリを走査して番号を決めさせる)**: 採番がモデルの実行に依存し、走査漏れで番号が重複する。決定論的に判定できることはスクリプトが担う原則(`../../dev/skills/dev-core/references/static-check.md` 1.)に沿ってエンジンへ寄せた。
- **連番を必須にし、連番を持たない workdir を検査の不備として報告する**: 利用側プロジェクトの既存 workdir を改名する必要が生じる。改名は state.json の内容を変えないため機械的には可能だが、凍結済みの workdir を含む改名をコアが要求する理由がない。
- **作業ブランチ名にも連番を付ける**: ブランチは作業単位に 1 本で、マージ後に消える。凍結して残る workdir と違い累積しないため、連番が参照の役に立たない。
- **採番を `init` とは別のサブコマンド(番号だけを返す read-only コマンド)にする**: 採番とディレクトリ作成の間に別の `init` が入ると同じ番号を 2 回使う。`init` の中で採番することでこの隙間を無くした。

## 帰結

- `../../dev/skills/dev-core/scripts/lib.py` に採番の関数(`sequence_of` / `strip_sequence` / `next_sequence` / `numbered_workdir` / `find_unit_dir` / `unit_name_problem`)を追加した。`import re` をファイル先頭の import 群へ移した。
- `../../dev/skills/dev-core/scripts/state.py` の `init` に `--root` を追加し、`--workdir` とどちらか一方だけを指定する形にした。`--root` 指定時は `--unit` を必須とし、unit 名の形式(空・パス区切り・連番始まり)と同じ unit の既存 workdir を拒否する。作成した workdir のパスを出力に加えた。
- `../../dev/skills/dev-core/references/static-check.md` 3. に採番規則の節(3.1)を追加し、check.py の検査対象を 3.2 に分けた。
- `../../dev/skills/flow-sdd/SKILL.md` の workdir の契約・ルーティング経路 A・Step 0 の手順 2 と 4・ブランチ運用を、連番付きの workdir と `scan` による特定に合わせた。
- `../../dev/skills/dev-release/SKILL.md` と `../../dev/skills/dev-release/templates/release-review-prompt.md` の workdir のパス表記を `docs/specs/NNN-<unit>/` に揃えた。
- `check.py` と `ext-dev-guardrails` の hook はディレクトリ名を参照しないため、変更しなかった。

## 再検討条件

利用側プロジェクトで連番を持たない workdir と持つ workdir の混在が読みにくさを生み、既存 workdir の改名を求める要望が出た場合(その場合は改名手順の提供を検討する)。または `docs/specs/` 直下に作業単位以外のディレクトリを置く運用が生じ、採番の対象がルート直下のディレクトリ全体では定まらなくなった場合。
