"""Stop の hook が応答から地の文を取り出す共通の処理。guard_next_line.py と guard_reader_context.py が使う。

コードフェンス・インラインのコード・URL・パス・ファイル名は読み手に向けた文でないため、検査の前に除く。
行の中で除く部分は同じ長さの空白にする。当たった位置を元の行のまま保ち、元の行から当たった部分を切り出せるためである。
"""

from __future__ import annotations

import json
import re
from typing import BinaryIO

FENCE = re.compile(r"[ \t]*(`{3,}|~{3,})")
BACKTICKS = re.compile(r"`+")
# 始まりを英数字の並びの先頭に限る(並びの途中の各位置から末尾まで読み直さない)
URL = re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*://\S+")
# 空白か開き括弧の後に始まり、斜線を含む語(docs/a.md・./x/y・~/z)。始まりの前に置ける括弧を語に含めない
# (「【【…」の各位置から末尾まで読み直さない)
PATH = re.compile(r"(?<![^\s(（「『【])(?:~|\.{1,2})?/?[^\s/()（）「」『』【】、。]+(?:/[^\s/()（）「」『』【】、。]+)+/?")
# 空白か開き括弧の後に始まり、英字で始まる拡張子で終わる斜線の無いファイル名(案A.md・x.json)。
# 拡張子を英字で始まるものに限り、番号(4.1)を消さない。語幹にひらがなを含めず、前に続く文(案Aの内容をnotes.md)を消さない
FILENAME = re.compile(r"(?<![^\s(（「『【])[^\s/()（）「」『』【】、。ぁ-ん]*?\.[A-Za-z][A-Za-z0-9]*(?![A-Za-z0-9])")


def read_payload(stdin: BinaryIO) -> dict | None:
    """UTF-8 のバイト列の JSON を dict で返す。読めないか dict でなければ None。"""
    try:
        payload = json.loads(stdin.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def prose_lines(message: str) -> list[str | None]:
    """行ごとに、コードフェンスの外の行は元のまま、フェンスの行と中の行は None にした一覧。

    閉じないフェンスは文書の終わりまで続く。開きと同じ文字で同じ本数以上の、後ろに何も無い行で閉じる。
    """
    lines: list[str | None] = []
    fence = None
    for line in message.splitlines():
        m = FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
                lines.append(None)
            else:
                lines.append(line)
        else:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line[m.end():].strip():
                fence = None
            lines.append(None)
    return lines


def blank(text: str, pattern: re.Pattern[str]) -> str:
    """当たった部分を同じ長さの空白にする(当たった位置を元の行のまま保つ)。"""
    return pattern.sub(lambda m: " " * len(m.group(0)), text)


def blank_code_spans(line: str) -> str:
    """CommonMark のコードスパン(同じ本数のバッククォートの対)を同じ長さの空白にする。対の無いバッククォートは残す。

    開きのバッククォートの並びごとに、同じ本数の次の並びを後ろから 1 回の走査で求めておき、行の長さに比例する時間で済ませる。
    """
    runs = list(BACKTICKS.finditer(line))
    closer: list[int | None] = [None] * len(runs)
    later: dict[int, int] = {}
    for i in range(len(runs) - 1, -1, -1):
        width = len(runs[i].group(0))
        closer[i] = later.get(width)
        later[width] = i
    parts: list[str] = []
    pos = i = 0
    while i < len(runs):
        j = closer[i]
        if j is None:
            i += 1
            continue
        start, end = runs[i].start(), runs[j].end()
        parts += [line[pos:start], " " * (end - start)]
        pos, i = end, j + 1
    parts.append(line[pos:])
    return "".join(parts)
