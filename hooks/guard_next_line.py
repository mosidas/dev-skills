#!/usr/bin/env python3
"""応答の最後の「次:」の行が記号で名付けた案(「案 A」「B 案」「第 2 案」「(a) か (b)」)を選ばせていたら止める Stop hook。

respond 3.2 は「次:」の行を、その 1 行だけを読んで意味が通る文にすると定める。記号は前の本文を読んだ読み手にしか
意味が通らないため、記号の案を見つけたら、選択肢ごとに中身を書いた「次:」の行を返し直させる。

入出力の契約:
  標準入力  UTF-8 の Stop の JSON(`stop_hook_active`・`last_assistant_message` を読む)。
            環境の符号化(PYTHONIOENCODING・ロケール)に依らず UTF-8 のバイト列として読む
  exit 0    検査を終えたとき(止めるときも通すときも)
  exit 1    hook 自身の想定外の例外。標準エラーに例外の型名だけを 1 行書く(応答の本文は書かない)
  標準出力  止めるときだけ `{"decision": "block", "reason": <理由>}` の JSON を ASCII で 1 つ書く。
            通すときは何も書かない
  標準エラー exit 1 のときだけ書く

`stop_hook_active` はターン全体の値であり、このターンで別の Stop hook が止めた後の応答でも true になる。true なら
検査せずに通す(止めた応答の書き直しを再び止めて完了を封じない)。そのため、別の hook が先に止めたターンでは、
書き直した応答の「次:」の行は検査されない。

UTF-8 の JSON の dict として読めない入力と、`last_assistant_message` が文字列でない入力は何も書かずに通す
(fail-open)。この hook は応答の形を直させるもので漏えいを防ぐものではなく、自分の解析の失敗で止めると
すべての応答の完了が止まるためである。想定外の例外も exit 1(Claude Code は止めずに続ける)で通す。
"""

from __future__ import annotations

import json
import re
import sys
from typing import BinaryIO

REASON = (
    "respond 3.2 の検査: 最後の「次:」の行が、記号で名付けた案(「{label}」)を選ばせている。"
    "読み手は記号が指す中身を覚えていない。"
    "前の応答の本文は繰り返さず、選択肢ごとに中身(何をするか)を書いた「次:」の行を 1 行だけ返す。"
)

# 理由に書く当たった部分の長さの上限。「案」と記号の間の空白は長さに上限が無いため
LABEL_MAX = 40

FENCE = re.compile(r"[ \t]*(`{3,}|~{3,})")
NEXT = re.compile(r"\s*次\s*[:：]")
BACKTICKS = re.compile(r"`+")
# 始まりを英数字の並びの先頭に限る(並びの途中の各位置から末尾まで読み直さない)
URL = re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*://\S+")
# 空白か開き括弧の後に始まり、斜線を含む語(docs/a.md・./x/y・~/z)。始まりの前に置ける括弧を語に含めない
# (「【【…」の各位置から末尾まで読み直さない)
PATH = re.compile(r"(?<![^\s(（「『【])(?:~|\.{1,2})?/?[^\s/()（）「」『』【】、。]+(?:/[^\s/()（）「」『』【】、。]+)+/?")
# 空白か開き括弧の後に始まり、英字で始まる拡張子で終わる斜線の無いファイル名(案A.md・x.json)。
# 拡張子を英字で始まるものに限り、番号(4.1)を消さない。語幹にひらがなを含めず、前に続く文(案Aの内容をnotes.md)を消さない
FILENAME = re.compile(r"(?<![^\s(（「『【])[^\s/()（）「」『』【】、。ぁ-ん]*?\.[A-Za-z][A-Za-z0-9]*(?![A-Za-z0-9])")
# 記号の英字(A・b・A1・B12)。英字 2 字以上の語(PR・API)は記号にしない
LETTER = r"[A-Za-zＡ-Ｚａ-ｚ][0-9０-９]*"
NUMBER = r"[0-9０-９]+(?:\.[0-9]+)*"
# 斜線でつないだ記号の案(A/B・案A/案B・1.1/1.2)。斜線を含む語のうちこれ以外をパスとして消す
SLASHED_SYMBOLS = re.compile(
    r"(?:案\s*)?(?:" + LETTER + "|" + NUMBER + r")(?:/案?(?:" + LETTER + "|" + NUMBER + r"))+"
    r"(?![A-Za-z0-9_/-]|\.[A-Za-z0-9])"
)

