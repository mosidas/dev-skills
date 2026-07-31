#!/usr/bin/env python3
"""スキル群のコード行数の集計(read-only)。

dev-skills を構成するファイル(用途グループ・`.claude`・`.meta`・`ports`・`extensions`・
ルート直下)の行数を、領域(スキルごと・エージェント・`.meta` 等)と種別(拡張子)ごとに
集計する。ファイルを書き換えない。標準ライブラリのみ(追加インストール不要の担保)。

行数の定義:
  総行数   物理行(改行で区切った行の数)
  実行数   空白のみでない行の数(コメント・散文を含む)
  空行     総行数 − 実行数

除外: `.git/`・`__pycache__/`・`*.pyc`・UTF-8 で読めないファイル(バイナリ)。

使い方:
  meta_loc.py [--root <ルート>] [--json] [--by-file]
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import meta_lib  # noqa: E402

EXCLUDE_DIRS = {".git", "__pycache__"}
EXCLUDE_SUFFIXES = {".pyc"}
# 領域をそのディレクトリ名で表すもの(スキル群の外側)。
NON_GROUP_TOPS = (".meta", "ports", "extensions")


def die(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def iter_files(root: Path):
    """除外条件に合致しないファイルを再帰的に返す。"""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        yield path, rel


def area_of(rel: Path) -> str:
    """相対パスから領域(集計の単位)を決める。

    スキルは名前そのものを領域にする(グループが変わっても同じ領域名で追える)。
    エージェントはグループ込みの `<グループ>/agents` を領域にする。
    """
    parts = rel.parts
    if parts[0] in NON_GROUP_TOPS:
        return parts[0]
    if len(parts) >= 3 and parts[1] == meta_lib.SKILLS_SUBDIR:
        return parts[2]
    if len(parts) >= 3 and parts[1] == meta_lib.AGENTS_SUBDIR:
        return f"{parts[0]}/{meta_lib.AGENTS_SUBDIR}"
    return "(ルート直下)"


def ext_of(rel: Path) -> str:
    return rel.suffix if rel.suffix else "(拡張子なし)"


def count_lines(path: Path) -> tuple[int, int] | None:
    """(総行数, 実行数) を返す。バイナリ(UTF-8 で読めない)なら None。"""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.splitlines()
    total = len(lines)
    code = sum(1 for line in lines if line.strip())
    return total, code


class Bucket:
    __slots__ = ("files", "total", "code")

    def __init__(self) -> None:
        self.files = 0
        self.total = 0
        self.code = 0

    def add(self, total: int, code: int) -> None:
        self.files += 1
        self.total += total
        self.code += code

    def as_dict(self) -> dict:
        return {"files": self.files, "total": self.total, "code": self.code}


def collect(root: Path) -> dict:
    by_area: dict[str, Bucket] = {}
    by_ext: dict[str, Bucket] = {}
    by_file: list[dict] = []
    grand = Bucket()
    skipped: list[str] = []
    for path, rel in iter_files(root):
        counts = count_lines(path)
        if counts is None:
            skipped.append(str(rel))
            continue
        total, code = counts
        by_area.setdefault(area_of(rel), Bucket()).add(total, code)
        by_ext.setdefault(ext_of(rel), Bucket()).add(total, code)
        grand.add(total, code)
        by_file.append({"path": str(rel), "total": total, "code": code})
    return {
        "by_area": by_area,
        "by_ext": by_ext,
        "by_file": by_file,
        "grand": grand,
        "skipped": skipped,
    }


def _sorted_items(buckets: dict[str, Bucket]) -> list[tuple[str, Bucket]]:
    return sorted(buckets.items(), key=lambda kv: (-kv[1].total, kv[0]))


def _dwidth(s: str) -> int:
    """端末での表示幅(全角=2、半角=1)。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def _ljust(s: str, width: int) -> str:
    return s + " " * max(0, width - _dwidth(s))


def _rjust(s: str, width: int) -> str:
    return " " * max(0, width - _dwidth(s)) + s


def print_table(title: str, buckets: dict[str, Bucket], label: str) -> None:
    rows = _sorted_items(buckets)
    lw = max([_dwidth(label)] + [_dwidth(k) for k, _ in rows]) if rows else _dwidth(label)
    nw = (8, 8, 8)  # ファイル / 総行数 / 実行数 の列幅
    print(f"\n{title}")
    header = (
        f"  {_ljust(label, lw)}  {_rjust('ファイル', nw[0])}"
        f"  {_rjust('総行数', nw[1])}  {_rjust('実行数', nw[2])}"
    )
    print(header)
    for name, b in rows:
        print(
            f"  {_ljust(name, lw)}  {_rjust(str(b.files), nw[0])}"
            f"  {_rjust(str(b.total), nw[1])}  {_rjust(str(b.code), nw[2])}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="スキル群のコード行数の集計(read-only)")
    parser.add_argument(
        "--root", help="dev-skills のルート(既定: スキルのグループを上方向に探索)"
    )
    parser.add_argument("--json", action="store_true", help="JSON で出力する")
    parser.add_argument(
        "--by-file", action="store_true", help="ファイルごとの行数も出力する"
    )
    args = parser.parse_args()

    if args.root:
        root = Path(args.root).resolve()
        if not meta_lib.is_root(root):
            die(f"--root にスキルのグループが無い: {root}")
    else:
        found = meta_lib.find_root(Path.cwd())
        if found is None:
            die("スキルのグループを含むルートが見つからない(--root で指定する)")
        root = found

    result = collect(root)
    grand: Bucket = result["grand"]

    if args.json:
        payload = {
            "root": str(root),
            "total_files": grand.files,
            "total_lines": grand.total,
            "code_lines": grand.code,
            "by_area": {k: v.as_dict() for k, v in _sorted_items(result["by_area"])},
            "by_ext": {k: v.as_dict() for k, v in _sorted_items(result["by_ext"])},
            "skipped": result["skipped"],
        }
        if args.by_file:
            payload["by_file"] = sorted(
                result["by_file"], key=lambda r: (-r["total"], r["path"])
            )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"集計対象ルート: {root}")
    print_table("領域ごと", result["by_area"], "領域")
    print_table("種別ごと(拡張子)", result["by_ext"], "種別")
    if args.by_file:
        print("\nファイルごと(総行数の多い順)")
        for r in sorted(result["by_file"], key=lambda r: (-r["total"], r["path"])):
            print(f"  {r['total']:>6}  {r['code']:>6}  {r['path']}")
    print(
        f"\n合計: {grand.files} ファイル / 総行数 {grand.total} / 実行数 {grand.code}"
    )
    if result["skipped"]:
        print(f"(バイナリ等で除外: {len(result['skipped'])} 件)")


if __name__ == "__main__":
    main()
