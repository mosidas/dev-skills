# guardrails — 規律の決定論的強制(バンドル群)

dev スキル群が文章で課している規律のうち、機械判定が閉じるものを hook で強制するバンドルを収める。文章の指示は助言であり毎回の遵守を保証しないという前提に立ち、守られないと作業ツリー・履歴・凍結済み成果物を壊す規律だけを対象にする(判断の根拠は `../../../.meta/decisions/D-018-hook-guardrail-bundle.md`)。

## 収録物

| バンドル | 収録物 | 強制する規律 |
| -------- | ------ | ------------ |
| [ext-dev-guardrails](ext-dev-guardrails/SKILL.md) | hooks 2 本 + `settings.snippet.json` | 破壊的な git 操作の禁止・一括ステージングの禁止・凍結済み中間生成物の変更禁止 |

## 導入

```console
$ python3 <dev-skills のパス>/install.py ext ext-dev-guardrails --target <利用側プロジェクト>
```

導入の一般規約(バンドル名の解決・`settings.snippet.json` のマージ・削除)は `../README.md` 2. に従う。差し替え port の要件はこのバンドル群には無い。

## 導入前に判断すること

- **効く範囲は導入したプロジェクトの全セッション**である。hook は `.claude/settings.json` に配線されるため、dev スキル群を使わない操作にも働く。
- **拒否は理由と代替手段を返す**。禁止だけを返して行き先を示さない形にはしない(コミット済みは `git revert`、未コミットは `git stash push`、ステージングは `git add <file>`)。
- **判定はコマンド文字列とパスの照合による**。変数展開・スクリプト経由の実行は判定できない。hook は文章の規律を置き換えず、上乗せする。
