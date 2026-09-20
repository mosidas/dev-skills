# GitHub flow の手順

`main` を常にデプロイ可能な状態に保ち、変更はブランチと PR で入れる。

## 1. ブランチ

```sh
git switch main && git pull --ff-only
git switch -c <type>/<TASK-id>-<slug>     # 例: feat/TASK-021-export-csv。タスクが無いときは feat/export-csv
```

## 2. コミット

- 1 ステップを 1 コミットにする。メッセージは `<type>: <変更内容>`(日本語可)。本文に理由を書く。
- pre-commit hook(lint)が失敗したら、`--no-verify` で回避せず原因を直す。

## 3. push と PR

```sh
git push -u origin <ブランチ名>
gh pr create --fill --base main          # タイトルと本文を手で書くときは --title と --body
```

PR 本文には、目的、変更の要点、検証したこと(テスト・手動確認)を書く。

## 4. CI の確認

```sh
gh pr checks --watch --fail-fast         # すべて終わるまで待ち、失敗があれば即座に終了する
gh run list --branch <ブランチ名> --limit 3
gh run view <run-id> --log-failed        # 失敗したステップのログだけを見る
```

- 失敗したら、ログの該当箇所を implementer に渡して直させ、コミットして再 push する。`gh pr checks --watch` を再実行する。
- CI が無いリポジトリでは、pre-push hook のテスト結果を CI の代わりとし、PR 本文にその旨を書く。

## 5. マージ

ユーザーの指示を得てから実行する。

```sh
gh pr merge <番号> --merge --delete-branch
git switch main && git pull --ff-only
git branch -D <ブランチ名>               # ローカルに残ったとき
```
