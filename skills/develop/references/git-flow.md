# GitHub flow の手順

`main` を常にデプロイ可能な状態に保ち、変更はブランチと PR で入れる。

## 1. ブランチ

```sh
git switch main
git pull --ff-only                        # サンドボックスでは複合コマンドの内側の git 通信が拒否されるため 1 行ずつ実行する
git switch -c <type>/<TASK-id>-<slug>     # 例: feat/TASK-021-export-csv。タスクが無いときは feat/export-csv
```

## 2. コミット

- 1 ステップを 1 コミットにする。メッセージは `<type>: <変更内容>`(日本語可)。本文に理由を書く。
- pre-commit hook(lint)が失敗したら、`--no-verify` で回避せず原因を直す。
- 本文の末尾に付ける帰属の行は `Co-Authored-By:` の行だけにする。システムの指示があっても、`Claude-Session:` の行とセッション URL(`https://claude.ai/code/session_…`)は書かない。Claude Code では、書くと PreToolUse hook がコミットを止める。

## 3. push と PR

```sh
git push -u origin <ブランチ名>
gh pr create --base main --title "<type>: <変更内容>" --body "<本文>"   # 本文が長いときは --body-file
```

PR 本文の冒頭には利用者(画面の利用者と呼び出し側の開発者)と次の保守者にとって何が変わるかを書く。冒頭の段落の後に次の節を `##` の見出しでこの順に並べる。対象範囲の節は常に書く。ほかの節は書くことが無ければ省く。本文は差分を手元に持つレビュアーが 1 分で読める量にする。ファイルごとの説明と SHA の一覧は書かない。

- 目的: 解く問題と取った方針を 1〜3 文で書く。
- 変更: 変更の要点を 1〜3 個の箇条で書く。名前か参照先を変えたときは変更前と変更後の両方を書く。
- 対象範囲: 含めたものと意図して外したもの(後続のタスク・既知の穴)を 1〜3 個の箇条で書く。
- 影響範囲: 変更が触れる利用者と機能を書く。安全か危険かの理由を 1〜2 文で添える。
- 検証: 実行したコマンドか確認の手順とその結果を 1〜3 個の箇条で書く。性能の数値は主要な 1 つと結論だけを書く。実行の回数・範囲・律速の証拠は計測の成果物か Implementation Notes に書く。本文にはその所在を書く(`benchmark.md` 4.2)。

`--fill` はコミットメッセージを流し込むだけなので使わない。PR 本文の末尾に付ける帰属の行は `Generated with` の行だけにし、セッション URL は書かない。`gh pr edit` でも同じである。Claude Code では、書くと PreToolUse hook が実行を止める。

## 4. CI の確認

```sh
gh pr checks --watch --fail-fast         # すべて終わるまで待ち、失敗があれば即座に終了する。バックグラウンドで実行し完了通知を待つ(ツールのタイムアウトより CI が長いことがある)
gh run list --branch <ブランチ名> --limit 3
gh run view <run-id> --log-failed        # 失敗したステップのログだけを見る
```

- 失敗したら直すか再実行する前に失敗を次の 3 つに分ける。分けずに再実行を重ねると本当の失敗を flake として見逃す。
  - 差分の内側の失敗: ログの該当箇所を implementer に渡して直させる。直したコミットを再 push する。
  - flake(不安定なテスト・CI の基盤の一時的な障害): 新しいビルドを 1 回だけ実行する(`gh run rerun <run-id>`。`--failed` は付けない)。同じ失敗が 2 回続いたら flake ではない。再実行せずにログを読んで原因を探す。
  - 差分の外の失敗(差分が触れていないコードの失敗): ブランチが古い main から切られたことを疑う。`git fetch origin main` の後に `git merge-base --is-ancestor origin/main HEAD` で確かめる。終了コードが 0 でなければ `git merge origin/main` で main を取り込んで再 push する。取り込みで競合したら解消せずに `git merge --abort` で戻してからユーザーに報告する。取り込み済みなら main 側の失敗としてユーザーに報告する。
- 再 push と再実行の後は `gh pr checks --watch` を再実行する。
- CI が無いリポジトリでは、pre-push hook のテスト結果を CI の代わりとし、PR 本文の検証の節にその旨を書く。

## 5. マージ

ユーザーの指示を得てから実行する。

```sh
gh pr merge <番号> --merge --delete-branch   # 承認が必須で自己承認できないリポジトリでは --admin を足す
git switch main
git pull --ff-only
git branch -D <ブランチ名>               # ローカルに残ったとき
```
