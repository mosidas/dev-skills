"""meta-core/scripts/meta_check.py の単体テスト。

参照の実在・frontmatter・inject 先の実在・依存規律・状態整合・部品名の実在・
未記入マーカー・回帰検出(--baseline)を対象にする。合成したスキル群を一時ディレクトリに
組み立て、違反を入れたときに検出し、正当な記述で誤検出しないことを確かめる。
"""

from __future__ import annotations

import json
import unittest

import helpers

from helpers import META_SCRIPTS, run_script

import meta_check

META_CHECK_PY = META_SCRIPTS / "meta_check.py"


def skill_md(name: str, description: str = "説明", body: str = "") -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n{body}\n"


class MetaCheckTestCase(helpers.TempDirTestCase):
    """最小構成のスキル群を組み立てる基底。"""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        (self.root / ".claude" / "skills").mkdir(parents=True)
        (self.root / ".claude" / "agents").mkdir(parents=True)

    def add_skill(self, name: str, **kwargs) -> None:
        d = self.root / ".claude" / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(skill_md(name, **kwargs), encoding="utf-8")

    def add_agent(self, name: str, text: str | None = None) -> None:
        path = self.root / ".claude" / "agents" / f"{name}.md"
        path.write_text(text or skill_md(name), encoding="utf-8")

    def add_port(self, rel: str, text: str) -> None:
        path = self.root / "ports" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def report(self, func, *args) -> meta_check.Report:
        report = meta_check.Report()
        func(self.root, *args, report)
        return report


class FrontmatterTest(MetaCheckTestCase):
    def run_check(self) -> meta_check.Report:
        return self.report(meta_check.check_frontmatter)

    def test_name_が配置と一致すれば指摘しない(self) -> None:
        self.add_skill("dev-spec")
        self.add_agent("dev-reviewer")
        self.assertEqual(self.run_check().findings, [])

    def test_name_と配置の不一致を_error_にする(self) -> None:
        d = self.root / ".claude" / "skills" / "dev-spec"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(skill_md("dev-other"), encoding="utf-8")
        report = self.run_check()
        self.assertEqual(report.count("error"), 1)
        self.assertAnyContains(self.messages(report.findings), "配置 'dev-spec' と一致しない")

    def test_引用符つきの_name_を不一致にしない(self) -> None:
        d = self.root / ".claude" / "skills" / "dev-spec"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            '---\nname: "dev-spec"\ndescription: 説明\n---\n', encoding="utf-8"
        )
        self.assertEqual(self.run_check().count("error"), 0)

    def test_ブロックスカラーの_description_を欠落にしない(self) -> None:
        d = self.root / ".claude" / "skills" / "dev-spec"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: dev-spec\ndescription: >-\n  複数行の\n  説明\n---\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_check().count("error"), 0)

    def test_description_の欠落を_error_にする(self) -> None:
        d = self.root / ".claude" / "skills" / "dev-spec"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: dev-spec\n---\n", encoding="utf-8")
        self.assertAnyContains(
            self.messages(self.run_check().findings), "description が無い"
        )

    def test_frontmatter_が無ければ_error(self) -> None:
        d = self.root / ".claude" / "skills" / "dev-spec"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# 見出しだけ\n", encoding="utf-8")
        self.assertAnyContains(
            self.messages(self.run_check().findings), "frontmatter が無い"
        )

    def test_解析できない記法を_warning_で区別する(self) -> None:
        d = self.root / ".claude" / "skills" / "dev-spec"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: dev-spec\ndescription: 説明\nnested:\n  key: value\n---\n",
            encoding="utf-8",
        )
        report = self.run_check()
        self.assertEqual(report.count("error"), 0)
        self.assertAnyContains(
            self.messages(report.findings, "warning"), "解析できない記法がある"
        )


