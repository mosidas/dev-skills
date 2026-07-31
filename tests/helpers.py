"""テストの共通ヘルパ。

スクリプトの実体は各スキルの `scripts/` にあり、パッケージ化されていない
(利用側へハードコピーで配る単体のスクリプトのため)。テストからはそのディレクトリを
`sys.path` へ追加して読み込む。exit code と日本語のエラーメッセージを確かめる検査は、
`die()` が `sys.exit` を呼ぶためサブプロセスで実行する。

Python 3 標準ライブラリのみを使用する(追加インストール不要の担保)。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEV_SCRIPTS = REPO_ROOT / "dev" / "skills" / "dev-core" / "scripts"
META_SCRIPTS = REPO_ROOT / ".claude" / "skills" / "meta-core" / "scripts"

for _d in (DEV_SCRIPTS, META_SCRIPTS):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))


def run_script(script: Path, *args: object) -> subprocess.CompletedProcess:
    """スクリプトをサブプロセスで実行する(exit code と出力を確かめる用)。"""
    return subprocess.run(
        [sys.executable, str(script), *[str(a) for a in args]],
        capture_output=True,
        text=True,
    )


def run_json(script: Path, *args: object) -> dict:
    """`--json` 付きで実行し、標準出力を辞書で返す。"""
    proc = run_script(script, *args)
    if not proc.stdout.strip():
        raise AssertionError(f"JSON 出力が空: {proc.stderr}")
    return json.loads(proc.stdout)


class TempDirTestCase(unittest.TestCase):
    """一時ディレクトリを持つテストの基底。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def write(self, rel: str, text: str) -> Path:
        """一時ディレクトリ配下へファイルを書く(親ディレクトリも作る)。"""
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def messages(self, findings: list[dict], severity: str | None = None) -> list[str]:
        """findings からメッセージだけを取り出す(重大度で絞れる)。"""
        return [
            f["message"]
            for f in findings
            if severity is None or f["severity"] == severity
        ]

    def assertAnyContains(self, texts: list[str], needle: str) -> None:
        if not any(needle in t for t in texts):
            raise AssertionError(f"{needle!r} を含む要素がない: {texts}")

    def assertNoneContains(self, texts: list[str], needle: str) -> None:
        hit = [t for t in texts if needle in t]
        if hit:
            raise AssertionError(f"{needle!r} を含む要素があってはならない: {hit}")


WORKFLOW_DEF = {
    "name": "testflow",
    "states": ["initialized", "drafted", "approved", "completed"],
    "initial": "initialized",
    "final": ["completed"],
    "transitions": [
        {"from": "initialized", "to": "drafted"},
        {"from": "drafted", "to": "approved", "gate": "draft"},
        {"from": "approved", "to": "completed"},
        {"from": "drafted", "to": "initialized"},
    ],
    "artifacts": {
        "drafted": ["spec.md"],
        "approved": ["spec.md"],
        "completed": ["spec.md"],
    },
}
