# git hook の導入

pre-commit で lint(整形を含む)、pre-push でテストを実行する。hook が無いリポジトリで、ブランチを切った直後に入れる。既に hook の仕組み(`lefthook.yml`・`.husky/`・`.pre-commit-config.yaml` など)があるときは、それを使い、別の仕組みを足さない。

## 1. 選び方

| リポジトリ | 手段 |
| :-- | :-- |
| `package.json` がある | husky |
| それ以外 | lefthook(単一バイナリで言語に依存しない) |

lint とテストのコマンドは、そのリポジトリが既に使っているもの(`package.json` の scripts、`Makefile`、`pyproject.toml` など)から選ぶ。無ければ言語の標準的なツールを入れる。

## 2. lefthook

```sh
brew install lefthook        # macOS。ほかは https://github.com/evilmartians/lefthook#install
lefthook install             # .git/hooks に登録する(clone 直後にも実行する)
```

`lefthook.yml` をリポジトリ直下に作る。

```yaml
pre-commit:
  commands:
    lint:
      run: <lint コマンド>        # 例: uv run ruff check . / go vet ./...
pre-push:
  commands:
    test:
      run: <テストコマンド>       # 例: uv run pytest -q / go test ./...
```

## 3. husky

```sh
npm install --save-dev husky
npx husky init                # .husky/pre-commit を作り、package.json に prepare スクリプトを足す
```

`.husky/pre-commit` と `.husky/pre-push` にコマンドを書く。

```sh
# .husky/pre-commit
npm run lint

# .husky/pre-push
npm test
```

## 4. 確認

- hook を直接実行し、lint とテストが動くことを確かめる。lefthook は `lefthook run pre-commit` と `lefthook run pre-push`、husky は `sh .husky/pre-commit` と `sh .husky/pre-push`。
- hook を入れたコミットは、計画の最初のステップとは別のコミットにする(`chore: git hook を導入する`)。