class PlaceholderTest(MetaCheckTestCase):
    def run_check(self, body: str) -> list[str]:
        self.add_skill("dev-spec", body=body)
        return self.messages(self.report(meta_check.check_placeholders).findings)

    def test_地の文のマーカーを検出する(self) -> None:
        self.assertAnyContains(self.run_check("TODO: 未記入"), "未記入マーカー TODO")

    def test_日本語に隣接するマーカーを検出する(self) -> None:
        self.assertAnyContains(self.run_check("未記入TODOです"), "未記入マーカー TODO")

    def test_インラインコード内の引用を除外する(self) -> None:
        self.assertEqual(self.run_check("`TODO` の残存を検査する"), [])

    def test_コードブロック内を除外する(self) -> None:
        self.assertEqual(self.run_check("```python\n# TODO: 例\n```"), [])

    def test_URL_内を除外する(self) -> None:
        self.assertEqual(self.run_check("https://example.com/TODO-list を見る"), [])

    def test_英単語の一部を検出しない(self) -> None:
        self.assertEqual(self.run_check("TODOS と ATODO と XXXCorp"), [])

    def test_TBD_と_FIXME_も検出する(self) -> None:
        messages = self.run_check("TBD の項目と FIXME の項目")
        self.assertEqual(len(messages), 2)


class DependencyDisciplineTest(MetaCheckTestCase):
    def test_dev_が_meta_を参照すると_error(self) -> None:
        self.add_skill("dev-spec", body="meta-core を参照する")
        report = self.report(meta_check.check_dependency_discipline)
        self.assertEqual(report.count("error"), 1)
        self.assertAnyContains(self.messages(report.findings), "依存規律違反")

    def test_dev_core_も検査の対象にする(self) -> None:
        self.add_skill("dev-core", body="meta-check を参照する")
        self.assertEqual(
            self.report(meta_check.check_dependency_discipline).count("error"), 1
        )

    def test_meta_同士の参照は指摘しない(self) -> None:
        self.add_skill("meta-check", body="meta-core を参照する")
        self.assertEqual(
            self.report(meta_check.check_dependency_discipline).findings, []
        )


class ReferenceTest(MetaCheckTestCase):
    def test_実在しない相対参照を_error_にする(self) -> None:
        self.add_skill("dev-spec", body="参照: `./missing.md`")
        report = self.report(meta_check.check_references)
        self.assertEqual(report.count("error"), 1)
        self.assertAnyContains(self.messages(report.findings), "参照先が存在しない")

    def test_実在する相対参照は指摘しない(self) -> None:
        self.add_skill("dev-spec", body="参照: `../dev-core/references/x.md`")
        refs = self.root / ".claude" / "skills" / "dev-core" / "references"
        refs.mkdir(parents=True)
        (refs / "x.md").write_text("内容", encoding="utf-8")
        self.assertEqual(self.report(meta_check.check_references).findings, [])

    def test_ルート外への参照は_warning_に留める(self) -> None:
        self.add_skill("dev-spec", body="参照: `../../../../outside.md`")
        report = self.report(meta_check.check_references)
        self.assertEqual(report.count("error"), 0)
        self.assertAnyContains(
            self.messages(report.findings, "warning"), "外部参照が検証できない"
        )


class InjectTargetTest(MetaCheckTestCase):
    def run_check(self) -> meta_check.Report:
        report = meta_check.Report()
        meta_check.check_inject_targets(
            self.root, meta_check.skill_names(self.root), report
        )
        return report

    def test_実在しない_inject_先を_error_にする(self) -> None:
        self.add_skill("dev-spec")
        self.add_port(
            "a.md",
            "---\nname: a\ndescription: x\ninject:\n  - dev-unknown\ncondition: 常時\n---\n",
        )
        self.assertAnyContains(
            self.messages(self.run_check().findings), "inject 先スキルが存在しない"
        )

    def test_実在する_inject_先は指摘しない(self) -> None:
        self.add_skill("dev-spec")
        self.add_port(
            "a.md",
            "---\nname: a\ndescription: x\ninject:\n  - dev-spec\ncondition: 常時\n---\n",
        )
        self.assertEqual(self.run_check().findings, [])

    def test_雛形はプレースホルダを持つため対象外にする(self) -> None:
        self.add_skill("dev-spec")
        self.add_port(
            "templates/knowledge-port.md",
            "---\nname: <name>\ndescription: x\ninject:\n  - <注入先スキル>\ncondition: 常時\n---\n",
        )
        self.assertEqual(self.run_check().findings, [])


