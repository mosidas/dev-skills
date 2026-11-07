# Markdown の形式の規範

## 1. 見出しの階層

- 見出しはレベル 2〜5 に付番する(レベル 2 は `1.`、レベル 3 は `1.1.`、以下同様)。レベル 1 とレベル 6 以上には付番しない。
- 本文は最下位の見出しの下にのみ置く。本文を持つ見出しの下にさらに見出しを置かない。

## 2. 記法

- Markdown 形式で記述し、GitHub での表示を前提に [GitHub Flavored Markdown](https://github.github.com/gfm/) に従う。
- 作成日・版・対象コミットなどのメタ情報は frontmatter に書く。本文へ書くのは、読み手の判断に関わる場合に限る。
- 他者向けの文書では、作り手が後でたどるための参照(素材と中間ファイルのパス・タスクの識別子)を frontmatter にも本文にも書かず、ファイルの末尾に HTML コメントで書く。読み手はそのパスを開けない(`../readers.md` 3.)。パスはリポジトリからの相対パスで書く。HTML コメントはファイルのソースに残るため、絶対パスを書くとホームディレクトリの名前が配布先に渡る。
- 必要に応じて[アラート記法](https://docs.github.com/ja/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts)を使用してよい。
