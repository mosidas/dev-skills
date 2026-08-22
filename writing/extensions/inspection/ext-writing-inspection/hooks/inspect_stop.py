#!/usr/bin/env python3
"""セッション完了前に日本語 Markdown を再検査し、重大カテゴリが残るあいだ完了をブロックする Stop hook。

このセッションで検査対象になったファイル(`inspect_write.py` が状態ファイルへ記録)を
lint.py で再検査し、重大カテゴリの宣言(`inspection.config.json` の `blocking`)に該当する
検出が残っていれば `{"decision": "block", "reason": ...}` で完了を差し戻す。エージェントは
理由に従って書き直してから再び完了を試み、そのたびに本 hook が再検査する。

無限ブロックの回避:
  ブロックの回数を状態ファイルへ記録し、`stop_max_blocks`(既定 3)を超えたら検出が
  残っていても完了を許可する(書き直しても解消しない検出で完了を封鎖しない)。
  重大カテゴリが解消された時点で状態ファイルを削除し、以後の Stop は素通しになる。

入出力の契約:
  標準入力  Stop の JSON(`session_id`・`stop_hook_active` を読む)
  exit 0    ブロックなし(何も出力しない)
  exit 0 + JSON 出力  ブロック。`{"decision": "block", "reason": <理由>}` を返す

uv・lint.py が欠けている場合や lint が失敗した場合、そのファイルの検査を諦めて許可側に
倒す(hook 自身の不具合や環境差で完了を止めない)。
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

    project = lib.project_dir(payload)
    session_id = payload.get("session_id")
    state_file = lib.state_path(project, session_id if isinstance(session_id, str) else "")
    state = lib.load_state(state_file)
    if not state["files"]:
        return

    config = lib.load_config(HOOK_DIR, project)
    remaining: dict[str, list[dict]] = {}
    for file in state["files"]:
        path = Path(file)
        inspect, doctype = lib.should_inspect(path, config, project)
        if not inspect:
            continue
        findings = lib.run_lint(path, doctype.get("genre"), config, project)
        if findings is None:
            continue
        findings = lib.blocking_findings(lib.filter_findings(findings, doctype), config)
        if findings:
            remaining[file] = findings

    if not remaining:
        try:
            state_file.unlink()
        except OSError:
            pass
        return

    max_blocks = int(config.get("stop_max_blocks", 3))
    if state["stop_blocks"] >= max_blocks:
        print(
            f"ext-writing-inspection: 重大カテゴリの検出が残るがブロック上限({max_blocks} 回)に"
            "達したため完了を許可する",
            file=sys.stderr,
        )
        return
    state["stop_blocks"] += 1
    lib.save_state(state_file, state)
    reason = lib.format_stop_reason(remaining, lib.load_guides(HOOK_DIR))
    lib.emit({"decision": "block", "reason": reason})


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001  hook 自身の不具合で完了を止めない
        pass
    sys.exit(0)
