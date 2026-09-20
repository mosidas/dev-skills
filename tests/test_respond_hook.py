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

    def test_CRLFのfrontmatterでも前後にCRを残さない(self) -> None:
        text = "---\r\nname: respond\r\ndescription: x\r\n---\r\n\r\n# 応答の形\r\n\r\n本文\r\n"
        self.assertEqual(hook.strip_frontmatter(text), "# 応答の形\r\n\r\n本文")


class HookProcessTest(helpers.TempDirTestCase):
    def copy_hook(self) -> Path:
        """`inject_respond.py` を一時ディレクトリの `hooks/` 配下へ複製する。

        hook は自身の 1 つ上の階層に `skills/respond/SKILL.md` を探すため、
        実物の SKILL.md の見出しに依存させないよう、対応する `skills/respond/SKILL.md`
        は呼び出し側が合成して置く。
        """
        script = self.tmp / "hooks" / "inject_respond.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(INJECT_RESPOND, script)
        return script

    def run_hook(self, script: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script)],
            input="{}",
            capture_output=True,
            text=True,
        )

    def test_スキルの本文を標準出力へ書く(self) -> None:
        script = self.copy_hook()
        self.write(
            "skills/respond/SKILL.md",
            "---\nname: respond\ndescription: x\n---\n\n# 合成した見出し\n\n合成した本文\n",
        )
        proc = self.run_hook(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("# 合成した見出し", proc.stdout)
        self.assertTrue(proc.stdout.startswith(hook.PREFACE))
        self.assertNotIn("name: respond", proc.stdout)

    def test_スキルが見つからなくても失敗しない(self) -> None:
        script = self.copy_hook()
        proc = self.run_hook(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
