"""build の loop.py(反復の起動と停止条件の判定)に対する単体テスト。

parse_progress は直接 import して呼び、起動の回数・exit code・出力が絡む検査は
サブプロセスで確かめる。claude は起動せず、環境変数 BUILD_AGENT_CMD に
一時ディレクトリへ書いたスタブを指定する。スタブは起動されるたびに手順の
リスト(steps.json)から次の 1 件を進捗ファイルに適用する。
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import unittest

import helpers

SCRIPTS = helpers.REPO_ROOT / "skills" / "build" / "scripts"
SCRIPT = SCRIPTS / "loop.py"

sys.path.insert(0, str(SCRIPTS))

import loop  # noqa: E402

HEADER = "| 日時 | タスク | 結果 | PR | 要点 |\n| :-- | :-- | :-- | :-- | :-- |\n"


def _progress(stop: str = "なし", max_failures: str = "3", rows: str = "") -> str:
    return (
        "# build: demo\n\n"
        "- PRD: docs/prd.md\n"
        f"- 失敗の上限: {max_failures}\n"
        f"- 停止: {stop}\n\n"
        "## 要判断\n\n"
        "## 記録\n\n"
        f"{HEADER}{rows}"
    )


def _row(task: str, result: str) -> str:
    return f"| 2026-10-11 12:00 | {task} | {result} | - | 要点 |\n"


STUB = r'''
import json, sys
from pathlib import Path

here = Path(__file__).resolve().parent
count_file = here / "count"
count = int(count_file.read_text()) if count_file.exists() else 0
count_file.write_text(str(count + 1))
with (here / "args.jsonl").open("a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\n")

steps = json.loads((here / "steps.json").read_text(encoding="utf-8"))
step = steps[count]
progress = here / "progress.md"
text = progress.read_text(encoding="utf-8")
if step["op"] == "append":
    progress.write_text(text + step["line"], encoding="utf-8")
elif step["op"] == "stop":
    lines = [
        "- 停止: " + step["value"] if l.startswith("- 停止:") else l
        for l in text.split("\n")
    ]
    progress.write_text("\n".join(lines), encoding="utf-8")
elif step["op"] == "exit":
    sys.exit(step["code"])
'''


class ParseProgressTest(unittest.TestCase):
    def test_見出しと区切りの行を失敗に数えない(self) -> None:
        progress = loop.parse_progress(_progress())
        self.assertEqual(progress, {"stop": "なし", "max_failures": 3, "failures": {}})

    def test_セル前後の空白を無視して失敗を数える(self) -> None:
        rows = "|2026-10-11|   TASK-1   |失敗|-|x|\n" + _row("TASK-1", "失敗") + _row("TASK-2", "完了")
        progress = loop.parse_progress(_progress(rows=rows))
        self.assertEqual(progress["failures"], {"TASK-1": 2})

    def test_解決済みの失敗を数えない(self) -> None:
        rows = _row("TASK-1", "失敗(解決済み)") + _row("TASK-1", "失敗")
        progress = loop.parse_progress(_progress(rows=rows))
        self.assertEqual(progress["failures"], {"TASK-1": 1})

    def test_停止の行が無いとValueErrorを送出する(self) -> None:
        text = _progress().replace("- 停止: なし\n", "")
        with self.assertRaises(ValueError):
            loop.parse_progress(text)

    def test_失敗の上限の行が無いとValueErrorを送出する(self) -> None:
        text = _progress().replace("- 失敗の上限: 3\n", "")
        with self.assertRaises(ValueError):
            loop.parse_progress(text)

    def test_失敗の上限が0だとValueErrorを送出する(self) -> None:
        with self.assertRaises(ValueError):
            loop.parse_progress(_progress(max_failures="0"))

    def test_失敗の上限が数字でないとValueErrorを送出する(self) -> None:
        with self.assertRaises(ValueError):
            loop.parse_progress(_progress(max_failures="三"))

    def test_SKILLmdの進捗ファイルの雛形を解析できる(self) -> None:
        skill = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
        template = skill.split("```markdown\n", 1)[1].split("\n```", 1)[0]
        progress = loop.parse_progress(template)
        self.assertEqual(progress, {"stop": "なし", "max_failures": 3, "failures": {}})


class LoopRunTest(helpers.TempDirTestCase):
    def run_loop(
        self, progress_text: str, steps: list[dict], *args: str
    ) -> subprocess.CompletedProcess:
        self.progress = self.write("progress.md", progress_text)
        self.write("steps.json", json.dumps(steps, ensure_ascii=False))
        stub = self.write("stub.py", STUB)
        env = dict(os.environ, BUILD_AGENT_CMD=shlex.join([sys.executable, str(stub)]))
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.progress), *args],
            capture_output=True,
            text=True,
            env=env,
        )

    def launches(self) -> int:
        count = self.tmp / "count"
        return int(count.read_text()) if count.exists() else 0

    def test_全Doneが書かれると0で終わる(self) -> None:
        steps = [{"op": "append", "line": _row("TASK-1", "完了")}, {"op": "stop", "value": "全 Done"}]
        proc = self.run_loop(_progress(), steps)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.launches(), 2)

    def test_起動前から停止していればスタブを起動せず1で終わる(self) -> None:
        proc = self.run_loop(_progress(stop="要判断(TASK-3)"), [])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.launches(), 0)
        self.assertIn("要判断(TASK-3)", proc.stdout)

    def test_同一タスクの失敗が上限に達すると次を起動しない(self) -> None:
        steps = [{"op": "append", "line": _row("TASK-2", "失敗")}] * 3
        proc = self.run_loop(_progress(), steps)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.launches(), 3)
        self.assertIn("TASK-2", proc.stdout)

    def test_別々のタスクの失敗の合計が上限を超えても止まらない(self) -> None:
        steps = [{"op": "append", "line": _row(f"TASK-{i}", "失敗")} for i in range(4)]
        steps.append({"op": "stop", "value": "全 Done"})
        proc = self.run_loop(_progress(), steps)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(self.launches(), 5)

    def test_進捗ファイルが変わらないと1回で1で終わる(self) -> None:
        proc = self.run_loop(_progress(), [{"op": "noop"}, {"op": "noop"}])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.launches(), 1)
        self.assertIn("進捗ファイルが更新されなかった", proc.stdout)

    def test_スタブが非0で終わると1で終わる(self) -> None:
        proc = self.run_loop(_progress(), [{"op": "exit", "code": 3}, {"op": "noop"}])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.launches(), 1)

    def test_反復の上限に達すると1で終わる(self) -> None:
        steps = [{"op": "append", "line": _row("TASK-1", "完了")}] * 3
        proc = self.run_loop(_progress(), steps, "--max-iterations", "2")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.launches(), 2)

    def test_最後の反復で全Doneになると0で終わる(self) -> None:
        steps = [{"op": "stop", "value": "全 Done"}]
        proc = self.run_loop(_progress(), steps, "--max-iterations", "1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.launches(), 1)

    def test_反復の上限に0を渡すと2で終わる(self) -> None:
        proc = self.run_loop(_progress(), [], "--max-iterations", "0")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(self.launches(), 0)

    def test_起動するコマンドが無いと1で終わりトレースバックを出さない(self) -> None:
        self.progress = self.write("progress.md", _progress())
        env = dict(os.environ, BUILD_AGENT_CMD=str(self.tmp / "no-such-command"))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.progress)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("コマンドが見つからない", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_区切りより後ろの引数がプロンプトの後ろに順に渡る(self) -> None:
        steps = [{"op": "stop", "value": "全 Done"}]
        proc = self.run_loop(_progress(), steps, "--", "--model", "opus", "--verbose")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        args = json.loads((self.tmp / "args.jsonl").read_text(encoding="utf-8").splitlines()[0])
        prompt = loop.PROMPT.format(path=self.progress.resolve())
        self.assertEqual(args, [prompt, "--model", "opus", "--verbose"])

    def test_停止の行が無い進捗ファイルでは2で終わる(self) -> None:
        proc = self.run_loop(_progress().replace("- 停止: なし\n", ""), [])
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(self.launches(), 0)
        self.assertTrue(proc.stderr.strip())


if __name__ == "__main__":
    unittest.main()
