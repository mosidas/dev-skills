"""ext-writing-inspection の hook の単体テスト。

検査対象の判定・重大カテゴリの絞り込み・設定の上書き・警告文の組み立てをライブラリ関数で、
発火から警告・完了ブロックまでの一連の動作をサブプロセスで確かめる。lint.py の実行は
環境変数 `WRITING_INSPECTION_LINT_CMD` でスタブに差し替える(テストは sudachipy・uv に
依存しない)。hook は入力を解釈できない場合・検査できない環境で許可側へ倒すため、その
挙動も確かめる。Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import helpers

HOOKS = (
    helpers.REPO_ROOT
    / "writing"
    / "extensions"
    / "inspection"
    / "ext-writing-inspection"
    / "hooks"
)

sys.path.insert(0, str(HOOKS))

import inspect_lib as lib  # noqa: E402

INSPECT_WRITE = HOOKS / "inspect_write.py"
INSPECT_STOP = HOOKS / "inspect_stop.py"

JAPANESE_TEXT = "この文書は検査対象の日本語で書かれている。文章の検査を確かめるための本文である。\n"

# スタブ lint: 対象ファイルの内容に含まれる目印で canned findings を返す。
STUB_LINT = '''
import json, sys
text = open(sys.argv[1], encoding="utf-8").read()
findings = []
if "NGWORD" in text:
    findings.append({"line": 1, "category": "forbidden_phrase", "severity": "warn",
                     "excerpt": "重要なのは", "detail": "禁止語"})
if "INFOONLY" in text:
    findings.append({"line": 2, "category": "translationese", "severity": "info",
                     "excerpt": "することができる", "detail": "翻訳調"})
print(json.dumps({"findings": findings}))
'''


class LibTestCase(helpers.TempDirTestCase):
    """ライブラリ関数のテストの基底(検査対象のファイルと設定を組み立てる)。"""

    def config(self, **overrides) -> dict:
        config = dict(lib.DEFAULT_CONFIG)
        config.update(overrides)
        return config


class ShouldInspectTest(LibTestCase):
    def test_日本語のMarkdownを検査対象にする(self) -> None:
        path = self.write("doc.md", JAPANESE_TEXT)
        inspect, doctype = lib.should_inspect(path, self.config(), self.tmp)
        self.assertTrue(inspect)
        self.assertEqual(doctype, lib.DEFAULT_CONFIG["default_doctype"])

    def test_Markdown以外は検査しない(self) -> None:
        path = self.write("doc.py", JAPANESE_TEXT)
        self.assertFalse(lib.should_inspect(path, self.config(), self.tmp)[0])

    def test_日本語がしきい値未満なら検査しない(self) -> None:
        path = self.write("doc.md", "# English only document\n\nhello world 日本\n")
        self.assertFalse(lib.should_inspect(path, self.config(), self.tmp)[0])

    def test_除外パターンに一致したら検査しない(self) -> None:
        path = self.write("drafts/doc.md", JAPANESE_TEXT)
        config = self.config(exclude=["drafts/*"])
        self.assertFalse(lib.should_inspect(path, config, self.tmp)[0])

    def test_文書種別の_inspect_false_で検査しない(self) -> None:
        path = self.write("novel/story.md", JAPANESE_TEXT)
        config = self.config(doctypes=[{"name": "fiction", "paths": ["novel/*"], "inspect": False}])
        self.assertFalse(lib.should_inspect(path, config, self.tmp)[0])

    def test_存在しないファイルは検査しない(self) -> None:
        self.assertFalse(lib.should_inspect(self.tmp / "none.md", self.config(), self.tmp)[0])


class ResolveDoctypeTest(LibTestCase):
    def test_最初に一致した種別を採る(self) -> None:
        config = self.config(
            doctypes=[
                {"name": "a", "paths": ["docs/*"], "genre": "tech"},
                {"name": "b", "paths": ["docs/deep/*"], "genre": "business"},
            ]
        )
        self.assertEqual(lib.resolve_doctype("docs/deep/x.md", config)["name"], "a")

    def test_一致しなければ既定を採る(self) -> None:
        config = self.config(default_doctype={"genre": "essay", "disabled_categories": []})
        self.assertEqual(lib.resolve_doctype("other.md", config)["genre"], "essay")


class FindingFilterTest(LibTestCase):
    FINDINGS = [
        {"line": 1, "category": "forbidden_phrase", "severity": "warn"},
        {"line": 2, "category": "forbidden_phrase", "severity": "info"},
        {"line": 3, "category": "antithesis_repetition", "severity": "warn"},
        {"line": 4, "category": "antithesis_repetition", "severity": "critical"},
        {"line": 5, "category": "translationese", "severity": "info"},
    ]

    def test_文書種別で無効化したカテゴリを除く(self) -> None:
        doctype = {"disabled_categories": ["translationese"]}
        remaining = lib.filter_findings(self.FINDINGS, doctype)
        self.assertNotIn("translationese", [f["category"] for f in remaining])
        self.assertEqual(len(remaining), 4)

    def test_重大カテゴリは宣言と_min_severity_で絞る(self) -> None:
        config = self.config(
            blocking=[
                {"category": "forbidden_phrase", "min_severity": "warn"},
                {"category": "antithesis_repetition", "min_severity": "critical"},
            ]
        )
        blocked = lib.blocking_findings(self.FINDINGS, config)
        self.assertEqual([f["line"] for f in blocked], [1, 4])

    def test_宣言が空ならブロックしない(self) -> None:
        self.assertEqual(lib.blocking_findings(self.FINDINGS, self.config(blocking=[])), [])


class ConfigTest(LibTestCase):
    def test_利用側の設定がバンドルの設定を浅く上書きする(self) -> None:
        hook_dir = self.tmp / "hooks"
        hook_dir.mkdir()
        (hook_dir / "inspection.config.json").write_text(
            json.dumps({"min_japanese_chars": 10, "stop_max_blocks": 5}), encoding="utf-8"
        )
        self.write(
            ".claude/ext-writing-inspection.config.json",
            json.dumps({"stop_max_blocks": 1}),
        )
        config = lib.load_config(hook_dir, self.tmp)
        self.assertEqual(config["min_japanese_chars"], 10)
        self.assertEqual(config["stop_max_blocks"], 1)

    def test_設定が壊れていても既定で動く(self) -> None:
        hook_dir = self.tmp / "hooks"
        hook_dir.mkdir()
        (hook_dir / "inspection.config.json").write_text("{broken", encoding="utf-8")
        config = lib.load_config(hook_dir, self.tmp)
        self.assertEqual(config["min_japanese_chars"], lib.DEFAULT_CONFIG["min_japanese_chars"])

    def test_同梱の設定ファイルが重大カテゴリを宣言している(self) -> None:
        config = lib.load_config(HOOKS, None)
        categories = [rule["category"] for rule in config["blocking"]]
        self.assertIn("forbidden_phrase", categories)


class FormatWarningTest(LibTestCase):
    def test_警告は書き直し指示と指針と検出を含む(self) -> None:
        findings = [
            {"line": 3, "category": "forbidden_phrase", "severity": "warn", "excerpt": "重要なのは"}
        ]
        guides = lib.load_guides(HOOKS)
        reason = lib.format_warning(Path("doc.md"), findings, self.config(), guides, findings)
        self.assertIn("丸ごと書き直す", reason)
        self.assertIn("forbidden_phrase", reason)
        self.assertIn("L3", reason)
        self.assertIn("例:", reason)  # rewrite_guides.json の言い換え例
        self.assertIn("完了がブロックされる", reason)

    def test_警告の件数は上限で打ち切る(self) -> None:
        findings = [
            {"line": i, "category": "translationese", "severity": "info", "excerpt": "x"}
            for i in range(1, 21)
        ]
        reason = lib.format_warning(
            Path("doc.md"), findings, self.config(max_findings_in_warning=5), {}, []
        )
        self.assertIn("ほか 15 件", reason)

    def test_同梱の指針が全カテゴリを持つ(self) -> None:
        """lint.py の検出カテゴリすべてに書き直しの指針が対応づく。"""
        lint_src = (
            helpers.REPO_ROOT
            / "writing"
            / "skills"
            / "japanese-writing"
            / "scripts"
            / "lint.py"
        ).read_text(encoding="utf-8")
        import re

        categories = set(re.findall(r'category="([a-z_]+)"', lint_src))
        guides = lib.load_guides(HOOKS)
        missing = sorted(c for c in categories if c not in guides)
        self.assertEqual(missing, [], f"指針が無いカテゴリ: {missing}")


class StateTest(LibTestCase):
    def test_検査したファイルを重複なく記録する(self) -> None:
        with mock.patch.object(lib.tempfile, "gettempdir", return_value=str(self.tmp)):
            path = self.write("doc.md", JAPANESE_TEXT)
            lib.record_inspected(path, self.tmp, "s1")
            lib.record_inspected(path, self.tmp, "s1")
            state = lib.load_state(lib.state_path(self.tmp, "s1"))
        self.assertEqual(state["files"], [str(path.resolve())])
        self.assertEqual(state["stop_blocks"], 0)

    def test_セッションとプロジェクトで状態を分ける(self) -> None:
        self.assertNotEqual(lib.state_path(self.tmp, "s1"), lib.state_path(self.tmp, "s2"))
        self.assertNotEqual(
            lib.state_path(self.tmp / "a", "s1"), lib.state_path(self.tmp / "b", "s1")
        )


class HookProcessTestCase(helpers.TempDirTestCase):
    """サブプロセスで hook を実行するテストの基底(スタブ lint と環境を組み立てる)。"""

    def setUp(self) -> None:
        super().setUp()
        self.project = self.tmp / "project"
        self.project.mkdir()
        self.state_dir = self.tmp / "state"
        self.state_dir.mkdir()
        stub = self.tmp / "stub_lint.py"
        stub.write_text(STUB_LINT, encoding="utf-8")
        self.env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(self.project),
            "TMPDIR": str(self.state_dir),
            lib.LINT_CMD_ENV: f'"{sys.executable}" "{stub}"',
        }

    def run_hook(self, script: Path, payload: object, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload),
            capture_output=True,
            text=True,
            env=env or self.env,
        )

    def write_payload(self, path: Path, tool: str = "Write") -> dict:
        return {
            "session_id": "sess-1",
            "cwd": str(self.project),
            "hook_event_name": "PostToolUse",
            "tool_name": tool,
            "tool_input": {"file_path": str(path)},
        }

    def stop_payload(self) -> dict:
        return {
            "session_id": "sess-1",
            "cwd": str(self.project),
            "hook_event_name": "Stop",
            "stop_hook_active": False,
        }

    def write_doc(self, rel: str, marker: str = "") -> Path:
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(JAPANESE_TEXT + marker + "\n", encoding="utf-8")
        return path

    def decision(self, proc: subprocess.CompletedProcess) -> dict:
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.strip(), "JSON 出力が無い")
        return json.loads(proc.stdout)


class InspectWriteTest(HookProcessTestCase):
    def test_検出があれば警告を返し処理は止めない(self) -> None:
        path = self.write_doc("doc.md", "NGWORD")
        proc = self.run_hook(INSPECT_WRITE, self.write_payload(path))
        decision = self.decision(proc)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("forbidden_phrase", decision["reason"])
        self.assertIn("丸ごと書き直す", decision["reason"])

    def test_検出がなければ何も出力しない(self) -> None:
        path = self.write_doc("doc.md")
        proc = self.run_hook(INSPECT_WRITE, self.write_payload(path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_検査対象外のツールでは発火しない(self) -> None:
        path = self.write_doc("doc.md", "NGWORD")
        proc = self.run_hook(INSPECT_WRITE, self.write_payload(path, tool="Bash"))
        self.assertEqual(proc.stdout, "")

    def test_lintが実行できない環境では素通しになる(self) -> None:
        path = self.write_doc("doc.md", "NGWORD")
        env = dict(self.env)
        env[lib.LINT_CMD_ENV] = f"{sys.executable} -c 'import sys; sys.exit(1)'"
        proc = self.run_hook(INSPECT_WRITE, self.write_payload(path), env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_壊れた入力では何もしない(self) -> None:
        proc = self.run_hook(INSPECT_WRITE, "not json")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")

    def test_検査したファイルを状態に記録する(self) -> None:
        path = self.write_doc("doc.md")
        self.run_hook(INSPECT_WRITE, self.write_payload(path))
        states = list(self.state_dir.rglob("*.json"))
        self.assertEqual(len(states), 1)
        state = json.loads(states[0].read_text(encoding="utf-8"))
        self.assertEqual(state["files"], [str(path.resolve())])


class InspectStopTest(HookProcessTestCase):
    def record(self, rel: str, marker: str = "") -> Path:
        """inspect_write を通してファイルを状態へ記録する。"""
        path = self.write_doc(rel, marker)
        self.run_hook(INSPECT_WRITE, self.write_payload(path))
        return path

    def test_重大カテゴリが残るあいだ完了をブロックする(self) -> None:
        self.record("doc.md", "NGWORD")
        proc = self.run_hook(INSPECT_STOP, self.stop_payload())
        decision = self.decision(proc)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("forbidden_phrase", decision["reason"])
        self.assertIn("doc.md", decision["reason"])

    def test_重大でない検出はブロックしない(self) -> None:
        self.record("doc.md", "INFOONLY")  # translationese info は blocking 宣言に無い
        proc = self.run_hook(INSPECT_STOP, self.stop_payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_解消済みなら状態を消して完了を許可する(self) -> None:
        path = self.record("doc.md", "NGWORD")
        path.write_text(JAPANESE_TEXT, encoding="utf-8")  # 書き直して解消
        proc = self.run_hook(INSPECT_STOP, self.stop_payload())
        self.assertEqual(proc.stdout, "")
        self.assertEqual(list(self.state_dir.rglob("*.json")), [])

    def test_ブロック回数の上限を超えたら完了を許可する(self) -> None:
        self.record("doc.md", "NGWORD")
        for _ in range(3):  # 既定の stop_max_blocks = 3
            decision = self.decision(self.run_hook(INSPECT_STOP, self.stop_payload()))
            self.assertEqual(decision["decision"], "block")
        proc = self.run_hook(INSPECT_STOP, self.stop_payload())
        self.assertEqual(proc.stdout, "")
        self.assertIn("上限", proc.stderr)

    def test_状態が無ければ何もしない(self) -> None:
        proc = self.run_hook(INSPECT_STOP, self.stop_payload())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
