"""check_prd.py — PRD を雛形 `references/prd.md` の形に照らして機械で検査する。

使い方:
    python3 check_prd.py <prd.md>

問題が無ければ何も出力せずに exit 0 で終わる。問題があれば 1 件を 1 行で
`<file>:<line>: <問題> → <直し方>` の形で標準出力に書き、exit 1 で終わる。
ファイルを読めないときは標準エラーに書いて exit 2 で終わる。
節の見出しは雛形から読む。コードブロックとインラインコードの中は検査しない。
標準ライブラリのみで動く。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "references" / "prd.md"
FOUR_LINES = ("目的", "完了条件", "対象外", "品質")
REQ_HEADING = re.compile(r"^### (R\d+)\.")
# 内側が空白で始まるか終わるもの(`< 10 かつ >`)は比較演算子として扱う。
PLACEHOLDER = re.compile(r"<(?=\S)[^<>\n]+(?<=\S)>")
# 自動リンク(<https://...>)と HTML タグ(<br>・</summary>)は未記入として扱わない。
NOT_PLACEHOLDER = re.compile(r"<(?:https?://|mailto:)[^<>]*>|</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>]*)?/?>")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
INLINE_CODE = re.compile(r"(`+)[^`]*?\1")


def section_headings(lines: list[str]) -> list[tuple[int, str]]:
    return [(n, line[3:].strip()) for n, line in lines if line.startswith("## ")]


def prose_lines(text: str) -> list[tuple[int, str]]:
    """コードブロックを除いた (行番号, 行) を返す。"""
    result = []
    fence = None
    for n, line in enumerate(text.splitlines(), start=1):
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)
            continue
        if fence is not None:
            # 開きと同じ文字で、長さが開き以上のときだけ閉じる。
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        result.append((n, line))
    return result


def check(text: str, template: str) -> list[tuple[int, str]]:
    lines = prose_lines(text)
    problems: list[tuple[int, str]] = []

    # 雛形の 7 節が順にあるか
    expected = [title for _, title in section_headings(prose_lines(template))]
    found = section_headings(lines)
    titles = [title for _, title in found]
    sections: dict[str, int] = {}
    pos = 0
    for title in expected:
        if title in titles[pos:]:
            pos = titles.index(title, pos) + 1
            sections[title] = found[pos - 1][0]
        else:
            problems.append((1, f"節「## {title}」が無いか雛形と順序が違う → 雛形 references/prd.md の節の順に「## {title}」の見出しを書く"))

    def section_line(prefix: str) -> int | None:
        return next((n for t, n in sections.items() if t.startswith(prefix)), None)

    def body(prefix: str) -> list[tuple[int, str]]:
        start = section_line(prefix)
        if start is None:
            return []
        rest = [(n, line) for n, line in lines if n > start]
        end = next((n for n, line in rest if line.startswith("## ")), None)
        return [(n, line) for n, line in rest if end is None or n < end]

    # 要求ごとの 4 行と受け入れ条件
    req_ids: list[str] = []
    req_line: dict[str, int] = {}
    blocks: list[tuple[str, int, list[str]]] = []
    for n, line in body("5."):
        m = REQ_HEADING.match(line)
        if m:
            blocks.append((m.group(1), n, []))
        elif blocks:
            blocks[-1][2].append(line)
    if section_line("5.") is not None and not blocks:
        problems.append((section_line("5."), "要求一覧に要求が無い → 「### R1. <タイトル>」の見出しで要求を 1 件以上書く"))
    for rid, n, block in blocks:
        if rid in req_line:
            problems.append((n, f"### {rid}. の見出しが重複している → 重複した見出しを 1 つにする"))
            continue
        req_ids.append(rid)
        req_line[rid] = n
        for label in FOUR_LINES:
            if not any(re.match(rf"^{label}: *\S", b) for b in block):
                problems.append((n, f"{rid} に「{label}:」の行が無い → 雛形の形で「{label}: <内容>」の 1 行を書く"))
        ac = next((i for i, b in enumerate(block) if b.strip() == "受け入れ条件:"), None)
        if ac is None:
            problems.append((n, f"{rid} に「受け入れ条件:」が無い → 「受け入れ条件:」の行とその下に検証できる条件の箇条を 1 件以上書く"))
        elif not any(b.startswith("- ") for b in block[ac + 1:]):
            problems.append((n, f"{rid} の受け入れ条件に箇条が無い → 「受け入れ条件:」の下に検証できる条件を「- 」の箇条で 1 件以上書く"))

    # 依存と順序の表
    rows: list[tuple[int, str, list[str]]] = []
    for n, line in body("6."):
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.lstrip().startswith("|") else []
        if len(cells) < 2 or cells[0] == "要求" or (cells[0] and set(cells[0]) <= set(":- ")):
            continue
        if not cells[0]:
            problems.append((n, "表の ID が空 → 要求一覧の ID を書く"))
            continue
        if not cells[1]:
            problems.append((n, f"{cells[0]} の依存先が空 → 無ければ「なし」と書く"))
        deps = [] if cells[1] == "なし" else [d.strip() for d in re.split(r"[,、]", cells[1]) if d.strip()]
        rows.append((n, cells[0], deps))
    row_index: dict[str, int] = {}
    for i, (n, rid, _) in enumerate(rows):
        if rid in row_index:
            problems.append((n, f"表の {rid} の行が重複している → 重複した行を 1 つにする"))
        else:
            row_index[rid] = i
    for i, (n, rid, deps) in enumerate(rows):
        if rid not in req_ids:
            problems.append((n, f"表の {rid} が要求一覧に無い → 要求一覧にある ID に直すか行を削除する"))
        for dep in deps:
            if dep == rid:
                problems.append((n, f"{rid} が自身に依存している → 依存先から {rid} を除く"))
                continue
            if dep not in req_ids:
                problems.append((n, f"{rid} の依存先 {dep} が要求一覧に無い → 要求一覧にある ID に直す"))
            elif dep in row_index and row_index[dep] >= i:
                problems.append((n, f"{rid} の依存先 {dep} が {rid} より下の行にある → {dep} の行を {rid} の行より上へ移す"))
    table_line = section_line("6.")
    if table_line is not None:
        for rid in req_ids:
            if rid not in row_index:
                problems.append((table_line, f"{rid} が依存と順序の表に無い → 表に {rid} の行を加える"))

    # 雛形のコメントと未記入
    in_comment = False
    for n, line in lines:
        rest = line
        if in_comment:
            if "-->" not in rest:
                continue
            rest = rest.split("-->", 1)[1]
            in_comment = False
        rest = INLINE_CODE.sub("", rest)
        if "<!--" in rest:
            problems.append((n, "雛形のコメントが残っている → すべての節を埋めたあとでコメントを削除する"))
            before, _, after = rest.partition("<!--")
            in_comment = "-->" not in after
            rest = before + (after.split("-->", 1)[1] if not in_comment else "")
        for m in PLACEHOLDER.finditer(rest):
            if not NOT_PLACEHOLDER.fullmatch(m.group(0)):
                problems.append((n, f"未記入の {m.group(0)} が残っている → 対話で得た答えで埋める。答えが無ければ 7. の未決事項に書く"))

    return sorted(problems, key=lambda p: p[0])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PRD を雛形の形に照らして検査する")
    parser.add_argument("prd", help="検査する PRD の Markdown ファイル")
    args = parser.parse_args(argv)
    try:
        text = Path(args.prd).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"PRD を読み込めない: {e}", file=sys.stderr)
        return 2
    problems = check(text, TEMPLATE.read_text(encoding="utf-8"))
    for n, message in problems:
        print(f"{args.prd}:{n}: {message}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
