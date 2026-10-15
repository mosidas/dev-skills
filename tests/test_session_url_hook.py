"""PreToolUse hook(`guard_session_url.py`)の単体テスト。

hook は `sys.exit` を呼ぶため、すべてサブプロセスで確かめる。止める入力と通す入力を対で書く。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest

import helpers

GUARD = helpers.REPO_ROOT / "hooks" / "guard_session_url.py"

SESSION_ID = "session_01TESTabcdef"
URL = f"https://claude.ai/code/{SESSION_ID}"
COAUTHOR = "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"


class GuardSessionUrlTest(helpers.TempDirTestCase):
    def run_hook(self, command: str, tool_name: str = "Bash") -> subprocess.CompletedProcess:
        payload = {"tool_name": tool_name, "tool_input": {"command": command}, "cwd": str(self.tmp)}
        return self.run_raw(json.dumps(payload))

    def run_raw(self, stdin: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GUARD)],
            input=stdin,
            capture_output=True,
            text=True,
        )

    def assertBlocked(self, proc: subprocess.CompletedProcess, needle: str = "消して") -> None:
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn(needle, proc.stderr)
        self.assertEqual(proc.stderr.rstrip("\n").count("\n"), 0, proc.stderr)
        self.assertTrue(proc.stderr.rstrip("\n").endswith("。"), proc.stderr)
        self.assertNotIn(SESSION_ID, proc.stderr)

    def assertPassed(self, proc: subprocess.CompletedProcess) -> None:
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, "")

    # 止める

    def test_heredocのコミットメッセージにClaude_Sessionの行とURLがあれば止める(self) -> None:
        command = (
            "git commit -m \"$(cat <<'EOF'\nfeat: x\n\n本文\n\n"
            f"{COAUTHOR}\nClaude-Session: {URL}\nEOF\n)\""
        )
        self.assertBlocked(self.run_hook(command))

    def test_git_Cのコミットメッセージにあれば止める(self) -> None:
        self.assertBlocked(self.run_hook(f'git -C /x commit -m "feat: x {URL}"'))

    def test_URLが無くてもClaude_Sessionの行を大文字小文字を問わず止める(self) -> None:
        self.assertBlocked(self.run_hook('git commit -m "feat: x" -m "claude-session: x"'))

    def test_Fで渡した本文ファイルにあれば止める(self) -> None:
        self.write("msg.txt", f"feat: x\n\nClaude-Session: {URL}\n")
        proc = self.run_hook("git commit -F msg.txt")
        self.assertBlocked(proc)
        self.assertIn("msg.txt", proc.stderr)

    def test_file等号で渡した本文ファイルにあれば止める(self) -> None:
        path = self.write("msg.txt", f"feat: x\n\n{URL}\n")
        self.assertBlocked(self.run_hook(f"git commit --file={path}"))

    def test_空白を含むパスのbody_fileにあれば止める(self) -> None:
        self.write("dir with space/b.md", f"本文\n\n{URL}\n")
        self.assertBlocked(self.run_hook('gh pr create --title t --body-file "dir with space/b.md"'))

    def test_gh_pr_createの本文にあれば止める(self) -> None:
        self.assertBlocked(self.run_hook(f'gh pr create --title t --body "本文\n\n{URL}"'))

    def test_gh_pr_editの本文ファイルにあれば止める(self) -> None:
        path = self.write("body.md", f"本文\n\n{URL}\n")
        self.assertBlocked(self.run_hook(f"gh pr edit 28 --body-file {path}"))

    def test_本文ファイルが読めなければ止める(self) -> None:
        self.assertBlocked(self.run_hook("git commit -F missing.txt"), needle="読めない")

    # 通す

    def test_Co_Authored_Byだけのコミットは通す(self) -> None:
        self.assertPassed(self.run_hook(f'git commit -m "feat: x" -m "{COAUTHOR}"'))

    def test_heredocでCo_Authored_Byだけを付けたコミットは通す(self) -> None:
        command = f"git commit -q -m \"$(cat <<'EOF'\nfeat: x\n\n{COAUTHOR}\nEOF\n)\""
        self.assertPassed(self.run_hook(command))

    def test_メッセージ中のオプション名は本文ファイルと見なさず通す(self) -> None:
        self.assertPassed(self.run_hook("git commit -m 'docs: --body-file の説明'"))

    def test_grep_Fによる検索は通す(self) -> None:
        self.assertPassed(self.run_hook("grep -F 'git commit' README.md"))

    def test_Generated_withを付けたgh_pr_createは通す(self) -> None:
        body = "本文\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"
        self.assertPassed(self.run_hook(f'gh pr create --title t --body "{body}"'))

    def test_git_logのgrepは通す(self) -> None:
        self.assertPassed(self.run_hook("git log --grep 'claude.ai/code/session_'"))

    def test_grepによる検索は通す(self) -> None:
        self.assertPassed(self.run_hook('grep -rn "claude.ai/code/session_" .'))

    def test_対象外のコマンドは通す(self) -> None:
        self.assertPassed(self.run_hook("python3 -m unittest discover -s tests -t tests"))

    def test_amend_no_editは通す(self) -> None:
        self.assertPassed(self.run_hook("git commit --amend --no-edit"))

    def test_メッセージ無しのgit_commitは通す(self) -> None:
        self.assertPassed(self.run_hook("git commit"))

    def test_標準入力から読むFは通す(self) -> None:
        self.assertPassed(self.run_hook("git commit -F -"))

    def test_Bash以外のツールは通す(self) -> None:
        self.assertPassed(self.run_hook(f'git commit -m "{URL}"', tool_name="Write"))

    def test_構文が不正なJSONは通す(self) -> None:
        self.assertPassed(self.run_raw("{not json"))


if __name__ == "__main__":
    unittest.main()
