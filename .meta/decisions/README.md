# 設計判断の記録(decisions)

`DESIGN.md` の**判断層**(手書き SSoT)を、1 判断 1 ファイルで記録する。各ファイルの必須節は次の 5 つとし、本書をその正本とする(他の文書は本書を参照し、必須節を独自に列挙しない)。

| 節               | 内容                                                             |
| ---------------- | ------------------------------------------------------------------ |
| 背景             | 判断が必要になった状況と、根拠にした事実(出典つき)               |
| 決定             | 何を決めたか                                                     |
| 却下した選択肢   | 採らなかった案と、採らなかった理由                               |
| 帰結             | この判断で変えたもの(該当が無い場合は「無し」と理由を書く)     |
| 再検討条件       | どの事象が観測されたら判断をやり直すか                           |

`DESIGN.md` の構造層(`meta-doc` がスキルの定義から生成する)は、この記録に `D-###` で参照を張る。層分離の原則は `../../.claude/skills/meta-core/references/principles.md` §3。

- ファイルは `D-<番号>-<スラグ>.md` で命名する。番号は採番したら再利用しない(索引に欠番が生じることがある)。
- 追記のみとする。判断を覆す場合は既存エントリを消さず、新エントリで supersede する(旧エントリに「→ D-### で更新」を追記)。
- `D-000` は meta-doc 導入前の手書き `DESIGN.md`(初版)の内容で、判断層の基底として保存したもの。

## 索引

- [D-000](D-000-original-design.md): dev スキル群 設計思想(初版・DESIGN.md 由来)
- [D-001](D-001-layer-b-quality.md): レイヤー B 品質のため `.claude` を SSoT とし、DESIGN を 2 層分離、`meta-*` を導入
- [D-004](D-004-design-template-overwrite.md): DESIGN.md をテンプレート準拠の現状生成物にし、更新は全上書きにする
- [D-005](D-005-quality-target-naming.md): 品質の対象の呼称を「レイヤー A/B」から「成果物の品質 / スキル群自体の品質」へ改める
- [D-006](D-006-install-hardcopy-exclude-meta.md): 導入をハードコピーにし、meta-* を消費側へ配布しない
- [D-007](D-007-script-driven-multistage.md): 多段オーケストレーションの禁止対象をエージェント主導に限定する
- [D-008](D-008-model-invocation-policy.md): 配布する部品をモデル自動起動の対象に置いたままにする
- [D-009](D-009-glossary-as-durable-info.md): 恒久情報の配置に用語集を追加する
- [D-010](D-010-script-unit-tests.md): スクリプトの単体テストを tests/ に置き、配布しない
- [D-011](D-011-skill-groups-outside-dotclaude.md): 配布するスキルを `.claude` の外の用途グループへ置く
- [D-012](D-012-generic-skill-groups.md): 汎用スキルを用途ごとのグループへ置き、グループ単位で導入する
- [D-013](D-013-group-config-declaration.md): グループ固有の規約を宣言ファイルへ外出しする
- [D-014](D-014-group-owned-mechanisms.md): port と拡張バンドルをグループ配下へ移す
- [D-015](D-015-reference-load-control.md): 参照を常時と条件付きに分け、100 行超の参照に目次を付ける
- [D-016](D-016-prompt-data-boundary.md): サブエージェント・プロンプトで指示とデータを構造で区別する
- [D-017](D-017-compaction-recovery.md): 圧縮後の再開をファイルからの再導出で担保する
- [D-018](D-018-hook-guardrail-bundle.md): 決定論的強制を hook 拡張バンドルとして配る
- [D-019](D-019-verification-modes.md): 検証手段の 3 方式を principles.md で対応づける
- [D-020](D-020-resume-and-rollback.md): 中断からの再開手順を固定し、巻き戻し手段を定める
- [D-021](D-021-completion-false-positive.md): 完了判定の偽陽性への対策を実装者と判定器に置く
- [D-022](D-022-autonomy-boundary.md): 自走と headless をレイヤー 3 に閉じ、dev-author をコアから外す
- [D-023](D-023-structure-inventory-keep.md): 4 観点の棚卸しで維持と決めた構成要素
- [D-024](D-024-workdir-sequence.md): workdir のディレクトリ名に連番を付け、採番をエンジンが行う
- [D-025](D-025-roadmap-scoped-spec-layout.md): specs を roadmap ごとの 2 階層にし、roadmap.md を状態機械で凍結する
