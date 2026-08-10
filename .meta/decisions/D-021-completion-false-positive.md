# D-021: 完了判定の偽陽性への対策を実装者と判定器に置く(2026-08-10)

## 背景

[Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) は「進捗を根拠にした早すぎる完了宣言」を長時間エージェントの典型的な失敗に挙げ、機能リストの改変禁止と「テストの削除・編集は許容しない」の明示で対処する。[Ralph Wiggum as a "software engineer"](https://ghuntley.com/ralph/) は「実装済みを装うスタブ」を失敗モードに挙げる。

本スキル群の現状の対策は 3 箇所に分かれている(`../notes/2026-08-10-engineering-lenses.md` L-5)。

| 対策 | 所在 |
| ---- | ---- |
| 判定基準を緩めて緑にしない(CI) | `git-convention.md` 9.4 |
| テストの削除・スキップで通すことの禁止 | `../../dev/agents/dev-debugger.md` |
| リファクタが振る舞いを変えていないか | `../../dev/skills/dev-implement/templates/reviewer-prompt.md` |

実装者へ渡すプロンプトには、REFACTOR の段に限った「テストの書き換えを要する整理はしない」があるだけで、GREEN にするためのテストの削除・スキップ・アサーション弱体化を禁じる記述は無い。未実装のスタブを完了として返さない旨も無い。タスク定義(`tasks.md`)からタスクを削って完了に見せることの禁止も、どこにも無い。

対策が実装者(最も強い誘因を持つ役)に無く、後段のレビューだけに置かれている。

## 決定

- **implementer-prompt の制約を段に依存しない禁止へ拡張する**: 「既存テストの削除・スキップ・アサーションの弱体化で検証を緑にしない」。既存の REFACTOR 限定の記述を置き換える。
- **スタブの申告を義務づける**: 「未実装であることを隠す返り値・空実装を `READY_FOR_REVIEW` で返さない」。実装できない場合は `BLOCKED` で返す。
- **reviewer-prompt の確認手順に検出を足す**: 差分に既存テストの削除・スキップ・アサーションの弱体化があれば、仕様変更に伴う正当な削除かを確認し、根拠が無ければ `[Critical]` とする。
- **`dev-implement/SKILL.md` にタスク定義の改変禁止を足す**: `tasks.md` のタスクを削除・改変して完了に見せない。チェックボックスの更新と `## Implementation Notes` への追記は許す(部品の出力として定義済み)。

## 却下した選択肢

- **hook で検出する**: 削除の検出には差分解析が要り、仕様変更に伴う正当な削除と区別できない。誤って拒否すると正当な作業を止める(D-018 の分類基準)。
- **`dev-debugger.md` の既存記述を実装者に参照させる**: dev-debugger は起動条件が限られ(`BLOCKED`・2 回 `REJECTED`・`NEEDS_CONTEXT` の未解消)、通常の実装経路では読まれない。
- **`git-convention.md` 9.4 を実装者の必読に加える**: 同節は CI 追従の規律であり、実装のたびに読ませると D-015 で削った読み込み量を戻すことになる。禁止の 1 文をプロンプトへ置くほうが小さい。

## 帰結

- `../../dev/skills/dev-implement/templates/implementer-prompt.md` の制約に「検証は実装で通す」(タスクが要求する変更と要求しない変更の分岐つき)と「未実装を完了として返さない」を追加し、返却フォーマットに `TEST_CHANGES` を加えた。
- `../../dev/skills/dev-implement/templates/reviewer-prompt.md` の確認手順に、既存テストの後退の検出(手順 4)と、空実装・固定値の返却を `[Critical]` とする判定(手順 3)を追加した。レビュー観点の一覧は変更していない。
- `../../dev/skills/dev-implement/SKILL.md` 13.(安全制約)にタスク定義の改変禁止と「検証を実装で通す」を追加した。
- `../../dev/skills/dev-implement/templates/debugger-prompt.md` の制約を「『とりあえず通す』修正をしない」として、テストの削除・スキップ・アサーションの弱体化の禁止と、テストが仕様と食い違う場合の差し戻しに書き換えた。
- `../../dev/skills/dev-implement/templates/final-review-prompt.md` の確認手順 2 に、既存テストの後退の検出を追加した(作業単位全体でも同じ判定を行う)。
- `../../dev/skills/dev-implement/SKILL.md` 9. の役割の記述に `TEST_CHANGES` の受け渡しを追加した。

## 再検討条件

禁止を明示したことで、仕様変更に伴う正当なテストの削除が滞る事例(実装者が削除を避けて古いテストを残す)が観測された場合。
