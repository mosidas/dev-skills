"""render.py — .mmd と SVG の対応を機械照合する。

LLM が .mmd を元に SVG を直接書く運用を前提に、SVG 側の書式規則
(ノードの図形に `data-id="<.mmd のノード id>"`、辺の要素に
`data-edge="<src>-><dst>"`)を定め、.mmd から抽出した id・辺の集合と
SVG の属性の集合を突き合わせる。標準ライブラリのみで動く(python3 で実行)。

使い方:
    python3 render.py <diagram.mmd> <diagram.svg> [--png OUT] [--width W] [--height H] [--timeout SEC]

対応する記法: flowchart/graph, stateDiagram-v2, sequenceDiagram。
classDiagram・erDiagram は照合対象外(整形式検査と禁止要素の検査のみ)。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# .mmd のパース
# ---------------------------------------------------------------------------

NODE_ID = r"[A-Za-z0-9_]+"
_SHAPE_ALT = r"\(\[.*?\]\)|\[.*?\]|\(.*?\)|\{.*?\}"
_NODE_ATOM = rf"{NODE_ID}(?:{_SHAPE_ALT})?"
# flowchart の `A & B --> C` 並列記法用: `&` 区切りのノード列をひとまとめに捕捉する。
_NODE_GROUP = rf"{_NODE_ATOM}(?:\s*&\s*{_NODE_ATOM})*"
# stateDiagram-v2 の開始・終了擬似状態 `[*]` を通常のノード id と並べて捕捉する。
_STATE_NODE = rf"(?:{NODE_ID}|\[\*\])"
START_STATE_ID = "_start"
END_STATE_ID = "_end"

NODE_DECL_RE = re.compile(rf"({NODE_ID})({_SHAPE_ALT})")
PARTICIPANT_RE = re.compile(rf"^(?:participant|actor)\s+({NODE_ID})")
EDGE_LABEL_RE = re.compile(r"\|[^|]*\|")

FLOW_EDGE_RE = re.compile(
    rf"({_NODE_GROUP})"
    r"\s*(?:-\.->|-->|---|==>|===|-\.-)\s*"
    r"(?:\|[^|]*\|\s*)?"
    rf"({_NODE_GROUP})"
)
STATE_EDGE_RE = re.compile(rf"({_STATE_NODE})\s*-->\s*({_STATE_NODE})\s*(?::\s*(.*))?")
SEQ_EDGE_RE = re.compile(rf"({NODE_ID})\s*(?:-->>|->>|-->|->)\s*({NODE_ID})\s*:\s*(.*)")

_SKIP_FIRST_WORDS = {
    "flowchart",
    "graph",
    "stateDiagram-v2",
    "sequenceDiagram",
    "subgraph",
    "end",
    "direction",
}

# 照合対象外の図の種類(整形式検査と禁止要素の検査だけを行う)。
UNSUPPORTED_DIAGRAM_TYPES = {"classDiagram", "erDiagram"}


def _register_node_decls(line: str, nodes: set[str], diagram_type: str) -> None:
    if diagram_type == "sequenceDiagram":
        # sequenceDiagram はメッセージ本文の角括弧(例: `A->>B: fetch data[1]`)を
        # ノード宣言と誤読しないよう、participant/actor 行だけを見る。
        m = PARTICIPANT_RE.match(line)
        if m:
            nodes.add(m.group(1))
        return
    # 辺ラベル `|...|` の中身にある角括弧をノード宣言と誤読しないよう、先に除去する。
    line_wo_labels = EDGE_LABEL_RE.sub("", line)
    for m in NODE_DECL_RE.finditer(line_wo_labels):
        nodes.add(m.group(1))


_SIDE_ATOM_RE = re.compile(rf"({NODE_ID})(?:{_SHAPE_ALT})?")


def _side_ids(text: str) -> list[str]:
    """flowchart の `A[A] & B[B]` のような `&` 区切りの片側からノード id を取り出す。

    `text.split("&")` で割ると `A[fetch & store]` のようなラベル本文の `&` を
    並列の区切りと誤読するため、片側のテキストからノード原子を順に拾う。
    """
    return [m.group(1) for m in _SIDE_ATOM_RE.finditer(text)]


def _edge_pairs(diagram_type: str, raw_src: str, raw_dst: str) -> list[tuple[str, str]]:
    if diagram_type == "flowchart":
        return [(s, d) for s in _side_ids(raw_src) for d in _side_ids(raw_dst)]
    if diagram_type == "stateDiagram-v2":
        src = START_STATE_ID if raw_src == "[*]" else raw_src
        dst = END_STATE_ID if raw_dst == "[*]" else raw_dst
        return [(src, dst)]
    return [(raw_src, raw_dst)]


def _parse_lines(
    lines: list[str], diagram_type: str, edge_re: re.Pattern
) -> tuple[set[str], set[tuple[str, str]]]:
    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("%%"):
            continue
        first_word = line.split()[0]
        if first_word in _SKIP_FIRST_WORDS:
            continue
        _register_node_decls(line, nodes, diagram_type)
        pos = 0
        while True:
            m = edge_re.search(line, pos)
            if not m:
                break
            for src, dst in _edge_pairs(diagram_type, m.group(1), m.group(2)):
                edges.add((src, dst))
                nodes.add(src)
                nodes.add(dst)
            pos = m.start(2)
    return nodes, edges


def parse_mmd(text: str) -> tuple[str, set[str] | None, set[tuple[str, str]] | None]:
    """.mmd を解析し、(図の種類, ノード id の集合, 辺の集合) を返す。

    classDiagram・erDiagram は照合対象外を示すため nodes・edges に None を返す。
    """
    lines = text.splitlines()
    diagram_type = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        diagram_type = stripped.split()[0]
        break
    if diagram_type is None:
        raise ValueError(".mmd が空、またはコメントしか含まない")

    if diagram_type in UNSUPPORTED_DIAGRAM_TYPES:
        return diagram_type, None, None

    if diagram_type in ("flowchart", "graph"):
        nodes, edges = _parse_lines(lines, "flowchart", FLOW_EDGE_RE)
    elif diagram_type == "stateDiagram-v2":
        nodes, edges = _parse_lines(lines, "stateDiagram-v2", STATE_EDGE_RE)
    elif diagram_type == "sequenceDiagram":
        nodes, edges = _parse_lines(lines, "sequenceDiagram", SEQ_EDGE_RE)
    else:
        return diagram_type, None, None

    return diagram_type, nodes, edges


# ---------------------------------------------------------------------------
# SVG のパース
# ---------------------------------------------------------------------------

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
FORBIDDEN_TAGS = {"script", "foreignObject", "image"}
EXTERNAL_URL_RE = re.compile(r"^\s*(?:https?:)?//")
CSS_URL_RE = re.compile(r"url\(\s*['\"]?(https?://[^'\")]+)")
MALFORMED_PREFIX = "SVG が整形式でない"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_svg(path: str | Path) -> tuple[set[str], set[tuple[str, str]], list[str]]:
    """SVG を解析し、(data-id の集合, data-edge の集合, 禁止事項の一覧) を返す。"""
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as e:
        return set(), set(), [f"{MALFORMED_PREFIX}: {e}"]

    ids: set[str] = set()
    edges: set[tuple[str, str]] = set()
    violations: list[str] = []

    for elem in tree.getroot().iter():
        tag = _local_name(elem.tag)
        if tag in FORBIDDEN_TAGS:
            violations.append(f"禁止要素 <{tag}> を検出")

        data_id = elem.get("data-id")
        if data_id:
            ids.add(data_id)

        data_edge = elem.get("data-edge")
        if data_edge:
            if "->" in data_edge:
                src, dst = data_edge.split("->", 1)
                edges.add((src, dst))
            else:
                violations.append(f"data-edge の形式が不正: {data_edge!r}")

        for attr_name in ("href", XLINK_HREF):
            value = elem.get(attr_name)
            if value and EXTERNAL_URL_RE.search(value):
                violations.append(f"外部参照を検出: {attr_name}={value!r}")

        style_attr = elem.get("style")
        if style_attr:
            m = CSS_URL_RE.search(style_attr)
            if m:
                violations.append(f"style 属性に外部参照 url() を検出: {m.group(1)!r}")

        if tag == "style" and elem.text:
            m = CSS_URL_RE.search(elem.text)
            if m:
                violations.append(f"<style> 要素に外部参照 url() を検出: {m.group(1)!r}")

    return ids, edges, violations


# ---------------------------------------------------------------------------
# 照合
# ---------------------------------------------------------------------------


def compare(
    mmd: tuple[str, set[str] | None, set[tuple[str, str]] | None],
    svg: tuple[set[str], set[tuple[str, str]], list[str]],
) -> list[str]:
    """.mmd と SVG の id・辺の集合の食い違いを日本語で列挙する。"""
    _diagram_type, nodes, edges = mmd
    svg_ids, svg_edges, _violations = svg
    if nodes is None or edges is None:
        return []

    mmd_ids = nodes
    missing_nodes = mmd_ids - svg_ids
    extra_nodes = svg_ids - mmd_ids
    missing_edges = edges - svg_edges
    extra_edges = svg_edges - edges

    findings = []
    if missing_nodes:
        findings.append("SVG に無いノード: " + ", ".join(sorted(missing_nodes)))
    if extra_nodes:
        findings.append(".mmd に無いノード: " + ", ".join(sorted(extra_nodes)))
    if missing_edges:
        findings.append(
            "SVG に無い辺: " + ", ".join(f"{s}->{d}" for s, d in sorted(missing_edges))
        )
    if extra_edges:
        findings.append(
            ".mmd に無い辺: " + ", ".join(f"{s}->{d}" for s, d in sorted(extra_edges))
        )
    return findings


# ---------------------------------------------------------------------------
# スクリーンショット(--png 指定時のみ)
# ---------------------------------------------------------------------------

DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEFAULT_CHROME_TIMEOUT_SECONDS = 60.0
_PNG_POLL_INTERVAL_SECONDS = 0.5
_PNG_IEND_CHUNK = b"\x00\x00\x00\x00IEND\xaeB\x60\x82"
_STDERR_TAIL_LINES = 20


def _default_chrome_timeout() -> float:
    try:
        return float(os.environ.get("DRAW_DIAGRAM_CHROME_TIMEOUT", str(DEFAULT_CHROME_TIMEOUT_SECONDS)))
    except ValueError:
        return DEFAULT_CHROME_TIMEOUT_SECONDS


def _svg_viewbox_size(svg_path: str) -> tuple[int, int]:
    try:
        root = ET.parse(svg_path).getroot()
        viewbox = root.get("viewBox")
        if viewbox:
            parts = viewbox.split()
            if len(parts) == 4:
                return int(float(parts[2])), int(float(parts[3]))
    except (ET.ParseError, OSError, ValueError):
        pass
    return 1200, 800


def _png_ready(png_abs: str) -> bool:
    """PNG が IEND チャンクまで書き終わっているかを見る(書き込み途中の誤認を防ぐ)。"""
    try:
        if os.path.getsize(png_abs) < len(_PNG_IEND_CHUNK):
            return False
        with open(png_abs, "rb") as f:
            f.seek(-len(_PNG_IEND_CHUNK), os.SEEK_END)
            return f.read() == _PNG_IEND_CHUNK
    except OSError:
        return False


def _read_stderr_tail(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-_STDERR_TAIL_LINES:]).strip()
    except OSError:
        return ""


def screenshot(
    svg: str,
    png: str,
    width: int | None = None,
    height: int | None = None,
    timeout: float | None = None,
) -> list[str]:
    """Chrome のヘッドレスモードで SVG を PNG に撮る。失敗理由の一覧を返す(空なら成功)。

    Chrome は PNG を書き出した後も終了しないため、プロセスの自然終了を待たず
    0.5 秒おきに PNG の出現を監視し、出現したら即座に kill して成功とみなす。
    """
    chrome = os.environ.get("CHROME_BIN", DEFAULT_CHROME)
    timeout = _default_chrome_timeout() if timeout is None else timeout
    if not os.path.exists(chrome):
        return [f"Chrome の実行ファイルが見つからない: {chrome}"]

    if width is None or height is None:
        vb_width, vb_height = _svg_viewbox_size(svg)
        width = width if width is not None else vb_width
        height = height if height is not None else vb_height

    svg_abs = os.path.abspath(svg)
    png_abs = os.path.abspath(png)
    Path(png_abs).unlink(missing_ok=True)

    # ponytail: サンドボックス内では Chrome が「Failed to create socket directory」で
    # 起動できないことがある。--user-data-dir を一時ディレクトリに固定しても解決しない
    # 場合は、サンドボックス外(または CI の専用コンテナ)で実行する必要がある。
    with tempfile.TemporaryDirectory() as user_data_dir:
        stderr_path = os.path.join(user_data_dir, "chrome-stderr.log")
        # stdout/stderr を PIPE のまま誰も読まないと、Chrome がパイプのバッファを
        # 埋めた時点で書き込みがブロックし撮影に到達できなくなるため、stdout は
        # 読み捨て、stderr は一時ディレクトリ内のファイルへ逃がす。
        with open(stderr_path, "wb") as stderr_file:
            try:
                proc = subprocess.Popen(
                    [
                        chrome,
                        "--headless=new",
                        "--disable-gpu",
                        "--disable-crash-reporter",
                        "--hide-scrollbars",
                        f"--user-data-dir={user_data_dir}",
                        f"--window-size={width},{height}",
                        f"--screenshot={png_abs}",
                        f"file://{svg_abs}",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_file,
                )
            except OSError as e:
                return [f"Chrome の起動に失敗した: {e}"]

            deadline = time.monotonic() + timeout
            while True:
                returncode = proc.poll()
                if _png_ready(png_abs):
                    if returncode is None:
                        proc.kill()
                        proc.wait()
                    break
                if returncode is not None:
                    if not _png_ready(png_abs):
                        return [
                            f"Chrome の実行に失敗した(exit={returncode}): "
                            f"{_read_stderr_tail(stderr_path)}"
                        ]
                    break
                if time.monotonic() >= deadline:
                    proc.kill()
                    proc.wait()
                    if not _png_ready(png_abs):
                        return [f"Chrome の起動がタイムアウトした({timeout:.0f}秒)"]
                    break
                time.sleep(_PNG_POLL_INTERVAL_SECONDS)

    if not _png_ready(png_abs):
        return [f"PNG が生成されなかった: {png_abs}"]
    return []


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=".mmd と SVG の対応を機械照合する")
    parser.add_argument("mmd", type=Path, help=".mmd ファイル")
    parser.add_argument("svg", type=Path, help="SVG ファイル")
    parser.add_argument("--png", type=Path, help="指定すると Chrome で PNG を撮る")
    parser.add_argument("--width", type=int, help="スクリーンショットの幅")
    parser.add_argument("--height", type=int, help="スクリーンショットの高さ")
    parser.add_argument(
        "--timeout",
        type=float,
        help="Chrome の起動タイムアウト秒数(既定は DRAW_DIAGRAM_CHROME_TIMEOUT 環境変数または60秒)",
    )
    args = parser.parse_args(argv)

    try:
        mmd_text = args.mmd.read_text(encoding="utf-8")
    except OSError as e:
        print(f".mmd を読み込めない: {e}", file=sys.stderr)
        return 1

    try:
        mmd_result = parse_mmd(mmd_text)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    diagram_type, nodes, _edges = mmd_result
    svg_ids, svg_edges, violations = parse_svg(args.svg)
    svg_result = (svg_ids, svg_edges, violations)

    findings = list(violations)
    malformed = any(v.startswith(MALFORMED_PREFIX) for v in violations)

    if nodes is None:
        print(f"{diagram_type} は照合対象外。整形式検査と禁止要素の検査だけを行った。")
    elif not malformed:
        findings.extend(compare(mmd_result, svg_result))

    if findings:
        for f in findings:
            print(f, file=sys.stderr)
        return 1

    if args.png:
        errors = screenshot(str(args.svg), str(args.png), args.width, args.height, args.timeout)
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
