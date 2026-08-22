# D-035: japanese-writing の検査を hook で発火させる拡張バンドルを writing グループに置く(2026-08-22)

## 背景

japanese-writing は規範(`references/`)と検査スクリプト(`scripts/lint.py` ほか)を持つが、実行はエージェントの自主性に委ねている。lint.py は「CI ゲートではなく lint」として検出件数によらず exit 0 を返す設計であり、読み飛ばせば検査は走らない。指摘した表現が次のセッションで再び現れる状態が観測されていた。

X の記事「AIの変な日本語、Hooksで撲滅しているお話」(まつにぃ, 2026-08-14)は、書き込み直後の PostToolUse で NG 表現を照合して書き直させ、セッション終了時の再検査で重大な違反が残るあいだ完了させない仕組みを述べる。記事の検出は正規表現と文書全体の集計だが、これらは lint.py が既に持つため、不足は発火・警告(言い換え例つき)・文書種別の切り替え・完了ゲートの 4 点になる。

D-018 は dev グループで同じ構図(文章の規律の決定論的強制)を hook 拡張バンドルとして解決した。ただし Stop hook によるブロックは「承認ゲート到達の停止と検証未達の停止を区別できない」(D-022)として却下している。

## 決定

- **writing グループの拡張バンドル `ext-writing-inspection`(バンドル群 `inspection`)として配る**。導入・削除は `install.py ext / remove` で行い、機構(ハードコピー・`settings.snippet.json` の冪等マージ・lock)は dev グループの拡張と共通にする。グループの機構はグループ配下に置く(D-014)ため、`writing/extensions/` を新設する。
- **hook が強制するのは検査の発火だけとし、検出への対応は書き込み後の書き直しに委ねる**。PostToolUse(Write / Edit / MultiEdit / NotebookEdit)は日本語 Markdown の書き込み直後に lint.py を実行し、検出があれば `decision: block` の警告(検出一覧・文単位の書き直し指示・カテゴリ別の言い換え指針・機械検出に出ない不自然さの自己判定の指示)を返す。書き込み自体は成立済みで、処理は止めない。
- **Stop hook は「重大カテゴリの検出が残る」ときだけ、上限つきで完了をブロックする**。D-022 の懸念(正当な停止の封鎖)には 3 点で対処する。判定を機械検出が閉じる条件(このセッションで検査したファイルに、宣言済みカテゴリの検出が残る)に限る。ブロック回数に上限(既定 3 回)を設け、解消しない検出で完了を封鎖し続けない。重大カテゴリを決定論的に直せて誤検知が少ないもの(`forbidden_phrase` の warn 以上・`antithesis_repetition` の critical)に絞り、判断を要する集計統計系は警告のみとする。
- **重大カテゴリと文書種別はバンドル内の設定ファイル(`hooks/inspection.config.json`)で宣言する**。文書種別はパスのパターンで解決し、lint.py の `--genre` プロファイルとカテゴリの無効化・検査除外を切り替える。利用側の恒久的な変更は `.claude/ext-writing-inspection.config.json`(浅い上書き)に書き、バンドル再導入で消えない形にする。
- **lint.py の exit 0 設計は変えない**。重大カテゴリの判定は hook 側が `--json` 出力を読んで行う。検査の実体は導入先の japanese-writing の lint.py であり、バンドルは検出器を持たない。
- **検査できない環境では素通しにする**。uv が無い・japanese-writing 未導入・lint 失敗・タイムアウトのいずれも、hook はエラーを出さず許可側に倒す(hook 自身の不具合や環境差で作業を封鎖しない。ext-dev-guardrails と同じ規律)。
- **重量級の `semantic.py` は hook から呼ばない**。正規表現と集計で拾えない不自然さは、警告文がエージェント自身の判定(LLM 判定)として指示する。

## 却下した選択肢

- **PreToolUse で書き込み自体を拒否する**: 検出は文章の中身への疑いの提示であり、絶対禁止(D-018 の 3 件)と違って誤検知がありうる。書き込みを拒否すると下書きすら保存できず、書いてから直す収束ループ(inspection.md 6.)と両立しない。記事の設計(処理を止めず書き直させる)にも一致しない。
- **japanese-writing 本体(コア)に hook を組み込む**: コアが harness の機構に依存することになり、「hooks・settings.json・MCP は本体では使用しない」(dev/extensions/README.md 3.2、DESIGN §3 規律 9)に反する。導入は利用側の明示操作(install.py)に残す。
- **Stop hook を持たず PostToolUse の警告だけにする**: 警告への対応は助言に留まり、無視したまま完了できる。「指摘した表現が次のセッションで再び現れる状態を塞ぐ」という本 issue の目的には、完了前のゲートが要る。ブロック条件の限定と上限で D-022 の懸念に対処できると判断した。
- **lint.py に重大カテゴリで exit 非 0 を返すモードを足す**: lint と CI ゲートの区別(inspection.md 1.)という設計思想を壊す。ブロックの可否は配布側でなく利用側の設定(hook)の関心事である。
- **NG ワード照合を hook 内に再実装する(記事の構成そのまま)**: lint.py が同じ検出(禁止語カタログ・集計検出)をコーパス校正済みの閾値で持っており、二重実装は校正結果を捨てて保守を分裂させる。
- **設定を port(`docs/dev/ports/`)として配る**: port は dev グループの機構であり、宛先の規約(`inject` の宛先)も dev 系に限られる。浅い上書きの設定ファイル 1 枚で足りる。

## 帰結

- `writing/extensions/README.md`(グループの拡張置き場)・`writing/extensions/inspection/README.md`(バンドル群)・`writing/extensions/inspection/ext-writing-inspection/`(SKILL.md・hooks 3 本・`inspection.config.json`・`rewrite_guides.json`・`settings.snippet.json`)を新設した。
- hook は `inspect_write.py`(PostToolUse)・`inspect_stop.py`(Stop)の 2 本と共通処理 `inspect_lib.py` とする。hook 自身は Python 3 標準ライブラリのみで動作し、lint.py の実行だけを `uv run` に委ねる。テストは環境変数 `WRITING_INSPECTION_LINT_CMD` で lint コマンドを差し替えて行う。
- 検査したファイルとブロック回数は一時ディレクトリ配下の状態ファイル(プロジェクトのハッシュ + セッション ID)に持ち、リポジトリには何も書かない。重大カテゴリが解消された時点で削除する。
- `rewrite_guides.json` に lint.py の全カテゴリ(EXPERIMENTAL 含む)の書き直し指針と言い換え例を対応づけ、警告へ同梱する。正本は japanese-writing の規範であり、指針は要約に留める。
- `tests/test_inspection_hooks.py` を追加した。`README.md`・`writing/skills/japanese-writing/references/inspection.md` に導入手順と自主実行との使い分けを追記した。

## 再検討条件

Stop hook が正当な完了(検出が文脈上正しいのに残るケース)を上限まで封鎖する事例が繰り返し観測された場合(重大カテゴリの縮小・上限の引き下げ・Stop hook の撤去を検討する)。または Claude Code の hook の入出力形式が変わった場合。lint.py の書き込みごとの実行が作業の体感を損なう場合(対象の絞り込み・デバウンスを検討する)。
