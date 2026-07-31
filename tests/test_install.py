"""install.py の core コマンドの単体テスト。

配布元の用途グループ(`<グループ>/skills`・`<グループ>/agents`)から、利用側の
`.claude/skills`・`.claude/agents` への展開を対象にする。配布対象の決め方を誤ると、
保守用の `meta-*` を利用側へ配ったり、逆に部品を配り漏らしたりする(D-006・D-011)。
"""

from __future__ import annotations

import json
import unittest

import helpers

from helpers import REPO_ROOT, run_script

INSTALL_PY = REPO_ROOT / "install.py"
CORE_LOCK = ".claude/dev-core.lock.json"


class CoreTestCase(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.src = self.tmp / "src"
        self.target = self.tmp / "target"
        self.target.mkdir(parents=True)

    def add_skill(self, group: str, name: str) -> None:
        d = self.src / group / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: 説明\n---\n", encoding="utf-8"
        )

    def add_agent(self, group: str, name: str) -> None:
        d = self.src / group / "agents"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

    def run_core(self, *args: object):
        return run_script(
            INSTALL_PY, "--root", self.src, "core", "--target", self.target, *args
        )

    def installed_skills(self) -> list[str]:
        d = self.target / ".claude" / "skills"
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def installed_agents(self) -> list[str]:
        d = self.target / ".claude" / "agents"
        return sorted(p.name for p in d.glob("*.md")) if d.is_dir() else []

    def lock(self) -> dict:
        return json.loads((self.target / CORE_LOCK).read_text(encoding="utf-8"))


class CoreTest(CoreTestCase):
    def test_グループのスキルとエージェントを配布する(self) -> None:
        self.add_skill("dev", "dev-spec")
        self.add_agent("dev", "dev-reviewer")
        proc = self.run_core()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.installed_skills(), ["dev-spec"])
        self.assertEqual(self.installed_agents(), ["dev-reviewer.md"])
        self.assertEqual(self.lock()["skills"], ["dev-spec"])
        self.assertEqual(self.lock()["agents"], [".claude/agents/dev-reviewer.md"])

    def test_claude_配下のスキルを配布しない(self) -> None:
        """`meta-*` は `.claude/skills` に置くため、グループ走査の対象外になる。"""
        self.add_skill("dev", "dev-spec")
        self.add_skill(".claude", "meta-check")
        self.run_core()
        self.assertEqual(self.installed_skills(), ["dev-spec"])

    def test_複数のグループをまとめて配布する(self) -> None:
        self.add_skill("dev", "dev-spec")
        self.add_skill("ops", "ops-deploy")
        self.add_agent("ops", "ops-runner")
        self.run_core()
        self.assertEqual(self.installed_skills(), ["dev-spec", "ops-deploy"])
        self.assertEqual(self.installed_agents(), ["ops-runner.md"])

    def test_スキル名がグループ間で衝突すれば停止する(self) -> None:
        """導入先は名前が平坦なため、同名を両方コピーすると先のものが消える。"""
        self.add_skill("dev", "dev-spec")
        self.add_skill("ops", "dev-spec")
        proc = self.run_core()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("複数のグループに存在する", proc.stderr)

    def test_エージェント名がグループ間で衝突すれば停止する(self) -> None:
        self.add_skill("dev", "dev-spec")
        self.add_agent("dev", "shared")
        self.add_skill("ops", "ops-deploy")
        self.add_agent("ops", "shared")
        proc = self.run_core()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("複数のグループに存在する", proc.stderr)

    def test_配布元から消えたスキルを削除する(self) -> None:
        self.add_skill("dev", "dev-spec")
        self.add_skill("dev", "dev-old")
        self.run_core()
        self.assertEqual(self.installed_skills(), ["dev-old", "dev-spec"])
        for p in (self.src / "dev" / "skills" / "dev-old").iterdir():
            p.unlink()
        (self.src / "dev" / "skills" / "dev-old").rmdir()
        self.run_core()
        self.assertEqual(self.installed_skills(), ["dev-spec"])

    def test_グループが無ければ停止する(self) -> None:
        (self.src / ".claude" / "skills" / "meta-check").mkdir(parents=True)
        proc = self.run_core()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("用途グループ", proc.stderr)

    def test_dry_run_は書き込まない(self) -> None:
        self.add_skill("dev", "dev-spec")
        proc = self.run_core("--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.installed_skills(), [])
        self.assertFalse((self.target / CORE_LOCK).exists())


class RealRepositoryTest(CoreTestCase):
    def test_実リポジトリの配布に_meta_を含めない(self) -> None:
        proc = run_script(
            INSTALL_PY, "--root", REPO_ROOT, "core", "--target", self.target
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        skills = self.installed_skills()
        self.assertIn("dev-core", skills)
        self.assertIn("flow-sdd", skills)
        self.assertEqual([s for s in skills if s.startswith("meta-")], [])
        self.assertTrue(self.installed_agents())


if __name__ == "__main__":
    unittest.main()
