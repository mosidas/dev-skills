---
type: regex
match: contains
arm: both
pattern: '^(?:\s*```[^\n]*\n)?\s*(?:\$\s*)?`?git commit --amend'
---
最後の返答が `git commit --amend` で始まるかを測る。先頭のコードフェンスの開始行(```)1 行は許す。根拠は `skills/respond/SKILL.md` の「3.1. 次の行動から書く」である。
当初は llm で判定したが、試行では 1 行目がコードフェンス、2 行目が `git commit --amend -m "…"` の正答を FAIL にしたため、機械判定に替えた。
行内コード(`` `git commit --amend …` ``)の 1 行と、フェンス内でプロンプト記号 `$` を付けた形も同じ正答であるため、どちらも拾うように pattern を広げた。
