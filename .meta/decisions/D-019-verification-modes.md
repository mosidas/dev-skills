# D-019: 検証手段の 3 方式を principles.md で対応づける(2026-08-10)

## 背景

[Building agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk) は、エージェントの検証を 3 方式に分ける。(1) ルールベース(lint・型検査・明示的なエラーチェック)、(2) 視覚フィードバック(スクリーンショット)、(3) LLM as judge。

本スキル群は 3 方式すべてに実装を持つが、対応が別々の文書に分かれ、どの方式をいつ使うかを 1 箇所で示していない(`../notes/2026-08-10-engineering-lenses.md` H-3)。

| 方式 | 実装 | 正本 |
| ---- | ---- | ---- |
| ルールベース | `check.py`・`state.py`・タスクの検証コマンド | `static-check.md` |
| 視覚フィードバック | 実行時検証の手段 1(ブラウザ自動化) | `runtime-verification.md` 3. |
| LLM as judge | dev-reviewer の観点別パネル | `review-perspectives.md` |

## 決定

`../../dev/skills/dev-core/references/principles.md` に「検証手段の選択」の節を足し、3 方式と適用対象・正本の所在を対応させる。3 方式が代替関係ではなく適用対象の違いであること(ルールベースの緑を実行時成立の根拠にしない、という既存規律と同じ構図)を明記する。

## 却下した選択肢

- **新しい参照ファイルを作る**: 対応表は 10 行程度であり、1 ファイルにすると各部品の参照の数が増える。D-015 で読み込み量を制御する方針と逆行する。
- **`runtime-verification.md` に置く**: 同ファイルは 3 方式のうち視覚フィードバック側の正本であり、3 方式全体の対応表を置くと役割が混ざる。
- **`review-perspectives.md` に置く**: 同ファイルは LLM as judge の観点カタログであり、同じ理由で採らない。

## 帰結

- `../../dev/skills/dev-core/references/principles.md` に 7.「検証手段の選択」を追加し、5.「決定論的補完」から参照を張った(決定論と意味判断の分担を、検証の側から見た対応として示す)。末尾へ足すことで既存の節番号を変えず、他文書からの `principles.md` §N の参照を保った。

## 再検討条件

3 方式に収まらない検証手段(形式手法・プロパティベーステスト等)を規約として採り入れる場合。
