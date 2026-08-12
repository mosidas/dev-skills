# D-018: 決定論的強制を hook 拡張バンドルとして配る(2026-08-10)

> バンドルの構成と対象の選び方は本エントリのまま有効である。`rm -rf` の判定の範囲は → [D-027](D-027-rm-rf-scope.md) で更新した(リポジトリの中に限る)。本エントリの再検討条件「hook が正当な操作を拒否した事例が観測された場合」に該当した。

## 背景

[Best practices for Claude Code](https://code.claude.com/docs/en/best-practices) は、文章による指示は助言(advisory)であり、毎回確実に実行させたい動作は hook(deterministic)で強制すると述べる。本スキル群の強制手段は決定論スクリプト(`state.py`・`check.py`)だけで、hook を持つ拡張は存在せず、レイヤー 3 は実体を持たない。

文章で守らせている規律を、機械判定の可否で分類した(`../notes/2026-08-10-engineering-lenses.md` H-1)。

| 規律 | 機械判定の可否 |
| ---- | -------------- |
| 破壊的な git 操作の禁止 | コマンド文字列の照合で判定できる |
| 選択的ステージング(`git add -A` / `git add .` の禁止) | 同上 |
| 凍結後の中間生成物を変更しない | 書き込み先のパスと `state.json` の `frozen` の照合で判定できる |
| コードに中間生成物の ID を残さない | 要件 ID の書式がコード中の通常の数値・バージョン表記と区別できない |
| テストの削除・スキップで緑にしない | 仕様変更に伴う正当な削除と区別できない |

`check.py` は凍結違反を error として検出するが、検出は書き込みの後になる。hook は書き込み自体を拒否する。

## 決定

- **上の 3 件を hook で強制する**。判定の性質で分ける。例外を持たない絶対禁止で、コマンド文字列とパスの照合だけで判定が閉じるものを hook にする。文脈に依存する判定(残る 2 件)は hook にせず、dev-reviewer とプロンプトの規律に委ねる。
- **拡張バンドルとして配る**。`dev/extensions/guardrails/ext-dev-guardrails/` を新設し、`install.py ext` で導入する(利用側の明示操作)。`../../dev/extensions/README.md` 3.2 の「hooks・settings.json・MCP は本体(レイヤー 0〜2)では使用しない」を維持する。
- **コア側の規律文を削らない**。バンドルを導入しない利用側では 3 件とも文章の規律のまま残るため、hook は上乗せの強制手段として位置づける。
- 配線は `settings.snippet.json` の `hooks` のみとし、`permissions` は使わない(拒否の理由を日本語で返すには hook が要る)。
- **バンドルの文書は、コアの正本を相対パスで参照しない**。バンドルはリポジトリ内(`dev/extensions/<バンドル群>/<バンドル名>/`)と導入先(`.claude/skills/<バンドル名>/`)で位置が変わり、コアの正本への相対パスはどちらか一方でしか解決しない。名前で参照し(`dev-core/references/git-convention.md` 6.)、導入先の実パスを併記する。
- **適用範囲は導入したプロジェクトの全セッションとする**。hook は `settings.json` に配線されるため、dev スキル群を使わない操作にも効く。禁止する 3 件はいずれもプロジェクト全体で守るべき規律(未コミット変更の喪失・無関係な変更の巻き込み・凍結済み成果物の変更)であり、範囲を dev スキル群の実行中に限定しない。この範囲を各バンドルの README に明記し、利用側が導入時に判断できるようにする。

## 却下した選択肢

- **コアの一部として `install.py core` で配線する**: 理由は 2 点ある。コアが harness の機構(Claude Code の hooks と `settings.json`)に依存することになり、`extensions/README.md` 3.2 の規律に反する。また `install.py core` の役割は用途グループの `skills/`・`agents/` のハードコピーであり、利用側の `settings.json` の書き換えはその範囲を超える。
- **Stop hook で検証未達のターン終了をブロックする**: 承認ゲートに到達したターンの終了は「ユーザーの応答を待つ」ための正しい停止であり、Stop hook はこれを検証未達の停止と区別できない(D-022)。
- **コアの規律文を hook へ置き換える**: hook を導入しない利用側で規律が消える。
- **`permissions.deny` で `git reset --hard` 等を禁止する**: 拒否はできるが、なぜ拒否されたか(代わりに何をすべきか)を返せない。`git-convention.md` が定める代替手段(D-020 の `git revert`・`git stash`)へ誘導できる hook を選ぶ。
- **バンドルからコアの正本を `../dev-core/...` の相対パスで参照する**(`extensions/README.md` 2. が述べる導入先での解決に合わせる): 導入先では解決するが、リポジトリ内では解決せず `meta_check.py` が参照切れの error を出す。検査を通すには `meta_check.py` へ拡張バンドル専用の解決規則を足す必要があり、1 バンドルのために検査の前提を増やすことになる。
- **`install.py` がコピー時に相対パスを書き換える**: 配布物の内容がコピー元と変わり、「ハードコピーで配る」(D-006)という導入方式の単純さを失う。

## 帰結

- `../../dev/extensions/guardrails/README.md`(バンドル群)と `../../dev/extensions/guardrails/ext-dev-guardrails/`(SKILL.md・hooks・settings.snippet.json)を新設した。
- hook は 2 本とする。`guard_bash.py`(PreToolUse: Bash。破壊的な git 操作と一括ステージングを拒否)と `guard_write.py`(PreToolUse: Write / Edit / MultiEdit / NotebookEdit。凍結済み中間生成物への書き込みを拒否)。
- 判定は同義の入力で回避されない形にする。`guard_bash.py` は、クォートを解釈してから区切る(クォート内の `;` `|` `&&` で分割しない)・環境変数の代入と前置コマンドを読み飛ばす・git のグローバルオプション(`-C`・`-c`・`--git-dir`・`--work-tree` 等)を読み飛ばして真のサブコマンドを判定する・フラグの別表記(`-df`・`--delete --force`)と `+` を前置した refspec による強制 push を検出する。`guard_write.py` は、シンボリックリンクを解決し、相対パスを入力の `cwd` で絶対化してから照合する。
- 正本(`git-convention.md` 6.)の列挙に `git restore`(`--staged` のみの用法を除く)・`git branch` の強制削除の同義表記・`+` を前置した refspec による強制 push を加え、hook の判定と一致させる(hook が正本にない禁止を独自に持たない)。
- `../../dev/extensions/README.md` を更新した。1. の「収録済みのバンドル群はない」に加え、冒頭のレイヤー 3 の性格づけ(「個別具体的なパターン(受託開発の納品物など)でのみ要求される拡張スキル・拡張ワークフローのサンプル」)を、汎用の強制手段も収めることが読める記述へ改めた。
- `../../tests/` に 2 本の hook の単体テストを追加した。

## 再検討条件

hook が正当な操作を拒否した事例が観測された場合(判定の緩和、または対象からの除外を検討する)。または Claude Code の hook の入出力形式が変わった場合。