# 数の後に助数詞が続くなら記号でなく数である(「案 3 件」「改善案 12 件」)。数字の途中で切って記号にしない
NOT_COUNT = (
    r"(?![0-9０-９]|\.[0-9])"
    r"(?!\s*(?:件|つ|個|行|点|案|本|回|か所|箇所|段|人|日|分|秒|ステップ|手順|枚|節|章|項|週|時間|号|版|年|%|％))"
)
SYMBOL = (
    r"(?:" + LETTER + r"(?![A-Za-z0-9])"
    r"|" + NUMBER + NOT_COUNT +
    r"|[(（][A-Za-z0-9ａ-ｚＡ-Ｚ０-９][)）]"
    r"|[①-⑳])"
)
PAREN_LABEL = r"[(（][A-Za-z0-9ａ-ｚＡ-Ｚ０-９][)）]"
LABELED_OPTION = re.compile(
    r"案\s*" + SYMBOL                                        # 案 A・案 A1・案 1・案 4.1・案 (a)・案②
    + r"|(?<![A-Za-z0-9])" + LETTER + r"\s*案(?![件内])"      # A 案・A1 案・B 案の変形(B 案件・A 案内は除く)
    + r"|第\s*[0-9０-９一二三四五六七八九十]+\s*案"            # 第 2 案
    # 採用する案の番号・3 案から採用する番号。番号の直前をひらがなに限り、PR 番号・節番号の複合語は除く
    + r"|案(?:の|から|のうち|の中から)[^。]{0,20}?(?<=[ぁ-ん])(?:番号|記号)"
    + r"|" + PAREN_LABEL + r"\s*(?:か|or)\s*" + PAREN_LABEL  # (a) か (b)
)


def read_payload(stdin: BinaryIO) -> dict | None:
    """UTF-8 のバイト列の JSON を dict で返す。読めないか dict でなければ None。"""
    try:
        payload = json.loads(stdin.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def last_line(message: str) -> str | None:
    """コードフェンスの外にある最後の空でない行。閉じないフェンスは文書の終わりまで続く。"""
    last = None
    fence = None
    for line in message.splitlines():
        m = FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)
            elif line.strip():
                last = line
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line[m.end():].strip():
            fence = None
    return last


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


def labeled_option(message: str) -> str | None:
    """最後の「次:」の行にある記号で名付けた案を返す。無ければ None。"""
    line = last_line(message)
    if line is None or not NEXT.match(line):
        return None
    prose = PATH.sub(
        lambda m: m.group(0) if SLASHED_SYMBOLS.match(m.group(0)) else " " * len(m.group(0)),
        blank(blank_code_spans(line), URL),
    )
    prose = blank(prose, FILENAME)
    m = LABELED_OPTION.search(prose)
    return line[m.start():m.end()] if m else None


def main() -> int:
    payload = read_payload(sys.stdin.buffer)
    if payload is None or payload.get("stop_hook_active"):
        return 0
    message = payload.get("last_assistant_message")
    if not isinstance(message, str):
        return 0
    label = labeled_option(message)
    if label is not None:
        shown = label if len(label) <= LABEL_MAX else label[:LABEL_MAX] + "…"
        json.dump({"decision": "block", "reason": REASON.format(label=shown)}, sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001  hook 自身の不具合で応答の完了を止めない(fail-open)。本文は書かない
        print(f"guard_next_line: 内部エラー {type(e).__name__}", file=sys.stderr)
        code = 1
    sys.exit(code)
