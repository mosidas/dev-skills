"""meta-core/scripts/trigger_check.py の単体テスト。

肯定例・否定例の判定、description の近接衝突、検査ケースの網羅、仕様ファイルの
異常系を対象にする。判定は語彙の重なりだけで行う近似のため、ここでは「意図した違反を
検出できるか」と「正当な構成で誤検出しないか」を確かめる。
"""

from __future__ import annotations

import json
import math
import unittest

import helpers

from helpers import META_SCRIPTS, run_json, run_script

import trigger_check

TRIGGER_PY = META_SCRIPTS / "trigger_check.py"

SPEC_DESC = "仕様部品。依頼内容を壁打ちで確定し、公開インターフェースとデータ構造の契約と受け入れ基準を spec.md に生成する。"
IMPL_DESC = "実装部品。タスク定義をもとに TDD で実装し、レビューと検証を回してコミットする。"


class SimilarityTest(unittest.TestCase):
    def test_同一の文字列は類似度_1(self) -> None:
        grams = trigger_check.bigrams("仕様を確定する")
        self.assertAlmostEqual(trigger_check.similarity(grams, grams), 1.0)

    def test_共通部分が無ければ_0(self) -> None:
        a = trigger_check.bigrams("あいうえお")
        b = trigger_check.bigrams("かきくけこ")
        self.assertEqual(trigger_check.similarity(a, b), 0.0)

    def test_空集合との類似度は_0(self) -> None:
        self.assertEqual(trigger_check.similarity(set(), trigger_check.bigrams("x")), 0.0)

    def test_記号と空白を語彙から除く(self) -> None:
        self.assertEqual(
            trigger_check.bigrams("仕様 を、確定"), trigger_check.bigrams("仕様を確定")
        )

    def test_長い_description_が一方的に有利にならない(self) -> None:
        prompt = trigger_check.bigrams("契約を確定する")
        short = trigger_check.bigrams("契約を確定する")
        long = trigger_check.bigrams("契約を確定する" + "無関係な記述" * 20)
        self.assertGreater(
            trigger_check.similarity(prompt, short),
            trigger_check.similarity(prompt, long),
        )
        # コサインの定義どおり、長い側は語彙数の平方根で割り引かれる。
        self.assertAlmostEqual(
            trigger_check.similarity(prompt, long),
            len(prompt & long) / math.sqrt(len(prompt) * len(long)),
        )


class TriggerCheckTestCase(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        (self.root / "dev" / "skills").mkdir(parents=True)
        self.add_skill("dev-spec", SPEC_DESC)
        self.add_skill("dev-implement", IMPL_DESC)

    def add_skill(self, name: str, description: str) -> None:
        d = self.root / "dev" / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
            encoding="utf-8",
        )

    def cases_file(self, cases: list[dict] | dict) -> str:
        path = self.tmp / "cases.json"
        payload = cases if isinstance(cases, dict) else {"cases": cases}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def run_check(self, cases, *extra) -> dict:
        return run_json(
            TRIGGER_PY, "--root", self.root, "--cases", self.cases_file(cases), "--json", *extra
        )

    def full_cases(self) -> list[dict]:
        return [
            {
                "id": "spec-pos",
                "skill": "dev-spec",
                "prompt": "公開インターフェースとデータ構造の契約を壁打ちで確定したい",
                "should_trigger": True,
            },
            {
                "id": "impl-pos",
                "skill": "dev-implement",
                "prompt": "タスク定義をもとに TDD で実装してレビューまで回して",
                "should_trigger": True,
            },
        ]


