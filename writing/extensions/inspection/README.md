# inspection — 日本語検査の決定論的発火(バンドル群)

japanese-writing スキルの検査(`scripts/lint.py`)を、エージェントの自主性に任せず hook で決定論的に発火させるバンドルを収める。文章の指示は助言であり毎回の実行を保証しないという前提に立ち、検査の**発火と完了前のゲート**だけを機械化する。検出への対応(書き直しの判断)はエージェントと書き手に残す(判断の根拠は `../../../.meta/decisions/D-035-writing-inspection-hooks.md`)。

## 収録物

| バンドル | 収録物 | 強制する動作 |
| -------- | ------ | ------------ |
| [ext-writing-inspection](ext-writing-inspection/SKILL.md) | hooks 3 本 + 検査設定 + 言い換え指針 + `settings.snippet.json` | 日本語 Markdown の書き込み直後の lint 実行と警告・セッション完了時の再検査と重大カテゴリによる完了ブロック |

## 導入

```console
$ python3 <dev-skills のパス>/install.py ext ext-writing-inspection --target <利用側プロジェクト>
```

導入の一般規約(バンドル名の解決・`settings.snippet.json` のマージ・削除)は `../../../dev/extensions/README.md` 2. に従う。

## 導入前に判断すること

- **前提が 2 つある**。導入先に japanese-writing が導入済みであること(`install.py core --target <利用側プロジェクト> writing`)と、`uv` が使えること。欠けている場合、hook はエラーを出さず素通しになる。
- **効く範囲は導入したプロジェクトの全セッション**である。日本語 Markdown を書くたびに lint(sudachipy の辞書ロードを含む)が走るため、書き込みのたびに数秒の遅延が乗る。
- **Stop hook はセッションの完了を差し戻すことがある**。重大カテゴリ(バンドルの `inspection.config.json` が宣言)の検出が残るあいだ完了をブロックする。ブロック回数には上限があり、無限には封鎖しない。
