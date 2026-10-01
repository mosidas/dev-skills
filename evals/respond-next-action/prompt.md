---
description: ファイル無しで答えられる短い作業依頼に、前置きと締めの定型句を付けず、実行できる操作から答えるか
tags: [respond, cheap]
runs: 3
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
---

直前のコミットのメッセージだけ直したい。新しいメッセージは「fix: README の誤字を直す」にしたい。まだ push していない。
