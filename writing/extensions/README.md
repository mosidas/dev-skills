# writing グループの拡張(Layer 3 相当)

writing グループのスキル(japanese-writing)に上乗せする拡張バンドルを収める。harness の機構(hooks・`settings.json`)に依存する強制手段は本体のスキルに置かないため、ここに置く。

バンドル構成・導入・削除の機構は dev グループと共通であり、規約の正本は `../../dev/extensions/README.md`(1.〜3.)にある。dev グループ固有の規律(Layer 0〜2 のレイヤー構造・dev-core への依存)は writing グループには適用せず、writing のバンドルは japanese-writing 等 writing グループのスキルに依存する。

**この場所のファイルは実行時に読まれない**。展開スクリプト(`../../install.py`)で利用側プロジェクトへ導入して使う。本体のスキルはこれらの拡張の存在を前提にしない(なくても動く)。

## バンドル群

| バンドル群 | 目的 |
| ---------- | ---- |
| [inspection](inspection/README.md) | japanese-writing の検査を hook で決定論的に発火させ、重大な検出が残るあいだ完了をブロックする |
