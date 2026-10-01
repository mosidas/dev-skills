---
type: regex
target: { source: file, path: docs/report.md }
match: not_contains
pattern: '筆者|私[はがのもた]'
---
レポートが話者標識に「筆者」「私」の人称を使っていないかを測る。根拠は `skills/write-doc/references/sentence.md` の「4. 事実・意見・確信度」(34 行目)である。
依頼文が質問せずに書き上げるよう指示しているため、`docs/report.md` は必ず書かれる前提で測る。
target を trace にしない。Skill の読み込み結果に sentence.md の本文が入り、規則の文面そのものに一致するためである。
