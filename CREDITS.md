# 出典

この文書は帰属表示と上流の差分の起点である。版とコミットの列は取り込んだ時点の値である。ファイルのどの節に何を取り込んだかは、`git log -S` で該当する語を含むコミットを探し、そのコミットのメッセージと差分で追う。

ライセンスの列の「明示なし」は資料にライセンスの表記が無いことを、「未確認」はライセンスを確かめていないことを示す。Google『Site Reliability Engineering』・OWASP の 2 件・OpenTelemetry Semantic Conventions・W3C Trace Context・RFC の 2 件・Amazon Builders' Library・Stripe API Reference・Google Search Central は、要点を自分の言葉でまとめ、文面は転載していない。ほかの資料の文面の使い方は、記録のあるものだけを反映先の列に括弧で書いた。

| 出典 | ライセンス | 著作権者 | 版とコミット | 反映先 |
| :-- | :-- | :-- | :-- | :-- |
| [cursor/plugins](https://github.com/cursor/plugins) の pstack | MIT | Copyright (c) 2026 Lauren Tan | コミット 997ffc7(2026-10-12 時点。specify)・0.15.36(コミット 1ba91fc、2026-10-28) | specify・interview・develop・build・ponytail・recover・retro・respond・agents・write-doc・draw-diagram・design-ui・explain・verify・README |
| [mattpocock/skills](https://github.com/mattpocock/skills) | MIT | Copyright (c) 2026 Matt Pocock | コミット 49dd158(2026-10-12 時点) | specify・interview |
| [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) | MIT | Copyright (c) 2026 DietrichGebert | v5.1.0 | ponytail |
| [coji/natural-japanese](https://github.com/coji/natural-japanese) | MIT | — | v1.5.0(9a78a42)・v1.6.0(03bc944)・v1.6.2(a88b8e9) | write-doc・write-slide・write-message |
| [nanaism/yomiyasu](https://github.com/nanaism/yomiyasu) | MIT | — | v1.1.1(373356e)・v2.0.1(84e1f5b)・v2.3.0(15244a1) | write-doc・write-message |
| [mizchi/explainer](https://github.com/mizchi/explainer) | MIT | — | 版の記載なし | write-doc |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | Apache-2.0 | — | 版の記載なし | write-doc(explainer を経由) |
| [carnot-tech/consulting-pptx-skill](https://github.com/carnot-tech/consulting-pptx-skill) | MIT | — | コミット bc9a587・b8f7dc4 | write-doc・write-slide・draw-diagram |
| [iKora128/stop-ai-slop-jp](https://github.com/iKora128/stop-ai-slop-jp) | MIT | — | コミット e09d327 | write-message |
| [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd) | MIT | Copyright (c) 2026 Ayoub Ghriss | 版の記載なし | respond |
| [cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design) | MIT | Copyright (c) 2025 Cathryn Lavery | v2.6.115(f2f4d49) | draw-diagram |
| [anthropics/skills frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | Apache-2.0 | — | 版の記載なし | design-ui |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Apache-2.0 | — | 4.7.1(コミット 9368675) | design-ui |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | MIT | — | 版の記載なし | design-ui |
| [vercel-labs/web-interface-guidelines](https://github.com/vercel-labs/web-interface-guidelines) | MIT | — | 版の記載なし | design-ui |
| `vercel-labs/agent-skills` の `skills/web-design-guidelines` | 未確認 | — | 版の記載なし | design-ui(web-interface-guidelines の経由先) |
| [s0xDk/refactoring-ui-skill](https://github.com/s0xDk/refactoring-ui-skill) | MIT | — | 版の記載なし | design-ui |
| [misskey-dev/misskey のバグ報告テンプレート](https://github.com/misskey-dev/misskey/blob/develop/.github/ISSUE_TEMPLATE/01_bug-report.yml) | AGPL-3.0 | — | 版の記載なし | write-message(バグ報告テンプレートの文面は取り込んでいない) |
| [asciidwango/js-primer](https://github.com/asciidwango/js-primer) | CC BY 4.0 | — | 版の記載なし | write-message([バグ報告テンプレート](https://github.com/asciidwango/js-primer/blob/master/.github/ISSUE_TEMPLATE/bug_report.md)の文面は取り込んでいない) |
| [vim-jp/vimdoc-ja](https://github.com/vim-jp/vimdoc-ja) | 未確認 | — | 版の記載なし | write-message(コメントの集計) |
| [textlint-ja/textlint-rule-preset-ja-technical-writing](https://github.com/textlint-ja/textlint-rule-preset-ja-technical-writing) | 未確認 | — | 版の記載なし | write-message(コメントの集計) |
| [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/) | Apache-2.0 | — | 1.44.0 | observe |
| Google『Site Reliability Engineering』 | CC BY-NC-ND 4.0 | — | 2017 年版の[第 6 章](https://sre.google/sre-book/monitoring-distributed-systems/)・[第 15 章](https://sre.google/sre-book/postmortem-culture/)・[第 22 章](https://sre.google/sre-book/addressing-cascading-failures/) | observe・recover・retro |
| [W3C Trace Context Level 1](https://www.w3.org/TR/trace-context/) | W3C Software and Document License | — | W3C 勧告(2021-11-23) | observe |
| [Kubernetes の liveness/readiness probe](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/) | 未確認 | — | 版の記載なし | observe |
| [Amazon Builders' Library "Timeouts, retries, and backoff with jitter"](https://builder.aws.com/content/3EumjoZascWd1oZiEgL8ORlv3qE/timeouts-retries-and-backoff-with-jitter) | 明示なし | © Amazon Web Services, Inc. | 版の記載なし | recover |
| [RFC 9110 HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) | IETF Trust Legal Provisions | — | 2022-06(STD 97) | recover |
| [RFC 6585 Additional HTTP Status Codes](https://www.rfc-editor.org/rfc/rfc6585.html) | IETF Trust Legal Provisions | — | 2012-04 | recover |
| [Stripe API Reference "Idempotent requests"](https://docs.stripe.com/api/idempotent_requests) | 明示なし | — | 版の記載なし | recover |
| [Google Search Central "How HTTP status codes, and network and DNS errors affect Google Search"](https://developers.google.com/search/docs/crawling-indexing/http-network-errors) | CC BY 4.0 | — | 2026-02-04 更新 | recover |
| Michael T. Nygard『Release It! Second Edition』 | 未確認 | — | 2018 年 | recover(書名だけを挙げる) |
| [OWASP Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/) | CC BY-SA 4.0 | — | 5.0.0(2025-05-30 公開) | secure |
| [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/) | CC BY-SA 4.0 | — | 版番号なし | secure |
| 木下是雄『理科系の作文技術』 | 未確認 | — | 版の記載なし | write-doc |
| 結城浩『数学文章作法 基礎編・推敲編』 | 未確認 | — | 版の記載なし | write-doc |
| Wathan & Schoger『Refactoring UI』 | 未確認 | — | 版の記載なし | design-ui(refactoring-ui-skill の原典) |
| [敬語の指針](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/keigo_tosin.pdf) | 未確認 | — | 平成 19 年 2 月 2 日 | write-message |
| [公用文作成の考え方](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/pdf/93651301_01.pdf) | 未確認 | — | 令和 4 年 1 月 7 日 | write-message |
| [分かり合うための言語コミュニケーション(報告)](https://www.bunka.go.jp/seisaku/bunkashingikai/kokugo/hokoku/wakariau/pdf/r1403493_01.pdf) | 未確認 | — | 平成 30 年 3 月 2 日 | write-message |
| [平成 25 年度「国語に関する世論調査」報告書](https://www.bunka.go.jp/tokei_hakusho_shuppan/tokeichosa/kokugo_yoronchosa/pdf/92701201_06.pdf) | 未確認 | — | 平成 25 年度 | write-message |
| [洞澤伸・岡江里子「「バイト敬語」を使う若者たち」](https://gifu-u.repo.nii.ac.jp/record/68522/files/reg_030019001.pdf) | 未確認 | — | 2006 年 | write-message |
| [ビジネスメールの基本構成(マイナビニュース)](https://news.mynavi.jp/article/businessmail-6/) | 明示なし | — | 版の記載なし | write-message(文面は転載していない) |
| [メールの書き方について(神田外語大学 学生課)](https://www.kandagaigo.ac.jp/kuis/cms/wp-content/uploads/2020/04/c7fa5f7a72fa9eb5d79262912a336d08.pdf) | 明示なし | — | 版の記載なし | write-message(文面は転載していない) |
| [Slack 公式ブログのチャットのエチケット](https://slack.com/intl/ja-jp/blog/collaboration/etiquette-tips-in-slack) | 明示なし | — | 版の記載なし | write-message(文面は転載していない) |
| [ITmedia NEWS の Slack マナーの記事](https://www.itmedia.co.jp/news/articles/2001/09/news073.html) | 明示なし | — | 版の記載なし | write-message(文面は転載していない) |
| [How to Report Bugs Effectively(Simon Tatham)](https://www.chiark.greenend.org.uk/~sgtatham/bugs.html) | OpenContent License | — | 版の記載なし | write-message(バグ報告テンプレートの文面は取り込んでいない) |
| [OSS Issue投稿ガイド(Zenn)](https://zenn.dev/immedio/articles/15c1b953696841) | 明示なし | — | 版の記載なし | write-message(文面は取り込まず URL だけを示す) |
| [OSS に Issue 報告する際の作法(DevelopersIO)](https://dev.classmethod.jp/articles/issue-report-to-oss/) | 明示なし | — | 版の記載なし | write-message(文面は取り込まず URL だけを示す) |
| [How to write code review comments(Google Engineering Practices)](https://google.github.io/eng-practices/review/reviewer/comments.html) | CC BY 3.0 | — | 版の記載なし | write-message(悪い例を日本語に訳して Before の例文にした) |
| [Conventional Comments](https://conventionalcomments.org/) | CC BY 3.0 | — | 版の記載なし | write-message |
| [レビューコメントで頻繁に使うプレフィックス(DevelopersIO)](https://dev.classmethod.jp/articles/prefixes-for-frequently-used-review-comments/) | 明示なし | — | 版の記載なし | write-message(文面は取り込まず URL だけを示す) |
| [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) | CC BY-SA 4.0 | — | 版の記載なし | write-message(文面を訳さずに規則として取り込んだ) |
| [大西夢「AI 生成文からみた「自然な日本語」についての研究」(広島大学文学部、卒業論文)](https://home.hiroshima-u.ac.jp/jshira/papers/AI生成文からみた「自然な日本語」についての研究（大西夢）.pdf) | 明示なし | — | 令和 7 年度 | write-message |
| [マナーべるの記事](https://mannerbell.com/ai-email-revise-manner/) | 明示なし | — | 2026-04-17 の記事 | write-message(文面は取り込まず URL だけを示す) |
| [KDDI のコラム](https://biz.kddi.com/content/column/smb/making-of-sentence/) | 明示なし | — | 版の記載なし | write-message(文面は取り込まず URL だけを示す) |
| [プレジデントオンラインの記事](https://news.yahoo.co.jp/articles/032bcc2f342a768b8ff275e43fa98dbc14febb1a) | 明示なし | — | 版の記載なし | write-message(文面は取り込まず URL だけを示す) |
| [NN/g](https://www.nngroup.com/articles/) の記事(Tooltip Guidelines・Icon Usability・Progressive Disclosure・Error-Message Guidelines) | 未確認 | — | 版の記載なし | design-ui |
| [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/) | 未確認 | — | 版の記載なし | design-ui |
| [Material Design 3](https://m3.material.io/) と developer.android.com の文書 | 未確認 | — | 版の記載なし | design-ui |
| [Flutter: Platform adaptations](https://docs.flutter.dev/platform-integration/platform-adaptations) | 未確認 | — | 版の記載なし | design-ui |
| [React Native: Platform-specific code](https://reactnative.dev/docs/platform-specific-code) | 未確認 | — | 版の記載なし | design-ui |
| [developersdigest](https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it)・[925studios](https://www.925studios.co/blog/ai-slop-design-tells)・[mania.design](https://www.mania.design/blog/spot-the-slop-a-ui-designers-guide-to-fixing-ai-defaults/)・[dev.to](https://dev.to/james_anderson_h/the-purple-gradient-problem-why-ai-ui-all-looks-alike-and-how-to-fix-it-3j65) の記事 | 未確認 | — | 版の記載なし | design-ui |
