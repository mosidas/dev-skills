---
name: develop
description: 機能追加・バグ修正・リファクタリングなど、コードを変更するタスクを進めるときの手順。Backlog.md のタスク、GitHub flow のブランチと PR、planner・implementer・reviewer のサブエージェント、push 後の CI 確認を 1 つのループにまとめる。「実装して」「直して」「〜を追加して」と頼まれたとき、計画から PR までを通して進めるときに使う。
---

# 開発の手順

本スキルは統括セッションが読む。統括は計画・委譲・検収・PR を担当し、コードは書かない。コードは implementer サブエージェントが書き、reviewer サブエージェントが点検する。

## 1. 工程

| 工程 | 担当 | 成果 |
| :-- | :-- | :-- |
| タスクを決める | 統括 | Backlog.md のタスク(既存または新規) |
| ブランチを切る | 統括 | `main` から切ったブランチと、有効な git hook |
| 計画する | planner | ステップごとの完了条件を持つ計画 |
| 実装する | implementer | ステップ 1 つ分のコミット |
| 点検する | reviewer | 承認、または修正点の一覧 |
| PR を出す | 統括 | push・PR・CI の通過 |
| 閉じる | 統括 | マージ後のタスクの Final Summary |

## 2. タスクを決める

- 既存のタスクがあればその id を使う。なければ作る。

```sh
backlog task create "<タイトル>" -l <area> -d "<目的と完了条件>"
```

- 以後の経過はすべてタスクの Implementation Notes に書く(`backlog task edit <id> --notes "<経過>"`)。日付ごとのファイルを作らない。

## 3. ブランチを切る

- `main` を最新にし、`<type>/<TASK-id>-<slug>` の名前でブランチを切る(`type` は `feat`・`fix`・`refactor`・`chore`)。
- git hook が無ければ入れる(`references/hooks.md`)。pre-commit で lint、pre-push でテストを実行する。
- 手順の詳細は `references/git-flow.md` に従う。

## 4. 計画する

- planner サブエージェント(`dev-skills:planner`)を起動し、タスクの目的・完了条件・対象リポジトリのパスを渡す。
- planner は計画を返す。統括は計画をユーザーに見せ、承認を得てからタスクの Implementation Notes に記録する。
- 計画のステップは 1 つずつ実装とレビューを回せる大きさにする。1 ステップが 1 コミットになる。

## 5. 実装と点検のループ

ステップごとに次を繰り返す。サブエージェントは毎回新しく起動し、前のステップの会話を引き継がない。

1. implementer サブエージェント(`dev-skills:implementer`)を起動する。渡すのは、対象リポジトリのパス、ブランチ名、そのステップの計画(変更するファイル・手順・完了条件・検証コマンド)、変更してよい範囲である。implementer は実装してテストを通し、コミットして、変更ファイルとテスト結果を報告する。
2. reviewer サブエージェント(`dev-skills:reviewer`)を起動する。渡すのは、対象リポジトリのパス、レビューする範囲(`<base>..HEAD` のコミット範囲)、そのステップの計画である。reviewer は「承認」か「要修正」と修正点の一覧を返す。
3. 要修正なら、修正点を implementer に渡して直させ、再び reviewer に点検させる。3 回直しても承認されないときは、統括がユーザーに状況を報告して判断を仰ぐ。
4. 承認されたら、ステップの結果をタスクの Implementation Notes に書く。

統括は各報告を鵜呑みにせず、テストの実行結果と `git log`・`git diff` で検収する。

## 6. PR を出す

- 全ステップが承認されたら push し、PR を作る。
- CI の結果を確認する。失敗したら、失敗ログを implementer に渡して直させ、再 push して再確認する。
- PR のマージはユーザーの指示を得てから行う。手順は `references/git-flow.md` に従う。

## 7. 閉じる

- マージ後に `main` を更新し、作業ブランチを削除する。
- タスクを Done にし、Final Summary に結果(何ができるようになったか、PR 番号、残した課題)を書く。

```sh
backlog task edit <id> -s Done --final-summary "<結果>"
```

## 8. 参照ファイル

| ファイル | 内容 |
| :-- | :-- |
| `references/git-flow.md` | ブランチ・コミット・push・PR・CI 確認・マージのコマンド |
| `references/hooks.md` | git hook(lefthook・husky)の導入 |
| `../../agents/planner.md` | planner の役割と出力形式 |
| `../../agents/implementer.md` | implementer の役割と報告形式 |
| `../../agents/reviewer.md` | reviewer の役割と判定形式 |
