"""install.py の core コマンドの単体テスト。

配布元の用途グループ(`<グループ>/skills`・`<グループ>/agents`)から、利用側の
`.claude/skills`・`.claude/agents` への展開を対象にする。配布対象の決め方を誤ると、
保守用の `meta-*` を利用側へ配ったり、逆に部品を配り漏らしたりする(D-006・D-011)。
グループを絞った導入では、触らないグループの導入物を消さないことが要件になる(D-012)。
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

    def locked(self, group: str) -> dict:
        return self.lock()["groups"][group]


class CoreTest(CoreTestCase):
    def test_グループのスキルとエージェントを配布する(self) -> None:
        self.add_skill("dev", "dev-spec")
        self.add_agent("dev", "dev-reviewer")
        proc = self.run_core()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.installed_skills(), ["dev-spec"])
        self.assertEqual(self.installed_agents(), ["dev-reviewer.md"])
        self.assertEqual(self.locked("dev")["skills"], ["dev-spec"])
        self.assertEqual(
            self.locked("dev")["agents"], [".claude/agents/dev-reviewer.md"]
        )

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
        self.assertIn("重複する", proc.stderr)

    def test_エージェント名がグループ間で衝突すれば停止する(self) -> None:
        self.add_skill("dev", "dev-spec")
        self.add_agent("dev", "shared")
        self.add_skill("ops", "ops-deploy")
        self.add_agent("ops", "shared")
        proc = self.run_core()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("重複する", proc.stderr)

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


class SelectGroupTest(CoreTestCase):
    """グループを選んだ導入(D-012)。"""

    def setUp(self) -> None:
        super().setUp()
        self.add_skill("dev", "dev-spec")
        self.add_agent("dev", "dev-reviewer")
        self.add_skill("writing", "japanese-writing")
        self.add_skill("authoring", "skill-authoring")

    def test_指定したグループだけを配布する(self) -> None:
        proc = self.run_core("writing")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.installed_skills(), ["japanese-writing"])
        self.assertEqual(sorted(self.lock()["groups"]), ["writing"])

    def test_複数のグループを指定できる(self) -> None:
        self.run_core("writing", "authoring")
        self.assertEqual(
            self.installed_skills(), ["japanese-writing", "skill-authoring"]
        )
        self.assertEqual(sorted(self.lock()["groups"]), ["authoring", "writing"])

    def test_絞った実行が他のグループの導入物を消さない(self) -> None:
        self.run_core("dev")
        self.run_core("writing")
        self.assertEqual(
            self.installed_skills(), ["dev-spec", "japanese-writing"]
        )
        self.assertEqual(self.installed_agents(), ["dev-reviewer.md"])
        self.assertEqual(sorted(self.lock()["groups"]), ["dev", "writing"])

    def test_絞った実行でも自グループの廃止分は消す(self) -> None:
        self.add_skill("writing", "old-writing")
        self.run_core("writing")
        self.assertIn("old-writing", self.installed_skills())
        (self.src / "writing" / "skills" / "old-writing" / "SKILL.md").unlink()
        (self.src / "writing" / "skills" / "old-writing").rmdir()
        self.run_core("writing")
        self.assertEqual(self.installed_skills(), ["japanese-writing"])

    def test_他のグループが導入済みの名前と衝突すれば停止する(self) -> None:
        self.run_core("dev")
        self.add_skill("writing", "dev-spec")
        proc = self.run_core("writing")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("重複する", proc.stderr)

    def test_グループ間で移動したスキルを消さない(self) -> None:
        self.run_core()
        for p in (self.src / "writing" / "skills" / "japanese-writing").iterdir():
            p.unlink()
        (self.src / "writing" / "skills" / "japanese-writing").rmdir()
        self.add_skill("authoring", "japanese-writing")
        self.run_core()
        self.assertIn("japanese-writing", self.installed_skills())
        self.assertEqual(self.locked("authoring")["skills"], ["japanese-writing", "skill-authoring"])
        self.assertEqual(self.locked("writing")["skills"], [])

    def test_配布元に無いグループを指定すれば停止する(self) -> None:
        proc = self.run_core("unknown")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("配布ルートに無いグループ", proc.stderr)


class LegacyLockTest(CoreTestCase):
    """グループ名を持たない旧形式の lock の扱い。"""

    def setUp(self) -> None:
        super().setUp()
        self.add_skill("dev", "dev-spec")
        self.add_skill("writing", "japanese-writing")
        (self.target / ".claude").mkdir(parents=True)
        (self.target / ".claude" / "skills" / "dev-old").mkdir(parents=True)
        (self.target / ".claude" / "skills" / "dev-old" / "SKILL.md").write_text(
            "旧", encoding="utf-8"
        )
        (self.target / CORE_LOCK).write_text(
            json.dumps({"skills": ["dev-old"], "agents": []}), encoding="utf-8"
        )

    def test_全グループの実行で旧形式の廃止分を消す(self) -> None:
        self.run_core()
        self.assertEqual(
            self.installed_skills(), ["dev-spec", "japanese-writing"]
        )
        self.assertEqual(sorted(self.lock()["groups"]), ["dev", "writing"])

    def test_絞った実行では旧形式の記録に触らない(self) -> None:
        self.run_core("writing")
        self.assertIn("dev-old", self.installed_skills())
        self.assertIn("", self.lock()["groups"])


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

    def test_実リポジトリの_writing_グループだけを配布できる(self) -> None:
        proc = run_script(
            INSTALL_PY, "--root", REPO_ROOT, "core", "--target", self.target, "writing"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.installed_skills(), ["japanese-writing"])


if __name__ == "__main__":
    unittest.main()
