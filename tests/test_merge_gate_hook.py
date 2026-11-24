"""gate-reviewer の判定を記録し、gh pr merge を記録と照合する hook(`merge_gate.py`)の単体テスト。

hook は `sys.exit` を呼び、`CLAUDE_PLUGIN_DATA` の下に記録とログを書くため、すべて `CLAUDE_PLUGIN_DATA` を
一時ディレクトリに向けたサブプロセスで確かめる。入力は実機で観測した形にする。auto モードでは
PostToolUse(SubagentHandback)の `tool_input.message` に、default モードでは SubagentStop の
`last_assistant_message` に報告が入る。記録する入力と記録しない入力を対で書く。
照合は PATH の先頭に置いた偽の gh で確かめ、ネットワークを使わない。main の取り込みは一時の bare リポジトリを
origin にした実際の git で確かめる。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import helpers

HOOK = helpers.REPO_ROOT / "hooks" / "merge_gate.py"
GATE = "dev-skills:gate-reviewer"
REPO = "github.com/example/demo"
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}
# 本文案の正規化の要求: CRLF・CR を LF に、行末の空白を除き、帰属の行と前後の空行を除く
BODY = (
    "\r\n## 概要\r\n\r\nゲートの判定を記録する。  \r\n変更点\t\r"
    "\r\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\r\n\r\n"
)
BODY_NORMALIZED = "## 概要\n\nゲートの判定を記録する。\n変更点"
SECRET = "本文にだけある語"
RUN_RAISES = (
    "import runpy, subprocess, sys\n"
    "def broken(*args, **kwargs):\n"
    "    raise RuntimeError('報告にだけある語')\n"
    "subprocess.run = broken\n"
    "runpy.run_path(sys.argv[1], run_name='__main__')\n"
)
BASENAME_RAISES = (
    "import os, runpy, sys\n"
    "def broken(*args, **kwargs):\n"
    "    raise RuntimeError('報告にだけある語')\n"
    "os.path.basename = broken\n"
    "runpy.run_path(sys.argv[1], run_name='__main__')\n"
)
SHORT_TIMEOUT = (
    "import runpy, subprocess, sys\n"
    "run = subprocess.run\n"
    "def short(*args, **kwargs):\n"
    "    kwargs['timeout'] = min(kwargs['timeout'], 1)\n"
    "    return run(*args, **kwargs)\n"
    "subprocess.run = short\n"
    "runpy.run_path(sys.argv[1], run_name='__main__')\n"
)
PR_URL = "https://github.com/example/demo/pull/7"
# テストを走らせる環境から受け継ぐと、照合の対象と cd の行き先が変わる変数
INHERITED = ("CLAUDE_PLUGIN_DATA", "GH_REPO", "GH_HOST", "GIT_DIR", "GIT_WORK_TREE", "GH_PROMPT_DISABLED", "CDPATH")
VIEW = ["--json", "headRefOid,body,url,baseRefName,commits"]


def view_argv(selector: str | None = None, repo: str | None = None) -> list[str]:
    """照合で偽の gh が受ける引数。selector は `--` の後に置く。"""
    return ["pr", "view", *(["-R", repo] if repo else []), *VIEW, *(["--", selector] if selector else [])]

NEXT = hashlib.sha1("ゲートの後のコミット".encode("utf-8")).hexdigest()
FAKE_GH = """#!{python}
import json, os, sys, time
from pathlib import Path
here = Path({bin_dir!r})
args = sys.argv[1:]
env = {{k: os.environ[k] for k in ("GH_REPO", "GH_HOST", "GIT_DIR", "GIT_WORK_TREE") if k in os.environ}}
call = {{"argv": args, "cwd": os.getcwd(), "env": env, "prompt_disabled": os.environ.get("GH_PROMPT_DISABLED")}}
with open(here / "calls.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(call) + "\\n")
views = json.loads((here / "views.json").read_text(encoding="utf-8"))
key = args[args.index("--") + 1] if "--" in args else ""
view = views.get(key, views.get("*"))
time.sleep(view.get("sleep", 0))
sys.stdout.buffer.write(view["stdout"].encode("utf-8"))
sys.exit(view.get("code", 0))
"""
NO_RECORD = (
    "example/demo#7 の今の head には、gate-reviewer の判定の記録がありません。このままマージしてよいか確認してください。"
)
UNRESOLVED = "マージする PR を特定できないため、ゲートの記録と照合できませんでした。このままマージしてよいか確認してください。"
VIEW_FAILED = (
    "GitHub から PR の head と本文を取得できなかったため、ゲートの記録と照合できませんでした。"
    "このままマージしてよいか確認してください。"
)


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, **GIT_ENV},
    )
    return proc.stdout.strip()


def make_repo(path: Path, origin: str | None = "git@github.com:example/demo.git") -> str:
    """コミットを 1 つ持つ git リポジトリを作り、head の SHA を返す。"""
    path.mkdir(parents=True)
    git(path, "init", "-q")
    if origin is not None:
        git(path, "remote", "add", "origin", origin)
    (path / "README.md").write_text("demo\n", encoding="utf-8")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "init")
    return git(path, "rev-parse", "HEAD")


def report(verdict: str, repo: Path, body: Path | None) -> str:
    lines = ["## 判定", verdict, f"- リポジトリ: {repo}"]
    if body is not None:
        lines.append(f"- PR 本文案: {body}")
    return "\n".join(lines) + "\n\n## 確認したこと\n- テスト: 通過\n"


def pr_view(
    head: str, body: str = BODY, commits: list[str] | None = None, url: str = PR_URL, base: str = "main"
) -> dict:
    """gh pr view の応答(views.json の 1 件)を作る。"""
    data = {
        "headRefOid": head,
        "body": body,
        "url": url,
        "baseRefName": base,
        "commits": [{"oid": oid} for oid in (commits or [head])],
    }
    return {"stdout": json.dumps(data, ensure_ascii=False)}


def handback(text: str, agent_type: str = GATE) -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "agent_type": agent_type,
        "tool_name": "SubagentHandback",
        "tool_input": {"message": text},
        "tool_response": {"success": True, "message": "Report delivered to your caller."},
    }


def subagent_stop(text: str | None, agent_type: str = GATE) -> dict:
    payload = {"hook_event_name": "SubagentStop", "agent_type": agent_type, "stop_hook_active": False}
    if text is not None:
        payload["last_assistant_message"] = text
    return payload


class MergeGateCase(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data = self.tmp / "data"
        self.store = self.data / "merge-gate"
        self.repo = self.tmp / "repo"
        self.head = make_repo(self.repo)
        self.body = self.tmp / "scratch" / "pr-body.md"
        self.body.parent.mkdir()
        self.body.write_bytes(BODY.encode("utf-8"))

    def invoke(
        self,
        payload: object,
        data: Path | None = None,
        path: str | None = None,
        launcher: tuple[str, ...] = (),
        extra_env: dict[str, str] | None = None,
    ) -> bytes:
        """hook を実行し、標準出力を返す。exit 0 で標準エラーが空であることを確かめる。"""
        env = {k: v for k, v in os.environ.items() if k not in INHERITED}
        env.update(GIT_ENV)
        env.update(extra_env or {})
        if path is not None:
            env["PATH"] = path
        if data is not None:
            env["CLAUDE_PLUGIN_DATA"] = str(data)
        stdin = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        proc = subprocess.run([sys.executable, *launcher, str(HOOK)], input=stdin, capture_output=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stderr, b"", "hook は標準エラーを書かない")
        return proc.stdout

    def run_hook(
        self, payload: object, data: Path | None = None, path: str | None = None, launcher: tuple[str, ...] = ()
    ) -> None:
        self.assertEqual(self.invoke(payload, data, path, launcher), b"", "記録の hook は標準出力を書かない")

    def record(self, payload: object) -> None:
        self.run_hook(payload, self.data)

    def record_path(self, head: str | None = None, repo: str = REPO) -> Path:
        name = hashlib.sha256(f"{repo}\n{head or self.head}".encode()).hexdigest()
        return self.store / f"{name}.json"

    def events(self) -> list[dict]:
        log = self.store / "events.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="ascii").splitlines()]

    def approve(self, body: Path | None = None, head: str | None = None) -> str:
        return report(f"マージ可 {head or self.head}", self.repo, body or self.body)

    def assertRecorded(self) -> None:
        saved = json.loads(self.record_path().read_text(encoding="ascii"))
        self.assertEqual(saved["repo"], REPO)
        self.assertEqual(saved["head"], self.head)
        self.assertEqual(saved["body_sha256"], hashlib.sha256(BODY_NORMALIZED.encode("utf-8")).hexdigest())
        self.assertEqual(saved["repo_path"], str(self.repo))
        self.assertRegex(saved["recorded_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def assertNotRecorded(self, reason: str) -> None:
        self.assertEqual(list(self.store.glob("*.json")), [], "記録を書かない")
        events = self.events()
        self.assertEqual(len(events), 1, events)
        self.assertEqual(
            (events[0]["level"], events[0]["event"], events[0]["reason"]), ("warn", "gate_not_recorded", reason)
        )


class MergeGateRecordTest(MergeGateCase):
    def test_auto_モードの報告のマージ可から記録ができる(self) -> None:
        self.record(handback(self.approve()))
        self.assertRecorded()
        events = self.events()
        self.assertEqual(len(events), 1, events)
        self.assertEqual(set(events[0]), {"ts", "level", "event", "reason", "repo", "pr", "head"})
        self.assertEqual((events[0]["level"], events[0]["event"]), ("info", "gate_recorded"))
        self.assertEqual((events[0]["repo"], events[0]["head"]), (REPO, self.head))

    def test_default_モードの報告のマージ可から記録ができる(self) -> None:
        self.record(subagent_stop(self.approve()))
        self.assertRecorded()
        self.assertEqual([e["event"] for e in self.events()], ["gate_recorded"])

    def test_auto_モードの報告の無い_SubagentStop_は何もしない(self) -> None:
        self.record(subagent_stop(None))
        self.record(subagent_stop("作業を終えた。"))
        self.assertFalse(self.store.exists(), "ログも書かない")
        self.record(subagent_stop(self.approve()))
        self.assertRecorded()

    def test_https_の_origin_も小文字の_host_owner_name_を鍵にしログに_URL_を書かない(self) -> None:
        credential = "user:" + "tok-secret"  # 秘密の検知が試験の値を資格情報と読まないよう、つないで作る
        git(self.repo, "remote", "set-url", "origin", f"https://{credential}@GitHub.com/Example/Demo.git")
        self.record(handback(self.approve()))
        self.assertRecorded()
        self.assertNotIn("tok-secret", (self.store / "events.jsonl").read_text(encoding="ascii"))

    def test_同じ判定を_2_回取り込んでも記録は_1_つで内容も同じ(self) -> None:
        self.record(handback(self.approve()))
        first = self.record_path().read_bytes()
        time.sleep(1.1)  # recorded_at が秒単位でも 2 回目は別の秒になる
        self.record(subagent_stop(self.approve()))
        self.assertEqual(list(self.store.glob("*.json")), [self.record_path()])
        self.assertEqual(self.record_path().read_bytes(), first)

    def test_差し戻しは同じ_SHA_の記録を消す(self) -> None:
        self.record(handback(self.approve()))
        self.assertTrue(self.record_path().exists())
        self.record(handback(report(f"差し戻し {self.head}", self.repo, None)))
        self.assertFalse(self.record_path().exists())
        self.assertEqual(
            [(e["level"], e["event"]) for e in self.events()], [("info", "gate_recorded"), ("info", "gate_record_removed")]
        )

    def test_本文案の行が絶対パスでない差し戻しも同じ_SHA_の記録を消す(self) -> None:
        self.record(handback(self.approve()))
        self.assertTrue(self.record_path().exists())
        self.record(handback(f"## 判定\n差し戻し {self.head}\n- リポジトリ: {self.repo}\n- PR 本文案: なし\n"))
        self.assertFalse(self.record_path().exists(), "差し戻しは本文案を使わない")
        self.assertEqual(
            [(e["level"], e["event"]) for e in self.events()], [("info", "gate_recorded"), ("info", "gate_record_removed")]
        )

    def test_差し戻しは別の_SHA_の記録を消さない(self) -> None:
        self.record(handback(self.approve()))
        self.record(handback(report(f"差し戻し {'0' * 40}", self.repo, None)))
        self.assertTrue(self.record_path().exists())

    def test_SHA_の無い旧形式の判定は記録しない(self) -> None:
        self.record(handback(f"## 判定\nマージ可\n\n- リポジトリ: {self.repo}\n- PR 本文案: {self.body}\n"))
        self.assertNotRecorded("verdict_malformed")
        self.assertEqual((self.events()[0]["repo"], self.events()[0]["head"]), (None, None))

    def test_相対パスの判定は記録しない(self) -> None:
        self.record(handback(report(f"マージ可 {self.head}", Path("repo"), self.body)))
        self.assertNotRecorded("verdict_malformed")

    def test_マージ可で本文案が相対パスなら記録しない(self) -> None:
        self.record(handback(self.approve(body=Path("pr-body.md"))))
        self.assertNotRecorded("verdict_malformed")

    def test_マージ可で本文案の行が無ければ記録しない(self) -> None:
        self.record(handback(report(f"マージ可 {self.head}", self.repo, None)))
        self.assertNotRecorded("verdict_malformed")

    def test_バッククォートで囲んだパスと_SHA_と太字の判定の語も読む(self) -> None:
        text = f"## 判定\n**マージ可** `{self.head}`\n- リポジトリ: `{self.repo}`\n- PR 本文案: `{self.body}`\n"
        self.record(handback(text))
        self.assertRecorded()
        self.record_path().unlink()
        self.record(handback(f"## 判定\n**マージ可 {self.head}**\n- リポジトリ: {self.repo}\n- PR 本文案: **{self.body}**\n"))
        self.assertRecorded()
        self.assertEqual([e["event"] for e in self.events()], ["gate_recorded", "gate_recorded"])

    def test_判定の_SHA_と_HEAD_が違えば記録しない(self) -> None:
        self.record(handback(self.approve(head="0" * 40)))
        self.assertNotRecorded("head_moved")

    def test_origin_の無いリポジトリは記録しない(self) -> None:
        git(self.repo, "remote", "remove", "origin")
        self.record(handback(self.approve()))
        self.assertNotRecorded("repo_unresolved")

    def test_git_が応答しなければ打ち切って記録しない(self) -> None:
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "git"
        fake.write_text("#!/bin/sh\nexec sleep 30\n", encoding="ascii")
        fake.chmod(0o755)
        started = time.monotonic()
        self.run_hook(handback(self.approve()), self.data, path=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
        self.assertLess(time.monotonic() - started, 15, "git の上限で打ち切る")
        self.assertNotRecorded("repo_unresolved")

    def test_本文案が無ければ記録しない(self) -> None:
        self.record(handback(self.approve(body=self.tmp / "missing.md")))
        self.assertNotRecorded("body_unreadable")
        self.assertEqual((self.events()[0]["repo"], self.events()[0]["head"]), (REPO, self.head))

    def test_本文案のパスに_NUL_があれば記録しない(self) -> None:
        self.record(handback(self.approve(body=Path(f"{self.body}\0.md"))))
        self.assertNotRecorded("body_unreadable")
        self.assertEqual((self.events()[0]["repo"], self.events()[0]["head"]), (REPO, self.head))

    def test_リポジトリのパスに_NUL_があれば記録しない(self) -> None:
        self.record(handback(report(f"マージ可 {self.head}", Path(f"{self.repo}\0x"), self.body)))
        self.assertNotRecorded("repo_unresolved")

    def test_本文案がディレクトリなら記録しない(self) -> None:
        self.record(handback(self.approve(body=self.body.parent)))
        self.assertNotRecorded("body_unreadable")

    def test_本文案が名前付きパイプでも止まらずに記録しない(self) -> None:
        fifo = self.tmp / "fifo.md"
        os.mkfifo(fifo)
        self.record(handback(self.approve(body=fifo)))
        self.assertNotRecorded("body_unreadable")

    def test_本文案が_UTF_8_でなければ記録しない(self) -> None:
        self.body.write_bytes("概要".encode("shift_jis"))
        self.record(handback(self.approve()))
        self.assertNotRecorded("body_unreadable")

    def test_本文案は_256_KiB_ちょうどなら記録し超えれば記録しない(self) -> None:
        limit = 256 * 1024
        self.body.write_bytes(("あ" * (limit // 3) + "a" * (limit % 3)).encode("utf-8"))
        self.assertEqual(self.body.stat().st_size, limit)
        self.record(handback(self.approve()))
        self.assertTrue(self.record_path().exists(), "上限ちょうどは記録する")
        self.record_path().unlink()
        (self.store / "events.jsonl").unlink()
        self.body.write_bytes(self.body.read_bytes() + b"a")
        self.record(handback(self.approve()))
        self.assertNotRecorded("body_unreadable")

    def test_記録のパスがリンクなら記録せずリンク先も書き換えない(self) -> None:
        self.store.mkdir(parents=True, mode=0o700)
        target = self.tmp / "target.json"
        target.write_text("original", encoding="ascii")
        self.record_path().symlink_to(target)
        self.record(handback(self.approve()))
        self.assertTrue(self.record_path().is_symlink(), "リンクを置き換えない")
        self.assertEqual(target.read_text(encoding="ascii"), "original")
        events = self.events()
        self.assertEqual(
            [(e["level"], e["event"], e["reason"]) for e in events], [("warn", "gate_not_recorded", "store_write_failed")]
        )

    def test_merge_gate_のディレクトリがリンクならリンク先に書かない(self) -> None:
        target = self.tmp / "elsewhere"
        target.mkdir(mode=0o700)
        self.data.mkdir()
        self.store.symlink_to(target)
        self.record(handback(self.approve()))
        self.assertTrue(self.store.is_symlink(), "リンクを置き換えない")
        self.assertEqual(list(target.iterdir()), [], "リンク先に記録もログも書かない")

    def test_gate_reviewer_でない報告は記録もログもしない(self) -> None:
        self.record(handback(self.approve(), agent_type="dev-skills:reviewer"))
        self.record(subagent_stop(self.approve(), agent_type="gate-reviewer"))
        self.assertFalse(self.store.exists())
        self.record(handback(self.approve()))
        self.assertRecorded()

    def test_判定の区間の無い報告は記録もログもしない(self) -> None:
        self.record(handback("## 結果\n完了\n"))
        self.assertFalse(self.store.exists())

    def test_CLAUDE_PLUGIN_DATA_が無ければ何も書かない(self) -> None:
        self.run_hook(handback(self.approve()), None)
        self.assertFalse(self.store.exists())

    def test_ログの行に本文と報告の中身を書かない(self) -> None:
        self.body.write_text(f"{SECRET}\n", encoding="utf-8")
        text = self.approve() + "- 提案: 報告にだけある語\n"
        self.record(handback(text))
        self.record(handback(text.replace(self.head, "0" * 40)))
        log = (self.store / "events.jsonl").read_text(encoding="ascii")
        self.assertEqual(len(log.splitlines()), 2)
        decoded = json.dumps(self.events(), ensure_ascii=False)
        self.assertNotIn(SECRET, decoded)
        self.assertNotIn("報告にだけある語", decoded)
        self.assertNotIn(str(self.body), decoded)

    def test_記録とログは所有者だけが読み書きできる(self) -> None:
        self.record(handback(self.approve()))
        self.assertEqual(self.store.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.record_path().stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.store / "events.jsonl").stat().st_mode & 0o777, 0o600)

    def test_hook_自身の不具合はログに_1_行残して止めない(self) -> None:
        self.run_hook(handback(self.approve()), self.data, launcher=("-c", RUN_RAISES))
        self.assertEqual(list(self.store.glob("*.json")), [], "記録を書かない")
        events = self.events()
        self.assertEqual(
            [(e["level"], e["event"], e["reason"], e.get("error_type")) for e in events],
            [("error", "gate_not_recorded", "hook_error", "RuntimeError")],
        )
        self.assertEqual(events[0]["head"], self.head, "判定の SHA を読めた後の失敗は head を残す")
        self.assertNotIn("報告にだけある語", json.dumps(events, ensure_ascii=False), "例外の中身を書かない")
        self.run_hook(handback(self.approve()), self.data)
        self.assertTrue(self.record_path().exists(), "起動役が無ければ同じ報告で記録する")

    def test_JSON_として読めない入力でも止めない(self) -> None:
        self.record(b"\xff not json")
        self.record(b"[]")
        self.assertFalse(self.store.exists())


class MergeGateCheckCase(MergeGateCase):
    def setUp(self) -> None:
        super().setUp()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(FAKE_GH.format(python=sys.executable, bin_dir=str(self.bin)), encoding="utf-8")
        gh.chmod(0o755)
        self.record(handback(self.approve()))
        self.assertTrue(self.record_path().exists(), "ステップ 1 の形でマージ可を記録した")
        (self.store / "events.jsonl").unlink()
        self.views({"*": pr_view(self.head)})

    def views(self, views: dict) -> None:
        (self.bin / "views.json").write_text(json.dumps(views, ensure_ascii=False), encoding="utf-8")

    def calls(self) -> list[dict]:
        path = self.bin / "calls.jsonl"
        calls = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
        path.unlink(missing_ok=True)
        return calls

    def checked(self) -> list[tuple]:
        return [(e["level"], e["reason"], e["pr"], e["head"]) for e in self.events() if e["event"] == "merge_checked"]

    def merge(
        self,
        command: str,
        data: Path | None | bool = True,
        launcher: tuple[str, ...] = (),
        tool_name: str = "Bash",
        cwd: Path | None = None,
        path: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[str, str] | None:
        """PreToolUse(Bash)の hook を実行し、(permissionDecision, 理由) を返す。何も出力しなければ None。"""
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": tool_name,
            "tool_input": {"command": command, "description": "マージする"},
            "cwd": str(cwd or self.repo),
        }
        return self.decision(payload, self.data if data is True else data, launcher, path, extra_env)

    def decision(
        self,
        payload: object,
        data: Path | None,
        launcher: tuple[str, ...] = (),
        path: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> tuple[str, str] | None:
        path = path or f"{self.bin}{os.pathsep}{os.environ['PATH']}"
        out = self.invoke(payload, data, path=path, launcher=launcher, extra_env=extra_env)
        if out == b"":
            return None
        output = json.loads(out.decode("ascii"))["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertNotIn("\n", output["permissionDecisionReason"], "理由は 1 行")
        return output["permissionDecision"], output["permissionDecisionReason"]

    def commit_after_gate(self, name: str = "after.txt") -> str:
        """作業ツリーにマージでないコミットを 1 つ足し、その SHA を返す。"""
        (self.repo / name).write_text(f"{name}\n", encoding="utf-8")
        git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "-m", name)
        return git(self.repo, "rev-parse", "HEAD")

    def merge_events(self) -> list[tuple]:
        return [(e["reason"], e.get("detail"), e["head"]) for e in self.events() if e["event"] == "merge_checked"]


class MergeGateCheckTest(MergeGateCheckCase):
    def test_ゲートの後に_1_コミットを足した_PR_のマージを止める(self) -> None:
        after = self.commit_after_gate()
        self.views({"7": pr_view(after, commits=[self.head, after])})
        decision, reason = self.merge("gh pr merge 7 --merge --delete-branch")
        self.assertEqual(decision, "deny")
        self.assertEqual(
            reason,
            f"ゲートの判定({self.head[:7]})の後に head が {after[:7]} へ進んだ。{self.head[:7]}..{after[:7]} のコミットと"
            " PR 本文の差分を gate-reviewer に渡して判定を取り直してから、実行し直す(develop 8.)。",
        )
        self.assertEqual(self.checked(), [("warn", "commits_after_gate", PR_URL, after)])
        self.assertEqual([e.get("detail") for e in self.events()], ["not_merge"], "マージでないコミットで止めた")

    def test_ゲートの後に_PR_本文を追記した_PR_のマージを止める(self) -> None:
        self.views({"7": pr_view(self.head, body=BODY + "ゲートの後に足した行\n")})
        decision, reason = self.merge("gh pr merge 7 --merge --delete-branch")
        self.assertEqual(decision, "deny")
        self.assertEqual(
            reason,
            "ゲートの判定の後に PR 本文が変わった。ゲートに渡した本文案のファイルと `gh pr view 7 --json body` の差分を"
            " gate-reviewer に渡して判定を取り直してから、実行し直す(develop 8.)。",
        )
        self.assertEqual(self.checked(), [("warn", "body_changed", PR_URL, self.head)])

    def test_帰属の語を含む説明の行を足した_PR_のマージを止める(self) -> None:
        for line in (
            "- Generated with [Claude Code] を含む説明",
            "🤖 Generated with [Claude Code](https://claude.com/claude-code) で書いた",
            "> 🤖 Generated with [Claude Code](https://claude.com/claude-code)",
        ):
            with self.subTest(line=line):
                self.views({"7": pr_view(self.head, body=BODY_NORMALIZED + "\n" + line + "\n")})
                result = self.merge("gh pr merge 7 --merge")
                self.assertIsNotNone(result, "本文の変更を見落として通した")
                self.assertEqual(result[0], "deny")
                self.assertEqual(self.checked()[-1], ("warn", "body_changed", PR_URL, self.head))

    def test_ゲートの後に何も変えていない_PR_は何も出力せずに通る(self) -> None:
        attributed = BODY_NORMALIZED + "\r\n\r\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\r\n"
        variants = [
            BODY_NORMALIZED + "\n\n" + line + "  \n"
            for line in (
                "Generated with [Claude Code](https://claude.com/claude-code)",
                "🤖Generated with [Claude Code](https://claude.com/claude-code)",
                "🤖 Generated with [Claude Code](https://claude.ai/code)",
            )
        ]
        for body in (BODY, BODY_NORMALIZED, attributed, *variants):
            with self.subTest(body=body):
                self.views({"7": pr_view(self.head, body=body)})
                self.assertIsNone(self.merge("gh pr merge 7 --merge --delete-branch"))
                calls = self.calls()
                self.assertEqual([c["argv"] for c in calls], [view_argv("7")], "gh pr view で照合した")
                self.assertEqual(os.path.realpath(calls[0]["cwd"]), os.path.realpath(self.repo), "hook の cwd で引く")
                self.assertEqual(calls[0]["prompt_disabled"], "1")
        self.assertEqual(self.checked(), [("info", "pass", PR_URL, self.head)] * 6)

    def test_記録の無い_PR_は確認を求める(self) -> None:
        self.views({"7": pr_view(NEXT, commits=["0" * 40, NEXT])})
        self.assertEqual(self.merge("gh pr merge 7 --squash"), ("ask", NO_RECORD))
        self.assertEqual(self.checked(), [("warn", "no_record", PR_URL, NEXT)])

    def test_R_の_repo_が記録と違う_PR_は確認を求める(self) -> None:
        other = "https://github.com/other/demo/pull/7"
        self.views({"7": pr_view(self.head, url=other)})
        decision, reason = self.merge("gh pr merge 7 -R other/demo --merge")
        self.assertEqual(decision, "ask")
        self.assertEqual(reason, NO_RECORD.replace("example/demo", "other/demo"))
        self.assertEqual([c["argv"] for c in self.calls()], [view_argv("7", "other/demo")])
        self.assertEqual(self.checked(), [("warn", "no_record", other, self.head)])

    def test_gh_pr_view_の失敗と不正な応答は確認を求める(self) -> None:
        good = json.loads(pr_view(self.head)["stdout"])
        cases = [
            ("view_failed", {"stdout": "", "code": 1}),
            ("view_malformed", {"stdout": "{"}),
            ("view_malformed", {"stdout": "[]"}),
            ("view_malformed", {"stdout": json.dumps({**good, "headRefOid": self.head[:39]})}),
            ("view_malformed", {"stdout": json.dumps({**good, "headRefOid": self.head.upper()})}),
            ("view_malformed", {"stdout": json.dumps({**good, "commits": [{"oid": "abc"}]})}),
            ("view_malformed", {"stdout": json.dumps({**good, "commits": None})}),
            ("view_malformed", {"stdout": json.dumps({**good, "body": None})}),
            ("view_malformed", {"stdout": json.dumps({**good, "baseRefName": None})}),
            ("view_malformed", {"stdout": json.dumps({**good, "url": "https://github.com/example/demo/issues/7"})}),
        ]
        for kind, view in cases:
            with self.subTest(view=view):
                self.views({"7": view})
                self.assertEqual(self.merge("gh pr merge 7 --merge"), ("ask", VIEW_FAILED))
                self.assertEqual(self.checked()[-1], ("warn", kind, None, None))
        self.assertEqual(len(self.checked()), len(cases), "照合ごとに 1 行")
        self.assertEqual(
            [(e.get("detail"), e.get("exit_code")) for e in self.events()],
            [("exit_nonzero", 1)] + [(None, None)] * (len(cases) - 1),
            "gh の非 0 の終了は終了コードを載せる",
        )

    def test_gh_を起動できなければ非_0_の終了と分けて確認を求める(self) -> None:
        empty = self.tmp / "empty-bin"
        empty.mkdir()
        self.assertEqual(self.merge("gh pr merge 7 --merge", path=str(empty)), ("ask", VIEW_FAILED))
        events = self.events()
        self.assertEqual(
            [(e["reason"], e.get("detail"), e.get("exit_code")) for e in events], [("view_failed", "spawn_failed", None)]
        )
        self.assertIsNone(self.merge("gh pr merge 7 --merge"), "gh があれば同じコマンドが照合で通る")

    def test_gh_pr_view_が応答しなければ打ち切って確認を求める(self) -> None:
        self.views({"7": {**pr_view(self.head), "sleep": 5}})
        started = time.monotonic()
        result = self.merge("gh pr merge 7 --merge", launcher=("-c", SHORT_TIMEOUT))
        self.assertLess(time.monotonic() - started, 4, "gh の上限で打ち切る")
        self.assertEqual(result, ("ask", VIEW_FAILED))
        self.assertEqual(self.checked(), [("warn", "view_timeout", None, None)])

    def test_PR_の指定と_repo_の指定でそのまま_gh_pr_view_を呼ぶ(self) -> None:
        url = "https://github.com/example/demo/pull/7"
        cases = [
            ("gh pr merge 7 -R o/r --merge", "7", "o/r", {}),
            ("gh pr merge --repo=o/r 7", "7", "o/r", {}),
            ("gh -R github.com/o/r pr merge 7", "7", "github.com/o/r", {}),
            ("GH_REPO=o/r gh pr merge 7", "7", None, {"GH_REPO": "o/r"}),
            (f"gh pr merge {url} --merge", url, None, {}),
            ("gh pr merge feat/TASK-1.2_x --squash", "feat/TASK-1.2_x", None, {}),
            ("gh pr merge --merge --delete-branch", None, None, {}),
            ("gh pr merge --merge --delete-branch 2>&1", None, None, {}),
            ("gh pr merge 7 > /dev/null", "7", None, {}),
            ("gh pr merge -b 'body 8' --subject=9 -t 10 --match-head-commit abc 7", "7", None, {}),
            ("gh pr merge -dR o/r 7", "7", "o/r", {}),
            ("gh pr merge --admin -- 7", "7", None, {}),
            ("gh pr merge -- --web", "--web", None, {}),
            (f"cd sub && gh pr merge {url}", url, None, {}),
            ("cd sub && gh pr merge 7 -R o/r", "7", "o/r", {}),
            ("cd sub && GH_REPO=o/r gh pr merge 7", "7", None, {"GH_REPO": "o/r"}),
            ("gh pr merge \\\n  7 --merge", "7", None, {}),
            ("gh pr merge 7 \\\n  -R o/r --merge", "7", "o/r", {}),
            ("gh pr \\\nmerge 7", "7", None, {}),
            ("gh pr merge 7 --merge -t ''", "7", None, {}),
            ('gh pr merge 7 && echo ""', "7", None, {}),
            ('echo "" && gh pr merge 7 -b ""', "7", None, {}),
            ("/opt/homebrew/bin/gh pr merge 7 --merge --delete-branch 2>&1 | tail -1", "7", None, {}),
            ("gh pr merge > log 7", "7", None, {}),
            ("gh pr merge 7 > /dev/null -R o/r", "7", "o/r", {}),
            ("gh pr merge 7 2>/dev/null >>log </dev/null -R o/r", "7", "o/r", {}),
            ("gh pr merge 2 > /dev/null 2>&1", "2", None, {}),
            ("gh pr merge 7>log", None, None, {}),
            ("gh pr merge '7'>log", "7", None, {}),
            ("gh pr merge 7 --subject ';' -R o/r", "7", "o/r", {}),
            ('gh pr merge 7 --subject "a && b | c (d)" -R o/r', "7", "o/r", {}),
            ("{ gh pr merge 7; }", "7", None, {}),
            ("! gh pr merge 7", "7", None, {}),
            ("if gh pr merge 7; then echo ok; fi", "7", None, {}),
            ("if true; then gh pr merge 7; fi", "7", None, {}),
            ("while true; do gh pr merge 7; done", "7", None, {}),
            ("time gh pr merge 7", "7", None, {}),
            ("command gh pr merge 7", "7", None, {}),
            ("nohup gh pr merge 7", "7", None, {}),
            ("exec gh pr merge 7", "7", None, {}),
            ("timeout 60 gh pr merge 7", "7", None, {}),
            ("/usr/bin/env gh pr merge 7", "7", None, {}),
            ("/usr/bin/time gh pr merge 7", "7", None, {}),
            ("/usr/bin/timeout 60 gh pr merge 7", "7", None, {}),
            ("noglob gh pr merge 7", "7", None, {}),
            ("builtin command gh pr merge 7", "7", None, {}),
            ("/usr/bin/env GH_REPO=o/r gh pr merge 7", "7", None, {"GH_REPO": "o/r"}),
            ("env GH_REPO=o/r gh pr merge 7", "7", None, {"GH_REPO": "o/r"}),
            ("GIT_DIR=x gh pr merge 7", "7", None, {"GIT_DIR": "x"}),
            (
                "GH_HOST=github.com GIT_WORK_TREE=w GH_REPO=o/r gh pr merge 7",
                "7",
                None,
                {"GH_HOST": "github.com", "GIT_WORK_TREE": "w", "GH_REPO": "o/r"},
            ),
            ("export NO_COLOR=1; X=1; gh pr merge 7", "7", None, {}),
            ("cat <<'EOF' > /tmp/x.md\ndon't\nEOF\ngh pr merge 7  # it's checked", "7", None, {}),
            ("cat <<EOF > a.txt\ndon't\nEOF\ngh pr merge 7\ncat <<EOF > b.txt\nwon't\nEOF", "7", None, {}),
            ("cat <<-EOF\n\tdon't\n\tEOF\ngh pr merge 7", "7", None, {}),
            ("cat <<A <<'B'\nit's\nA\nwon't\nB\ngh pr merge 7", "7", None, {}),
            ("cat <<EOF\n$HOME don't\nEOF\ngh pr merge 7", "7", None, {}),
            ("cat <<< \"it's\" && gh pr merge 7", "7", None, {}),
            ("gh pr merge --squash --body \"$(cat <<'EOF'\nsee \"PR 9 here\"\nEOF\n)\" 7", "7", None, {}),
            ('gh pr merge 7 --squash --body "$(echo "a -R o/r b")"', "7", None, {}),
            ("gh pr merge 7 --body \"$(cat <<'EOF'\ndon't :)\nEOF\n)\" -R o/r", "7", "o/r", {}),
            ('gh pr merge 7 --subject "$(git log -1 --format="%s")" -R o/r', "7", "o/r", {}),
            ("gh pr merge 7 -b \"`echo \"it's\"`\" -R o/r", "7", "o/r", {}),
            ("echo $'it\\'s'\ngh pr merge 7 # don't", "7", None, {}),
        ]
        self.views({"*": pr_view(NEXT)})
        for command, selector, repo, env in cases:
            with self.subTest(command=command):
                self.assertEqual(self.merge(command), ("ask", NO_RECORD), "記録の無い応答なので確認を求める")
                calls = self.calls()
                self.assertEqual([c["argv"] for c in calls], [view_argv(selector, repo)])
                self.assertEqual(calls[0]["env"], env, "コマンドの前置きの代入を gh pr view に渡す")

    def test_cd_の後のマージは_cd_の先で照合する(self) -> None:
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        cases = [
            (f"cd {self.repo} && gh pr merge 7 --merge", "7", self.repo),
            ("cd repo && gh pr merge 7", "7", self.repo),
            (f"cd '{self.repo}'\ngh pr merge 7", "7", self.repo),
            (f"pushd {self.repo}; gh pr merge 7", "7", self.repo),
            (f"builtin cd {self.repo} && gh pr merge 7", "7", self.repo),
            (f"cd {self.repo}; cd ../elsewhere && gh pr merge 7", "7", elsewhere),
            (f"cd {self.repo} && cd ../elsewhere && gh pr merge 7", "7", elsewhere),
            (f"cd {self.repo} && gh pr merge --merge", None, self.repo),
            (f"cat > run.sh <<'EOF'\ncd {self.repo}\nEOF\ngh pr merge 7", "7", self.tmp),
            # シェルの cd は `..` をリンクの先でなく字面で畳む
            ("cd repo/link/.. && gh pr merge 7", "7", self.repo),
        ]
        (elsewhere / "deep").mkdir()
        (self.repo / "link").symlink_to(elsewhere / "deep")
        self.views({"*": pr_view(NEXT)})
        for command, selector, where in cases:
            with self.subTest(command=command):
                self.assertEqual(self.merge(command, cwd=self.tmp), ("ask", NO_RECORD))
                calls = self.calls()
                self.assertEqual([c["argv"] for c in calls], [view_argv(selector)])
                self.assertEqual(os.path.realpath(calls[0]["cwd"]), os.path.realpath(where))

    def test_CDPATH_があれば相対の_cd_の先を不明として確認を求める(self) -> None:
        cdpath = {"CDPATH": str(self.tmp / "elsewhere")}
        self.views({"*": pr_view(NEXT)})
        self.assertEqual(self.merge("cd repo && gh pr merge 7", cwd=self.tmp, extra_env=cdpath), ("ask", UNRESOLVED))
        self.assertEqual(self.calls(), [], "gh を呼ばない")
        self.assertEqual([e.get("detail") for e in self.events()], ["cd"])
        for command in ("cd ./repo && gh pr merge 7", f"cd {self.repo} && gh pr merge 7"):
            with self.subTest(command=command):
                self.assertEqual(self.merge(command, cwd=self.tmp, extra_env=cdpath), ("ask", NO_RECORD))
                calls = self.calls()
                self.assertEqual(os.path.realpath(calls[0]["cwd"]), os.path.realpath(self.repo), "CDPATH を引かない形は追う")

    def test_PR_を特定できないマージは_gh_を呼ばずに確認を求める(self) -> None:
        cases = [
            ("cd sub && gh pr merge 7", "cd"),
            ("pushd sub; gh pr merge --merge", "cd"),
            ('cd "$D" && gh pr merge 7', "cd"),
            ("cd ~/repo && gh pr merge 7", "cd"),
            ("cd `pwd` && gh pr merge 7", "cd"),
            ("cd && gh pr merge 7", "cd"),
            ("cd - && gh pr merge 7", "cd"),
            (f"cd -P {self.repo} && gh pr merge 7", "cd"),
            (f"cd {self.repo} {self.repo} && gh pr merge 7", "cd"),
            (f"cd {self.repo}/missing/.. && gh pr merge 7", "cd"),
            (f"( cd {self.repo}; gh pr merge 7 )", "cd"),
            (f"(cd {self.repo}); gh pr merge 7", "cd"),
            (f"true || cd {self.repo}; gh pr merge 7", "cd"),
            (f"true && cd {self.repo}; gh pr merge 7", "cd"),
            (f"cd {self.repo} | gh pr merge 7", "cd"),
            (f"cd {self.repo} & gh pr merge 7", "cd"),
            (f"pushd {self.repo}; popd; gh pr merge 7", "cd"),
            (f"if true; then cd {self.repo}; fi; gh pr merge 7", "cd"),
            (f"true && cd {self.repo} && cd ../elsewhere; gh pr merge 7", "cd"),
            ('gh pr merge "$N" --merge', "dollar"),
            ("gh pr merge `cat n` --merge", "dollar"),
            ("gh pr merge 7 -R '$REPO'", "dollar"),
            ("GH_REPO=$R gh pr merge 7", "dollar"),
            ("for p in 7 8; do gh pr merge $p; done", "dollar"),
            ("gh pr merge 7 -R not-a-repo", "shape"),
            ("gh pr merge 'a b'", "shape"),
            ("env -i gh pr merge 7", "prefix_option"),
            ("time -p gh pr merge 7", "prefix_option"),
            ("timeout -s KILL 60 gh pr merge 7", "prefix_option"),
            ('gh pr merge 7 --body "x', "quote"),
            ("gh pr merge 1 2", "shape"),
            ("gh pr merge 7 2>x 8", "shape"),
            ("export GH_REPO=o/r; gh pr merge 7", "env"),
            ("export GH_REPO=o/r && gh pr merge 7", "env"),
            ("GH_REPO=o/r; gh pr merge 7", "env"),
            ("declare -x GIT_DIR=x\ngh pr merge 7", "env"),
            ("typeset -x GH_HOST=h; gh pr merge 7", "env"),
            ("unset GIT_WORK_TREE; gh pr merge 7", "env"),
            ("PATH=/tmp/bin gh pr merge 7", "env"),
            ("GIT_CONFIG_COUNT=1 gh pr merge 7", "env"),
            ("GIT_DIR=$D gh pr merge 7", "dollar"),
            ("GIT_DIR=`pwd`/.git gh pr merge 7", "dollar"),
            ("r=$(gh pr merge 7)", "substitution"),
            ('x="$(gh pr merge 7 2>&1)"', "substitution"),
            ("echo `gh pr merge 7`", "substitution"),
            ("echo $(echo $(gh pr merge 7))", "substitution"),
            ("echo `echo $(gh pr merge 7)`", "substitution"),
            ("cat <<EOF\n$(gh pr merge 7)\nEOF", "substitution"),
            ("cat <<EOF\ngh pr merge 7", "quote"),
            ("echo $(gh pr merge 7", "quote"),
            ("echo `gh pr merge 7", "quote"),
            ("git switch feat && gh pr merge --merge", "no_selector_after_command"),
            ("gh pr checkout 8\ngh pr merge --squash", "no_selector_after_command"),
        ]
        for command, detail in cases:
            with self.subTest(command=command):
                self.assertEqual(self.merge(command, cwd=self.tmp), ("ask", UNRESOLVED))
                self.assertEqual(self.calls(), [], "gh を呼ばない")
                events = self.events()
                (self.store / "events.jsonl").unlink()
                self.assertEqual(
                    [(e["level"], e["event"], e["reason"], e.get("detail")) for e in events],
                    [("warn", "merge_checked", "target_unresolved", detail)],
                )

    def assertUnresolved(self, command: str, detail: str, extra_env: dict[str, str] | None = None) -> None:
        self.assertEqual(self.merge(command, cwd=self.tmp, extra_env=extra_env), ("ask", UNRESOLVED))
        self.assertEqual(self.calls(), [], "gh を呼ばない")
        events = self.events()
        (self.store / "events.jsonl").unlink()
        self.assertEqual(
            [(e["level"], e["event"], e["reason"], e.get("detail")) for e in events],
            [("warn", "merge_checked", "target_unresolved", detail)],
        )

    def test_シェルか起動役に渡すマージは_gh_を呼ばずに確認を求める(self) -> None:
        commands = [
            "bash <<'EOF'\ngh pr merge 7\nEOF",
            "cat <<EOF | sh\ngh pr merge 7\nEOF",
            "sh -c 'gh pr merge 7'",
            'eval "gh pr merge 7"',
            "echo 7 | xargs gh pr merge",
            "sudo gh pr merge 7",
            "x=$(bash -c 'gh pr merge 7')",
            "x=`y=$(bash -c 'gh pr merge 7')`",
            "/bin/zsh -c 'gh pr merge 7'",
            "env bash -c 'gh pr merge 7'",
            "/usr/bin/env bash -c 'gh pr merge 7'",
            'builtin eval "gh pr merge 7"',
            "env -i bash <<'EOF'\ngh pr merge 7\nEOF",
            "cat <<EOF | timeout -s KILL 60 sh\ngh pr merge 7\nEOF",
            "source ./merge.sh  # gh pr merge 7",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertUnresolved(command, "nested")
        self.assertIsNone(self.merge("cat > f.md <<'EOF'\ngh pr merge 7\nEOF"), "シェルに渡さない本文は読まない")
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.store / "events.jsonl").exists(), "ログも書かない")

    def test_照合で通るマージとシェルに渡すマージが並べば確認を求める(self) -> None:
        self.assertIsNone(self.merge("gh pr merge 7"), "7 だけなら照合で通る")
        self.calls()
        (self.store / "events.jsonl").unlink()
        self.assertEqual(self.merge("gh pr merge 7 && sh -c 'gh pr merge 8'"), ("ask", UNRESOLVED))
        self.assertEqual([c["argv"] for c in self.calls()], [view_argv("7")], "読めるマージは照合する")
        self.assertEqual(
            sorted((e["reason"], e.get("detail")) for e in self.events()),
            [("pass", None), ("target_unresolved", "nested")],
        )

    def test_github_com_以外の_host_のマージは_gh_を呼ばずに確認を求める(self) -> None:
        cases = [
            ("gh pr merge 7 -R evil.example/o/r", None),
            ("gh pr merge https://evil.example/o/r/pull/7", None),
            ("GH_HOST=evil.example gh pr merge 7", None),
            ("GH_REPO=evil.example/o/r gh pr merge 7", None),
            ("gh pr merge 7", {"GH_HOST": "evil.example"}),
            ("gh pr merge 7", {"GH_REPO": "evil.example/o/r"}),
            ("gh pr merge 7", {"GH_REPO": "https://evil.example/o/r"}),
            ("gh pr merge 7 -R o/r", {"GH_HOST": "evil.example"}),
        ]
        for command, extra_env in cases:
            with self.subTest(command=command, env=extra_env):
                self.assertUnresolved(command, "host", extra_env)
        self.views({"*": pr_view(NEXT)})
        allowed = [
            ("gh pr merge 7 -R github.com/o/r", None, view_argv("7", "github.com/o/r")),
            ("gh pr merge 7 -R GitHub.com/o/r", None, view_argv("7", "GitHub.com/o/r")),
            ("gh pr merge 7 -R o/r", None, view_argv("7", "o/r")),
            ("gh pr merge 7", {"GH_HOST": "github.com"}, view_argv("7")),
            ("gh pr merge 7", {"GH_REPO": "github.com/example/demo"}, view_argv("7")),
        ]
        for command, extra_env, argv in allowed:
            with self.subTest(command=command, env=extra_env):
                self.assertEqual(self.merge(command, extra_env=extra_env), ("ask", NO_RECORD))
                self.assertEqual([c["argv"] for c in self.calls()], [argv], "github.com なら照合する")

    def test_1_つのコマンドの_2_つのマージは強いほうの判定になる(self) -> None:
        url8 = "https://github.com/example/demo/pull/8"
        after = self.commit_after_gate()
        self.views({"7": pr_view(self.head), "8": pr_view(after, commits=[self.head, after], url=url8)})
        for command in ("gh pr merge 7 && gh pr merge 8", "gh pr merge 8\ngh pr merge 7"):
            with self.subTest(command=command):
                decision, reason = self.merge(command)
                self.assertEqual(decision, "deny")
                self.assertIn("gate-reviewer に渡して", reason)
                self.assertEqual(sorted(c["argv"][-1] for c in self.calls()), ["7", "8"])
        self.assertEqual(
            sorted(self.checked()),
            sorted([("info", "pass", PR_URL, self.head), ("warn", "commits_after_gate", url8, after)] * 2),
        )
        url9 = "https://github.com/example/demo/pull/9"
        self.views({"8": pr_view(after, commits=[self.head, after], url=url8), "9": pr_view(NEXT, url=url9)})
        for command in ("gh pr merge 9; gh pr merge 8", "gh pr merge 8; gh pr merge 9"):
            with self.subTest(command=command):
                self.assertEqual(self.merge(command)[0], "deny", "止めるは確認より強い")
        self.views({"7": pr_view(self.head), "8": pr_view(NEXT, url=url8)})
        for command in ("gh pr merge 7; gh pr merge 8", "gh pr merge 8; gh pr merge 7"):
            with self.subTest(command=command):
                self.assertEqual(self.merge(command), ("ask", NO_RECORD.replace("#7", "#8")), "確認は通すより強い")

    def test_マージでないコマンドは_gh_を呼ばずに何も出力しない(self) -> None:
        self.views({"*": pr_view(NEXT)})
        commands = [
            'git commit -m "gh pr merge 7"',
            "grep 'gh pr merge' f",
            "gh pr merge --disable-auto 7",
            "gh pr view 7",
            "echo gh pr merge 7",
            "cat <<'EOF'\nit's\nEOF",
            "cat <<'EOF'\ngh pr merge 7\nEOF",
            "cat <<'EOF'\n$(gh pr merge 7)\nEOF",
            "cat <<-EOF\n\tgh pr merge 7\n\tEOF",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(self.merge(command))
                self.assertEqual(self.calls(), [])
        self.assertIsNone(self.merge("gh pr merge 7", tool_name="Write"))
        self.assertIsNone(self.decision(b"{not json", self.data))
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.checked(), [])
        self.assertEqual(self.merge("gh pr merge 7"), ("ask", NO_RECORD), "同じ偽の gh でマージは照合する")
        self.assertEqual(len(self.calls()), 1)

    def test_壊れた記録は記録なしとして確認を求め警告を残す(self) -> None:
        saved = json.loads(self.record_path().read_text(encoding="ascii"))
        broken = [
            json.dumps({**saved, "repo_path": "x" * 4096}),
            "not json",
            json.dumps({**saved, "body_sha256": 1}),
            json.dumps({k: v for k, v in saved.items() if k != "recorded_at"}),
            json.dumps({**saved, "head": NEXT}),
            json.dumps({**saved, "repo": "github.com/other/demo"}),
        ]
        for text in broken:
            with self.subTest(text=text[:60]):
                self.record_path().write_text(text, encoding="ascii")
                self.assertEqual(self.merge("gh pr merge 7"), ("ask", NO_RECORD))
                events = self.events()
                (self.store / "events.jsonl").unlink()
                self.assertEqual(
                    [(e["level"], e["event"], e["reason"]) for e in events],
                    [("warn", "record_unreadable", None), ("warn", "merge_checked", "no_record")],
                )
                self.assertEqual((events[0]["repo"], events[0]["head"]), (REPO, self.head))
        self.record_path().write_text(json.dumps(saved), encoding="ascii")
        self.assertIsNone(self.merge("gh pr merge 7"), "壊れていない記録なら通る")

    def test_記録のパスがリンクなら記録なしとして確認を求める(self) -> None:
        target = self.tmp / "elsewhere.json"
        self.record_path().rename(target)
        self.record_path().symlink_to(target)
        self.assertEqual(self.merge("gh pr merge 7"), ("ask", NO_RECORD))

    def test_CLAUDE_PLUGIN_DATA_が無ければ記録なしとして確認を求める(self) -> None:
        self.assertEqual(self.merge("gh pr merge 7", data=None), ("ask", NO_RECORD))
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.checked(), [], "ログは書けない")

    def test_照合の内部エラーは型名だけを付けて確認を求める(self) -> None:
        for launcher in (RUN_RAISES, BASENAME_RAISES):
            with self.subTest(launcher=launcher):
                result = self.merge("gh pr merge 7", launcher=("-c", launcher))
                self.assertEqual(
                    result,
                    (
                        "ask",
                        "ゲートの記録との照合が途中で失敗しました(RuntimeError)。このままマージしてよいか確認してください。",
                    ),
                )
                events = self.events()
                (self.store / "events.jsonl").unlink()
                self.assertEqual(
                    [(e["level"], e["event"], e["reason"], e.get("error_type")) for e in events],
                    [("error", "merge_checked", "internal_error", "RuntimeError")],
                )
                self.assertNotIn("報告にだけある語", json.dumps(events, ensure_ascii=False), "例外の中身を書かない")

    def test_照合のログに本文を書かない(self) -> None:
        self.views({"7": pr_view(self.head, body=BODY + SECRET)})
        self.assertEqual(self.merge("gh pr merge 7")[0], "deny")
        self.assertNotIn(SECRET, json.dumps(self.events(), ensure_ascii=False))


class MergeGateMainMergeTest(MergeGateCheckCase):
    """ゲートの後に origin の main を取り込んだだけのマージコミットの照合。"""

    def setUp(self) -> None:
        super().setUp()
        origin = self.tmp / "origin.git"
        git(self.tmp, "init", "-q", "--bare", str(origin))
        git(self.repo, "push", "-q", str(origin), "HEAD:refs/heads/main")
        self.root = self.head
        self.upstream = self.tmp / "upstream"
        git(self.tmp, "clone", "-q", "-b", "main", str(origin), str(self.upstream))
        git(self.repo, "switch", "-q", "-c", "feat")
        (self.repo / "README.md").write_text("demo\nfeat\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "feat")
        self.gated = git(self.repo, "rev-parse", "HEAD")
        self.record(handback(self.approve(head=self.gated)))
        self.assertTrue(self.record_path(self.gated).exists(), "ステップ 1 の形でコミット A にマージ可を記録した")
        (self.store / "events.jsonl").unlink()
        git(self.repo, "remote", "set-url", "origin", str(origin))

    def push_upstream(self, name: str, text: str, branch: str = "main") -> None:
        """origin の branch にファイル name を text にするコミットを積む。"""
        git(self.upstream, "switch", "-q", "-C", branch, "origin/main")
        (self.upstream / name).write_text(text, encoding="utf-8")
        git(self.upstream, "add", name)
        git(self.upstream, "commit", "-q", "-m", name)
        git(self.upstream, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")

    def merge_origin(self, branch: str = "main") -> str:
        git(self.repo, "fetch", "-q", "origin")
        git(self.repo, "merge", "-q", "--no-edit", f"origin/{branch}")
        return git(self.repo, "rev-parse", "HEAD")

    def merge_origin_with(self, name: str) -> str:
        """origin の main を取り込むマージに、ゲートを通していないファイル name を足してコミットし、その SHA を返す。"""
        git(self.repo, "fetch", "-q", "origin")
        git(self.repo, "merge", "-q", "--no-commit", "--no-ff", "origin/main")
        (self.repo / name).write_text("ゲートを通していない変更\n", encoding="utf-8")
        git(self.repo, "add", name)
        git(self.repo, "commit", "-q", "--no-edit")
        return git(self.repo, "rev-parse", "HEAD")

    def assertDenied(self, head: str, commits: list[str], kind: str, detail: str, **kwargs: object) -> str:
        """照合が kind で止め、events.jsonl の merge_checked が kind と detail を載せることを確かめ、理由を返す。"""
        self.views({"7": pr_view(head, commits=commits)})
        decision, reason = self.merge("gh pr merge 7 --merge", **kwargs)
        self.assertEqual(decision, "deny")
        self.assertEqual(self.merge_events(), [(kind, detail, head)])
        return reason

    def test_main_を競合なしで取り込んだだけの_PR_は通る(self) -> None:
        self.push_upstream("main.txt", "main\n")
        merged = self.merge_origin()
        self.views({"7": pr_view(merged, commits=[self.gated, merged])})
        self.assertIsNone(self.merge("gh pr merge 7 --merge"))
        self.assertEqual(self.merge_events(), [("pass", "main_merge_only", merged)])
        (self.store / "events.jsonl").unlink()
        self.push_upstream("main2.txt", "main2\n")
        again = self.merge_origin()
        self.views({"7": pr_view(again, commits=[self.gated, merged, again])})
        self.assertIsNone(self.merge("gh pr merge 7 --merge"), "2 回の取り込みも通る")
        self.assertEqual(self.merge_events(), [("pass", "main_merge_only", again)])

    def test_main_を取り込んだ後に本文を追記した_PR_は止める(self) -> None:
        self.push_upstream("main.txt", "main\n")
        merged = self.merge_origin()
        self.views({"7": pr_view(merged, body=BODY + "ゲートの後に足した行\n", commits=[self.gated, merged])})
        decision, reason = self.merge("gh pr merge 7 --merge")
        self.assertEqual(decision, "deny")
        self.assertIn("ゲートの判定の後に PR 本文が変わった。", reason)
        self.assertEqual(self.merge_events(), [("body_changed", "main_merge_only", merged)])

    def test_競合を手で解いたマージは止める(self) -> None:
        self.push_upstream("README.md", "demo\nmain\n")
        git(self.repo, "fetch", "-q", "origin")
        conflicted = subprocess.run(
            ["git", "-C", str(self.repo), "merge", "-q", "--no-edit", "origin/main"],
            capture_output=True,
            env={**os.environ, **GIT_ENV},
        )
        self.assertNotEqual(conflicted.returncode, 0, "README.md が競合する")
        (self.repo / "README.md").write_text("demo\nfeat\nmain\n", encoding="utf-8")
        git(self.repo, "commit", "-q", "-am", "resolve")
        resolved = git(self.repo, "rev-parse", "HEAD")
        self.assertDenied(resolved, [self.gated, resolved], "commits_after_gate", "conflict")

    def test_取り込みに別の変更を足したマージは止める(self) -> None:
        self.push_upstream("main.txt", "main\n")
        evil = self.merge_origin_with("extra.txt")
        self.assertDenied(evil, [self.gated, evil], "commits_after_gate", "tree_mismatch")

    def test_古い取り込みに別の変更を足し新しい取り込みが正しいマージは止める(self) -> None:
        self.push_upstream("main.txt", "main\n")
        evil = self.merge_origin_with("extra.txt")
        self.push_upstream("main2.txt", "main2\n")
        merged = self.merge_origin()
        self.assertDenied(merged, [self.gated, evil, merged], "commits_after_gate", "tree_mismatch")

    def test_古い取り込みが正しく新しい取り込みに別の変更を足したマージは止める(self) -> None:
        self.push_upstream("main.txt", "main\n")
        merged = self.merge_origin()
        self.push_upstream("main2.txt", "main2\n")
        evil = self.merge_origin_with("extra.txt")
        self.assertDenied(evil, [self.gated, merged, evil], "commits_after_gate", "tree_mismatch")

    def test_main_でない枝の取り込みは止める(self) -> None:
        self.push_upstream("other.txt", "other\n", branch="other")
        merged = self.merge_origin("other")
        self.assertDenied(merged, [self.gated, merged], "commits_after_gate", "not_base")

    def test_取り込みの後の通常のコミットは止める(self) -> None:
        self.push_upstream("main.txt", "main\n")
        merged = self.merge_origin()
        after = self.commit_after_gate()
        reason = self.assertDenied(after, [self.gated, merged, after], "commits_after_gate", "not_merge")
        self.assertNotIn("main の取り込みだけと確かめられなかった。", reason)

    def test_通常のコミットの後の取り込みは止める(self) -> None:
        self.push_upstream("main.txt", "main\n")
        after = self.commit_after_gate()
        merged = self.merge_origin()
        self.assertDenied(merged, [self.gated, after, merged], "commits_after_gate", "not_merge")

    def test_git_replace_で取り込みに見せた通常のコミットは止める(self) -> None:
        self.push_upstream("main.txt", "main\n")
        after = self.commit_after_gate("evil.txt")
        git(self.repo, "switch", "-q", "--detach", self.gated)
        disguise = self.merge_origin()
        git(self.repo, "replace", after, disguise)
        git(self.repo, "switch", "-q", "feat")
        self.assertEqual(len(git(self.repo, "rev-list", "--parents", "-1", after).split()), 3, "置き換えで親が 2 つに見える")
        self.assertDenied(after, [self.gated, after], "commits_after_gate", "not_merge")

    def test_main_と別の枝を一度に取り込んだマージは止める(self) -> None:
        self.push_upstream("other.txt", "other\n", branch="other")
        self.push_upstream("main.txt", "main\n")
        git(self.repo, "fetch", "-q", "origin")
        git(self.repo, "merge", "-q", "--no-edit", "origin/main", "origin/other")
        octopus = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(len(git(self.repo, "rev-list", "--parents", "-1", octopus).split()), 4, "親が 3 つのマージ")
        self.assertDenied(octopus, [self.gated, octopus], "commits_after_gate", "not_merge")

    def test_ゲートのコミットを含まない枝のマージは止める(self) -> None:
        self.push_upstream("main.txt", "main\n")
        git(self.repo, "switch", "-q", "-c", "side", self.root)
        git(self.repo, "fetch", "-q", "origin")
        git(self.repo, "merge", "-q", "--no-edit", "--no-ff", "origin/main")
        merged = git(self.repo, "rev-parse", "HEAD")
        self.assertDenied(merged, [self.gated, merged], "commits_after_gate", "not_ancestor")

    def test_取り込みは_20_回まで通し_21_回目で止める(self) -> None:
        commits = [self.gated]
        for i in range(21):
            self.push_upstream(f"main{i}.txt", f"{i}\n")
            commits.append(self.merge_origin())
        twenty = commits[20]
        self.views({"7": pr_view(twenty, commits=commits[:21])})
        self.assertIsNone(self.merge("gh pr merge 7 --merge"), "20 回の取り込みは通る")
        (self.store / "events.jsonl").unlink()
        self.assertDenied(commits[21], commits, "commits_after_gate", "too_many_merges")

    def test_確かめられない取り込みは理由を足して止める(self) -> None:
        self.push_upstream("main.txt", "main\n")
        merged = self.merge_origin()
        real_git = shutil.which("git")
        old_git = self.tmp / "old-git"
        old_git.mkdir()
        fake = old_git / "git"
        fake.write_text(
            f'#!/bin/sh\nfor a; do [ "$a" = merge-tree ] && exit 129; done\nexec {real_git} "$@"\n', encoding="ascii"
        )
        fake.chmod(0o755)
        slow_git = self.tmp / "slow-git"
        slow_git.mkdir()
        (slow_git / "git").write_text("#!/bin/sh\nexec sleep 30\n", encoding="ascii")
        (slow_git / "git").chmod(0o755)
        gh_path = f"{self.bin}{os.pathsep}{os.environ['PATH']}"
        cases = [
            ("missing_commit", None, NEXT, {}),
            ("git_failed", 129, merged, {"path": f"{old_git}{os.pathsep}{gh_path}"}),
            ("git_failed", None, merged, {"path": str(self.bin)}),
            ("timeout", None, merged, {"path": f"{slow_git}{os.pathsep}{gh_path}", "launcher": ("-c", SHORT_TIMEOUT)}),
        ]
        for detail, exit_code, head, kwargs in cases:
            with self.subTest(detail=detail, exit_code=exit_code):
                started = time.monotonic()
                reason = self.assertDenied(head, [self.gated, head], "merge_unverified", detail, **kwargs)
                self.assertLess(time.monotonic() - started, 10, "git の上限で打ち切る")
                self.assertEqual(
                    [e.get("exit_code") for e in self.events()], [exit_code], "git の非 0 の終了だけ終了コードを載せる"
                )
                (self.store / "events.jsonl").unlink()
                self.assertEqual(
                    reason,
                    f"ゲートの判定({self.gated[:7]})の後に head が {head[:7]} へ進んだ。main の取り込みだけと確かめられなかった。"
                    f"{self.gated[:7]}..{head[:7]} のコミットと PR 本文の差分を gate-reviewer に渡して判定を取り直してから、"
                    "実行し直す(develop 8.)。",
                )
        for base in ("../main", "-main", "ma in"):
            with self.subTest(base=base):
                self.views({"7": pr_view(merged, commits=[self.gated, merged], base=base)})
                self.assertEqual(self.merge("gh pr merge 7 --merge")[0], "deny")
                self.assertEqual(self.merge_events(), [("merge_unverified", "base_shape", merged)])
                (self.store / "events.jsonl").unlink()
        shutil.rmtree(self.repo)
        self.assertDenied(merged, [self.gated, merged], "merge_unverified", "missing_repo", cwd=self.tmp)

    def test_hook_の環境の_GIT_DIR_に依らず記録の作業ツリーで確かめる(self) -> None:
        self.push_upstream("main.txt", "main\n")
        merged = self.merge_origin()
        self.views({"7": pr_view(merged, commits=[self.gated, merged])})
        elsewhere = {"GIT_DIR": str(self.upstream / ".git"), "GIT_WORK_TREE": str(self.upstream)}
        self.assertIsNone(self.merge("gh pr merge 7 --merge", extra_env=elsewhere))
        self.assertEqual(self.merge_events(), [("pass", "main_merge_only", merged)])
