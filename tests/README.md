# スクリプトの単体テスト

各スキルの `scripts/` に置く決定論スクリプトと `install.py` に対する単体テスト。スキル群自体の品質(メタレベル)を担保する道具の 1 つで、機械検査(meta-check)が「文書間の整合」を見るのに対し、本テストは「スクリプトが主張どおり動くこと」を見る。

## 1. 実行

リポジトリのルートで実行する。

```sh
python3 -m unittest discover -s tests -t tests
```

個別のファイルだけを走らせるときは次のようにする。

```sh
python3 -m unittest discover -s tests -t tests -p test_state.py
```

追加インストールは不要である(標準ライブラリの `unittest` のみを使う。dev-core・meta-core のスクリプトが標準ライブラリのみで動く規律と揃える)。

## 2. 配置と配布

- テストは**配布物に含めない**。`install.py core` は用途グループの `skills/*` と `agents/*` をコピーするため、`tests/` はその対象外になる。`meta-*` を配布しない方針(D-006)と同じ扱いである(D-010)。
- スクリプトはパッケージ化されていない(利用側へ単体でハードコピーするため)。テストからは `helpers.py` が `sys.path` へスクリプトのディレクトリを追加して読み込む。

## 3. 構成

| ファイル                | 対象                       | 主な検査                                                             |
| ----------------------- | -------------------------- | ---------------------------------------------------------------------- |
| `helpers.py`            | —                          | 一時ディレクトリ・サブプロセス実行・共通のワークフロー定義             |
| `test_install.py`       | `install.py`               | 用途グループの走査・配布対象・名前衝突・廃止分の削除・拡張バンドルの解決と導入 |
| `test_lib.py`           | `dev-core/lib.py`          | 定義データの検証・中間生成物のパース・依存循環の検出・凍結             |
| `test_state.py`         | `dev-core/state.py`        | 遷移の拒否・承認ゲートの強制・完了時の凍結・横断集約                   |
| `test_check.py`         | `dev-core/check.py`        | 状態検査・凍結違反・トレーサビリティ・対象ファイルの行数               |
| `test_ports.py`         | `dev-core/ports.py`        | frontmatter の走査と規約違反の警告                                     |
| `test_meta_lib.py`      | `meta-core/meta_lib.py`    | frontmatter の YAML サブセット解析・配置の走査・グループの機構の列挙・グループ規約の読み込み |
| `test_meta_check.py`    | `meta-core/meta_check.py`  | 参照・frontmatter・依存規律・状態整合・グループ規約・未記入マーカー・回帰検出 |
| `test_trigger_check.py` | `meta-core/trigger_check.py` | 肯定例・否定例・近接衝突・ケース網羅・仕様ファイルの異常系            |
| `test_meta_extract.py`  | `meta-core/meta_extract.py` | 部品・スクリプト・エージェント・状態機械・inject グラフの抽出         |
| `test_meta_loc.py`      | `meta-core/meta_loc.py`    | 領域の割り当て・行数の数え方・除外条件                                 |

## 4. 書き方の規律

- **一時ディレクトリで自己完結させる**。リポジトリ内のファイルを書き換えるテストを書かない。実リポジトリを対象にするのは read-only の検査(`--root` を渡して実行する形)に限る。
- **exit code とエラーメッセージはサブプロセスで確かめる**。`die()` が `sys.exit` を呼ぶため、関数を直接呼ぶと処理が中断する。
- **検出できることと誤検出しないことを対で書く**。違反を入れて検出を確かめるだけでは、常に検出する実装(偽陽性)を通してしまう。
- テスト名は日本語で、何が成り立つべきかを書く(`test_定義にない遷移を拒否する`)。Python の識別子に使えない記号(半角スペース・括弧)を含めない。
