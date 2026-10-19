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

## 4. シークレット検知・依存監査・SAST

要件の品質がプロダクトのとき、hook にシークレット検知と依存監査を追加する。pre-commit で gitleaks、pre-push で osv-scanner を実行する。エコシステム標準の監査(`npm audit`・`cargo audit`・`pip-audit` など)が既に入っていればそれを使い、osv-scanner を重ねて入れない。依存が 1 つも無いリポジトリ(マニフェストやロックファイルが無い、または依存の記載が 0 件)では osv-scanner を入れない。監査の対象が無いと終了コード 128 で失敗し、push が止まる。オフラインでも API に届かず、終了コード 129 で止まる。

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

CI があるリポジトリでは、hook と同じ検査を CI にも入れる。hook は `--no-verify` を付けたときや、hook を入れていない clone では動かない。osv-scanner を入れない条件は hook と同じである。GitHub Actions では次の 2 つの job を追加する。

```yaml
jobs:
  secrets:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0               # gitleaks は履歴全体を走査する
          persist-credentials: false
      - uses: gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e # v3.0.0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_ENABLE_COMMENTS: false   # 既定では PR にコメントする
  audit:
    permissions:
      actions: read
      contents: read
      security-events: write
    uses: google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@b1d267aea5211fa648d9d442fa64b90dbdcbdd36 # v2.7.0
```

organization のリポジトリでは、gitleaks-action に `GITLEAKS_LICENSE`(無料で発行される)の secret が必要である。

品質がプロダクトのとき、CI に SAST を入れる。public リポジトリでは CodeQL(GitHub の code scanning。public は無料)を使い、private リポジトリでは semgrep を使う。CodeQL の job の例を次に示す。`languages:` にはリポジトリの言語を書く。

```yaml
jobs:
  codeql:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: github/codeql-action/init@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee # v4.39.0
        with:
          languages: python            # 例: javascript-typescript / go / actions
      - uses: github/codeql-action/analyze@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee # v4.39.0
```

semgrep は CI の step で `semgrep scan --config p/default --error` を実行する。この形はログインが要らず、検出があると終了コード 1 で失敗する。

## 5. 確認

- hook を直接実行し、lint とテストが動くことを確かめる。lefthook は `lefthook run pre-commit` と `lefthook run pre-push`、husky は `sh .husky/pre-commit` と `sh .husky/pre-push`。
- 4. を入れたときは、gitleaks と osv-scanner も hook から実行され、終了コード 0 で終わることを確かめる。
- 4. の CI の job を入れたときは、PR の CI でその job が成功することを確かめる。
- hook を入れたコミットは、計画の最初のステップとは別のコミットにする(`chore: git hook を導入する`)。
