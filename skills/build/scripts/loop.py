"""loop.py — build の反復を 1 回ずつ新しい claude のプロセスで起動する。

反復の前に進捗ファイルを読んで停止条件を判定し、停止しなければ claude を起動する。
進捗ファイルに書き込むのは反復のセッションであり、本スクリプトは読むだけである。
標準ライブラリのみで動く(python3 で実行)。

使い方:
    python3 loop.py <進捗ファイル> [--max-iterations N] [-- <claude に渡す引数>...]

起動するコマンドは環境変数 BUILD_AGENT_CMD で差し替えられる(既定は `claude -p`)。

解析する進捗ファイルの形式:
    - 失敗の上限: 3
    - 停止: なし

    | 日時 | タスク | 結果 | PR | 要点 |
    | :-- | :-- | :-- | :-- | :-- |
    | 2026-10-11 13:00 | TASK-2 | 失敗 | - | reviewer 3 回不承認 |

- 停止が `全 Done` で始まれば終了コード 0、`なし` 以外なら 1 で止まる。
- 結果が `失敗` と完全一致する行をタスクごとに数え、上限に達したタスクがあれば 1 で止まる。
  `失敗(解決済み)` は数えない。

終了コード: 0 = 全 Done、1 = 停止・失敗・上限、2 = 進捗ファイルの不備(読めない・形式が不正)または引数の誤り。
"""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

AGENT_CMD_ENV = "BUILD_AGENT_CMD"
PROMPT = "dev-skills の build スキルの「反復する」工程を 1 回行う。進捗ファイル: {path}"

_STOP = "- 停止:"
_MAX_FAILURES = "- 失敗の上限:"


def parse_progress(text: str) -> dict:
    """停止の行・失敗の上限・タスクごとの失敗の回数を読む。"""
    stop = None
    max_failures = None
    failures: dict[str, int] = {}
    for line in text.splitlines():
        if line.startswith(_STOP):
            stop = line[len(_STOP):].strip()
        elif line.startswith(_MAX_FAILURES):
            max_failures = line[len(_MAX_FAILURES):].strip()
        elif line.startswith("|"):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) > 3 and cells[3] == "失敗":
                failures[cells[2]] = failures.get(cells[2], 0) + 1
    if stop is None:
        raise ValueError(f"`{_STOP}` の行が無い")
    if max_failures is None:
        raise ValueError(f"`{_MAX_FAILURES}` の行が無い")
    if not (max_failures.isascii() and max_failures.isdigit() and int(max_failures) > 0):
        raise ValueError(f"失敗の上限が正の整数でない: {max_failures!r}")
    return {"stop": stop, "max_failures": int(max_failures), "failures": failures}


def stop_reason(progress: dict) -> tuple[int, str] | None:
    """停止するなら (終了コード, 理由) を、続けるなら None を返す。"""
    stop = progress["stop"]
    if stop.startswith("全 Done"):
        return 0, stop
    if stop != "なし":
        return 1, stop
    for task, count in progress["failures"].items():
        if count >= progress["max_failures"]:
            return 1, f"{task} が {count} 回失敗した"
    return None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"進捗ファイルを読めない: {e}", file=sys.stderr)
        return None


def _positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError(f"正の整数でない: {value!r}")
    return n


def main(argv: list[str]) -> int:
    if "--" in argv:
        sep = argv.index("--")
        argv, extra = argv[:sep], argv[sep + 1:]
    else:
        extra = []
    parser = argparse.ArgumentParser(description="build の反復を繰り返し起動する。")
    parser.add_argument("progress", type=Path, help="進捗ファイル")
    parser.add_argument("--max-iterations", type=_positive_int, default=20, help="反復の上限(既定 20)")
    args = parser.parse_args(argv)

    path = args.progress.resolve()
    cmd = shlex.split(os.environ.get(AGENT_CMD_ENV, "")) or ["claude", "-p"]
    cmd += [PROMPT.format(path=path), *extra]

    # 上限回の反復のあとも停止条件を判定し、最後の反復で全 Done になった場合を 0 で返す。
    for i in range(1, args.max_iterations + 2):
        before = _read(path)
        if before is None:
            return 2
        try:
            reason = stop_reason(parse_progress(before))
        except ValueError as e:
            print(f"進捗ファイルの形式が不正: {e}", file=sys.stderr)
            return 2
        if reason is not None:
            code, message = reason
            print(f"停止: {message}")
            return code
        if i > args.max_iterations:
            print(f"反復の上限 {args.max_iterations} 回に達した")
            return 1

        print(f"反復 {i}: 起動", flush=True)
        try:
            proc = subprocess.run(cmd)
        except FileNotFoundError:
            print(f"コマンドが見つからない: {cmd[0]}", file=sys.stderr)
            return 1
        if proc.returncode != 0:
            print(f"反復 {i} が終了コード {proc.returncode} で終わった")
            return 1
        after = _read(path)
        if after is None:
            return 2
        if after == before:
            print("進捗ファイルが更新されなかった")
            return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
