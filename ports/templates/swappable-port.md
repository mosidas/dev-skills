---
name: <差し替え対象の固定 port 名(部品が参照する名前。例: hearing-questions)>
description: <1 行の要約。どの部品のどのデフォルトを差し替えるか>
inject:
  - <差し替え先スキル(例: dev-spec)>
condition: 常時
---

# <タイトル>(<name>)

<!-- 差し替え port の雛形。docs/dev/ports/swappable/<name>.md にコピーして使う。この HTML コメントは削除する。
     差し替え port = 部品が name で参照する固定の拡張点。部品のデフォルト手順・データ(例: dev-spec の
     ヒアリング質問セット)を、この port があれば置き換える。name は部品が参照する固定名にする
     (自由に変えない。どの部品が何の name を参照するかは各部品の SKILL.md「契約」節を見る)。
     正本は利用側プロジェクトに置く(ports.md §1・§4)。 -->

<この port が差し替える部品デフォルトと、差し替え後の内容を書く。>

## <差し替え内容>

- <...>
