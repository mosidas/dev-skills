# タスクの追加

タスクの追加では利用者がブラウザーか CLI から期限付きのタスクを保存する。書きかけの入力は取り消せる。保存したタスクは一覧から開いた別の画面で確かめられる。

## サブ機能

- `add-open`: ブラウザーの各入口から空の入力欄を開く。
- `add-save`: 題と期限を保存する。
- `add-cancel`: ブラウザーで書きかけの入力を破棄する。
- `add-cli`: 端末から同じ形のタスクを作る。

## 利用者からの到達

- ブラウザーのツールバーの `タスクを追加` ボタンを押す。
- 入力欄の外にフォーカスがある状態でブラウザーで `a` を押す。
- 端末で `tasks add --title <題> --due <期限>` を実行する。

## 操作

前提:

- Tasks が `http://127.0.0.1:5173` で健康診断を通っている。
- 題が `議事録の共有` のタスクが無い。
- `drive doctor` が期待する URL と使い捨てのデータのディレクトリを示す。

- **入力欄を開く**: `タスクを追加` を押す。`drive browser click --role button --name "タスクを追加"` を実行する。`タスクの入力` という名前のフォームが現れる。`題` の入力欄にフォーカスがある。
- **内容を入れる**: 題と期限を入力する。`drive browser fill --role textbox --name "題" --value "議事録の共有"` と `drive browser fill --role textbox --name "期限" --value "2026-11-30"` を実行する。`保存` ボタンが押せる状態になる。
- **保存する**: `保存` を押す。`drive browser click --role button --name "保存"` を実行する。`保存しました` という名前のステータスが現れる。一覧に `議事録の共有` が加わる。
- **保存を確かめる**: 一覧から開き直す。`drive browser click --role link --name "すべてのタスク"` と `drive browser click --role link --name "議事録の共有"` を実行する。詳細の画面に保存した題と期限が出る。
- **取り消す**: 新しい入力欄を開いて `破棄するタスク` と入れてから `取り消し` を押す。`drive browser click --role button --name "タスクを追加"`・`drive browser fill --role textbox --name "題" --value "破棄するタスク"`・`drive browser click --role button --name "取り消し"` を実行する。一覧に戻る。一覧に `破棄するタスク` のリンクが無い。
- **CLI から追加する**: 2 件目を端末から作る。`drive cli -- tasks add --title "CLI のタスク" --due 2026-12-01 --format json` を実行する。終了コードが `0` である。標準出力に新しいタスクの ID と題がある。
- **証拠を取る**: `すべてのタスク` から保存した 2 件を開き直す。`drive browser snapshot --aria --path "$EVIDENCE_DIR/add-task/list.aria.txt"` と `drive browser screenshot --path "$EVIDENCE_DIR/add-task/list.png"` を実行する。2 つの証拠に `議事録の共有` と `CLI のタスク` が写る。

## 落とし穴

- 入力欄にフォーカスがあるときに `a` を押すと文字が入力される。入力欄は開かない。
- 題は前後の空白を除いて保存される。確かめるのは表示された題である。入力欄の値ではない。
- 保存のステータスだけでは証拠に足りない。一覧から開き直して確かめる。
- 後始末で `議事録の共有` と `CLI のタスク` を削除する。証拠は残す。
