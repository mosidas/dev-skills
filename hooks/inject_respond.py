#!/usr/bin/env python3
"""セッション開始時に respond スキルの本文を注入する SessionStart hook。

`skills/respond/SKILL.md` の frontmatter を取り除いた本文を、セッション開始時の
コンテキストへ注入する。respond スキルは「常時適用」の規範であり、エージェントが
明示的に読み込まなくてもセッションのすべての応答へ適用されるようにする。

入出力の契約:
  標準入力  使わない(SessionStart の JSON は読まない)
  exit 0    常に(注入の有無にかかわらずセッション開始を止めない)
  標準出力  SKILL.md が読めれば、前置き 1 行と空行に続けて本文を書く。
            SKILL.md が無い・読めない場合は何も出力しない。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# 上流 i-have-adhd の always-on.mjs と同じ: ファイル先頭の frontmatter ブロックにのみ一致する。
FRONTMATTER_RE = re.compile(r"^---[^\S\r\n]*\r?\n[\s\S]*?\r?\n---[^\S\r\n]*(?:\r?\n|$)")

PREFACE = "respond(常時適用): 以下の規範をこのセッションのすべての応答に適用する。"


def strip_frontmatter(text: str) -> str:
    """先頭 frontmatter を取り除き、前後の空行(CRLF 含む)を落とす(本文中の `---` は残す)。"""
    return FRONTMATTER_RE.sub("", text, count=1).strip("\r\n")


def skill_body(path: Path) -> str | None:
    """SKILL.md の本文を返す(frontmatter 抜き)。読めなければ None。"""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return strip_frontmatter(text)


def main() -> None:
    skill_path = Path(__file__).resolve().parent.parent / "skills" / "respond" / "SKILL.md"
    body = skill_body(skill_path)
    if body is None:
        return
    print(PREFACE)
    print()
    print(body)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001  hook 自身の不具合でセッション開始を止めない
        pass
    sys.exit(0)
