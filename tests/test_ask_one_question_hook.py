"""PreToolUse hook(`guard_ask_one_question.py`)の単体テスト。

hook は `sys.exit` を呼び、状態を一時ディレクトリに書くため、すべて `TMPDIR` を一時ディレクトリに
向けたサブプロセスで確かめる。止める入力と通す入力を対で書く。
元の指摘で 3 論点を 1 回で聞いた問いの文面は retro の記録に無いため、実例は本人の判断 3 論点の形で作った。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

import helpers

GUARD = helpers.REPO_ROOT / "hooks" / "guard_ask_one_question.py"
STATE_DIR_NAME = "dev-skills-ask-one-question"
REASON = "本人の判断は 1 問ずつ聞き、判断が必要な理由を問いの前に書く"


def question(text: str, header: str, first: str, second: str) -> dict:
    return {
        "question": text,
        "header": header,
        "options": [
            {"label": first, "description": f"{first}にする"},
            {"label": second, "description": f"{second}にする"},
        ],
        "multiSelect": False,
    }


SAVE = question("保存先をどこにするか", "保存先", "ローカル", "クラウド")
ORDER = question("一覧の並び順をどうするか", "並び順", "新しい順", "名前順")
SCOPE = question("公開の範囲をどうするか", "公開範囲", "チーム内", "全体")
NOTIFY = question("通知をいつ送るか", "通知", "すぐ", "まとめて")


class GuardAskOneQuestionTest(helpers.TempDirTestCase):
    def run_hook(
        self,
        questions: object,
        session_id: object = "s1",
        agent_id: str | None = None,
        tool_name: str = "AskUserQuestion",
    ) -> subprocess.CompletedProcess:
        payload = {
            "session_id": session_id,
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": {"questions": questions},
        }
        if agent_id is not None:
            payload["agent_id"] = agent_id
        return self.run_raw(json.dumps(payload, ensure_ascii=False))

    def run_raw(self, stdin: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GUARD)],
            input=stdin,
            capture_output=True,
            text=True,
            env={**os.environ, "TMPDIR": str(self.tmp)},
        )

    def assertDenied(self, proc: subprocess.CompletedProcess) -> None:
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        output = json.loads(proc.stdout)
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "PreToolUse")
        self.assertEqual(specific["permissionDecision"], "deny")
        reason = specific["permissionDecisionReason"]
        self.assertIn(REASON, reason)
        self.assertNotIn("\n", reason)

    def assertPassed(self, proc: subprocess.CompletedProcess) -> None:
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    # 止める

    def test_本人の判断3論点を1回で聞く呼び出しを止める(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER, SCOPE]))

    def test_2問を止める(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER]))

    def test_4問を止める(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER, SCOPE, NOTIFY]))

    def test_止めた直後の同じ内容は1回だけ通しもう一度は止める(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER, SCOPE]))
        self.assertPassed(self.run_hook([SAVE, ORDER, SCOPE]))
        self.assertDenied(self.run_hook([SAVE, ORDER, SCOPE]))

    def test_止めた後に別の2問を挟むと最初の内容も止める(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER]))
        self.assertDenied(self.run_hook([SCOPE, NOTIFY]))
        self.assertDenied(self.run_hook([SAVE, ORDER]))

    def test_止めた後に1問を挟むと最初の内容を止める(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER]))
        self.assertPassed(self.run_hook([SCOPE]))
        self.assertDenied(self.run_hook([SAVE, ORDER]))

    def test_別のsessionで止めた内容は止める(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER], session_id="s1"))
        self.assertDenied(self.run_hook([SAVE, ORDER], session_id="s2"))

    def test_agent_idが違えば止めた内容も止める(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER]))
        self.assertDenied(self.run_hook([SAVE, ORDER], agent_id="agent-1"))

    def test_状態を書けなくても1回目も2回目も止める(self) -> None:
        self.write(STATE_DIR_NAME, "ディレクトリの代わりのファイル")
        self.assertDenied(self.run_hook([SAVE, ORDER]))
        self.assertDenied(self.run_hook([SAVE, ORDER]))

    def test_session_idとagent_idが文字列でなくても止める(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER], session_id=123, agent_id=["x"]))
        self.assertPassed(self.run_hook([SAVE, ORDER], session_id=123, agent_id=["x"]))

    def test_対になっていないサロゲートを含む問いも止める(self) -> None:
        payload = (
            '{"session_id": "s1", "tool_name": "AskUserQuestion", "tool_input": {"questions": '
            '[{"question": "\\ud800"}, {"question": "b"}]}}'
        )
        self.assertDenied(self.run_raw(payload))
        self.assertPassed(self.run_raw(payload))

    # 通す

    def test_1問を通す(self) -> None:
        self.assertPassed(self.run_hook([SAVE]))

    def test_止めた直後にキーの順だけ違う同じ内容を通す(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER]))
        reordered = [dict(reversed(list(q.items()))) for q in (SAVE, ORDER)]
        self.assertPassed(self.run_hook(reordered))

    def test_AskUserQuestion以外のツールは通す(self) -> None:
        self.assertPassed(self.run_hook([SAVE, ORDER], tool_name="Bash"))

    def test_構文が不正なJSONは通す(self) -> None:
        self.assertPassed(self.run_raw("{not json"))

    def test_questionsが無ければ通す(self) -> None:
        payload = {"session_id": "s1", "tool_name": "AskUserQuestion", "tool_input": {}}
        self.assertPassed(self.run_raw(json.dumps(payload)))

    def test_questionsがlistでなければ通す(self) -> None:
        self.assertPassed(self.run_hook("abc"))

    def test_session_idのパスの記号では状態のディレクトリの外に書かない(self) -> None:
        self.assertDenied(self.run_hook([SAVE, ORDER], session_id="../../escape"))
        state_dir = self.tmp / STATE_DIR_NAME
        self.assertEqual(len(list(state_dir.iterdir())), 1, "状態のファイルは状態のディレクトリに 1 つだけある")
        outside = [p for p in self.tmp.rglob("*") if p != state_dir and state_dir not in p.parents]
        self.assertEqual(outside, [], "状態のディレクトリの外にファイルを作らない")
        self.assertPassed(self.run_hook([SAVE, ORDER], session_id="../../escape"))


if __name__ == "__main__":
    unittest.main()
