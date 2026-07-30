"""dev-core/scripts/check.py の単体テスト。

状態検査(凍結のハッシュ照合を含む)・トレーサビリティ検査・対象ファイルの行数検査を
対象にする。凍結違反の検出は、実装完了後に中間生成物が書き換わっていないことの機械的な
担保であり、退行すると凍結が名目だけになる。
"""

from __future__ import annotations

import json
import unittest

import helpers

from helpers import DEV_SCRIPTS, run_json, run_script

import check

CHECK_PY = DEV_SCRIPTS / "check.py"
STATE_PY = DEV_SCRIPTS / "state.py"


class StateCheckTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.defn_path = self.tmp / "workflow.json"
        self.defn_path.write_text(
            json.dumps(helpers.WORKFLOW_DEF, ensure_ascii=False), encoding="utf-8"
        )
        self.defn = json.loads(self.defn_path.read_text(encoding="utf-8"))
        self.workdir = self.tmp / "unit"
        self.workdir.mkdir()

    def report_for(self, state: dict) -> check.Report:
        (self.workdir / "state.json").write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
        report = check.Report()
        check.check_state(self.defn, self.workdir, report)
        return report

    def base_state(self, **overrides) -> dict:
        state = {
            "workflow": "testflow",
            "unit": "unit",
            "state": "initialized",
            "approvals": {"draft": False},
            "created": "2026-01-01",
            "updated": "2026-01-01",
        }
        state.update(overrides)
        return state

    def test_state_json_が無ければ_error(self) -> None:
        report = check.Report()
        check.check_state(self.defn, self.workdir, report)
        self.assertEqual(report.count("error"), 1)
        self.assertAnyContains(self.messages(report.findings), "state.json が存在しない")

    def test_必須フィールドの欠落を_error_にする(self) -> None:
        state = self.base_state()
        del state["unit"]
        report = self.report_for(state)
        self.assertAnyContains(self.messages(report.findings), "必須フィールド 'unit'")

    def test_ワークフロー名の不一致を_error_にする(self) -> None:
        report = self.report_for(self.base_state(workflow="other"))
        self.assertAnyContains(self.messages(report.findings), "ワークフロー不一致")

    def test_定義にない状態を_error_にする(self) -> None:
        report = self.report_for(self.base_state(state="unknown"))
        self.assertAnyContains(self.messages(report.findings), "states に含まれない")

    def test_成果物の欠落を_error_にする(self) -> None:
        report = self.report_for(self.base_state(state="drafted"))
        self.assertAnyContains(
            self.messages(report.findings), "存在すべき成果物がない: spec.md"
        )

    def test_承認ゲートのキー欠落を_warning_にする(self) -> None:
        report = self.report_for(self.base_state(approvals={}))
        self.assertAnyContains(
            self.messages(report.findings, "warning"), "ゲート 'draft' のキーがない"
        )

    def test_完了状態で凍結が無ければ_error(self) -> None:
        (self.workdir / "spec.md").write_text("内容", encoding="utf-8")
        report = self.report_for(self.base_state(state="completed"))
        self.assertAnyContains(self.messages(report.findings), "frozen(凍結ハッシュ)")

    def test_凍結後の変更を凍結違反として_error_にする(self) -> None:
        path = self.workdir / "spec.md"
        path.write_text("内容", encoding="utf-8")
        import lib

        digest = lib.sha256_of(path)
        path.write_text("書き換えた内容", encoding="utf-8")
        report = self.report_for(
            self.base_state(state="completed", frozen={"spec.md": digest})
        )
        self.assertAnyContains(self.messages(report.findings), "凍結違反")

    def test_凍結した成果物の削除を_error_にする(self) -> None:
        report = self.report_for(
            self.base_state(state="completed", frozen={"spec.md": "0" * 64})
        )
        self.assertAnyContains(self.messages(report.findings), "削除されている")

    def test_ハッシュが一致すれば_error_を出さない(self) -> None:
        path = self.workdir / "spec.md"
        path.write_text("内容", encoding="utf-8")
        import lib

        report = self.report_for(
            self.base_state(state="completed", frozen={"spec.md": lib.sha256_of(path)})
        )
        self.assertEqual(report.count("error"), 0, self.messages(report.findings))

    def test_完了前の凍結記録を_warning_にする(self) -> None:
        (self.workdir / "spec.md").write_text("内容", encoding="utf-8")
        report = self.report_for(self.base_state(state="drafted", frozen={}))
        self.assertAnyContains(
            self.messages(report.findings, "warning"), "完了状態でないのに frozen"
        )


class MarkdownCheckTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.workdir = self.tmp / "unit"
        self.workdir.mkdir()

    def run_markdown(self, ports_root: str = "docs/dev/ports", max_lines: int = 600):
        report = check.Report()
        check.check_markdown(
            self.workdir, self.tmp / ports_root, self.tmp, max_lines, report
        )
        return report

    def test_要件番号の欠番を_warning_にする(self) -> None:
        (self.workdir / "spec.md").write_text(
            "### Requirement 1: A\n\n1.1. 基準\n\n### Requirement 3: B\n\n3.1. 基準\n",
            encoding="utf-8",
        )
        self.assertAnyContains(
            self.messages(self.run_markdown().findings, "warning"), "要件番号に欠番"
        )

    def test_トレーサビリティの前方と後方を照合する(self) -> None:
        (self.workdir / "spec.md").write_text(
            "### Requirement 1: A\n\n1.1. 基準\n1.2. 基準\n", encoding="utf-8"
        )
        (self.workdir / "tasks.md").write_text(
            "- [ ] 1.1 サブ\n        _Requirements: 1.1, 9.9_\n"
            "    - 対象ファイル: `src/a.py`\n    - 検証コマンド: `true`\n",
            encoding="utf-8",
        )
        messages = self.messages(self.run_markdown().findings, "warning")
        self.assertAnyContains(messages, "_Requirements: 9.9 が spec.md に無い")
        self.assertAnyContains(messages, "カバーされていない要件 ID: 1.2")

    def test_依存の循環を_error_にする(self) -> None:
        (self.workdir / "tasks.md").write_text(
            "- [ ] 1.1 サブ\n        _Depends: 1.2_\n"
            "- [ ] 1.2 サブ\n        _Depends: 1.1_\n",
            encoding="utf-8",
        )
        report = self.run_markdown()
        self.assertEqual(report.count("error"), 1)
        self.assertAnyContains(self.messages(report.findings), "_Depends: に循環がある")

    def test_タスク固有情報の欠落を_warning_にする(self) -> None:
        (self.workdir / "tasks.md").write_text("- [ ] 1.1 サブ\n", encoding="utf-8")
        messages = self.messages(self.run_markdown().findings, "warning")
        self.assertAnyContains(messages, "「対象ファイル」が無い")
        self.assertAnyContains(messages, "「検証コマンド」が無い")

    def test_残存マーカーと曖昧語を報告する(self) -> None:
        (self.workdir / "spec.md").write_text(
            "### Requirement 1: A\n\n1.1. 適切に処理する\n[要確認: 未確定]\n",
            encoding="utf-8",
        )
        report = self.run_markdown()
        self.assertAnyContains(
            self.messages(report.findings, "warning"), "残存マーカー [要確認:"
        )
        self.assertAnyContains(self.messages(report.findings, "info"), "曖昧語")

    def test_Knowledge_注記の_port_実在を照合する(self) -> None:
        (self.tmp / "docs/dev/ports").mkdir(parents=True)
        (self.tmp / "docs/dev/ports/known.md").write_text(
            "---\nname: known\ndescription: x\ninject:\n  - dev-implement\ncondition: 常時\n---\n",
            encoding="utf-8",
        )
        (self.workdir / "tasks.md").write_text(
            "- [ ] 1.1 サブ\n        _Knowledge: unknown-port_\n"
            "    - 対象ファイル: `src/a.py`\n    - 検証コマンド: `true`\n",
            encoding="utf-8",
        )
        self.assertAnyContains(
            self.messages(self.run_markdown().findings, "warning"),
            "_Knowledge: unknown-port が port 走査結果に無い",
        )


class TargetFileSizeTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.tmp / "repo"
        (self.repo / "src").mkdir(parents=True)
        self.workdir = self.tmp / "wd"
        self.workdir.mkdir()

    def tasks(self, targets: str) -> list[dict]:
        import lib

        path = self.workdir / "tasks.md"
        path.write_text(
            f"- [ ] 1.1 サブ\n    - 対象ファイル: {targets}\n    - 検証コマンド: `true`\n",
            encoding="utf-8",
        )
        return lib.parse_tasks(path)

    def make_file(self, rel: str, lines: int) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n" * lines, encoding="utf-8")

    def run_sizes(self, targets: str, repo=None, max_lines: int = 600) -> check.Report:
        report = check.Report()
        check.check_target_file_sizes(
            self.tasks(targets), repo or self.repo, max_lines, report
        )
        return report

    def test_閾値を超えるファイルを_warning_にする(self) -> None:
        self.make_file("src/big.py", 700)
        report = self.run_sizes("`src/big.py`")
        self.assertAnyContains(
            self.messages(report.findings, "warning"), "src/big.py が 700 行"
        )

    def test_閾値以下のファイルは指摘しない(self) -> None:
        self.make_file("src/small.py", 10)
        self.assertEqual(self.run_sizes("`src/small.py`").findings, [])

    def test_未存在のファイルは対象にしない(self) -> None:
        self.assertEqual(self.run_sizes("`src/new.py`").findings, [])

    def test_基点が存在しなければ検査できないことを_warning_にする(self) -> None:
        self.make_file("src/big.py", 700)
        report = self.run_sizes("`src/big.py`", repo=self.tmp / "missing")
        messages = self.messages(report.findings, "warning")
        self.assertAnyContains(messages, "対象ファイルの行数を検査できない")
        self.assertNoneContains(messages, "700 行")

    def test_基点の外を指すパスを_warning_にする(self) -> None:
        report = self.run_sizes("`../outside.py`")
        self.assertAnyContains(
            self.messages(report.findings, "warning"), "の外を指すため検査しない"
        )

    def test_対象ファイルが無ければ基点を検査しない(self) -> None:
        report = check.Report()
        check.check_target_file_sizes([], self.tmp / "missing", 600, report)
        self.assertEqual(report.findings, [])

    def test_ディレクトリやバイナリで落ちない(self) -> None:
        (self.repo / "src" / "pkg.py").mkdir(parents=True)
        (self.repo / "src" / "blob.bin").write_bytes(b"\x00\xff" * 1000)
        self.assertEqual(
            self.run_sizes("`src/pkg.py`, `src/blob.bin`", max_lines=1).findings, []
        )

    def test_閾値を引数で変えられる(self) -> None:
        self.make_file("src/mid.py", 100)
        self.assertEqual(self.run_sizes("`src/mid.py`", max_lines=600).findings, [])
        self.assertEqual(len(self.run_sizes("`src/mid.py`", max_lines=50).findings), 1)


class CliTest(helpers.TempDirTestCase):
    def test_error_があれば終了コード_1(self) -> None:
        workdir = self.tmp / "wd"
        workdir.mkdir()
        (workdir / "tasks.md").write_text(
            "- [ ] 1.1 サブ\n        _Depends: 1.2_\n"
            "- [ ] 1.2 サブ\n        _Depends: 1.1_\n",
            encoding="utf-8",
        )
        proc = run_script(CHECK_PY, "--workdir", workdir)
        self.assertEqual(proc.returncode, 1)

    def test_error_が無ければ終了コード_0(self) -> None:
        workdir = self.tmp / "wd"
        workdir.mkdir()
        (workdir / "tasks.md").write_text(
            "- [ ] 1.1 サブ\n    - 対象ファイル: `src/a.py`\n    - 検証コマンド: `true`\n",
            encoding="utf-8",
        )
        proc = run_script(CHECK_PY, "--workdir", workdir)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_workdir_が無ければ停止する(self) -> None:
        proc = run_script(CHECK_PY, "--workdir", self.tmp / "missing")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("workdir が存在しません", proc.stderr)

    def test_json_出力が件数と指摘を持つ(self) -> None:
        workdir = self.tmp / "wd"
        workdir.mkdir()
        (workdir / "tasks.md").write_text("- [ ] 1.1 サブ\n", encoding="utf-8")
        result = run_json(CHECK_PY, "--workdir", workdir, "--json")
        self.assertEqual(result["errors"], 0)
        self.assertGreater(result["warnings"], 0)
        self.assertTrue(all("severity" in f for f in result["findings"]))


if __name__ == "__main__":
    unittest.main()
