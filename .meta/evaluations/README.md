# 評価シナリオ(evaluations)

スキル群が実タスクで意図どおり働くかを、代表シナリオで確認する。[Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) が「広範な文書を書く前に評価を作る」(3 つ以上の代表シナリオ、利用するモデルすべてでの実行)を求めることに対応する。

- **シナリオの定義は本書に置き、実行結果は日付ごとのファイル(`<日付>-results.md`)に置く**。定義は改修をまたいで維持し、結果は実行のたびに追加する。
- **確認できることとできないことを分ける**。決定論スクリプト・hook の挙動は実行して確かめられる。スキルの手順の選択(どの経路を選ぶか・どの参照を読むか)は、手順を読んで適用した結果を記録する。実際の起動が description で選ばれるかは、この評価では確かめない(`trigger_check.py` が語彙の一致だけを見る近似を担う)。
- **期待挙動は事前に書く**。実行してから期待を書き直さない。満たさなかった場合は、結果ファイルに不一致として記録する。

## 実行環境

シナリオは、一時ディレクトリに作った利用側プロジェクトで実行する。

```console
$ python3 <dev-skills>/install.py core --target <一時プロジェクト> dev
$ python3 <dev-skills>/install.py ext ext-dev-guardrails --target <一時プロジェクト>
```

## シナリオ

### E-001: 軽微な変更の経路判定

- **入力**: 「ログイン画面の見出しのタイポを直して」
- **対象**: `../../dev/skills/flow-sdd/SKILL.md` 2.(ルーティング)・3.(ブランチ運用)・5. Step 4
- **期待挙動**: 経路 B(作業単位化が不要)を選ぶ。状態機械を使わず、`state.json`・`roadmap.md` を作らない。現在のブランチで作業する。Step 4(PR 作成と CI 追従)を実行しない。経路の確定に人間承認を求める。
- **確認方法**: 手順を適用して選んだ経路と、その帰結(作らないファイル・実行しない Step)を記録する。

### E-002: 中断からの再開

- **入力**: workdir に `spec-generated` の `state.json` と `spec.md` があり `tasks.md` が無い状態で「SDD を再開して」
- **対象**: `../../dev/skills/flow-sdd/SKILL.md` 5. Step 0(D-020)
- **期待挙動**: 手順 1〜4 をこの順で実行する。手順 3(開始時の検証)は `tasks.md` が実在しないため省く。手順 4 で `spec-generated` に対応する Step 1 の承認待ちから続行し、明示承認を待って停止する。
- **確認方法**: 手順 1・2 を実際に実行して出力を記録し、手順 3 の省略条件の判定結果と、手順 4 で選んだ続行先を記録する。

### E-003: 条件付き参照の選択

- **入力**: 3 種のタスク。(A) 外部ライブラリを使わず公開インターフェースも足さない純ロジックの実装、(B) 外部 API を呼び、新しい公開インターフェースを定義する実装、(C) 全タスク完了後の最終検証
- **対象**: `../../dev/skills/dev-implement/SKILL.md` 2.(D-015)
- **期待挙動**: (A) は常時参照のみを読む。(B) は `source-driven.md` と `contract-and-domain.md` を追加で読む。(C) は `review-perspectives.md` と `final-review-prompt.md` を追加で読む。いずれの場合も、条件に当たらない参照は読まない。
- **確認方法**: 条件表を適用して読む参照を決め、それぞれの行数を合計して記録する。改修前(必読 13 ファイル・1,036 行)と比較する。

### E-004: 破壊的な git 操作と一括ステージングの拒否

- **入力**: バンドル導入後のプロジェクトで、`guard_bash.py` へ PreToolUse の JSON を渡す。拒否されるべき 5 種(`git reset --hard`・`git add -A`・`git -C . reset --hard`・`FOO=1 git clean -fd`・`git push origin +main`)と、通るべき 5 種(`git add <file>`・`git revert`・`git stash push`・禁止語を含むコミットメッセージ・`--force-with-lease`)
- **対象**: `../../dev/extensions/guardrails/ext-dev-guardrails/hooks/guard_bash.py`(D-018)
- **期待挙動**: 拒否は exit 2 と、禁止の理由・代替手段を含む標準エラー出力。許可は exit 0 で出力なし。
- **確認方法**: 導入先のパスから hook を実行し、exit code と出力を記録する。

### E-005: 凍結済み中間生成物への書き込みの拒否

- **入力**: 状態機械で `completed` まで進めた workdir に対し、`spec.md` への Edit(絶対パス・相対パス・シンボリックリンク経由)、凍結対象外の `research.md` への Write、コードへの Write
- **対象**: `../../dev/extensions/guardrails/ext-dev-guardrails/hooks/guard_write.py`(D-018)
- **期待挙動**: 凍結済みの `spec.md` は 3 通りの指定すべてで拒否(exit 2)。凍結対象外とコードは許可(exit 0)。
- **あわせて確認する縮退**: バンドルを導入しない場合、同じ変更は `check.py` が凍結違反として事後検出する(error・exit 1)。hook は検出を防止へ変える上乗せであり、置き換えではないことを示す。
- **確認方法**: `state.py` で凍結した workdir を作り、hook と `check.py` の両方を実行して記録する。

### E-006: 圧縮後の現在地の再導出

- **入力**: 一部のタスクが `[x]` の `tasks.md`、`implementing` の `state.json`、コミット済みの実装、`## Implementation Notes` の記録がある状態
- **対象**: `../../dev/skills/dev-implement/SKILL.md` 6.1(D-017)
- **期待挙動**: 6.1 の手順 1〜4 だけで、未完了タスク・直近のコミット・状態・これまでの学習をすべて再導出できる。会話の要約に依存しない。
- **確認方法**: 手順 1〜4 を実行し、それぞれの出力を記録する。

### E-007: `dev-author` を配布しない

- **入力**: `install.py core --target <一時プロジェクト> dev`
- **対象**: D-022
- **期待挙動**: 配布されるエージェントは 4 件(dev-implementer・dev-reviewer・dev-debugger・dev-explorer)で、`dev-author.md` を含まない。
- **確認方法**: 導入先の `.claude/agents/` を一覧して記録する。

## 結果

- [2026-08-10-results.md](2026-08-10-results.md): D-015〜D-023 の改修後の実行結果
