"""planner を起動していないセッションの複数ステップの implementer の起動を止める hook(`planner_gate.py`)の単体テスト。

hook は `CLAUDE_PLUGIN_DATA` の下に印とログを書くため、すべて `CLAUDE_PLUGIN_DATA` を一時ディレクトリに向けた
サブプロセスで確かめる。入力は実機で観測した形にする。SubagentStart は `agent_type`(plugin 名つき)と
`session_id` を、PreToolUse(Agent)は `tool_input` の `subagent_type`・`prompt`・`description` を持つ。
止める入力と通す入力を対で書く。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import helpers

HOOK = helpers.REPO_ROOT / "hooks" / "planner_gate.py"
DEVELOP = helpers.REPO_ROOT / "skills" / "develop" / "SKILL.md"
SESSION = "11111111-2222-3333-4444-555555555555"
OTHER_SESSION = "99999999-8888-7777-6666-555555555555"
# 元の指摘の実例の要旨(作った形)。planner を起動しないまま 2 ステップの計画の 1 ステップ目を渡した
INCIDENT_FIRST = (
    "対象リポジトリ: /work/plugin\n"
    "要件の品質: プロダクト\n\n"
    "ステップ 1/2: 規範ファイルに規則を 3 件足す。\n"
)
INCIDENT_SECOND = "対象リポジトリ: /work/plugin\n\nステップ 2/2: README と version を更新する。\n"
# 見出しの括弧の中にステップ数を書いた形
HEADING_FORM = "対象リポジトリ: /work/plugin\n\n## このステップの計画(ステップ 1/3)\n- README の出典を表にする。\n"
SINGLE_STEP = "要件の品質: プロダクト\n\nステップ 1/1: 設定値を 30 から 60 に変える。\n"
NO_STEPS = "要件の品質: 簡易\n\n誤字を 1 か所直す。\n"
INHERITED = "ステップ 3/4: 検索の結果を並べ替える。\nplanner の計画: TASK-12 の Implementation Notes\n"
EMPTY_INHERITED = "ステップ 3/4: 検索の結果を並べ替える。\nplanner の計画:\n"
# 1 ステップの変更のプロンプトが別の `ステップ n/m` を引用した形
SINGLE_QUOTING_EXAMPLE = "ステップ 1/1: develop 6. の手順 2 の例の行 `ステップ 2/3` を `ステップ 2/4` に変える。\n"
SINGLE_QUOTING_HISTORY = "ステップ 1/1: 設定値を変える。\n背景: TASK-40 のステップ 2/3 で入れた値が大きすぎた。\n"
RAISES = (
    "import hashlib, runpy, sys\n"
    "def broken(*args, **kwargs):\n"
    "    raise RuntimeError('例外にだけある語')\n"
    "hashlib.sha256 = broken\n"
    "runpy.run_path(sys.argv[1], run_name='__main__')\n"
)
OTHER_OWNER = (
    "import os, runpy, sys\n"
    "uid = os.getuid() + 1\n"
    "os.getuid = lambda: uid\n"
    "runpy.run_path(sys.argv[1], run_name='__main__')\n"
)


def launch(prompt: object, subagent_type: str = "dev-skills:implementer", session: object = SESSION) -> dict:
    return {
        "session_id": session,
        "hook_event_name": "PreToolUse",
        "tool_name": "Agent",
        "tool_input": {"description": "step", "prompt": prompt, "subagent_type": subagent_type},
    }


def started(agent_type: str = "dev-skills:planner", session: object = SESSION) -> dict:
    return {
        "session_id": session,
        "hook_event_name": "SubagentStart",
        "agent_id": "a0123456789abcdef",
        "agent_type": agent_type,
    }


class PlannerGateCase(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data = self.tmp / "data"
        self.store = self.data / "planner-gate"

    def invoke(
        self,
        payload: object,
        data: Path | None | str = "default",
        launcher: tuple[str, ...] = (),
        extra_env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess:
        """hook を実行して結果を返す。exit 0 であることを確かめる。"""
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"}
        env.update(extra_env or {})
        if data == "default":
            env["CLAUDE_PLUGIN_DATA"] = str(self.data)
        elif data is not None:
            env["CLAUDE_PLUGIN_DATA"] = str(data)
        stdin = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        proc = subprocess.run(
            [sys.executable, *launcher, str(HOOK)], input=stdin, capture_output=True, env=env, cwd=cwd or self.tmp
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        return proc

    def deny_reason(self, payload: object, **kwargs) -> str:
        proc = self.invoke(payload, **kwargs)
        self.assertNotEqual(proc.stdout, b"", "止める")
        output = json.loads(proc.stdout.decode("ascii"))["hookSpecificOutput"]
        self.assertEqual((output["hookEventName"], output["permissionDecision"]), ("PreToolUse", "deny"))
        return output["permissionDecisionReason"]

    def assertPasses(self, payload: object, **kwargs) -> subprocess.CompletedProcess:
        proc = self.invoke(payload, **kwargs)
        self.assertEqual(proc.stdout, b"", "何も出力せずに通す")
        return proc

    def mark(self, session: str = SESSION) -> Path:
        return self.store / hashlib.sha256(session.encode()).hexdigest()

    def events(self) -> list[dict]:
        log = self.store / "events.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="ascii").splitlines()]

    def last(self) -> tuple:
        event = self.events()[-1]
        return event["level"], event["event"], event["reason"]


class JudgeTest(PlannerGateCase):
    def test_planner_の印の無いセッションの元の指摘の実例は_1_回目から止める(self) -> None:
        reason = self.deny_reason(launch(INCIDENT_FIRST))
        for needle in ("dev-skills:planner", "develop 5.", "planner の計画:", "行頭", "2 ステップ", "ステップ 1/1"):
            self.assertIn(needle, reason)
        self.assertEqual(self.last(), ("warn", "implementer_checked", "multi_step_without_planner"))
        self.assertEqual(self.events()[-1]["steps"], 2)
        self.deny_reason(launch(INCIDENT_SECOND))

    def test_見出しの括弧の中のステップ数も読んで止める(self) -> None:
        self.assertIn("3 ステップ", self.deny_reason(launch(HEADING_FORM)))

    def test_同じセッションで_planner_を起動した後は通り別のセッションでは止める(self) -> None:
        self.assertPasses(started())
        self.assertEqual(self.last(), ("info", "planner_recorded", None))
        self.assertPasses(launch(INCIDENT_FIRST))
        self.assertEqual(self.last(), ("info", "implementer_checked", "planner_ran"))
        self.deny_reason(launch(INCIDENT_FIRST, session=OTHER_SESSION))

    def test_1_ステップの計画は印が無くても_1_回目で通る(self) -> None:
        self.assertPasses(launch(SINGLE_STEP))
        self.assertEqual(self.last(), ("info", "implementer_checked", "single_step"))

    def test_1_ステップの計画は別の組を引用しても通る(self) -> None:
        for prompt in (SINGLE_QUOTING_EXAMPLE, SINGLE_QUOTING_HISTORY):
            with self.subTest(prompt=prompt):
                self.assertPasses(launch(prompt))
                self.assertEqual(self.last(), ("info", "implementer_checked", "single_step"))

    def test_ステップ数の無いプロンプトは通して読めなかったことを残す(self) -> None:
        self.assertPasses(launch(NO_STEPS))
        self.assertEqual(self.last(), ("info", "implementer_checked", "step_unreadable"))

    def test_planner_の計画の行があれば通り値が空なら止める(self) -> None:
        self.assertPasses(launch(INHERITED))
        self.assertEqual(self.last(), ("info", "implementer_checked", "inherited_plan"))
        self.assertPasses(launch(INHERITED.replace("計画: ", "計画:")))
        self.assertPasses(launch(INHERITED.replace("計画: ", "計画: ")))
        for mark in ("-", "*", "+"):
            self.assertPasses(launch(INHERITED.replace("planner の計画", f"{mark} planner の計画")))
            self.assertEqual(self.last(), ("info", "implementer_checked", "inherited_plan"))
        self.deny_reason(launch("ステップ 2/3: 続き。`planner の計画:` の行は書かない。\n"))
        self.deny_reason(launch(EMPTY_INHERITED))
        self.deny_reason(launch(EMPTY_INHERITED + "TASK-12 の Implementation Notes\n"))

    def test_ステップ数は総数が_1_の組があれば_1_で無ければ総数の最大値で読み範囲外の組は読まない(self) -> None:
        self.assertPasses(launch("ステップ 1/1 は済んだ。\nステップ 2/3: 続き\n"))
        self.assertEqual(self.last(), ("info", "implementer_checked", "single_step"))
        self.assertIn("3 ステップ", self.deny_reason(launch("ステップ 1/2 は済んだ。\nステップ 2/3: 続き\n")))
        self.assertPasses(launch("ステップ 3/2 と ステップ 0/2 の表記\n"))
        self.assertEqual(self.last(), ("info", "implementer_checked", "step_unreadable"))
        self.deny_reason(launch("ステップ2 / 2: 空白の揺れ\n"))

    def test_implementer_でない起動は通しログも残さない(self) -> None:
        for subagent_type in ("dev-skills:reviewer", "general-purpose", "implementer"):
            self.assertPasses(launch(INCIDENT_FIRST, subagent_type=subagent_type))
        self.assertFalse(self.store.exists(), "置き場も作らない")

    def test_planner_でない_SubagentStart_は印を作らない(self) -> None:
        self.assertPasses(started("dev-skills:implementer"))
        self.assertPasses(started("dev-skills:reviewer"))
        self.assertFalse(self.store.exists())
        self.deny_reason(launch(INCIDENT_FIRST))

    def test_planner_の_SubagentStart_を_2_回受けても印は_1_つで通る(self) -> None:
        self.assertPasses(started())
        self.assertPasses(started())
        self.assertEqual(sorted(p.name for p in self.store.iterdir()), [self.mark().name, "events.jsonl"])
        self.assertPasses(launch(INCIDENT_FIRST))

    def test_develop_6_の手順_2_の例の行は止めると通るに分かれる(self) -> None:
        text = DEVELOP.read_text(encoding="utf-8")
        section = text.split("\n## 6.", 1)[1].split("\n## 7.", 1)[0]
        step2 = next(line for line in section.splitlines() if line.startswith("2. "))
        quoted = re.findall(r"`([^`]+)`", step2)
        steps = [q for q in quoted if q.startswith("ステップ ")]
        inherited = [q for q in quoted if q.startswith("planner の計画")]
        self.assertTrue(steps and inherited, quoted)
        self.deny_reason(launch(steps[0]))
        self.assertPasses(launch(steps[0] + "\n" + inherited[0]))
        self.assertEqual(self.last(), ("info", "implementer_checked", "inherited_plan"))


class StoreTest(PlannerGateCase):
    def test_CLAUDE_PLUGIN_DATA_が無ければ通しファイルを作らず標準エラーに_1_行書く(self) -> None:
        for data in (None, ""):
            proc = self.assertPasses(launch(INCIDENT_FIRST), data=data)
            lines = proc.stderr.decode("utf-8").splitlines()
            self.assertEqual(len(lines), 1, lines)
            self.assertIn("error.type=store_unavailable", lines[0])
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), [], "cwd にも置き場を作らない")

    def test_置き場がリンクならリンク先に書かず通す(self) -> None:
        target = self.tmp / "elsewhere"
        target.mkdir(mode=0o700)
        self.data.mkdir()
        self.store.symlink_to(target)
        self.assertPasses(started())
        proc = self.assertPasses(launch(INCIDENT_FIRST))
        self.assertIn("error.type=store_unavailable", proc.stderr.decode("utf-8"))
        self.assertTrue(self.store.is_symlink(), "リンクを置き換えない")
        self.assertEqual(list(target.iterdir()), [], "リンク先に印もログも書かない")

    def test_置き場が他人の所有なら書かず通す(self) -> None:
        proc = self.assertPasses(launch(INCIDENT_FIRST), launcher=("-c", OTHER_OWNER))
        self.assertIn("error.type=store_unavailable", proc.stderr.decode("utf-8"))
        self.assertEqual(self.events(), [], "ログを書かない")
        self.assertPasses(started(), launcher=("-c", OTHER_OWNER))
        self.assertFalse(self.mark().exists(), "印を書かない")

    def test_印のパスがリンクなら書かず印として数えない(self) -> None:
        self.store.mkdir(parents=True, mode=0o700)
        target = self.tmp / "target"
        self.mark().symlink_to(target)
        self.assertPasses(started())
        self.assertFalse(target.exists(), "リンク先を作らない")
        self.assertEqual(self.last(), ("warn", "planner_not_recorded", "store_write_failed"))
        target.write_text("", encoding="ascii")
        self.deny_reason(launch(INCIDENT_FIRST))

    def test_印のパスが名前付きパイプでも止まらずに印として数えない(self) -> None:
        self.store.mkdir(parents=True, mode=0o700)
        os.mkfifo(self.mark())
        self.invoke(started())
        self.assertEqual(self.last(), ("warn", "planner_not_recorded", "store_write_failed"))
        self.deny_reason(launch(INCIDENT_FIRST))

    def test_session_id_の無い_SubagentStart_は記録しない(self) -> None:
        self.assertPasses(started(session=None))
        self.assertEqual(self.last(), ("warn", "planner_not_recorded", "session_missing"))
        self.assertEqual([p.name for p in self.store.iterdir()], ["events.jsonl"])

    def test_session_id_の無い起動は判定せずに通し_session_missing_を残す(self) -> None:
        for session in (None, "", 123):
            with self.subTest(session=session):
                self.assertPasses(launch(INCIDENT_FIRST, session=session))
                self.assertEqual(self.last(), ("warn", "implementer_checked", "session_missing"))
                self.assertIsNone(self.events()[-1]["session"])
        self.deny_reason(launch(INCIDENT_FIRST))

    def test_置き場と印とログは所有者だけが読み書きできる(self) -> None:
        self.assertPasses(started())
        self.assertEqual(self.store.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.mark().stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.store / "events.jsonl").stat().st_mode & 0o777, 0o600)

    def test_ログにプロンプトの本文と計画の所在を書かない(self) -> None:
        self.deny_reason(launch(INCIDENT_FIRST))
        self.assertPasses(launch(INHERITED))
        decoded = json.dumps(self.events(), ensure_ascii=False)
        self.assertNotIn("規則を 3 件", decoded)
        self.assertNotIn("TASK-12", decoded)
        self.assertEqual([e["session"] for e in self.events()], [SESSION, SESSION])

    def test_hook_自身の不具合は型名だけをログに残して通す(self) -> None:
        self.assertPasses(launch(INCIDENT_FIRST), launcher=("-c", RAISES))
        events = self.events()
        self.assertEqual(
            [(e["level"], e["event"], e["reason"], e.get("error_type")) for e in events],
            [("error", "implementer_checked", "internal_error", "RuntimeError")],
        )
        self.assertNotIn("例外にだけある語", json.dumps(events, ensure_ascii=False))
        self.deny_reason(launch(INCIDENT_FIRST))

    def test_記録の不具合は型名だけをログに残し印を作らない(self) -> None:
        self.assertPasses(started(), launcher=("-c", RAISES))
        self.assertEqual(
            [(e["level"], e["event"], e["reason"], e.get("error_type")) for e in self.events()],
            [("error", "planner_not_recorded", "internal_error", "RuntimeError")],
        )
        self.assertEqual([p.name for p in self.store.iterdir()], ["events.jsonl"])


class InputTest(PlannerGateCase):
    def test_読めない入力は何も出力せずに通す(self) -> None:
        for payload in (
            b"\xff not json",
            b"not json",
            b"[]",
            json.dumps({**launch(INCIDENT_FIRST), "tool_input": "ステップ 1/2"}).encode("utf-8"),
            json.dumps(launch(["ステップ 1/2"])).encode("utf-8"),
            json.dumps(launch(None)).encode("utf-8"),
        ):
            self.assertPasses(payload)
        self.assertEqual(self.events(), [])

    def test_標準入出力の符号化が日本語を表せなくても止めて_ASCII_の_JSON_を書く(self) -> None:
        env = {"PYTHONIOENCODING": "ascii", "LC_ALL": "C"}
        self.assertIn("planner の計画:", self.deny_reason(launch(INCIDENT_FIRST), extra_env=env))
        self.assertPasses(launch(INCIDENT_FIRST), data=None, extra_env=env)


class RegistrationTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.hooks = json.loads((helpers.REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]

    def commands(self, event: str, matcher: str) -> list[str]:
        entries = [entry for entry in self.hooks.get(event, []) if entry.get("matcher") == matcher]
        self.assertEqual(len(entries), 1, entries)
        return [hook["command"] for hook in entries[0]["hooks"]]

    def test_PreToolUse_の_Agent_と_SubagentStart_の_planner_に登録する(self) -> None:
        command = 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/planner_gate.py"'
        self.assertIn(command, self.commands("PreToolUse", "Agent"))
        self.assertIn(command, self.commands("SubagentStart", "^dev-skills:planner$"))
