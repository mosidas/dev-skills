# 場ごとの規範

## 1. 場ごとの形

| 要素 | issue・PR のコメント | レビューコメント | 業務チャット | メール |
| :-- | :-- | :-- | :-- | :-- |
| 宛名 | 書かない。特定の人に頼むときは `@` メンション | 書かない | 書かない。特定の人に頼むときはメンション | 書く(「株式会社サンプル 山田様」) |
| 挨拶 | 書かない | 書かない | 社内なら最初の行に 1 回まで | 書く |
| 名乗り | 書かない | 書かない | 書かない | 書く |
| 結び | 書かない | 書かない | 依頼のときだけ 1 回まで | 書く |
| 署名 | 書かない | 書かない | 書かない | 書く |
| Markdown | 使える | 使える | ツールが描画する記法だけを使う | 使わない |
| ラベル | リポジトリの慣習に合わせる | 必須かどうかを示す(4.) | なし | なし |

- メールの返信では、件名を変えない。
- チャットでは、挨拶だけのメッセージを送らない。挨拶と用件を 1 つのメッセージにまとめる。
- issue・PR のコメントは、敬体で用件(閉じる、マージする、確認を頼む)から書く。

## 2. 残す定型句と削る定型句

lint が検出しても、次の表で「残す」とした場の定型句は残す。

| 定型句 | 残す | 削る |
| :-- | :-- | :-- |
| 「お世話になっております」 | 社外メールの挨拶 | ほかの場 |
| 「お疲れ様です」 | 社内メールと社内チャットの最初の行(1 回) | 社外への連絡、issue・PR のコメント |
| 「よろしくお願いいたします」 | メールの結び、チャットの依頼の結び(1 回) | issue・PR のコメント、レビューコメント |
| 「何かございましたらご連絡ください」 | 社外メールの結び | チャット、issue・PR のコメント、レビューコメント |
| 「ご確認いただけますと幸いです」 | 期限も要否も無い依頼 | 期限か要否のある依頼(`keigo.md` 6.) |

表に無い定型の謝辞・申し出・結びは、`SKILL.md` 5. に従って削る。

## 3. バグ報告

- 次の 5 つを書く。
  1. 再現手順(番号付きの箇条書き)
  2. 期待した結果
  3. 実際の結果
  4. 具体的なバージョン(「最新版」と書かない)
  5. エラーメッセージ(コードブロックに原文のまま)
- 原因の推測は、症状と分けて書く。推測であることを明示し、症状も省かない。
- 公開してよい情報だけを書く。アカウント ID・ユーザー名・トークン・社内のホスト名は、ダミーの値に置き換える。
- 1 つの issue には 1 つの話題だけを書く。既存の issue への賛同は「+1」のコメントでなく、リアクションで示す。

## 4. レビューコメント

- コードについて書き、人について書かない。
  - Before: 「なぜここでスレッドを使ったのですか？」
  - After: 「この処理は並行にしても速くならないため、スレッドを使わない形にできますか？」
- 指摘には理由を書く。
- 必須の指摘か任意の提案かを、ラベルで示す。ラベルが無いと、すべてが必須と読まれる。ラベル(`nit:` `suggestion:` や `[must]` `[imo]`)は、そのリポジトリの既存のレビューコメントの慣習に合わせる。慣習が読み取れなければユーザーに確かめる。
- 問題かどうか確信が無いときは、指摘でなく質問として書く。
- 称賛は `SKILL.md` 5. に従う。

## 5. 出典

- [ビジネスメールの基本構成(日本ビジネスメール協会、マイナビニュース)](https://news.mynavi.jp/article/businessmail-6/)と[メールの書き方について(神田外語大学 学生課)](https://www.kandagaigo.ac.jp/kuis/cms/wp-content/uploads/2020/04/c7fa5f7a72fa9eb5d79262912a336d08.pdf)(どちらもライセンス表記なし): メールの宛名・挨拶・名乗り・要旨・詳細・結び・署名の構成と、挨拶・結びの定型句を 1. と 2. に取り込んだ。文面は転載していない。
- [Slack 公式ブログのチャットのエチケット](https://slack.com/intl/ja-jp/blog/collaboration/etiquette-tips-in-slack)と[ネットで叩かれている「Slackマナー」は本当にアホらしいのか?(ITmedia NEWS)](https://www.itmedia.co.jp/news/articles/2001/09/news073.html)(どちらもライセンス表記なし): チャットで挨拶だけのメッセージを送らないこと、宛名・所属・署名を書かないことを取り込んだ。文面は転載していない。
- [How to Report Bugs Effectively(Simon Tatham)](https://www.chiark.greenend.org.uk/~sgtatham/bugs.html)(OpenContent License)、[misskey-dev/misskey のバグ報告テンプレート](https://github.com/misskey-dev/misskey/blob/develop/.github/ISSUE_TEMPLATE/01_bug-report.yml)(AGPL-3.0)、[asciidwango/js-primer のバグ報告テンプレート](https://github.com/asciidwango/js-primer/blob/master/.github/ISSUE_TEMPLATE/bug_report.md)(CC BY 4.0): バグ報告の項目と、症状と推測を分けることを取り込んだ。テンプレートの文面は取り込んでいない。
- 次の記事から、1 つの issue に 1 つの話題、賛同はリアクションで示すこと、公開してよい情報だけを書くことを取り込んだ。ライセンス表記が無いため URL だけを示す: [OSS Issue投稿ガイド(Zenn)](https://zenn.dev/immedio/articles/15c1b953696841)、[OSS に Issue 報告する際の作法(DevelopersIO)](https://dev.classmethod.jp/articles/issue-report-to-oss/)
- [How to write code review comments(Google Engineering Practices)](https://google.github.io/eng-practices/review/reviewer/comments.html)(CC BY 3.0)と [Conventional Comments](https://conventionalcomments.org/)(CC BY 3.0): コードについて書くこと、理由を書くこと、重大度のラベル、確信が無いときは質問にすることを取り込んだ。Before の例文は Google の悪い例を日本語にした。
- [レビューコメントで頻繁に使うプレフィックス(DevelopersIO)](https://dev.classmethod.jp/articles/prefixes-for-frequently-used-review-comments/)(ライセンス表記なし): 日本のチームのラベル(`[must]` `[imo]`)の例として URL だけを示す。
- 出典の無い設計上の判断: issue・PR のコメントで宛名・挨拶・名乗り・結びを書かない規則は、日本語の OSS 3 リポジトリ([vim-jp/vimdoc-ja](https://github.com/vim-jp/vimdoc-ja)、[asciidwango/js-primer](https://github.com/asciidwango/js-primer)、[textlint-ja/textlint-rule-preset-ja-technical-writing](https://github.com/textlint-ja/textlint-rule-preset-ja-technical-writing))のコメント 106 件を数えた結果から一般化した。チャットの結びを 1 回までとする規則と、ラベルの慣習が読み取れないときに確かめる規則も、本スキルの判断である。
