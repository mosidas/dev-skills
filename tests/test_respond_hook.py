"""SessionStart hook(`inject_respond.py`)の単体テスト。

frontmatter の除去はライブラリ関数を直接呼んで確かめ、標準出力への注入とスキルが
無い環境での素通しはサブプロセスで確かめる(hook は `sys.exit` を呼ぶため)。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import helpers

HOOKS = helpers.REPO_ROOT / "hooks"
INJECT_RESPOND = HOOKS / "inject_respond.py"

sys.path.insert(0, str(HOOKS))

import inject_respond as hook  # noqa: E402


class StripFrontmatterTest(unittest.TestCase):
    def test_先頭のfrontmatterを取り除く(self) -> None:
        text = "---\nname: respond\ndescription: x\n---\n\n# 応答の形\n\n本文\n"
        self.assertEqual(hook.strip_frontmatter(text), "# 応答の形\n\n本文")

    def test_本文中の区切り線を残す(self) -> None:
        text = "# 見出し\n\n上\n\n---\n\n下\n"
        self.assertEqual(hook.strip_frontmatter(text), text.rstrip("\n"))


class HookProcessTest(helpers.TempDirTestCase):
    def run_hook(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(INJECT_RESPOND)],
            input="{}",
            capture_output=True,
            text=True,
        )

    def test_スキルの本文を標準出力へ書く(self) -> None:
        proc = self.run_hook()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("# 応答の形", proc.stdout)
        self.assertIn(hook.PREFACE, proc.stdout)
        self.assertNotIn("name: respond", proc.stdout)

    def test_スキルが見つからなくても失敗しない(self) -> None:
        script = self.tmp / "inject_respond.py"
        shutil.copy(INJECT_RESPOND, script)
        proc = subprocess.run(
            [sys.executable, str(script)],
            input="{}",
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
