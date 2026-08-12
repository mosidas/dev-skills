"""dev-core/scripts/state.py の単体テスト。

状態遷移の拒否・承認ゲートの機械的強制・完了時の凍結を対象にする。承認ゲートは
「gate 付き遷移は approve のみ通過できる」ことが原則の機械的な担保であり、
退行すると人間の承認を経ずに工程が進む。`die()` が `sys.exit` を呼ぶため、
exit code とメッセージはサブプロセスで確かめる。
"""

from __future__ import annotations

import json
import unittest

import helpers

from helpers import DEV_SCRIPTS, run_json, run_script

STATE_PY = DEV_SCRIPTS / "state.py"


class StateMachineTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.defn = self.tmp / "workflow.json"
        self.defn.write_text(
            json.dumps(helpers.WORKFLOW_DEF, ensure_ascii=False), encoding="utf-8"
        )
        self.workdir = self.tmp / "unit-a"
        self.workdir.mkdir()

    def init(self, unit: str = "unit-a"):
        return run_script(
            STATE_PY, "init", "--def", self.defn, "--workdir", self.workdir, "--unit", unit
        )

    def state_json(self) -> dict:
        return json.loads((self.workdir / "state.json").read_text(encoding="utf-8"))

    def set_state(self, target: str):
        return run_script(
            STATE_PY, "set-state", "--def", self.defn, "--workdir", self.workdir, target
        )

    def approve(self, gate: str):
        return run_script(
            STATE_PY, "approve", "--def", self.defn, "--workdir", self.workdir, gate
        )

    # --- init ---

    def test_初期化で初期状態と未承認のゲートを書く(self) -> None:
        proc = self.init()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        state = self.state_json()
        self.assertEqual(state["workflow"], "testflow")
        self.assertEqual(state["unit"], "unit-a")
        self.assertEqual(state["state"], "initialized")
        self.assertEqual(state["approvals"], {"draft": False})

    def test_二重初期化を拒否する(self) -> None:
        self.init()
        proc = self.init()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("既に存在します", proc.stderr)

    def test_定義が不正なら初期化しない(self) -> None:
        broken = self.tmp / "broken.json"
        broken.write_text(json.dumps({"name": "x"}), encoding="utf-8")
        proc = run_script(
            STATE_PY, "init", "--def", broken, "--workdir", self.tmp / "unit-b"
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("states が未定義", proc.stderr)

    # --- init の採番(--root) ---

    def init_root(self, root, unit: str, unique_root=None):
        extra = ["--unique-root", unique_root] if unique_root is not None else []
        return run_script(
            STATE_PY, "init", "--def", self.defn, "--root", root, "--unit", unit, *extra
        )

    def test_root_指定で連番付きの_workdir_を作る(self) -> None:
        root = self.tmp / "specs"
        proc = self.init_root(root, "user-auth")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        created = root / "001-user-auth"
        self.assertTrue(created.is_dir())
        self.assertIn(f"workdir: {created}", proc.stdout)
        state = json.loads((created / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["unit"], "user-auth")

    def test_連番は既存の最大番号の次になり欠番を埋めない(self) -> None:
        root = self.tmp / "specs"
        (root / "001-a").mkdir(parents=True)
        (root / "005-b").mkdir()
        proc = self.init_root(root, "c")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((root / "006-c").is_dir())

    def test_連番を持たないディレクトリを採番の対象にしない(self) -> None:
        root = self.tmp / "specs"
        (root / "legacy-unit").mkdir(parents=True)
        proc = self.init_root(root, "fresh")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((root / "001-fresh").is_dir())

    def test_999_を超えても採番が続く(self) -> None:
        root = self.tmp / "specs"
        (root / "999-old").mkdir(parents=True)
        proc = self.init_root(root, "next")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((root / "1000-next").is_dir())

    def test_同じ_unit_の_workdir_が既にあれば拒否する(self) -> None:
        root = self.tmp / "specs"
        self.init_root(root, "user-auth")
        proc = self.init_root(root, "user-auth")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("同じ作業単位の workdir が既にあります", proc.stderr)
        self.assertFalse((root / "002-user-auth").exists())

    def test_連番を持たない同名の_workdir_も重複として拒否する(self) -> None:
        root = self.tmp / "specs"
        (root / "user-auth").mkdir(parents=True)
        proc = self.init_root(root, "user-auth")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("同じ作業単位の workdir が既にあります", proc.stderr)

    def test_別の_unit_なら拒否しない(self) -> None:
        root = self.tmp / "specs"
        self.init_root(root, "user-auth")
        proc = self.init_root(root, "user-auth-2")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((root / "002-user-auth-2").is_dir())

    # --- 階層を分けたルート(roadmap ごとに採番を閉じる構成) ---

    def test_採番はルート直下で閉じるため階層ごとに独立する(self) -> None:
        specs = self.tmp / "specs"
        self.init_root(specs / "001-mvp", "test-harness")
        self.init_root(specs / "001-mvp", "foot-player")
        proc = self.init_root(specs / "002-v2", "netspace-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((specs / "001-mvp" / "001-test-harness").is_dir())
        self.assertTrue((specs / "001-mvp" / "002-foot-player").is_dir())
        self.assertTrue((specs / "002-v2" / "001-netspace-run").is_dir())

    def test_unique_root_が上位の階層の同名_unit_を拒否する(self) -> None:
        specs = self.tmp / "specs"
        self.init_root(specs / "001-mvp", "foot-player")
        proc = self.init_root(specs / "002-v2", "foot-player", unique_root=specs)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("同じ作業単位の workdir が既にあります", proc.stderr)
        self.assertFalse((specs / "002-v2" / "001-foot-player").exists())

    def test_unique_root_なしならルート直下だけを見る(self) -> None:
        specs = self.tmp / "specs"
        self.init_root(specs / "001-mvp", "foot-player")
        proc = self.init_root(specs / "002-v2", "foot-player")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((specs / "002-v2" / "001-foot-player").is_dir())

    def test_unique_root_でも別の_unit_なら通す(self) -> None:
        specs = self.tmp / "specs"
        self.init_root(specs / "001-mvp", "foot-player")
        proc = self.init_root(specs / "002-v2", "netspace-run", unique_root=specs)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((specs / "002-v2" / "001-netspace-run").is_dir())

    def test_root_指定で_unit_を省略すると拒否する(self) -> None:
        proc = run_script(
            STATE_PY, "init", "--def", self.defn, "--root", self.tmp / "specs"
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--root には --unit が要ります", proc.stderr)

    def test_workdir_名に使えない_unit_名を拒否する(self) -> None:
        root = self.tmp / "specs"
        for unit, needle in (
            ("a/b", "パス区切り"),
            ("007-bond", "連番で始まっています"),
        ):
            with self.subTest(unit=unit):
                proc = self.init_root(root, unit)
                self.assertEqual(proc.returncode, 1)
                self.assertIn(needle, proc.stderr)

    def test_root_がディレクトリでなければ拒否する(self) -> None:
        root = self.tmp / "specs"
        root.write_text("ファイル", encoding="utf-8")
        proc = self.init_root(root, "user-auth")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--root がディレクトリではありません", proc.stderr)

    def test_root_と_workdir_の同時指定を拒否する(self) -> None:
        proc = run_script(
            STATE_PY,
            "init",
            "--def",
            self.defn,
            "--root",
            self.tmp / "specs",
            "--workdir",
            self.workdir,
            "--unit",
            "x",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not allowed with argument", proc.stderr)

    def test_workdir_指定の初期化は連番を付けない(self) -> None:
        proc = self.init()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.workdir / "state.json").is_file())
        self.assertEqual(self.state_json()["unit"], "unit-a")

    # --- set-state ---

    def test_定義された遷移で状態を進める(self) -> None:
        self.init()
        proc = self.set_state("drafted")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.state_json()["state"], "drafted")

    def test_定義にない状態への遷移を拒否する(self) -> None:
        self.init()
        proc = self.set_state("unknown")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("定義にありません", proc.stderr)
        self.assertEqual(self.state_json()["state"], "initialized")

    def test_定義にない遷移を拒否する(self) -> None:
        self.init()
        proc = self.set_state("completed")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("遷移 initialized -> completed は定義にありません", proc.stderr)

    def test_ゲート付き遷移を_set_state_で通過できない(self) -> None:
        self.init()
        self.set_state("drafted")
        proc = self.set_state("approved")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("承認ゲート", proc.stderr)
        self.assertIn("approve draft", proc.stderr)
        self.assertEqual(self.state_json()["state"], "drafted")

    def test_差し戻しの遷移を通す(self) -> None:
        self.init()
        self.set_state("drafted")
        proc = self.set_state("initialized")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.state_json()["state"], "initialized")

    # --- approve ---

    def test_承認でゲートを通過し承認フラグを立てる(self) -> None:
        self.init()
        self.set_state("drafted")
        proc = self.approve("draft")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        state = self.state_json()
        self.assertEqual(state["state"], "approved")
        self.assertTrue(state["approvals"]["draft"])

    def test_定義にないゲート名を拒否する(self) -> None:
        self.init()
        self.set_state("drafted")
        proc = self.approve("unknown")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("ゲート 'unknown' は定義にありません", proc.stderr)

    def test_現在の状態から到達しないゲートを拒否する(self) -> None:
        self.init()
        proc = self.approve("draft")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("ゲート 'draft' 付きの遷移はありません", proc.stderr)
        self.assertFalse(self.state_json()["approvals"]["draft"])

    # --- 凍結 ---

    def test_完了状態への到達で成果物を凍結する(self) -> None:
        self.init()
        (self.workdir / "spec.md").write_text("内容", encoding="utf-8")
        self.set_state("drafted")
        self.approve("draft")
        proc = self.set_state("completed")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        frozen = self.state_json()["frozen"]
        self.assertIn("spec.md", frozen)
        self.assertEqual(len(frozen["spec.md"]), 64)

    def test_存在しない成果物は凍結の対象にしない(self) -> None:
        self.init()
        self.set_state("drafted")
        self.approve("draft")
        self.set_state("completed")
        self.assertEqual(self.state_json()["frozen"], {})

    # --- 読み取り系 ---

    def test_status_が承認と成果物と次の遷移を返す(self) -> None:
        self.init()
        (self.workdir / "spec.md").write_text("内容", encoding="utf-8")
        self.set_state("drafted")
        result = run_json(
            STATE_PY, "status", "--def", self.defn, "--workdir", self.workdir, "--json"
        )
        self.assertEqual(result["state"], "drafted")
        self.assertFalse(result["final"])
        self.assertEqual(result["approvals"], {"draft": False})
        self.assertEqual(result["artifacts"], {"spec.md": True})
        self.assertIn(
            {"to": "approved", "gate": "draft"}, result["next_transitions"]
        )

    def test_show_が_state_json_をそのまま返す(self) -> None:
        self.init()
        proc = run_script(STATE_PY, "show", "--workdir", self.workdir)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["unit"], "unit-a")

    def test_scan_が複数の_workdir_を集約し別ワークフローを除く(self) -> None:
        self.init()
        self.set_state("drafted")
        self.approve("draft")
        self.set_state("completed")
        other = self.tmp / "unit-b"
        other.mkdir()
        (other / "state.json").write_text(
            json.dumps({"workflow": "another", "state": "x"}), encoding="utf-8"
        )
        result = run_json(
            STATE_PY, "scan", "--def", self.defn, "--root", self.tmp, "--json"
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(len(result["others"]), 1)
        self.assertIn("別ワークフロー", result["others"][0]["note"])

    def test_scan_が連番付きと連番なしの_workdir_を同じに扱う(self) -> None:
        root = self.tmp / "specs"
        self.init_root(root, "user-auth")
        legacy = root / "legacy-unit"
        legacy.mkdir()
        run_script(STATE_PY, "init", "--def", self.defn, "--workdir", legacy)
        result = run_json(
            STATE_PY, "scan", "--def", self.defn, "--root", root, "--json"
        )
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["others"], [])
        self.assertEqual(
            [u["unit"] for u in result["units"]], ["user-auth", "legacy-unit"]
        )

    def test_scan_の各行がどの定義に属するかを持つ(self) -> None:
        self.init()
        result = run_json(
            STATE_PY, "scan", "--def", self.defn, "--root", self.tmp, "--json"
        )
        self.assertEqual(result["workflows"], ["testflow"])
        self.assertEqual(result["units"][0]["workflow"], "testflow")

    def test_scan_は複数の定義を指定すると両方を集約する(self) -> None:
        other_def = self.tmp / "other.json"
        other_def.write_text(
            json.dumps(
                {
                    "name": "otherflow",
                    "states": ["initialized", "frozen"],
                    "initial": "initialized",
                    "final": ["frozen"],
                    "transitions": [{"from": "initialized", "to": "frozen"}],
                    "artifacts": {"frozen": ["note.md"]},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        root = self.tmp / "specs"
        run_script(
            STATE_PY, "init", "--def", other_def, "--root", root, "--unit", "mvp"
        )
        self.init_root(root / "001-mvp", "user-auth")

        only_one = run_json(
            STATE_PY, "scan", "--def", self.defn, "--root", root, "--json"
        )
        self.assertEqual(only_one["total"], 1)
        self.assertEqual(len(only_one["others"]), 1)
        self.assertIn("別ワークフロー: otherflow", only_one["others"][0]["note"])

        both = run_json(
            STATE_PY,
            "scan",
            "--def", self.defn,
            "--def", other_def,
            "--root", root,
            "--json",
        )
        self.assertEqual(both["workflows"], ["testflow", "otherflow"])
        self.assertEqual(both["total"], 2)
        self.assertEqual(both["others"], [])
        self.assertEqual(
            {(u["workflow"], u["unit"]) for u in both["units"]},
            {("otherflow", "mvp"), ("testflow", "user-auth")},
        )

    def test_scan_は不正な_JSON_を対象外として報告する(self) -> None:
        broken = self.tmp / "unit-c"
        broken.mkdir()
        (broken / "state.json").write_text("{壊れた", encoding="utf-8")
        result = run_json(
            STATE_PY, "scan", "--def", self.defn, "--root", self.tmp, "--json"
        )
        self.assertEqual(result["total"], 0)
        self.assertIn("不正な JSON", result["others"][0]["note"])

    def test_ワークフロー名が一致しない_state_json_を拒否する(self) -> None:
        self.init()
        state = self.state_json()
        state["workflow"] = "other"
        (self.workdir / "state.json").write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
        proc = self.set_state("drafted")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("ワークフロー不一致", proc.stderr)


class FlowSddDefinitionTest(helpers.TempDirTestCase):
    """flow-sdd が配る 2 つの定義データを、実物のまま駆動して確かめる。

    roadmap と unit を階層で分ける構成(flow-sdd/SKILL.md 1.)が成立するかは、
    定義データの妥当性と 2 つの状態機械の独立性に依存する。定義を書き写さず
    配布物そのものを読むことで、定義の変更が検査を素通りしない形にする。
    """

    FLOW_SDD = helpers.REPO_ROOT / "dev" / "skills" / "flow-sdd"
    UNIT_DEF = FLOW_SDD / "workflow.json"
    ROADMAP_DEF = FLOW_SDD / "roadmap.json"

    def roadmap_state(self, workdir) -> dict:
        return json.loads((workdir / "state.json").read_text(encoding="utf-8"))

    def test_roadmap_は生成から承認を経て凍結へ進む(self) -> None:
        specs = self.tmp / "docs" / "specs"
        proc = run_script(
            STATE_PY, "init", "--def", self.ROADMAP_DEF,
            "--root", specs, "--unit", "mvp",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        workdir = specs / "001-mvp"
        (workdir / "roadmap.md").write_text("# roadmap", encoding="utf-8")

        for args in (
            ("set-state", "roadmap-generated"),
            ("approve", "roadmap"),
            ("set-state", "frozen"),
        ):
            proc = run_script(
                STATE_PY, args[0], "--def", self.ROADMAP_DEF,
                "--workdir", workdir, args[1],
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)

        state = self.roadmap_state(workdir)
        self.assertEqual(state["state"], "frozen")
        self.assertTrue(state["approvals"]["roadmap"])
        self.assertEqual(len(state["frozen"]["roadmap.md"]), 64)

    def test_roadmap_の承認ゲートは_set_state_で通過できない(self) -> None:
        specs = self.tmp / "docs" / "specs"
        run_script(
            STATE_PY, "init", "--def", self.ROADMAP_DEF,
            "--root", specs, "--unit", "mvp",
        )
        workdir = specs / "001-mvp"
        run_script(
            STATE_PY, "set-state", "--def", self.ROADMAP_DEF,
            "--workdir", workdir, "roadmap-generated",
        )
        proc = run_script(
            STATE_PY, "set-state", "--def", self.ROADMAP_DEF,
            "--workdir", workdir, "roadmap-approved",
        )
        self.assertEqual(proc.returncode, 1)

    def test_roadmap_は差し戻して再承認できる(self) -> None:
        specs = self.tmp / "docs" / "specs"
        run_script(
            STATE_PY, "init", "--def", self.ROADMAP_DEF,
            "--root", specs, "--unit", "mvp",
        )
        workdir = specs / "001-mvp"
        (workdir / "roadmap.md").write_text("# roadmap", encoding="utf-8")
        run_script(
            STATE_PY, "set-state", "--def", self.ROADMAP_DEF,
            "--workdir", workdir, "roadmap-generated",
        )
        run_script(
            STATE_PY, "approve", "--def", self.ROADMAP_DEF,
            "--workdir", workdir, "roadmap",
        )
        proc = run_script(
            STATE_PY, "set-state", "--def", self.ROADMAP_DEF,
            "--workdir", workdir, "roadmap-generated",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("frozen", self.roadmap_state(workdir))

    def test_unit_の連番は_roadmap_ごとに閉じ名前は跨いで一意になる(self) -> None:
        specs = self.tmp / "docs" / "specs"
        for name in ("mvp", "v2"):
            run_script(
                STATE_PY, "init", "--def", self.ROADMAP_DEF,
                "--root", specs, "--unit", name,
            )

        def init_unit(roadmap: str, unit: str):
            return run_script(
                STATE_PY, "init", "--def", self.UNIT_DEF,
                "--root", specs / roadmap, "--unit", unit,
                "--unique-root", specs,
            )

        self.assertEqual(init_unit("001-mvp", "test-harness").returncode, 0)
        self.assertEqual(init_unit("001-mvp", "foot-player").returncode, 0)
        self.assertEqual(init_unit("002-v2", "netspace-run").returncode, 0)
        self.assertTrue((specs / "001-mvp" / "002-foot-player").is_dir())
        self.assertTrue((specs / "002-v2" / "001-netspace-run").is_dir())

        collide = init_unit("002-v2", "foot-player")
        self.assertEqual(collide.returncode, 1)
        self.assertIn("同じ作業単位の workdir が既にあります", collide.stderr)

    def test_scan_が_roadmap_と_unit_を同時に一覧する(self) -> None:
        specs = self.tmp / "docs" / "specs"
        run_script(
            STATE_PY, "init", "--def", self.ROADMAP_DEF,
            "--root", specs, "--unit", "mvp",
        )
        run_script(
            STATE_PY, "init", "--def", self.UNIT_DEF,
            "--root", specs / "001-mvp", "--unit", "test-harness",
            "--unique-root", specs,
        )
        result = run_json(
            STATE_PY, "scan",
            "--def", self.UNIT_DEF,
            "--def", self.ROADMAP_DEF,
            "--root", specs, "--json",
        )
        self.assertEqual(result["others"], [])
        self.assertEqual(
            {(u["workflow"], u["unit"]) for u in result["units"]},
            {("roadmap", "mvp"), ("sdd", "test-harness")},
        )


if __name__ == "__main__":
    unittest.main()
