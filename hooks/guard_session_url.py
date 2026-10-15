#!/usr/bin/env python3
"""コミットメッセージと PR 本文へのセッション URL の混入を実行前に止める PreToolUse hook(Bash)。

`git commit`・`gh pr create`・`gh pr edit` を含む Bash のコマンドについて、コマンド文字列
(heredoc・`-m`・`--body` を含む)と、`-F`・`--file`・`--body-file` で渡した本文ファイルに
`claude.ai/code/session_` の URL か `Claude-Session:` の行があれば、実行させずに止める。
`Co-Authored-By` と `Generated with` の行は止めない。

入出力の契約:
  標準入力  PreToolUse の JSON(`tool_name`・`tool_input.command`・`cwd` を読む)
  exit 0    対象外のコマンド、または検出なし(何も出力しない)
  exit 2    検出あり、本文ファイルが読めない、または検査が失敗した。標準エラーに 1 行を書き、
            その行がエージェントへ返る(ツールは実行されない)

対象のコマンドと判定したあとは、検査できないときも止める(fail-closed)。検査の失敗を素通しすると、
混入を防ぐ hook が黙って無効になるためである。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# shortcut: --amend --no-edit と -C <commit> で再利用するメッセージは検査しない, 再利用での混入が起きたら元のコミットのメッセージを読む
COMMIT_RE = re.compile(r"\bgit(?:\s+-[Cc]\s+(?:\"[^\"]*\"|'[^']*'|\S+)|\s+--[\w-]+(?:=\S+)?)*\s+commit\b")
PR_RE = re.compile(r"\bgh\s+pr\s+(?:create|edit)\b")
FORBIDDEN_RE = re.compile(r"claude\.ai/code/session_|claude-session\s*:", re.I)
# 引用符の区間を先に読み飛ばし、`-m '... -F ...'` のような文字列の中をオプションと見なさない。
# shortcut: 短いオプションの結合形(-aF・-Fpath)は読まない, 取りこぼしが起きたら引数を shlex で分解する
FILE_RE = re.compile(
    r"\"[^\"]*\"|'[^']*'|(?:^|\s)(?:-F|--file|--body-file)(?:=|\s+)(\"[^\"\n]*\"|'[^'\n]*'|[^\s;&|)]+)"
)

DETECTED = (
    "コミットメッセージ・PR 本文から Claude-Session の行と claude.ai/code/session_ の URL を消して"
    "実行し直す(検出箇所: {where})。"
)
UNREADABLE = "本文ファイル {path} を読めないため止めた。ファイルを先に作り、絶対パスで渡して実行し直す。"
FAILED = "セッション URL の検査が失敗したため止めた({name})。"


def body_files(command: str, cwd: str) -> list[Path]:
    """`-F`・`--file`・`--body-file` で渡した本文ファイルのパスを返す(`-` は標準入力なので除く)。"""
    # 対象のコマンドより前の `-F`(`grep -F 'git commit'` など)は別のコマンドのオプションなので読まない。
    start = min(m.start() for m in (COMMIT_RE.search(command), PR_RE.search(command)) if m)
    paths = []
    for match in FILE_RE.finditer(command):
        raw = match.group(1)
        if not raw or match.start() < start:
            continue
        if raw[0] in "\"'":
            raw = raw[1:-1]
        if raw == "-":
            continue
        path = Path(os.path.expanduser(os.path.expandvars(raw)))
        paths.append(path if path.is_absolute() else Path(cwd) / path)
    return paths


def find_violation(command: str, cwd: str) -> str | None:
    """止める理由を返す。混入が無ければ None。"""
    if FORBIDDEN_RE.search(command):
        return DETECTED.format(where="コマンド")
    for path in body_files(command, cwd):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return UNREADABLE.format(path=path)
        if FORBIDDEN_RE.search(text):
            return DETECTED.format(where=path)
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    if not (COMMIT_RE.search(command) or PR_RE.search(command)):
        return 0
    cwd = payload.get("cwd")
    try:
        reason = find_violation(command, cwd if isinstance(cwd, str) else os.getcwd())
    except Exception as exc:  # noqa: BLE001  対象のコマンドは検査できなければ止める(fail-closed)
        reason = FAILED.format(name=type(exc).__name__)
    if reason is None:
        return 0
    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # noqa: BLE001  対象と判定する前の不具合で Bash を止めない
        code = 0
    sys.exit(code)
