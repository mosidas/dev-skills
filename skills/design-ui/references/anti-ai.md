# AI っぽさの一覧

本ファイルは既定の一覧である。複数案件で機械的に繰り返される見た目・文言・モーションを挙げる。ユーザーがここに挙げたものを名指しで指定したら、その指定に従う。指定が無く軸が自由なときだけ、既定を避けて選び直す。

## 1. 見た目

| 既定 | 代わりにすること |
| :-- | :-- |
| 紫から青へのグラデーションの hero | 題材固有の画像・実データ・実際の操作画面を hero に配置する |
| gradient text | 太さかサイズで強調する |
| glassmorphism・ネオンの発光 | 効果を装飾として足さず、必要な箇所に限って使う理由を持たせる |
| Inter・Space Grotesk・Instrument Serif の組み合わせ、暖色クリーム地(#F4F1EA 付近)にテラコッタ | 題材の産業・素材・語彙から書体と配色を選択する |
| 近黒の背景にアクセントカラー 1 色 | 配色は `../SKILL.md` 4. のスケールから、題材に合わせて選ぶ |
| 中央寄せの hero に CTA 1 つ、誰の製品にも当てはまる見出し | 見出しは題材固有の一文にする(`text.md`) |
| 同じ大きさのカード 3 枚の格子、カードの入れ子 | すべてをカードにしない。区切りが不要な箇所は余白と整列だけで並べる |
| 全要素に同じ角丸・同じ薄いグレーの影 | 角丸と影は階層に応じて変える。1 種類に統一する場合も題材の判断として選ぶ |
| カードの色付き左ボーダー(1px 超) | 色は背景か見出しで示す |
| 全大文字の eyebrow ラベル | 見出し自体の強さで示す。ラベルを見出しの上に足さない |
| 01 / 02 / 03 の番号 | 内容が実際に手順・時系列であるときだけ番号を使う(`../SKILL.md` 6.) |
| 大きな数字と小さなラベルの統計バナー | 数値は文脈の中に置き、単独のバナーにしない |
| 絵文字をアイコン代わりに使う | 一貫したストローク・太さの SVG アイコンか、実在のアイコンライブラリを使う |
| monospace を「技術っぽさ」の記号として使う | monospace はコード・データ・計測値だけに使う |
| 中黒つなぎのメタ情報(「A・B・C」) | 語を並べる理由がある場合だけ中黒を使う。無ければ文にする |
| リンク末尾の「→」 | リンクの文言自体で行き先を示す |
| 幾何学マスク(円・多角形)で写真の輪郭を近似する | 実際の画像からアルファマットを作るか、切り抜き済みの素材を使う |
| ハードオフセットの影(`box-shadow: 4px 4px 0`)を常用する | ネオブルータリズムを明確に選んだとき以外は、オフセットと薄いぼかしを組み合わせた影にする |
| スケッチ風の SVG イラスト、`feTurbulence` のノイズ | 実在のイラストを使うか、幾何学的な図形・線画にとどめる |

## 2. モーション

- セクションごとの fade-and-slide-up を、すべてのセクションに同じ調子で繰り返さない。動かす箇所は 1 回の演出に絞る。
- すべてのカードに同じ hover 効果を機械的に付けない。
- bounce のイージングを既定にしない。ユーザーの操作に応じるモーションは、指数関数的な減速などで自然に止める。
- モーションは `prefers-reduced-motion` を尊重する(`checklist.md`)。
- 動かす対象は、状態の変化を示す要素に絞る。画像そのものを hover で動かさない。動かすなら、画像を包む枠のほうに反応させる。

## 3. 文言

- 誰の製品にも当てはまる見出し(「あなたの仕事を、もっと簡単に。」)を書かない。題材固有の一文にする。
- 「→」を文言の締めに使わない。
- 中黒つなぎ(「速い・軽い・安全」)を、語を並べる必然性が無いのに使わない。
- 感嘆符を多用しない。エラー・空状態は謝罪や煽りでなく、事実と次の行動を書く(`text.md`)。
- 宣伝語(「業界最高水準」「圧倒的な」)を、根拠を示さずに書かない。
- 同じ意味の見出しラベルを、全セクションの冒頭に機械的に繰り返さない。見出し自体に語らせる。

## 4. 判断の仕方

一覧は禁止の目録ではない。既定を疑う対象の目録である。ブリーフがその見た目を名指しで求めていれば、そのまま採用する。軸が空いているときだけ描き直す。仕上げの段階では、際立たせたい要素を 1 つだけ残し、周囲のあしらいを一段ずつ弱め、それでも目立ってしまう装飾を見つけたら削るという、最後の引き算を繰り返し行う。

## 5. 出典

- [anthropics/skills frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design)(Apache-2.0)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)(Apache-2.0)、`skill/reference/craft-floor.md`
- [developersdigest: AI design slop and how to spot it](https://www.developersdigest.tech/blog/ai-design-slop-and-how-to-spot-it)
- [925studios: AI slop design tells](https://www.925studios.co/blog/ai-slop-design-tells)
- [mania.design: spot the slop](https://www.mania.design/blog/spot-the-slop-a-ui-designers-guide-to-fixing-ai-defaults/)
- [dev.to: the purple gradient problem](https://dev.to/james_anderson_h/the-purple-gradient-problem-why-ai-ui-all-looks-alike-and-how-to-fix-it-3j65)