class StateConsistencyTest(MetaCheckTestCase):
    def add_flow(self, states: list[str], body: str) -> None:
        d = self.root / ".claude" / "skills" / "flow-x"
        d.mkdir(parents=True)
        (d / "workflow.json").write_text(
            json.dumps({"name": "x", "states": states}), encoding="utf-8"
        )
        (d / "SKILL.md").write_text(skill_md("flow-x", body=body), encoding="utf-8")

    def test_SKILL_に記述の無い状態を_warning_にする(self) -> None:
        self.add_flow(["initialized", "completed"], body="`initialized` のみ書く")
        self.assertAnyContains(
            self.messages(self.report(meta_check.check_state_consistency).findings),
            "状態 'completed' の記述が無い",
        )

    def test_定義に無い状態名の記述を_warning_にする(self) -> None:
        self.add_flow(["initialized"], body="`initialized` と `spec-generated`")
        self.assertAnyContains(
            self.messages(self.report(meta_check.check_state_consistency).findings),
            "`spec-generated` が workflow.json に無い",
        )

    def test_整合していれば指摘しない(self) -> None:
        self.add_flow(["initialized"], body="`initialized` を使う")
        self.assertEqual(
            self.report(meta_check.check_state_consistency).findings, []
        )


class PartNameTest(MetaCheckTestCase):
    def run_check(self) -> meta_check.Report:
        report = meta_check.Report()
        meta_check.check_part_names(
            self.root,
            meta_check.skill_names(self.root),
            meta_check.agent_names(self.root),
            report,
        )
        return report

    def test_実在しない部品名を_warning_にする(self) -> None:
        self.add_skill("dev-spec", body="dev-nonexistent を呼ぶ")
        self.assertAnyContains(
            self.messages(self.run_check().findings), "実在しない: dev-nonexistent"
        )

    def test_実在する部品名とリポジトリ名は指摘しない(self) -> None:
        self.add_skill("dev-spec", body="dev-spec と dev-skills を挙げる")
        self.assertEqual(self.run_check().findings, [])


class BaselineTest(MetaCheckTestCase):
    def test_基準に無い指摘だけを新規と判定する(self) -> None:
        path = self.write(
            "baseline.json",
            json.dumps(
                {"findings": [{"severity": "warning", "message": "既存の指摘"}]},
                ensure_ascii=False,
            ),
        )
        known = meta_check.load_baseline(path)
        self.assertIn(("warning", "既存の指摘"), known)
        self.assertNotIn(("warning", "新しい指摘"), known)

    def test_形式が違う基準を拒否する(self) -> None:
        self.add_skill("dev-spec")
        path = self.write("baseline.json", json.dumps({"findings": "not-a-list"}))
        proc = run_script(META_CHECK_PY, "--root", self.root, "--baseline", path)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("形式が", proc.stderr)

    def test_読めない基準を拒否する(self) -> None:
        self.add_skill("dev-spec")
        proc = run_script(
            META_CHECK_PY, "--root", self.root, "--baseline", self.tmp / "missing.json"
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("読み込みに失敗", proc.stderr)


class CliTest(MetaCheckTestCase):
    def test_root_に_claude_が無ければ停止する(self) -> None:
        proc = run_script(META_CHECK_PY, "--root", self.tmp / "missing")
        self.assertEqual(proc.returncode, 1)
        self.assertIn(".claude が無い", proc.stderr)

    def test_error_があれば終了コード_1(self) -> None:
        d = self.root / ".claude" / "skills" / "dev-spec"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(skill_md("dev-other"), encoding="utf-8")
        proc = run_script(META_CHECK_PY, "--root", self.root)
        self.assertEqual(proc.returncode, 1)

    def test_違反が無ければ終了コード_0(self) -> None:
        self.add_skill("dev-spec")
        proc = run_script(META_CHECK_PY, "--root", self.root)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_NEW_の印で回帰を区別する(self) -> None:
        self.add_skill("dev-spec")
        baseline = self.tmp / "baseline.json"
        proc = run_script(META_CHECK_PY, "--root", self.root, "--json")
        baseline.write_text(proc.stdout, encoding="utf-8")
        self.add_skill("dev-decompose", body="dev-nonexistent を呼ぶ")
        proc = run_script(META_CHECK_PY, "--root", self.root, "--baseline", baseline)
        self.assertIn("NEW", proc.stdout)
        self.assertIn("新規 1 件", proc.stdout)


if __name__ == "__main__":
    unittest.main()
