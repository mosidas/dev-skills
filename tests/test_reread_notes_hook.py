"""SessionStart hook(`inject_reread_notes.py`)の単体テスト。

hook はサブプロセスで実行し、入力は UTF-8 のバイト列で渡す。backlog CLI は PATH の先頭に置いた偽の CLI で差し替え、
受けた argv と cwd を記録させる。実物の CLI との契約は、CLI があるときだけ一時ディレクトリのプロジェクトで確かめる。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

import helpers

HOOK = helpers.REPO_ROOT / "hooks" / "inject_reread_notes.py"
INHERITED = ("CLAUDE_PROJECT_DIR", "BACKLOG_CWD")

FAKE_BACKLOG = """#!{python}
import json, os, sys, time
from pathlib import Path
here = Path({bin_dir!r})
with open(here / "calls.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
out = json.loads((here / "out.json").read_text(encoding="utf-8"))
time.sleep(out.get("sleep", 0))
sys.stdout.buffer.write(bytes.fromhex(out["hex"]) if "hex" in out else out["stdout"].encode("utf-8"))
sys.stderr.write("fake stderr\\n")
sys.exit(out.get("code", 0))
"""

MORE = "- ほか {n} 件(`backlog task list --status \"In Progress\" --plain` で見る)"


def task(task_id: str, title: str, updated: str) -> dict:
    return {"id": task_id, "title": title, "status": "In Progress", "updatedAt": updated}


def listing(tasks: list) -> str:
    return json.dumps({"schemaVersion": 1, "kind": "task-list", "tasks": tasks}, ensure_ascii=False)


def items(context: str) -> list[str]:
    return [line for line in context.splitlines() if line.startswith("- ")]


class RereadNotesCase(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        fake = self.bin / "backlog"
        fake.write_text(FAKE_BACKLOG.format(python=sys.executable, bin_dir=str(self.bin)), encoding="utf-8")
        fake.chmod(0o755)
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.respond(listing([]))

    def respond(self, stdout: str = "", code: int = 0, sleep: float = 0, raw: bytes | None = None) -> None:
        out: dict = {"stdout": stdout, "code": code, "sleep": sleep}
        if raw is not None:
            out["hex"] = raw.hex()
        (self.bin / "out.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    def calls(self) -> list[dict]:
        path = self.bin / "calls.jsonl"
        calls = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        path.unlink(missing_ok=True)
        return calls

    def run_hook(
        self, payload: object, path: str | None = None, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if k not in INHERITED}
        env["PATH"] = path if path is not None else f"{self.bin}{os.pathsep}{os.environ['PATH']}"
        env.update(extra_env or {})
        stdin = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        proc = subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        return proc

    def compact(self, cwd: object = None) -> dict:
        return {"hook_event_name": "SessionStart", "source": "compact", "cwd": str(self.work) if cwd is None else cwd}

    def context(self, proc: subprocess.CompletedProcess) -> str:
        output = json.loads(proc.stdout.decode("ascii"))["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        return output["additionalContext"]

    def stderr(self, proc: subprocess.CompletedProcess) -> str:
        return proc.stderr.decode("utf-8")

    def assertFallback(self, proc: subprocess.CompletedProcess, error_type: str) -> str:
        ctx = self.context(proc)
        self.assertIn("一覧を取れなかった", ctx)
        self.assertIn("要約だけで作業を続けない", ctx)
        self.assertIn("`backlog task <id> --plain`", ctx)
        self.assertIn("Implementation Notes", ctx)
        self.assertEqual(items(ctx), [], "一覧の行を含まない")
        self.assertIn(f"inject_reread_notes: 一覧を取らない error.type={error_type}", self.stderr(proc))
        return ctx

    def assertSilent(self, proc: subprocess.CompletedProcess) -> None:
        self.assertEqual(proc.stdout, b"", "何も注入しない")


class CompactTest(RereadNotesCase):
    def test_compactなら一覧つきの指示を新しい順に注入する(self) -> None:
        self.respond(
            listing([task("TASK-1", "古いタスク", "2026-11-20T10:00:00Z"), task("TASK-2", "新しいタスク", "2026-11-24T09:00:00Z")])
        )
        proc = self.run_hook(self.compact())
        ctx = self.context(proc)
        self.assertEqual(items(ctx), ["- TASK-2 新しいタスク", "- TASK-1 古いタスク"])
        self.assertTrue(ctx.startswith("dev-skills: 会話の要約の後である。"), ctx)
        self.assertLess(ctx.index("要約だけで作業を続けない"), ctx.index("- TASK-2"), "指示の後ろに一覧を置く")
        self.assertIn("`backlog task <id> --plain`", ctx)
        self.assertIn("Implementation Notes", ctx)
        self.assertIn("要約に無いタスクは読まず、続けない。", ctx)
        self.assertNotIn("一覧を取れなかった", ctx)
        self.assertEqual(proc.stderr, b"", "正常時は標準エラーを書かない")
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["argv"], ["task", "list", "--status", "In Progress", "--json"])
        self.assertEqual(os.path.realpath(calls[0]["cwd"]), os.path.realpath(self.work))

    def test_compact以外のsourceとsource無しでは何も出さずCLIを呼ばない(self) -> None:
        self.respond(listing([task("TASK-1", "タスク", "2026-11-24T09:00:00Z")]))
        for source in ("startup", "resume", "clear", "fork", None):
            with self.subTest(source=source):
                payload = {"hook_event_name": "SessionStart", "cwd": str(self.work)}
                if source is not None:
                    payload["source"] = source
                proc = self.run_hook(payload)
                self.assertSilent(proc)
                self.assertEqual(proc.stderr, b"")
                self.assertEqual(self.calls(), [], "CLI を呼ばない")

    def test_In_Progressが0件なら何も出さない(self) -> None:
        proc = self.run_hook(self.compact())
        self.assertSilent(proc)
        self.assertEqual(proc.stderr, b"")
        self.assertEqual(len(self.calls()), 1, "CLI は呼んだ")

    def test_20件までは全件を出しほかの行を出さない(self) -> None:
        self.respond(listing([task(f"TASK-{i}", f"タスク{i}", f"2026-11-{i:02d}T00:00:00Z") for i in range(1, 21)]))
        ctx = self.context(self.run_hook(self.compact()))
        self.assertEqual(len(items(ctx)), 20)
        self.assertNotIn("ほか", ctx)

    def test_21件なら新しい20件とほか1件の行を出す(self) -> None:
        self.respond(listing([task(f"TASK-{i}", f"タスク{i}", f"2026-11-{i:02d}T00:00:00Z") for i in range(1, 22)]))
        ctx = self.context(self.run_hook(self.compact()))
        lines = items(ctx)
        self.assertEqual(len(lines), 21)
        self.assertEqual(lines[0], "- TASK-21 タスク21")
        self.assertEqual(lines[19], "- TASK-2 タスク2")
        self.assertEqual(lines[20], MORE.format(n=1))
        self.assertNotIn("- TASK-1 タスク1", ctx, "もっとも古い 1 件を省く")

    def test_updatedAtが無いタスクはcreatedAtの順に並べる(self) -> None:
        self.respond(
            listing([
                task("TASK-2", "編集済み", "2026-11-24T09:00:00Z"),
                {"id": "TASK-1", "title": "未編集", "createdAt": "2026-11-25T00:00:00Z"},
            ])
        )
        ctx = self.context(self.run_hook(self.compact()))
        self.assertEqual(items(ctx), ["- TASK-1 未編集", "- TASK-2 編集済み"])

    def test_updatedAtもcreatedAtも無いタスクは最後に並べる(self) -> None:
        self.respond(listing([{"id": "TASK-1", "title": "日時なし"}, task("TASK-2", "日時あり", "2026-11-24T09:00:00Z")]))
        ctx = self.context(self.run_hook(self.compact()))
        self.assertEqual(items(ctx), ["- TASK-2 日時あり", "- TASK-1 日時なし"])

    def test_201字のタイトルは200字で切る(self) -> None:
        self.respond(listing([task("TASK-1", "あ" * 200 + "い", "2026-11-24T09:00:00Z")]))
        ctx = self.context(self.run_hook(self.compact()))
        self.assertEqual(items(ctx), ["- TASK-1 " + "あ" * 200])

    def test_タイトルの改行で偽の行を注入できない(self) -> None:
        titles = ["本物\n- TASK-999 偽物", "本物\r\n- TASK-998 偽物", "本物\u2028- TASK-997 偽物", "本物\x85- TASK-996 偽物"]
        tasks = [task(f"TASK-{i}", t, "2026-11-24T09:00:00Z") for i, t in enumerate(titles, 1)]
        tasks.append(task("TASK-5\n- TASK-995 偽物", "本物", "2026-11-24T09:00:00Z"))
        self.respond(listing(tasks))
        ctx = self.context(self.run_hook(self.compact()))
        lines = items(ctx)
        self.assertEqual(len(lines), 5, lines)
        for fake in ("- TASK-999", "- TASK-998", "- TASK-997", "- TASK-996", "- TASK-995"):
            self.assertFalse(any(line.startswith(fake) for line in lines), fake)
        self.assertIn("- TASK-1 本物 - TASK-999 偽物", lines)
        self.assertIn("- TASK-5 - TASK-995 偽物 本物", lines)

    def test_cwdが無ければCLAUDE_PROJECT_DIRで呼ぶ(self) -> None:
        project = self.tmp / "project"
        project.mkdir()
        self.respond(listing([task("TASK-1", "タスク", "2026-11-24T09:00:00Z")]))
        for cwd in (str(self.tmp / "missing"), 5, ""):
            with self.subTest(cwd=cwd):
                proc = self.run_hook(self.compact(cwd), extra_env={"CLAUDE_PROJECT_DIR": str(project)})
                self.assertEqual(items(self.context(proc)), ["- TASK-1 タスク"])
                calls = self.calls()
                self.assertEqual(len(calls), 1)
                self.assertEqual(os.path.realpath(calls[0]["cwd"]), os.path.realpath(project))

    def test_cwdもCLAUDE_PROJECT_DIRも使えなければ何も出さない(self) -> None:
        missing = str(self.tmp / "missing")
        for extra in ({}, {"CLAUDE_PROJECT_DIR": str(self.tmp / "missing-project")}):
            with self.subTest(extra=extra):
                proc = self.run_hook(self.compact(missing), extra_env=extra)
                self.assertSilent(proc)
                self.assertEqual(self.calls(), [], "CLI を呼ばない")
                self.assertEqual(self.stderr(proc), "inject_reread_notes: 一覧を取らない error.type=cwd_unavailable\n")
                self.assertNotIn(missing, self.stderr(proc), "パスを書かない")

    def test_符号化が日本語を表せなくてもASCIIのJSONで日本語のタイトルを渡す(self) -> None:
        self.respond(listing([task("TASK-1", "日本語のタイトル", "2026-11-24T09:00:00Z")]))
        proc = self.run_hook(self.compact(), extra_env={"PYTHONIOENCODING": "ascii", "LC_ALL": "C", "LANG": "C"})
        self.assertEqual(items(self.context(proc)), ["- TASK-1 日本語のタイトル"])


class FailureTest(RereadNotesCase):
    def test_backlogがPATHに無ければ何も出さない(self) -> None:
        empty = self.tmp / "empty-bin"
        empty.mkdir()
        proc = self.run_hook(self.compact(), path=str(empty))
        self.assertSilent(proc)
        self.assertEqual(self.stderr(proc), "inject_reread_notes: 一覧を取らない error.type=backlog_not_found\n")

    def test_CLIが非0で終われば何も出さず終了コードを書く(self) -> None:
        self.respond("TASK-1 秘密のタイトル", code=1)
        proc = self.run_hook(self.compact())
        self.assertSilent(proc)
        stderr = self.stderr(proc)
        self.assertIn("inject_reread_notes: 一覧を取らない error.type=backlog_exit", stderr)
        self.assertIn("exit_code=1", stderr)
        self.assertEqual(len(stderr.splitlines()), 1, stderr)
        self.assertNotIn("秘密", stderr, "CLI の出力を書かない")
        self.assertNotIn("fake stderr", stderr, "CLI の標準エラーを書かない")
        self.assertNotIn(str(self.work), stderr, "パスを書かない")

    def test_CLIの出力が想定の形でなければ一覧なしの指示を出す(self) -> None:
        outputs = {
            "JSON でない": "TASK-7 秘密のタイトル",
            "kind が違う": json.dumps({"kind": "task-detail", "tasks": [task("TASK-7", "秘密", "x")]}),
            "kind が無い": json.dumps({"tasks": [task("TASK-7", "秘密", "x")]}),
            "dict でない": json.dumps([task("TASK-7", "秘密", "x")]),
            "tasks が list でない": json.dumps({"kind": "task-list", "tasks": {"TASK-7": "秘密"}}),
            "要素が dict でない": listing(["TASK-7"]),
            "id が文字列でない": listing([{"id": 7, "title": "秘密"}]),
            "title が文字列でない": listing([{"id": "TASK-7", "title": None}]),
            "title が無い": listing([{"id": "TASK-7"}]),
        }
        for name, stdout in outputs.items():
            with self.subTest(name):
                self.respond(stdout)
                proc = self.run_hook(self.compact())
                ctx = self.assertFallback(proc, "backlog_output_invalid")
                self.assertNotIn("TASK-7", ctx)
                self.assertNotIn("秘密", self.stderr(proc), "CLI の出力を書かない")

    def test_CLIの出力が不正なUTF_8なら一覧なしの指示を出す(self) -> None:
        self.respond(raw=b'{"kind": "task-list", "tasks": [{"id": "TASK-7", "title": "\xff"}]}')
        ctx = self.assertFallback(self.run_hook(self.compact()), "backlog_output_invalid")
        self.assertNotIn("TASK-7", ctx)

    def test_CLIが応答しなければ打ち切って一覧なしの指示を出す(self) -> None:
        self.respond(listing([task("TASK-7", "タスク", "2026-11-24T09:00:00Z")]), sleep=30)
        started = time.monotonic()
        proc = self.run_hook(self.compact())
        self.assertLess(time.monotonic() - started, 9, "CLI の上限で打ち切る")
        ctx = self.assertFallback(proc, "backlog_timeout")
        self.assertNotIn("TASK-7", ctx)

    def test_想定外の例外では終了コード1で型名だけを書く(self) -> None:
        self.respond(listing([task("TASK-7", "秘密のタイトル", "2026-11-24T09:00:00Z")]))
        for name, extra in (("既定", {}), ("ASCII", {"PYTHONIOENCODING": "ascii", "LC_ALL": "C", "LANG": "C"})):
            with self.subTest(name):
                env = {k: v for k, v in os.environ.items() if k not in INHERITED}
                env["PATH"] = f"{self.bin}{os.pathsep}{os.environ['PATH']}"
                env.update(extra)
                proc = subprocess.run(
                    [sys.executable, str(HOOK)],
                    input=json.dumps(self.compact()).encode("utf-8"),
                    capture_output=True,
                    env=env,
                    timeout=60,
                    preexec_fn=lambda: os.close(1),
                )
                self.assertEqual(len(self.calls()), 1, "CLI を呼んでから標準出力に書いて失敗する")
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(proc.stdout, b"")
                stderr = self.stderr(proc)
                self.assertEqual(stderr, "inject_reread_notes: 内部エラー AttributeError\n")
                self.assertNotIn("秘密", stderr, "タイトルを書かない")
                self.assertNotIn(str(self.work), stderr, "パスを書かない")

    def test_標準入力が読めなければ何も出さない(self) -> None:
        for name, stdin in (
            ("JSON でない", b"not json"),
            ("dict でない", json.dumps(["compact"]).encode("utf-8")),
            ("不正な UTF-8", b'{"source": "compact", "cwd": "\xff"}'),
        ):
            with self.subTest(name):
                proc = self.run_hook(stdin)
                self.assertSilent(proc)
                self.assertEqual(self.calls(), [], "CLI を呼ばない")


@unittest.skipUnless(shutil.which("backlog"), "backlog CLI が無い")
class RealCliTest(helpers.TempDirTestCase):
    def test_実物のCLIのIn_Progressのタスクを注入する(self) -> None:
        project = self.tmp / "proj"
        project.mkdir()
        env = {k: v for k, v in helpers.git_isolated_env().items() if k not in INHERITED}

        def run(*args: str) -> None:
            subprocess.run(
                args, cwd=project, env=env, stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=60
            )

        run("git", "init", "-q")
        run("backlog", "init", "proj", "--defaults")
        run("backlog", "task", "create", "実物の日本語タイトル")
        run("backlog", "task", "edit", "1", "-s", "In Progress")
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"hook_event_name": "SessionStart", "source": "compact", "cwd": str(project)}).encode(),
            capture_output=True,
            env=env,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stderr, b"")
        ctx = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("- TASK-1 実物の日本語タイトル", ctx.splitlines())


if __name__ == "__main__":
    unittest.main()
