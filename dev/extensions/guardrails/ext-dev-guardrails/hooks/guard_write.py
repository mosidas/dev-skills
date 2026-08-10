#!/usr/bin/env python3
"""凍結済みの中間生成物への書き込みを拒否する PreToolUse hook(Write / Edit / MultiEdit / NotebookEdit)。

文章の規律(`principles.md` 1.「凍結された中間生成物を変更してはならない」)を決定論的に
強制する。`check.py` は凍結違反を書き込みの**後**に error として検出するのに対し、本 hook は
書き込み自体を拒否する(D-018)。

判定は、書き込み先と同じディレクトリの `state.json` の `frozen`(`{ファイル名: ハッシュ}`)に
そのファイル名が記録されているかで行う。`frozen` は状態機械が完了状態への遷移時に記録する。

入出力の契約:
  標準入力  PreToolUse の JSON(`tool_name` と `tool_input` のファイルパスを読む)
  exit 0    許可(何も出力しない)
  exit 2    拒否。標準エラーへ書いた理由が Claude へ返る

Python 3 標準ライブラリのみで動作する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PATH_KEYS = ("file_path", "notebook_path", "path")
DURABLE = "dev-core/references/durable-info.md"


def target_path(tool_input: dict) -> Path | None:
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return Path(value)
    return None


def frozen_names(workdir: Path) -> set[str]:
    """workdir の `state.json` が記録する凍結済み成果物のファイル名。"""
    state_file = workdir / "state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return set()
    frozen = state.get("frozen")
    if not isinstance(frozen, dict):
        return set()
    return {name for name in frozen if isinstance(name, str)}


def candidates(path: Path, cwd: str | None = None) -> list[Path]:
    """判定に使うパス(渡された形と、実体へ解決した形)を返す。

    シンボリックリンク経由の別名で凍結済み成果物を書き換えられないよう、実体へ解決した
    パスでも照合する。相対パスは hook の実行ディレクトリに依存しないよう、入力の `cwd`
    (PreToolUse の JSON が持つ)を基点に絶対化する。
    """
    found = [path]
    base = Path(cwd) / path if cwd and not path.is_absolute() else path
    try:
        resolved = base.resolve()
    except OSError:
        resolved = base
    for cand in (base, resolved):
        if cand not in found:
            found.append(cand)
    return found


def check(path: Path, cwd: str | None = None) -> str | None:
    """拒否する理由を返す(許可なら None)。"""
    for cand in candidates(path, cwd):
        if cand.name in frozen_names(cand.parent):
            return f"{cand.name} は完了状態で凍結された中間生成物である"
    return None


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        sys.exit(0)  # 解釈できない入力で作業を止めない
    if payload.get("tool_name") not in WRITE_TOOLS:
        sys.exit(0)
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        sys.exit(0)
    path = target_path(tool_input)
    if path is None:
        sys.exit(0)
    cwd = payload.get("cwd")
    reason = check(path, cwd if isinstance(cwd, str) else None)
    if reason is None:
        sys.exit(0)
    print(
        f"この書き込みは dev スキル群の規律で禁止されている: {reason}。\n"
        f"実装後に判明した差異は、中間生成物へ書き戻さずコードと恒久情報({DURABLE})へ反映する。"
        "仕様そのものを変える必要がある場合は、新しい作業単位(別の workdir)を立てる。",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
