"""dev-core/scripts/ports.py の単体テスト。

port の frontmatter 走査と、規約違反(name の重複・inject の欠落・flow 形式・
condition の欠落・閉じの --- 欠落)の警告を対象にする。走査結果は各部品の注入判断の
入力になるため、取りこぼしと誤検出のどちらも下流の挙動を変える。
"""

from __future__ import annotations

import unittest

import helpers

from helpers import DEV_SCRIPTS, run_json, run_script

import ports

PORTS_PY = DEV_SCRIPTS / "ports.py"


def port_text(
    name: str = "sample",
    inject: list[str] | None = None,
    condition: str = "常時",
    description: str = "説明",
    closed: bool = True,
) -> str:
    lines = ["---", f"name: {name}", f"description: {description}"]
    if inject is not None:
        lines.append("inject:")
        lines.extend(f"  - {i}" for i in inject)
    if condition:
        lines.append(f"condition: {condition}")
    if closed:
        lines.append("---")
    lines.append("")
    lines.append("# 本文")
    return "\n".join(lines) + "\n"


class ScanTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "ports"
        self.root.mkdir()

    def scan(self):
        return ports.scan(self.root)

    def test_frontmatter_を持つ_port_を返す(self) -> None:
        (self.root / "a.md").write_text(
            port_text(name="alpha", inject=["dev-spec", "dev-implement"]),
            encoding="utf-8",
        )
        found, no_fm, warnings = self.scan()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], "alpha")
        self.assertEqual(found[0]["inject"], ["dev-spec", "dev-implement"])
        self.assertEqual(found[0]["condition"], "常時")
        self.assertEqual(no_fm, [])
        self.assertEqual(warnings, [])

    def test_README_は_port_として扱わない(self) -> None:
        (self.root / "README.md").write_text("# 説明\n", encoding="utf-8")
        found, no_fm, warnings = self.scan()
        self.assertEqual((found, no_fm, warnings), ([], [], []))

    def test_frontmatter_が無いファイルを別掲する(self) -> None:
        (self.root / "plain.md").write_text("# 見出しだけ\n", encoding="utf-8")
        found, no_fm, warnings = self.scan()
        self.assertEqual(found, [])
        self.assertEqual(len(no_fm), 1)
        self.assertEqual(warnings, [])

    def test_閉じの_区切りが無ければ警告して別掲する(self) -> None:
        (self.root / "broken.md").write_text(
            port_text(inject=["dev-spec"], closed=False), encoding="utf-8"
        )
        found, no_fm, warnings = self.scan()
        self.assertEqual(found, [])
        self.assertEqual(len(no_fm), 1)
        self.assertAnyContains(warnings, "frontmatter が閉じていない")

    def test_name_が無ければ警告して_port_に含めない(self) -> None:
        (self.root / "noname.md").write_text(
            "---\ndescription: x\ninject:\n  - dev-spec\ncondition: 常時\n---\n",
            encoding="utf-8",
        )
        found, _, warnings = self.scan()
        self.assertEqual(found, [])
        self.assertAnyContains(warnings, "name がない")

    def test_name_の重複を警告する(self) -> None:
        (self.root / "a.md").write_text(
            port_text(name="dup", inject=["dev-spec"]), encoding="utf-8"
        )
        (self.root / "b.md").write_text(
            port_text(name="dup", inject=["dev-spec"]), encoding="utf-8"
        )
        found, _, warnings = self.scan()
        self.assertEqual(len(found), 2)
        self.assertAnyContains(warnings, "name 重複")

    def test_inject_が無ければ警告する(self) -> None:
        (self.root / "a.md").write_text(port_text(inject=None), encoding="utf-8")
        _, _, warnings = self.scan()
        self.assertAnyContains(warnings, "inject がない")

    def test_flow_形式の_inject_を警告する(self) -> None:
        (self.root / "a.md").write_text(
            "---\nname: x\ndescription: y\ninject: [dev-spec, dev-implement]\ncondition: 常時\n---\n",
            encoding="utf-8",
        )
        _, _, warnings = self.scan()
        self.assertAnyContains(warnings, "flow 形式の疑い")

    def test_condition_が無ければ警告する(self) -> None:
        (self.root / "a.md").write_text(
            port_text(inject=["dev-spec"], condition=""), encoding="utf-8"
        )
        _, _, warnings = self.scan()
        self.assertAnyContains(warnings, "condition がない")

    def test_入れ子のディレクトリも走査する(self) -> None:
        nested = self.root / "knowledge" / "domain"
        nested.mkdir(parents=True)
        (nested / "a.md").write_text(
            port_text(name="nested", inject=["dev-spec"]), encoding="utf-8"
        )
        found, _, _ = self.scan()
        self.assertEqual(found[0]["name"], "nested")


class CliTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "ports"
        self.root.mkdir()
        (self.root / "a.md").write_text(
            port_text(name="alpha", inject=["dev-spec"]), encoding="utf-8"
        )
        (self.root / "b.md").write_text(
            port_text(name="beta", inject=["dev-implement"]), encoding="utf-8"
        )

    def test_skill_で_inject_先を絞る(self) -> None:
        result = run_json(PORTS_PY, "--skill", "dev-spec", "--root", self.root, "--json")
        self.assertEqual([p["name"] for p in result["matched"]], ["alpha"])

    def test_skill_の指定が無ければ全件を返す(self) -> None:
        result = run_json(PORTS_PY, "--root", self.root, "--json")
        self.assertEqual(
            sorted(p["name"] for p in result["matched"]), ["alpha", "beta"]
        )

    def test_ルートが無ければ_port_なしとして正常終了する(self) -> None:
        result = run_json(PORTS_PY, "--root", self.tmp / "missing", "--json")
        self.assertEqual(result["matched"], [])
        self.assertAnyContains(result["warnings"], "port ルートが存在しない")
        proc = run_script(PORTS_PY, "--root", self.tmp / "missing")
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
