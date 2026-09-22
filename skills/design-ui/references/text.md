# UI テキストの規範

## 1. 最小化の原則

画面に残す文字は、操作に必要な語だけにする。理由・背景・補足の説明はツールチップかヘルプのポップオーバーへ移す。ただし、完了に必須の情報(入力要件・手順)はツールチップに入れず、フィールドの脇に常時表示する。読み手はツールチップを開かなくても、そのフィールドを埋め終えられなければならない。

## 2. ツールチップとヘルプ

- ツールチップは動詞で始める。コントロールの名前を繰り返さない。
- 1〜2 文に収める。長い説明が必要になるなら、ツールチップでなく UI 自体を単純にする。
- hover と focus の両方で表示する。hover の無いタッチ端末(モバイルアプリを含む)では、情報アイコンからのポップオーバー(iOS の tip、Material の長押しによる rich tooltip)か、フィールド下のインラインの補助文で代替する。
- plain tooltip(ラベルの無い要素の短い説明)と rich tooltip(見出し・複数行・リンクを持てる)を区別し、内容に応じて使い分ける。
- ヘルパーテキストは、コントロールの言い換えでなく、読み手が抱く暗黙の問いに答える。

## 3. アイコンと開示

- アイコンだけのボタンには、常時表示のラベルを付記するか、`aria-label` で名前を与える。hover で出すラベルだけでは足りない。
- progressive disclosure(段階的な開示)は 2 段までにする。最初は重要な選択肢だけを見せる。
- ラベルは最後の手段である。多くのデータは書式(`$19.99`、メールアドレス)や文脈で自ずと意味を持つ。ラベルが必要になるときは、値に埋め込む(「12 left in stock」であって「In stock: 12」ではない)か、明確に副次的な扱いにする。

## 4. ボタンとアクション

- ボタンは結果を言う。「送信」でなく「変更を保存」のように、押した結果を明示する。
- 同じ操作には、画面をまたいでも同じ語を使う。「公開」で始めた操作の完了通知が「アップロード完了」に変わると、読み手は同じ操作だと認識できない。
- 破壊的な操作は、対象と結果を名指しする。復旧できるなら確認ダイアログでなく取り消し(undo)を用意する。確認が必要になるときは、ボタンに「はい」でなくその操作名を書く。

## 5. エラーと空状態

エラーは、何が失敗したか、分かる範囲でなぜ失敗したか、どう直せば回復するかの 3 点を書く。原因を断定できないときは、断定せず次に取れる行動を書く。内部のエラーコードを主文にしない。

空状態は、初回利用・検索結果なし・絞り込み中・権限なし・失敗を区別し、それぞれに応じた次の行動を示す招待にする。「データがありません」だけで終えない。

読み込み中の表示は、待つ理由が分かる操作名を書く。進捗を測れるときは実際の割合を出し、測れない進捗を演出で装わない。成功の通知は簡潔にとどめ、次の行動が変わるときだけその内容を書く。

## 6. 語彙

同じ操作には同じ語を当てる。文書内で言い換えると、読み手は別の操作だと解釈する。用語の一貫性は、製品内を移動する読み手にとっての道しるべである。「編集」と「変更」、「削除」と「消去」のように、同じ対象を指す語を機能ごとに使い分けない。

## 7. 見出しとラベル

見出しは、名詞句の見出しか、文で言い切る見出しかを画面の種類でそろえる。設定画面のセクション見出しに「〜を変更する」と動詞形を混ぜ、隣を体言止めのままにすると、読み手はどちらの型で探すべきか迷う。

## 8. 日本語の文言

日本語で UI テキストを書くときの語の選び方・文体は、`../../write-doc/references/sentence.md` に従う。本ファイルが定めるのは、UI 内での文字の配置と分量であり、文体そのものではない。

## 9. 出典

- [NN/g: Tooltip Guidelines](https://www.nngroup.com/articles/tooltip-guidelines/)
- [NN/g: Icon Usability](https://www.nngroup.com/articles/icon-usability/)
- [NN/g: Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/)
- [Apple Human Interface Guidelines: Offering help](https://developer.apple.com/design/human-interface-guidelines/offering-help)
- [Material Design 3: Tooltips](https://m3.material.io/components/tooltips)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)(Apache-2.0)、`skill/reference/clarify.md`
- [s0xDk/refactoring-ui-skill](https://github.com/s0xDk/refactoring-ui-skill)(MIT。原典 Wathan & Schoger, *Refactoring UI*)
- [anthropics/skills frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design)(Apache-2.0)
