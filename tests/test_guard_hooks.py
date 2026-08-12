"""ext-dev-guardrails の hook の単体テスト。

検出できることと誤検出しないことを対で確かめる。hook は入力を解釈できない場合に許可側へ
倒す(hook 自身の不具合で作業を止めない)ため、その挙動も確かめる。exit code と日本語の
理由はサブプロセスで確かめる。
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import helpers

HOOKS = (
    helpers.REPO_ROOT
    / "dev"
    / "extensions"
    / "guardrails"
    / "ext-dev-guardrails"
    / "hooks"
)

sys.path.insert(0, str(HOOKS))

import guard_bash  # noqa: E402
import guard_write  # noqa: E402


def run_hook(script: Path, payload: object) -> subprocess.CompletedProcess:
    """hook をサブプロセスで実行し、標準入力へ JSON を渡す。"""
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload),
        capture_output=True,
        text=True,
    )


class GuardBashTest(unittest.TestCase):
    def assertDenied(self, command: str, cwd: str | None = None) -> None:
        self.assertIsNotNone(
            guard_bash.check(command, cwd), f"拒否されるべきコマンドが通った: {command}"
        )

    def assertAllowed(self, command: str, cwd: str | None = None) -> None:
        self.assertIsNone(
            guard_bash.check(command, cwd), f"許可されるべきコマンドが拒否された: {command}"
        )

    def test_破壊的な_git_操作を拒否する(self) -> None:
        for command in (
            "git reset --hard HEAD~1",
            "git checkout .",
            "git checkout -- src/main.py",
            "git checkout ./src/main.py",
            "git checkout HEAD -- .",
            "git restore .",
            "git restore src/main.py",
            "git restore --staged --worktree .",
            "git clean -fd",
            "git clean --force",
            "git branch -D feature",
            "git push --force origin main",
            "git push -f",
            "rm -rf build",
            "rm -r -f build",
        ):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_グローバルオプションの前置で回避できない(self) -> None:
        for command in (
            "git -C /repo reset --hard",
            "git -c core.editor=vim reset --hard",
            "git --git-dir=.git reset --hard",
            "git --work-tree=. checkout .",
            "git -C sub add -A",
        ):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_環境変数の前置で回避できない(self) -> None:
        for command in (
            "FOO=1 git reset --hard",
            "env FOO=1 git reset --hard",
            "GIT_DIR=.git PAGER=cat git clean -fd",
        ):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_ブランチ強制削除の別表記を拒否する(self) -> None:
        for command in (
            "git branch --delete --force feature",
            "git branch -df feature",
            "git branch -d --force feature",
        ):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_refspec_による強制_push_を拒否する(self) -> None:
        for command in (
            "git push origin +main",
            "git push origin +refs/heads/main:refs/heads/main",
        ):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_クォートが閉じていなくても検査を続ける(self) -> None:
        self.assertDenied('git reset --hard "閉じていない')

    def test_一括ステージングを拒否する(self) -> None:
        for command in ("git add -A", "git add --all", "git add ."):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_通常の操作を拒否しない(self) -> None:
        for command in (
            "git add src/main.py",
            "git add docs/specs/user-auth/spec.md docs/specs/user-auth/state.json",
            "git commit -m 'feat: 追加'",
            "git push origin feature",
            "git push --force-with-lease origin feature",
            "git status",
            "git checkout feature",
            "git switch -c user-auth",
            "git revert HEAD",
            "git stash push -m 'wip'",
            "git branch -d merged",
            "git reset HEAD src/main.py",
            "git restore --staged src/main.py",
            "git clean -n",
            "git clean -nf",
            "git clean --dry-run --force",
            "git add ./src/main.py",
            "git add .gitignore",
            "git -C sub status",
            "git log --format='%H rm -rf'",
            "rm build/out.txt",
            "rm -r build",
            "python3 -m unittest discover -s tests -t tests",
        ):
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_文字列リテラルの中の語を拒否しない(self) -> None:
        self.assertAllowed('echo "git add -A は使わない"')
        self.assertAllowed("git commit -m 'chore: git reset --hard の禁止を明記'")

    def test_クォート内の区切り文字で分割しない(self) -> None:
        for command in (
            'git commit -m "wip; git reset --hard now"',
            'git commit -m "see | git add -A x"',
            'git commit -m "do && rm -rf x now"',
        ):
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_連結されたコマンドの後段も検査する(self) -> None:
        self.assertDenied("git status && git add -A")
        self.assertDenied("make build; rm -rf dist")
        self.assertAllowed("git status && git add src/main.py")

    def test_sudo_を前置しても検査する(self) -> None:
        self.assertDenied("sudo rm -rf build")
        self.assertDenied("sudo git reset --hard")

    def test_拒否時に_exit_2_と理由を返す(self) -> None:
        proc = run_hook(
            HOOKS / "guard_bash.py",
            {"tool_name": "Bash", "tool_input": {"command": "git reset --hard"}},
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("git reset --hard", proc.stderr)
        self.assertIn("git revert", proc.stderr)

    def test_許可時に_exit_0_で何も出力しない(self) -> None:
        proc = run_hook(
            HOOKS / "guard_bash.py",
            {"tool_name": "Bash", "tool_input": {"command": "git status"}},
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertEqual(proc.stderr.strip(), "")

    def test_対象外のツールを素通しする(self) -> None:
        proc = run_hook(
            HOOKS / "guard_bash.py",
            {"tool_name": "Read", "tool_input": {"command": "git reset --hard"}},
        )
        self.assertEqual(proc.returncode, 0)

    def test_解釈できない入力で作業を止めない(self) -> None:
        proc = run_hook(HOOKS / "guard_bash.py", "これは JSON ではない")
        self.assertEqual(proc.returncode, 0)


class GuardBashRemovePathTest(helpers.TempDirTestCase):
    """`rm -rf` の削除対象がリポジトリの内か外かで判定が分かれることを確かめる。

    正本(git-convention.md 6.)が禁じる理由は未コミットの変更を失うことにあり、
    リポジトリの外の削除はこの理由に当たらない。変異検査のように使い捨ての複製を
    リポジトリの外に作る作業を止めないための判定である(D-027)。
    """

    def setUp(self) -> None:
        super().setUp()
        self.repo = self.tmp / "repo"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "src").mkdir()
        self.outside = self.tmp / "scratch"
        self.outside.mkdir()
        self.cwd = str(self.repo)

    def assertDenied(self, command: str) -> None:
        self.assertIsNotNone(
            guard_bash.check(command, self.cwd),
            f"拒否されるべきコマンドが通った: {command}",
        )

    def assertAllowed(self, command: str) -> None:
        self.assertIsNone(
            guard_bash.check(command, self.cwd),
            f"許可されるべきコマンドが拒否された: {command}",
        )

    def test_リポジトリ外の絶対パスを通す(self) -> None:
        self.assertAllowed(f"rm -rf {self.outside}/work")

    def test_cd_で外へ移った後の相対パスを通す(self) -> None:
        self.assertAllowed(f"cd {self.outside} && rm -rf work && mkdir work")

    def test_リポジトリ内の相対パスを拒否する(self) -> None:
        for command in ("rm -rf src", "rm -rf ./src", "rm -rf src/", "rm -rf ."):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_リポジトリ内の絶対パスを拒否する(self) -> None:
        self.assertDenied(f"rm -rf {self.repo}/src")

    def test_リポジトリのルート自体を拒否する(self) -> None:
        self.assertDenied(f"rm -rf {self.repo}")

    def test_外へ出てから戻る_cd_を追跡する(self) -> None:
        self.assertDenied(f"cd {self.outside} && cd {self.repo} && rm -rf src")

    def test_相対パスの_cd_を追跡する(self) -> None:
        self.assertAllowed(f"cd .. && cd {self.outside.name} && rm -rf work")

    def test_上位への相対パスでリポジトリを抜けたことを判定する(self) -> None:
        self.assertAllowed("rm -rf ../scratch/work")

    def test_変数展開を含む対象は拒否側に倒す(self) -> None:
        for command in (
            'MUT=$(mktemp -d) && rm -rf "$MUT/.git"',
            "rm -rf $BUILD_DIR",
            "rm -rf `pwd`/build",
        ):
            with self.subTest(command=command):
                self.assertDenied(command)

    def test_行き先を解決できない_cd_の後は拒否側に倒す(self) -> None:
        self.assertDenied("cd $WORK && rm -rf tmpdir")

    def test_チルダ展開は確定しないため拒否側に倒す(self) -> None:
        self.assertDenied("rm -rf ~/scratch/work")

    def test_複数の対象は_1_つでも内側なら拒否する(self) -> None:
        self.assertDenied(f"rm -rf {self.outside}/work src")

    def test_リポジトリを特定できなければ拒否側に倒す(self) -> None:
        outside_repo = str(self.outside)
        self.assertIsNotNone(
            guard_bash.check(f"rm -rf {self.outside}/work", outside_repo)
        )

    def test_再帰と強制が揃わなければ対象にしない(self) -> None:
        for command in ("rm -r src", "rm -f src/main.py", "rm src/main.py"):
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_削除対象を持たない_rm_rf_を対象にしない(self) -> None:
        self.assertAllowed("rm -rf")

    def test_リポジトリ内でも_git_の禁止操作は変わらず拒否する(self) -> None:
        self.assertDenied("git reset --hard")
        self.assertDenied("git add -A")

    def test_hook_が_cwd_を読んで判定する(self) -> None:
        allowed = run_hook(
            HOOKS / "guard_bash.py",
            {
                "tool_name": "Bash",
                "tool_input": {"command": f"rm -rf {self.outside}/work"},
                "cwd": self.cwd,
            },
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        denied = run_hook(
            HOOKS / "guard_bash.py",
            {
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf src"},
                "cwd": self.cwd,
            },
        )
        self.assertEqual(denied.returncode, 2)
        self.assertIn("リポジトリ内", denied.stderr)


class GuardWriteTest(helpers.TempDirTestCase):
    def freeze(self, unit: str, names: list[str]) -> Path:
        """凍結済みの workdir を作り、そのパスを返す。"""
        workdir = self.tmp / "docs" / "specs" / unit
        workdir.mkdir(parents=True, exist_ok=True)
        for name in names:
            (workdir / name).write_text("# 中間生成物\n", encoding="utf-8")
        (workdir / "state.json").write_text(
            json.dumps(
                {
                    "state": "completed",
                    "frozen": {name: "0" * 64 for name in names},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return workdir

    def test_凍結済みの成果物への書き込みを拒否する(self) -> None:
        workdir = self.freeze("user-auth", ["spec.md", "tasks.md"])
        self.assertIsNotNone(guard_write.check(workdir / "spec.md"))
        self.assertIsNotNone(guard_write.check(workdir / "tasks.md"))

    def test_凍結されていないファイルを拒否しない(self) -> None:
        workdir = self.freeze("user-auth", ["spec.md"])
        self.assertIsNone(guard_write.check(workdir / "research.md"))
        self.assertIsNone(guard_write.check(workdir / "state.json"))
        self.assertIsNone(guard_write.check(self.tmp / "src" / "main.py"))

    def test_シンボリックリンク経由の別名で回避できない(self) -> None:
        workdir = self.freeze("user-auth", ["spec.md"])
        link = workdir / "spec-link.md"
        link.symlink_to(workdir / "spec.md")
        self.assertIsNotNone(guard_write.check(link))

    def test_相対パスを_cwd_で解決する(self) -> None:
        self.freeze("user-auth", ["spec.md"])
        rel = Path("docs/specs/user-auth/spec.md")
        self.assertIsNotNone(guard_write.check(rel, str(self.tmp)))
        self.assertIsNone(guard_write.check(rel, str(self.tmp / "other")))

    def test_frozen_が空辞書なら拒否しない(self) -> None:
        workdir = self.tmp / "docs" / "specs" / "empty"
        workdir.mkdir(parents=True)
        (workdir / "spec.md").write_text("# spec\n", encoding="utf-8")
        (workdir / "state.json").write_text(
            json.dumps({"state": "completed", "frozen": {}}), encoding="utf-8"
        )
        self.assertIsNone(guard_write.check(workdir / "spec.md"))

    def test_state_json_が無い場所を拒否しない(self) -> None:
        path = self.tmp / "docs" / "dev" / "tasks.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# tasks\n", encoding="utf-8")
        self.assertIsNone(guard_write.check(path))

    def test_未完了の_workdir_を拒否しない(self) -> None:
        workdir = self.tmp / "docs" / "specs" / "wip"
        workdir.mkdir(parents=True)
        (workdir / "spec.md").write_text("# spec\n", encoding="utf-8")
        (workdir / "state.json").write_text(
            json.dumps({"state": "spec-generated"}), encoding="utf-8"
        )
        self.assertIsNone(guard_write.check(workdir / "spec.md"))

    def test_壊れた_state_json_で作業を止めない(self) -> None:
        workdir = self.tmp / "docs" / "specs" / "broken"
        workdir.mkdir(parents=True)
        (workdir / "spec.md").write_text("# spec\n", encoding="utf-8")
        (workdir / "state.json").write_text("{ 壊れている", encoding="utf-8")
        self.assertIsNone(guard_write.check(workdir / "spec.md"))

    def test_拒否時に_exit_2_と理由を返す(self) -> None:
        workdir = self.freeze("user-auth", ["spec.md"])
        proc = run_hook(
            HOOKS / "guard_write.py",
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(workdir / "spec.md")},
            },
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("凍結", proc.stderr)
        self.assertIn("durable-info.md", proc.stderr)

    def test_許可時に_exit_0_で何も出力しない(self) -> None:
        workdir = self.freeze("user-auth", ["spec.md"])
        proc = run_hook(
            HOOKS / "guard_write.py",
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(workdir / "research.md")},
            },
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr.strip(), "")

    def test_対象外のツールを素通しする(self) -> None:
        workdir = self.freeze("user-auth", ["spec.md"])
        proc = run_hook(
            HOOKS / "guard_write.py",
            {"tool_name": "Read", "tool_input": {"file_path": str(workdir / "spec.md")}},
        )
        self.assertEqual(proc.returncode, 0)

    def test_解釈できない入力で作業を止めない(self) -> None:
        proc = run_hook(HOOKS / "guard_write.py", "これは JSON ではない")
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
