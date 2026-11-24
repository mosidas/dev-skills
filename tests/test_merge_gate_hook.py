"""gate-reviewer の判定を記録する hook(`merge_gate.py`)の単体テスト。

hook は `sys.exit` を呼び、`CLAUDE_PLUGIN_DATA` の下に記録とログを書くため、すべて `CLAUDE_PLUGIN_DATA` を
一時ディレクトリに向けたサブプロセスで確かめる。入力は実機で観測した形にする。auto モードでは
PostToolUse(SubagentHandback)の `tool_input.message` に、default モードでは SubagentStop の
`last_assistant_message` に報告が入る。記録する入力と記録しない入力を対で書く。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import hashlib
import json
import os
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
# hook 自身の不具合を起こす。git の呼び出しが hook の想定しない例外を送出する
GIT_RAISES = (
    "import runpy, subprocess, sys\n"
    "def broken(*args, **kwargs):\n"
    "    raise RuntimeError('報告にだけある語')\n"
    "subprocess.run = broken\n"
    "runpy.run_path(sys.argv[1], run_name='__main__')\n"
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


class MergeGateRecordTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data = self.tmp / "data"
        self.store = self.data / "merge-gate"
        self.repo = self.tmp / "repo"
        self.head = make_repo(self.repo)
        self.body = self.tmp / "scratch" / "pr-body.md"
        self.body.parent.mkdir()
        self.body.write_bytes(BODY.encode("utf-8"))

    def run_hook(
        self, payload: object, data: Path | None = None, path: str | None = None, launcher: tuple[str, ...] = ()
    ) -> None:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"}
        env.update(GIT_ENV)
        if path is not None:
            env["PATH"] = path
        if data is not None:
            env["CLAUDE_PLUGIN_DATA"] = str(data)
        stdin = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        proc = subprocess.run([sys.executable, *launcher, str(HOOK)], input=stdin, capture_output=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stdout, b"", "hook は標準出力を書かない")
        self.assertEqual(proc.stderr, b"", "hook は標準エラーを書かない")

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
        self.run_hook(handback(self.approve()), self.data, launcher=("-c", GIT_RAISES))
        self.assertEqual(list(self.store.glob("*.json")), [], "記録を書かない")
        events = self.events()
        self.assertEqual(
            [(e["level"], e["event"], e["reason"], e.get("error_type")) for e in events],
            [("error", "gate_not_recorded", "hook_error", "RuntimeError")],
        )
        self.assertNotIn("報告にだけある語", json.dumps(events, ensure_ascii=False), "例外の中身を書かない")
        self.run_hook(handback(self.approve()), self.data)
        self.assertTrue(self.record_path().exists(), "起動役が無ければ同じ報告で記録する")

    def test_JSON_として読めない入力でも止めない(self) -> None:
        self.record(b"\xff not json")
        self.record(b"[]")
        self.assertFalse(self.store.exists())