class CaseJudgementTest(TriggerCheckTestCase):
    def test_肯定例で対象が_1_位なら通過する(self) -> None:
        result = self.run_check(self.full_cases())
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["warnings"], 0)

    def test_肯定例で別スキルが_1_位なら_warning(self) -> None:
        cases = self.full_cases()
        cases[0]["prompt"] = "タスク定義をもとに TDD で実装してレビューまで回して"
        result = self.run_check(cases)
        self.assertEqual(result["warnings"], 1)
        self.assertAnyContains(
            self.messages(result["findings"]), "肯定例で dev-spec が 1 位にならない"
        )

    def test_否定例で対象が_1_位なら_warning(self) -> None:
        cases = self.full_cases()
        cases[0]["should_trigger"] = False
        result = self.run_check(cases)
        self.assertAnyContains(
            self.messages(result["findings"]), "否定例で dev-spec が 1 位になる"
        )

    def test_否定例で対象が_1_位でなければ通過する(self) -> None:
        cases = self.full_cases()
        cases.append(
            {
                "id": "spec-neg",
                "skill": "dev-spec",
                "prompt": "タスク定義をもとに TDD で実装してレビューまで回して",
                "should_trigger": False,
            }
        )
        self.assertEqual(self.run_check(cases)["passed"], 3)

    def test_実在しないスキルを_error_にする(self) -> None:
        cases = self.full_cases()
        cases.append(
            {"id": "x", "skill": "dev-unknown", "prompt": "何か", "should_trigger": True}
        )
        result = self.run_check(cases)
        self.assertEqual(result["errors"], 1)
        self.assertAnyContains(self.messages(result["findings"]), "実在しない")

    def test_error_があれば終了コード_1(self) -> None:
        cases = [
            {"id": "x", "skill": "dev-unknown", "prompt": "何か", "should_trigger": True}
        ]
        proc = run_script(
            TRIGGER_PY, "--root", self.root, "--cases", self.cases_file(cases)
        )
        self.assertEqual(proc.returncode, 1)


class CoverageTest(TriggerCheckTestCase):
    def test_ケースの無いスキルを_warning_にする(self) -> None:
        cases = [c for c in self.full_cases() if c["skill"] == "dev-spec"]
        result = self.run_check(cases)
        self.assertAnyContains(
            self.messages(result["findings"]), "dev-implement の検査ケースが仕様ファイルに 1 件も無い"
        )

    def test_全スキルにケースがあれば指摘しない(self) -> None:
        self.assertEqual(self.run_check(self.full_cases())["warnings"], 0)

    def test_description_を持たないスキルは対象にしない(self) -> None:
        d = self.root / "dev" / "skills" / "dev-core"
        d.mkdir(parents=True)
        (d / "references").mkdir()
        self.assertEqual(self.run_check(self.full_cases())["warnings"], 0)


class CollisionTest(TriggerCheckTestCase):
    def test_近接する_description_を_warning_にする(self) -> None:
        self.add_skill("dev-twin", SPEC_DESC)
        cases = self.full_cases() + [
            {"id": "twin", "skill": "dev-twin", "prompt": "x", "should_trigger": False}
        ]
        result = self.run_check(cases)
        self.assertAnyContains(
            self.messages(result["findings"]), "description が近接している"
        )

    def test_閾値を上げれば指摘しない(self) -> None:
        self.add_skill("dev-twin", SPEC_DESC + "ただし別の役割を持つ。")
        cases = self.full_cases() + [
            {"id": "twin", "skill": "dev-twin", "prompt": "x", "should_trigger": False}
        ]
        result = self.run_check(cases, "--collision-threshold", "0.99")
        self.assertNoneContains(
            self.messages(result["findings"]), "description が近接している"
        )


class SpecFileTest(TriggerCheckTestCase):
    def test_cases_が配列でなければ停止する(self) -> None:
        proc = run_script(
            TRIGGER_PY,
            "--root",
            self.root,
            "--cases",
            self.cases_file({"cases": {"a": 1}}),
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("形式が不正", proc.stderr)

    def test_要素が辞書でなければ停止する(self) -> None:
        proc = run_script(
            TRIGGER_PY, "--root", self.root, "--cases", self.cases_file(["文字列"])
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("形式が不正", proc.stderr)

    def test_仕様ファイルが読めなければ停止する(self) -> None:
        proc = run_script(
            TRIGGER_PY, "--root", self.root, "--cases", self.tmp / "missing.json"
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("読めない", proc.stderr)

    def test_root_にスキルのグループが無ければ停止する(self) -> None:
        proc = run_script(TRIGGER_PY, "--root", self.tmp / "missing")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("スキルのグループが無い", proc.stderr)


class RealRepositoryTest(unittest.TestCase):
    def test_同梱の仕様ファイルが全ケース通過する(self) -> None:
        result = run_json(TRIGGER_PY, "--root", helpers.REPO_ROOT, "--json")
        self.assertEqual(result["passed"], result["cases"])
        self.assertEqual(result["errors"], 0)
        self.assertEqual(result["warnings"], 0)


if __name__ == "__main__":
    unittest.main()
