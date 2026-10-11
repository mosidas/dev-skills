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

## 4. シークレット検知と依存監査

要件の品質がプロダクトのとき、hook にシークレット検知と依存監査を追加する。pre-commit で gitleaks、pre-push で osv-scanner を実行する。エコシステム標準の監査(`npm audit`・`cargo audit`・`pip-audit` など)が既に入っていればそれを使い、osv-scanner を重ねて入れない。

```sh
brew install gitleaks osv-scanner   # macOS。ほかは https://github.com/gitleaks/gitleaks と https://google.github.io/osv-scanner/installation/
```

lefthook では `lefthook.yml` の各 `commands:` に次のコマンドを追加する。

```yaml
pre-commit:
  commands:
    secrets:
      run: gitleaks git --pre-commit --staged --redact
pre-push:
  commands:
    audit:
      run: osv-scanner scan source -r .
```

husky では `.husky/pre-commit` と `.husky/pre-push` の末尾に 1 行ずつ追加する。

```sh
# .husky/pre-commit
gitleaks git --pre-commit --staged --redact

# .husky/pre-push
osv-scanner scan source -r .
```

## 5. 確認

- hook を直接実行し、lint とテストが動くことを確かめる。lefthook は `lefthook run pre-commit` と `lefthook run pre-push`、husky は `sh .husky/pre-commit` と `sh .husky/pre-push`。
- hook を入れたコミットは、計画の最初のステップとは別のコミットにする(`chore: git hook を導入する`)。
