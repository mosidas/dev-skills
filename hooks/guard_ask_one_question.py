#!/usr/bin/env python3
"""本人への質問を 2 問以上まとめた AskUserQuestion をフォームを出す前に止める PreToolUse hook。

入出力の契約:
  標準入力  UTF-8 の PreToolUse の JSON(`session_id`・`agent_id`・`tool_name`・`tool_input.questions` を読む)。
            環境の符号化(PYTHONIOENCODING・ロケール)に依らず UTF-8 のバイト列として読む
  exit 0    常に
  標準出力  止めるときだけ `permissionDecision: deny` の JSON を 1 つ書く。通すときは何も書かない
  標準エラー 書かない

`tool_input.questions` が 2 問以上なら止める。ただし、止めた直後に同じ内容(キーの順は問わない)で
呼び直した 1 回だけは通す。ほかのプラグインの手順が複数の問いを 1 回で聞くと定めているときの逃げ道である。
間に別の内容の呼び出しを挟むと、逃げ道は消える。直前に止めた内容は session と agent ごとに一時ディレクトリの
中の、自分が所有する実際のディレクトリへ記録し、シンボリックリンクをたどらずに読み書きする。呼び直しを通すのは
記録を消せたときだけで、並行した呼び直しは 1 つだけが通る。記録を読めないときは記録なしとみなす。一時ディレクトリを
取得できない、状態のディレクトリがリンクか他人の所有である、記録を書けない・消せないときも止める(逃げ道が
使えなくなるだけで、2 問以上を通すより害が小さい)。

UTF-8 の JSON として読めない入力、AskUserQuestion 以外のツール、`questions` が list でない入力は何も書かずに通す
(fail-open)。この hook は質問の形を直させるもので漏えいを防ぐものではなく、自分の解析の失敗で止めると
すべてのプラグインの質問が止まるためである。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO

REASON = (
    "本人の判断は 1 問ずつ聞き、判断が必要な理由を問いの前に書く。"
    "ほかのプラグインの手順が複数の問いを 1 回で聞くと定めているときだけ、同じ内容でもう一度呼ぶと通る。"
)
DENY = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": REASON,
    }
}


def read_questions(stdin: BinaryIO) -> tuple[list, object, object] | None:
    """UTF-8 のバイト列の JSON から (questions, session_id, agent_id) を返す。対象外か読めなければ None。"""
    try:
        payload = json.loads(stdin.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("tool_name") != "AskUserQuestion":
        return None
    tool_input = payload.get("tool_input")
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    if not isinstance(questions, list):
        return None
    return questions, payload.get("session_id"), payload.get("agent_id")


def safe(value: object) -> str:
    """ID をファイル名に使える文字だけにする(パスの記号で状態のディレクトリの外に出さない)。"""
    text = value if isinstance(value, str) and value else "unknown"
    return re.sub(r"[^A-Za-z0-9_-]", "_", text)


# shortcut: 一時ディレクトリの状態ファイルは消し残りを掃除しない, 1 件 64 字で OS の一時領域の掃除に任せる。増えて困ったら session の終了で消す
def state_path(session_id: object, agent_id: object) -> Path:
    return Path(tempfile.gettempdir()) / "dev-skills-ask-one-question" / f"{safe(session_id)}-{safe(agent_id)}.txt"


def fingerprint(questions: list) -> str:
    text = json.dumps(questions, sort_keys=True, ensure_ascii=False)
    # 入力の JSON は対になっていないサロゲート(`"\ud800"`)を含みうる。encode で例外にして素通しさせない。
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def owned_dir(path: Path) -> bool:
    """path がリンクでない実際のディレクトリで、この利用者が所有するときだけ True。"""
    st = os.lstat(path)
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid()


def recall(path: Path) -> str | None:
    try:
        if not owned_dir(path.parent):
            return None
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), encoding="ascii") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def remember(path: Path, digest: str) -> None:
    """記録を書く。書けなければ例外を送出する。"""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not owned_dir(path.parent):
        raise PermissionError(f"not an own directory: {path.parent}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(digest)


def forget(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def main() -> int:
    read = read_questions(sys.stdin.buffer)
    if read is None:
        return 0
    questions, session_id, agent_id = read
    if len(questions) < 2:
        forget(state_path(session_id, agent_id))
        return 0
    digest = fingerprint(questions)
    try:
        path = state_path(session_id, agent_id)
        if recall(path) == digest:
            # 消せたときだけ通す。並行した呼び直しは 1 つだけが消せ、残りは FileNotFoundError で止まる
            path.unlink()
            return 0
        remember(path, digest)
    except Exception:  # noqa: BLE001  記録を使えないときは逃げ道なしで止める(gettempdir の失敗・O_NOFOLLOW の無い OS を含む)
        pass
    json.dump(DENY, sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # noqa: BLE001  hook 自身の不具合ですべてのプラグインの質問を止めない(fail-open)
        code = 0
    sys.exit(code)
