"""Claude と Codex のマニフェスト(`plugin.json`)の version の一致の単体テスト。

README 6.1 は、プラグインを変更したら 2 つのマニフェストの version を同じ値に上げると定める。
直下の `plugin.json`(Antigravity 用)は version を持たないため対象にしない。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from helpers import REPO_ROOT

CLAUDE_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
CODEX_MANIFEST = REPO_ROOT / ".codex-plugin" / "plugin.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ManifestVersionTest(unittest.TestCase):
    def test_ClaudeとCodexのマニフェストのversionが一致する(self) -> None:
        versions = {}
        for path in (CLAUDE_MANIFEST, CODEX_MANIFEST):
            name = path.relative_to(REPO_ROOT).as_posix()
            manifest = _load(path)
            self.assertIn("version", manifest, f"{name} に version が無い")
            version = manifest["version"]
            self.assertIsInstance(version, str, f"{name} の version が文字列でない: {version!r}")
            self.assertTrue(version.strip(), f"{name} の version が空である")
            versions[name] = version

        claude_name, codex_name = versions
        self.assertEqual(
            versions[claude_name],
            versions[codex_name],
            f"{claude_name} の version {versions[claude_name]!r} と "
            f"{codex_name} の version {versions[codex_name]!r} が一致しない"
            "(README 6.1: 2 つの version を同じ値に上げる)",
        )


if __name__ == "__main__":
    unittest.main()
