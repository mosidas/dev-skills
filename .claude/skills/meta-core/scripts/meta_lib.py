"""meta-* スクリプトの共通ロジック。

frontmatter(YAML のサブセット)の解析を 1 箇所に集約する。meta_check.py・
meta_extract.py・trigger_check.py が共有し、同じフィールドに対して別々の結論を
出さないようにする。Python 3 標準ライブラリのみを使用する。

解釈する記法(サブセット):
  key: value            スカラー(前後の引用符を剥がす)
  key: "value"          引用符つきスカラー
  key: |  / >  / |- 等  ブロックスカラー(後続のインデント行を連結する)
  key:                  ブロックシーケンス(後続の `  - item` 行を集める)
  # comment             行コメント(無視する)

解釈できない行は捨てずに `unparsable` として返す。呼び出し側はこれを「値が違う」
と断定せず、「この解析器が解釈できない記法」として区別して報告する。
"""

from __future__ import annotations

import re

KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
SEQ_ITEM_RE = re.compile(r"^\s+-\s+(.*)$")
BLOCK_SCALAR_RE = re.compile(r"^([|>])([+-]?)(\d*)\s*$")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _collect_indented(lines: list[str], start: int) -> tuple[list[str], int]:
    """start 以降の連続するインデント行(と空行)を集める。"""
    body: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if line.strip() and not line.startswith((" ", "\t")):
            break
        body.append(line)
        i += 1
    while body and not body[-1].strip():
        body.pop()
    return body, i


def _split_frontmatter(text: str) -> list[str] | None:
    """先頭 frontmatter の本体行を返す。開始・終了の `---` が無ければ None。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return body
        body.append(line)
    return None


def parse_frontmatter(text: str) -> tuple[dict, list[str]] | None:
    """frontmatter を解析する。

    返り値: `(値の辞書, 解析できなかった行の一覧)`。frontmatter が無い(または
    閉じの `---` が無い)場合は None。値は str(スカラー・ブロックスカラー)または
    list[str](ブロックシーケンス)。
    """
    body = _split_frontmatter(text)
    if body is None:
        return None
    data: dict = {}
    unparsable: list[str] = []
    i = 0
    while i < len(body):
        line = body[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = KEY_RE.match(line)
        if not m:
            unparsable.append(line.rstrip())
            i += 1
            continue
        key, raw = m.group(1), m.group(2).strip()
        block = BLOCK_SCALAR_RE.match(raw)
        if block:
            chunk, i = _collect_indented(body, i + 1)
            joiner = "\n" if block.group(1) == "|" else " "
            data[key] = joiner.join(s.strip() for s in chunk if s.strip())
            continue
        if raw == "":
            chunk, nxt = _collect_indented(body, i + 1)
            items = [SEQ_ITEM_RE.match(s) for s in chunk if s.strip()]
            if chunk and all(items):
                data[key] = [_unquote(m2.group(1).strip()) for m2 in items if m2]
                i = nxt
                continue
            if chunk:
                unparsable.append(line.rstrip())
                i = nxt
                continue
            data[key] = ""
            i += 1
            continue
        data[key] = _unquote(raw)
        i += 1
    return data, unparsable


def scalar(data: dict, key: str) -> str | None:
    """スカラー値を取り出す(リスト等の非スカラーは None)。"""
    value = data.get(key)
    return value if isinstance(value, str) else None
