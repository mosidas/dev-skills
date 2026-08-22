#!/usr/bin/env python3
"""日本語 Markdown の書き込み直後に検査を発火させる PostToolUse hook(Write / Edit / MultiEdit / NotebookEdit)。

書き込まれたファイルが日本語の Markdown なら、japanese-writing の lint.py(導入先の
`.claude/skills/japanese-writing/scripts/lint.py`)を `--json` で実行し、検出があれば
警告(該当文を丸ごと書き直す指示・カテゴリ別の言い換え指針・機械検出に出ない不自然さの
自己判定の指示)をエージェントへ返す。書き込み自体は成立済みであり、処理は止めない。
書き直しの結果には再びこの hook がかかる。

検査したファイルはセッション状態に記録し、Stop hook(`inspect_stop.py`)の再検査対象にする。

入出力の契約:
  標準入力  PostToolUse の JSON(`tool_name`・`tool_input`・`cwd`・`session_id` を読む)
  exit 0    検出なし・検査対象外・検査不能(何も出力しない)
  exit 0 + JSON 出力  検出あり。`{"decision": "block", "reason": <警告文>}` が
            エージェントへ自動フィードバックされる(ツールの実行は取り消されない)

uv・lint.py・設定が欠けている場合や lint が失敗した場合は検査を諦めて何もしない
(hook 自身の不具合や環境差で書き込みを止めない)。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inspect_lib as lib  # noqa: E402

HOOK_DIR = Path(__file__).resolve().parent


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict):
        return
    if payload.get("tool_name") not in lib.WRITE_TOOLS:
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    path = lib.target_path(tool_input, cwd)
    if path is None:
        return

    project = lib.project_dir(payload)
    config = lib.load_config(HOOK_DIR, project)
    inspect, doctype = lib.should_inspect(path, config, project)
    if not inspect:
        return

    findings = lib.run_lint(path, doctype.get("genre"), config, project)
    if findings is None:
        return
    findings = lib.filter_findings(findings, doctype)

    session_id = payload.get("session_id")
    lib.record_inspected(path, project, session_id if isinstance(session_id, str) else "")

    if not findings:
        return
    guides = lib.load_guides(HOOK_DIR)
    blocking = lib.blocking_findings(findings, config)
    reason = lib.format_warning(path, findings, config, guides, blocking)
    lib.emit({"decision": "block", "reason": reason})


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001  hook 自身の不具合で書き込みを止めない
        pass
    sys.exit(0)
