"""meta-core/scripts/meta_extract.py の単体テスト。

DESIGN.md の構造層の素材(部品・スクリプト・エージェント・状態機械・inject グラフ)の
抽出を対象にする。抽出結果は DESIGN.md の生成の入力であり、取りこぼしはそのまま
俯瞰文書と実体の乖離になる。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import helpers

from helpers import META_SCRIPTS, run_script

import meta_extract

EXTRACT_PY = META_SCRIPTS / "meta_extract.py"


DEV_LAYERS = {"0": ["dev-core"], "2": ["flow-*"], "3": ["ext-*"]}


class ClassifyTest(helpers.TempDirTestCase):
    """分類はグループ名から、レイヤーはグループの規約から決まる(D-013)。"""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        self.write_group("dev", {"layers": DEV_LAYERS})
        self.write_group(".claude", {"layers": {"0": ["meta-core"]}})
        self.write_group("ops", None)

    def write_group(self, group: str, config: dict | None) -> None:
        (self.root / group / "skills").mkdir(parents=True)
        if config is not None:
            (self.root / group / "group.json").write_text(
                json.dumps(config), encoding="utf-8"
            )

    def skill(self, group: str, name: str) -> Path:
        return self.root / group / "skills" / name

    def test_基盤スキルをレイヤー_0_にする(self) -> None:
        self.assertEqual(meta_extract.classify(self.skill("dev", "dev-core")), ("dev", 0))
        self.assertEqual(
            meta_extract.classify(self.skill(".claude", "meta-core")), ("meta", 0)
        )

    def test_部品をレイヤー_1_にする(self) -> None:
        self.assertEqual(meta_extract.classify(self.skill("dev", "dev-spec")), ("dev", 1))
        self.assertEqual(
            meta_extract.classify(self.skill(".claude", "meta-check")), ("meta", 1)
        )

    def test_composition_をレイヤー_2_にする(self) -> None:
        self.assertEqual(meta_extract.classify(self.skill("dev", "flow-sdd")), ("dev", 2))

    def test_拡張をレイヤー_3_にする(self) -> None:
        self.assertEqual(
            meta_extract.classify(self.skill("dev", "ext-anything")), ("dev", 3)
        )

    def test_分類をグループ名から決める(self) -> None:
        """名前ではなく配置(どのグループに置いたか)が分類を決める。"""
        self.assertEqual(meta_extract.classify(self.skill("ops", "ops-deploy"))[0], "ops")

    def test_規約を持たないグループは全て部品にする(self) -> None:
        """レイヤー構造を持たない群でも、規約を書かずに抽出が成立する。"""
        self.assertEqual(meta_extract.classify(self.skill("ops", "dev-core")), ("ops", 1))


class ExtractTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        (self.root / "dev" / "skills").mkdir(parents=True)
        (self.root / "dev" / "agents").mkdir(parents=True)

    def add_skill(self, name: str, description: str = "説明") -> None:
        d = self.root / "dev" / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n", encoding="utf-8"
        )

    def test_部品の分類とレイヤーと役割を返す(self) -> None:
        self.add_skill("dev-spec", "仕様部品")
        parts = meta_extract.extract_parts(self.root)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["family"], "dev")
        self.assertEqual(parts[0]["layer"], 1)
        self.assertEqual(parts[0]["role"], "仕様部品")
        self.assertTrue(parts[0]["has_skill_md"])

    def test_配布しないグループの部品も返す(self) -> None:
        """`.claude` に置く meta-* も抽出の対象にする(DESIGN の構成要素に載せるため)。"""
        d = self.root / ".claude" / "skills" / "meta-check"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: meta-check\ndescription: 機械検査\n---\n", encoding="utf-8"
        )
        parts = meta_extract.extract_parts(self.root)
        self.assertEqual([(p["name"], p["family"]) for p in parts], [("meta-check", "meta")])

    def test_SKILL_を持たない基盤も部品として返す(self) -> None:
        (self.root / "dev" / "skills" / "dev-core" / "references").mkdir(parents=True)
        parts = meta_extract.extract_parts(self.root)
        self.assertFalse(parts[0]["has_skill_md"])
        self.assertEqual(parts[0]["role"], "")

    def test_引用符つきの_description_を剥がして返す(self) -> None:
        d = self.root / "dev" / "skills" / "dev-spec"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            '---\nname: dev-spec\ndescription: "仕様部品"\n---\n', encoding="utf-8"
        )
        self.assertEqual(meta_extract.extract_parts(self.root)[0]["role"], "仕様部品")

    def test_スクリプトの所有部品と役割を返す(self) -> None:
        (self.root / "dev" / "group.json").write_text(
            json.dumps({"layers": DEV_LAYERS}), encoding="utf-8"
        )
        d = self.root / "dev" / "skills" / "dev-core" / "scripts"
        d.mkdir(parents=True)
        (d / "sample.py").write_text('"""サンプルの役割。\n\n続き。\n"""\n', encoding="utf-8")
        scripts = meta_extract.extract_scripts(self.root)
        self.assertEqual(scripts[0]["name"], "dev-core/scripts/sample.py")
        self.assertEqual(scripts[0]["role"], "サンプルの役割。")
        self.assertEqual(scripts[0]["layer"], 0)

    def test_エージェントの_model_と役割を返す(self) -> None:
        (self.root / "dev" / "agents" / "dev-reviewer.md").write_text(
            "---\nname: dev-reviewer\ndescription: 判定器\nmodel: opus\n---\n",
            encoding="utf-8",
        )
        agents = meta_extract.extract_agents(self.root)
        self.assertEqual(agents[0]["model"], "opus")
        self.assertEqual(agents[0]["role"], "判定器")

    def test_状態機械の状態とゲートを返す(self) -> None:
        d = self.root / "dev" / "skills" / "flow-x"
        d.mkdir(parents=True)
        (d / "workflow.json").write_text(
            json.dumps(helpers.WORKFLOW_DEF, ensure_ascii=False), encoding="utf-8"
        )
        machines = meta_extract.extract_state_machines(self.root)
        self.assertEqual(machines[0]["owner"], "flow-x")
        self.assertEqual(machines[0]["gates"], ["draft"])
        self.assertIn("completed", machines[0]["final"])

    def test_壊れた状態機械定義をエラーとして返す(self) -> None:
        d = self.root / "dev" / "skills" / "flow-x"
        d.mkdir(parents=True)
        (d / "workflow.json").write_text("{壊れた", encoding="utf-8")
        self.assertIn("error", meta_extract.extract_state_machines(self.root)[0])

    def test_inject_グラフを_name_で引けるようにする(self) -> None:
        ports = self.root / "ports"
        ports.mkdir()
        (ports / "a.md").write_text(
            "---\nname: alpha\ndescription: x\ninject:\n  - dev-spec\ncondition: 常時\n---\n",
            encoding="utf-8",
        )
        graph = meta_extract.extract_inject_graph(self.root)
        self.assertEqual(graph["alpha"]["inject"], ["dev-spec"])
        self.assertEqual(graph["alpha"]["condition"], "常時")

    def test_雛形を_inject_グラフから除く(self) -> None:
        ports = self.root / "ports" / "templates"
        ports.mkdir(parents=True)
        (ports / "t.md").write_text(
            "---\nname: <name>\ndescription: x\ninject:\n  - <スキル>\ncondition: 常時\n---\n",
            encoding="utf-8",
        )
        self.assertEqual(meta_extract.extract_inject_graph(self.root), {})


class CliTest(unittest.TestCase):
    def test_実リポジトリで全区分を返す(self) -> None:
        proc = run_script(EXTRACT_PY, "--root", helpers.REPO_ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(
            sorted(data), ["agents", "inject_graph", "parts", "scripts", "state_machines"]
        )
        self.assertTrue(data["parts"])
        self.assertTrue(data["agents"])


if __name__ == "__main__":
    unittest.main()
