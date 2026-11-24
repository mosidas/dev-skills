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
  標準入力  Stop の UTF-8 の JSON(`session_id` を読む)。環境の符号化(PYTHONIOENCODING など)に
            依らず UTF-8 のバイト列として読む
  exit 0    ブロックなし(何も出力しない)。ブロックの上限で許可したときは標準エラーに UTF-8 で 1 行書く
  exit 0 + JSON 出力  ブロック。`{"decision": "block", "reason": <理由>}` を ASCII の JSON
            (非 ASCII の文字は \\uXXXX)で返す。環境の符号化に依らず書ける
  標準エラー  状態を保存できないとき、error.type 付きの 1 行を UTF-8 で書く

uv・lint.py が欠けている場合や lint が失敗した場合、そのファイルの検査を諦めて許可側に
倒す(hook 自身の不具合や環境差で完了を止めない)。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inspect_lib as lib  # noqa: E402

HOOK_DIR = Path(__file__).resolve().parent


def main() -> None:
    payload = lib.read_payload(sys.stdin.buffer)
    if payload is None:
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
        result = lib.run_lint(path, doctype.get("genre"), config)
        if result is None:
            continue
        findings = lib.blocking_findings(lib.filter_findings(result.findings, doctype), config)
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
        lib.warn(
            f"write-doc 検査: 重大カテゴリの検出が残るがブロック上限({max_blocks} 回)に"
            "達したため完了を許可する"
        )
        return
    state["stop_blocks"] += 1
    lib.save_state(state_file, state)
    reason = lib.format_stop_reason(
        remaining, lib.load_guides(HOOK_DIR), lib.load_phrase_okays()
    )
    lib.emit({"decision": "block", "reason": reason})


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001  hook 自身の不具合で完了を止めない
        pass
    sys.exit(0)
