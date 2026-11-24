#!/usr/bin/env python3
"""会話の要約(compact)の後に、In Progress のタスクの Implementation Notes を読み直させる SessionStart hook。

要約は作業の経過を落とすため、要約だけで作業を続けさせず、要約に書かれた作業のタスクの Notes から再開点を決めさせる。
`backlog task list --status "In Progress" --json` の一覧を指示に添えて注入する。

入出力の契約:
  標準入力  UTF-8 の SessionStart の JSON(`source`・`cwd` を読む)。環境の符号化に依らず UTF-8 のバイト列として読む
  exit 0    検査を終えたとき(注入するときもしないときも)。セッションを止めない
  exit 1    hook 自身の想定外の例外。標準エラーに例外の型名だけを 1 行書く
  標準出力  `source` が compact で In Progress のタスクが 1 件以上あれば、一覧つきの指示を
            `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": <指示>}}` の ASCII の JSON で書く。
            一覧の取得が打ち切られたか出力が想定の形でなければ、一覧なしの指示を同じ形で書く。
            compact でない・読めない入力・0 件・CLI を起動できない・CLI が非 0 で終わったときは何も書かない
  標準エラー 一覧を取らなかった理由を `error.type` 付きの 1 行で書く(タイトル・パス・CLI の出力は書かない)

hooks.json の matcher に加えてここでも `source` を判定するのは、compact 以外で注入しないことをテストで確かめるためである。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import BinaryIO

LIST_COMMAND = ["backlog", "task", "list", "--status", "In Progress", "--json"]
# shortcut: 仮に 3 秒(実測 0.11〜0.20 秒の約 15 倍、hooks.json の timeout 10 秒より短い), 利用者の環境で task list の p99.9 を実測したら置き換える
LIST_TIMEOUT = 3
LIST_LIMIT = 20
TITLE_LIMIT = 200
# str.splitlines が行の区切りとみなす文字をすべて含む(C0・DEL・C1・U+2028・U+2029)
LINE_BREAKING = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")

HEADING = "dev-skills: 会話の要約の後である。\n"
LISTED = (
    HEADING + "要約だけで作業を続けない。要約に書かれた作業のタスクを下の一覧から id かタイトルで選び、"
    "`backlog task <id> --plain` で Implementation Notes を読み、develop 11.(再開する)の手順で再開点を決めてから続ける。"
    "一覧には並行する別のセッションのタスクも入る。要約に無いタスクは読まず、続けない。要約の作業が一覧に無ければ何もしない。\n"
    "\n"
    "In Progress のタスク(更新の新しい順。タイトルはタスクのファイルの値):"
)
MORE = "- ほか {n} 件(`backlog task list --status \"In Progress\" --plain` で見る)"
FALLBACK = (
    HEADING + "In Progress のタスクの一覧を取れなかった。要約だけで作業を続けない。"
    "要約に書かれた作業が backlog のタスクなら、`backlog task <id> --plain` で Implementation Notes を読み、"
    "develop 11.(再開する)の手順で再開点を決めてから続ける。"
)


class NotListed(Exception):
    """一覧を取らなかった。`fallback` なら一覧なしの指示を注入する。"""

    def __init__(self, error_type: str, fallback: bool, exit_code: int | None = None) -> None:
        super().__init__(error_type)
        self.error_type = error_type
        self.fallback = fallback
        self.exit_code = exit_code


def read_payload(stdin: BinaryIO) -> dict | None:
    """UTF-8 のバイト列の JSON を dict で返す。読めないか dict でなければ None。"""
    try:
        payload = json.loads(stdin.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def work_dir(payload: dict) -> str:
    """CLI を走らせるディレクトリ。入力の cwd、無ければ CLAUDE_PROJECT_DIR。"""
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if isinstance(candidate, str) and candidate and os.path.isdir(candidate):
            return candidate
    raise NotListed("cwd_unavailable", fallback=False)


def in_progress_tasks(cwd: str) -> list[dict]:
    """In Progress のタスク(id・title が文字列の dict)の一覧。"""
    try:
        proc = subprocess.run(
            LIST_COMMAND, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, timeout=LIST_TIMEOUT
        )
    except subprocess.TimeoutExpired:
        raise NotListed("backlog_timeout", fallback=True) from None
    except OSError:
        raise NotListed("backlog_not_found", fallback=False) from None
    if proc.returncode != 0:
        raise NotListed("backlog_exit", fallback=False, exit_code=proc.returncode)
    try:
        listing = json.loads(proc.stdout.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise NotListed("backlog_output_invalid", fallback=True) from None
    tasks = listing.get("tasks") if isinstance(listing, dict) and listing.get("kind") == "task-list" else None
    if not isinstance(tasks, list) or not all(
        isinstance(t, dict) and isinstance(t.get("id"), str) and isinstance(t.get("title"), str) for t in tasks
    ):
        raise NotListed("backlog_output_invalid", fallback=True)
    return tasks


def one_line(text: str) -> str:
    """改行と制御文字を空白にして 1 行にし、TITLE_LIMIT 字で切る(タスクのファイルの値で指示の行を作らせない)。"""
    return LINE_BREAKING.sub(" ", text)[:TITLE_LIMIT]


def listed(tasks: list[dict]) -> str:
    def updated(t: dict) -> str:
        # backlog 1.51.0 は作成後に一度も編集していないタスクに updatedAt を出さず createdAt だけを出す。どちらも Z 付きの ISO 8601
        for key in ("updatedAt", "createdAt"):
            if isinstance(t.get(key), str):
                return t[key]
        return ""

    ordered = sorted(tasks, key=updated, reverse=True)
    lines = [LISTED] + [f"- {one_line(t['id'])} {one_line(t['title'])}" for t in ordered[:LIST_LIMIT]]
    if len(ordered) > LIST_LIMIT:
        lines.append(MORE.format(n=len(ordered) - LIST_LIMIT))
    return "\n".join(lines)


def log_not_listed(e: NotListed) -> None:
    line = f"inject_reread_notes: 一覧を取らない error.type={e.error_type}"
    if e.exit_code is not None:
        line += f" exit_code={e.exit_code}"
    sys.stderr.buffer.write((line + "\n").encode("utf-8"))
    sys.stderr.buffer.flush()


def main() -> int:
    payload = read_payload(sys.stdin.buffer)
    if payload is None or payload.get("source") != "compact":
        return 0
    try:
        tasks = in_progress_tasks(work_dir(payload))
    except NotListed as e:
        log_not_listed(e)
        if not e.fallback:
            return 0
        context = FALLBACK
    else:
        if not tasks:
            return 0
        context = listed(tasks)
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}, sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001  hook 自身の不具合でセッションを止めない。入力と CLI の出力は書かない
        sys.stderr.buffer.write(f"inject_reread_notes: 内部エラー {type(e).__name__}\n".encode("utf-8"))
        sys.stderr.buffer.flush()
        code = 1
    sys.exit(code)
