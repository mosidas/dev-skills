#!/usr/bin/env python3
"""planner を起動していないセッションで、2 ステップ以上の計画の implementer の起動を止める hook。

入口:
  SubagentStart(`agent_type` が `dev-skills:planner`)  記録。そのセッションに planner を起動した印を残す
  PreToolUse(Agent、`tool_input.subagent_type` が `dev-skills:implementer`)  判定。`tool_input.prompt` を読む

入出力の契約:
  標準入力  UTF-8 の hook の JSON。環境の符号化に依らず UTF-8 のバイト列として読む
  exit 0    常に
  標準出力  判定で止めるときだけ `permissionDecision: deny` の ASCII の JSON を 1 つ書く。記録と、通すときは書かない
  標準エラー 記録の置き場を使えないときだけ `error.type=store_unavailable` の 1 行を UTF-8 で書く

判定は次の順に最初に当たったもので決める。
  1. そのセッションに planner の印がある → 通す(planner_ran)
  2. プロンプトから計画のステップ数を読めない → 通す(step_unreadable)
  3. ステップ数が 1 → 通す(single_step)
  4. プロンプトの行頭に `planner の計画: <所在>` と書いた行がある → 通す(inherited_plan)
  5. それ以外(ステップ数が 2 以上) → 止める(multi_step_without_planner)
ステップ数はプロンプトの `ステップ <n>/<m>` の組のうち 1 ≦ n ≦ m を満たすものから読み、m が 1 の組があれば 1、
無ければ m の最大値である。1 ステップの変更のプロンプトは別の組を引用しうるため、m が 1 の組を先に見る。
行を書き忘れた 1 ステップの変更を止めないため、読めないときは止めない。
`planner の計画:` は行頭の箇条の印(`-`・`*`・`+` と空白)の後に書いてもよい。

記録: 印は `${CLAUDE_PLUGIN_DATA}/planner-gate/<session_id の SHA-256>` の空のファイルで、有無だけが意味を持つ。
置き場はリンクでない自分所有のディレクトリに限り、印はリンクをたどらずに作り、`os.lstat` で通常のファイルのときだけ
印として数える。記録と判定の結果は同じディレクトリの `events.jsonl` に 1 イベント 1 行で追記し、プロンプトの本文と
計画の所在を書かない。置き場を使えない・入力を読めない・`session_id` が空でない文字列でない・hook 自身が失敗した
ときは通す(`session_id` が無いときは判定せずに `session_missing` を残す)。止めると planner を
起動し直しても記録できず、同じ拒否を繰り返すためである。

範囲の外: 偽の宣言(`ステップ 1/1`・`planner の計画:` の行)、起動した後に失敗した planner、ステップ数を書かない
複数ステップの計画、同じセッションの別のタスクで起動した planner。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Literal

PLANNER = "dev-skills:planner"
IMPLEMENTER = "dev-skills:implementer"
STEP = re.compile(r"ステップ\s*(\d+)\s*/\s*(\d+)")
INHERITED = re.compile(r"^[ \t]*(?:[-*+][ \t]+)?planner の計画[::][ \t]*\S", re.M)
REASON = (
    "このセッションで planner を起動しないまま、{steps} ステップの計画の implementer を起動しようとした。"
    "planner を省けるのは 1 ステップで済む変更だけである(develop 5.)。"
    "1 ステップで済む変更なら、プロンプトに `ステップ 1/1` と書いた行を足して起動し直す"
    "(`ステップ 1/1` は、プロンプトが引用した別のタスクの `ステップ n/m` より先に読む)。"
    "planner(`dev-skills:planner`)を起動して計画を立ててから implementer を起動し直す。"
    "planner が立てた計画(別のセッションで立てて Implementation Notes に記録した計画など)で進めているなら、"
    "プロンプトの行頭に `planner の計画: <計画の所在>` と書いた行を足して起動し直す(develop 6.)。"
)
STORE_UNAVAILABLE = "planner-gate: 記録の置き場を使えないため照合しない(error.type=store_unavailable)"

Verdict = Literal["planner_ran", "step_unreadable", "single_step", "inherited_plan", "multi_step_without_planner"]


def read_payload(stdin: BinaryIO) -> dict | None:
    """UTF-8 のバイト列の JSON を dict で返す。読めないか dict でなければ None。"""
    try:
        payload = json.loads(stdin.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def open_store(data: str | None) -> Path | None:
    """置き場を 0o700 で作り、リンクでない自分所有のディレクトリのときだけ返す。"""
    if not data:
        return None
    store = Path(data) / "planner-gate"
    try:
        store.mkdir(mode=0o700, parents=True, exist_ok=True)
        st = os.lstat(store)
    except OSError:
        return None
    return store if stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() else None


def record_path(store: Path, session_id: str) -> Path:
    # 入力の JSON は対になっていないサロゲート(`"\ud800"`)を含みうる
    return store / hashlib.sha256(session_id.encode("utf-8", "surrogatepass")).hexdigest()


def record_planner(store: Path, session_id: str) -> None:
    """印を作る。リンク・名前付きパイプ・書けないときは OSError を送出する。"""
    fd = os.open(
        record_path(store, session_id), os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
    )
    os.close(fd)


def planner_ran(store: Path, session_id: str) -> bool:
    try:
        st = os.lstat(record_path(store, session_id))
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode)


def plan_steps(prompt: str) -> int | None:
    totals = {int(m) for n, m in STEP.findall(prompt) if 1 <= int(n) <= int(m)}
    return 1 if 1 in totals else max(totals, default=None)


def judge(prompt: str, ran: bool) -> tuple[Verdict, int | None]:
    steps = plan_steps(prompt)
    if ran:
        return "planner_ran", steps
    if steps is None:
        return "step_unreadable", None
    if steps == 1:
        return "single_step", steps
    if INHERITED.search(prompt):
        return "inherited_plan", steps
    return "multi_step_without_planner", steps


def log_event(
    store: Path, level: str, event: str, reason: str | None, session: str | None, **extra: str | int | None
) -> None:
    """1 行を追記する。`extra`(steps・error_type)は値があるときだけ載せる。"""
    entry: dict[str, str | int | None] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "level": level,
        "event": event,
        "reason": reason,
        "session": session,
    }
    entry.update((key, value) for key, value in extra.items() if value is not None)
    line = (json.dumps(entry, ensure_ascii=True) + "\n").encode("ascii")
    try:
        fd = os.open(store / "events.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(line)
    except OSError:
        pass


def warn(message: str) -> None:
    sys.stderr.buffer.write((message + "\n").encode("utf-8", "backslashreplace"))
    sys.stderr.flush()


def emit_deny(reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    sys.stdout.write(json.dumps(output, ensure_ascii=True))


def record(store: Path, session: str | None) -> None:
    if session is None:
        log_event(store, "warn", "planner_not_recorded", "session_missing", None)
        return
    try:
        record_planner(store, session)
    except OSError:
        log_event(store, "warn", "planner_not_recorded", "store_write_failed", session)
        return
    log_event(store, "info", "planner_recorded", None, session)


def check(store: Path, session: str | None, prompt: str) -> None:
    if session is None:
        log_event(store, "warn", "implementer_checked", "session_missing", None)
        return
    verdict, steps = judge(prompt, planner_ran(store, session))
    if verdict == "multi_step_without_planner":
        log_event(store, "warn", "implementer_checked", verdict, session, steps=steps)
        emit_deny(REASON.format(steps=steps))
    else:
        log_event(store, "info", "implementer_checked", verdict, session, steps=steps)


# shortcut: 印とログを掃除しない, 印は 0 バイト・ログは 1 行 200 バイトほどで増え続ける。容量が問題になったら古い印とログを消す
def main(stdin: BinaryIO) -> None:
    payload = read_payload(stdin)
    if payload is None:
        return
    session = payload.get("session_id")
    session = session if isinstance(session, str) and session else None
    event = payload.get("hook_event_name")
    if event == "SubagentStart" and payload.get("agent_type") == PLANNER:
        name, prompt = "planner_not_recorded", None
    elif event == "PreToolUse" and payload.get("tool_name") == "Agent":
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict) or tool_input.get("subagent_type") != IMPLEMENTER:
            return
        prompt = tool_input.get("prompt")
        if not isinstance(prompt, str):
            return
        name = "implementer_checked"
    else:
        return
    store = open_store(os.environ.get("CLAUDE_PLUGIN_DATA"))
    if store is None:
        warn(STORE_UNAVAILABLE)
        return
    try:
        if prompt is None:
            record(store, session)
        else:
            check(store, session, prompt)
    except Exception as e:  # noqa: BLE001  hook 自身の不具合でサブエージェントの起動を妨げない
        log_event(store, "error", name, "internal_error", session, error_type=type(e).__name__)


if __name__ == "__main__":
    try:
        main(sys.stdin.buffer)
    except Exception:  # noqa: BLE001  置き場を開く前の不具合でサブエージェントの起動を妨げない
        pass
    sys.exit(0)
