"""meta-core/scripts/meta_loc.py の単体テスト。

領域の割り当て・行数の数え方・除外条件を対象にする。集計値はスキル群の分量を判断する
材料になるため、除外の取りこぼし(バイナリ・キャッシュ)は数値を歪める。
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import helpers

from helpers import META_SCRIPTS, run_script

import meta_loc

LOC_PY = META_SCRIPTS / "meta_loc.py"


class AreaTest(unittest.TestCase):
    def test_スキルごとの領域に割り当てる(self) -> None:
        self.assertEqual(
            meta_loc.area_of(Path(".claude/skills/dev-spec/SKILL.md")), "dev-spec"
        )

    def test_エージェントを_1_つの領域にまとめる(self) -> None:
        self.assertEqual(
            meta_loc.area_of(Path(".claude/agents/dev-reviewer.md")), ".claude/agents"
        )

    def test_meta_と_ports_と_extensions_を領域にする(self) -> None:
        self.assertEqual(meta_loc.area_of(Path(".meta/DESIGN.md")), ".meta")
        self.assertEqual(meta_loc.area_of(Path("ports/README.md")), "ports")
        self.assertEqual(meta_loc.area_of(Path("extensions/README.md")), "extensions")

    def test_それ以外をルート直下にする(self) -> None:
        self.assertEqual(meta_loc.area_of(Path("README.md")), "(ルート直下)")

    def test_拡張子が無いファイルを別扱いにする(self) -> None:
        self.assertEqual(meta_loc.ext_of(Path("Makefile")), "(拡張子なし)")
        self.assertEqual(meta_loc.ext_of(Path("a.md")), ".md")


class CountTest(helpers.TempDirTestCase):
    def test_総行数と実行数を数える(self) -> None:
        path = self.write("a.md", "1 行目\n\n3 行目\n")
        self.assertEqual(meta_loc.count_lines(path), (3, 2))

    def test_バイナリは_None_を返す(self) -> None:
        path = self.tmp / "blob.bin"
        path.write_bytes(b"\x00\xff" * 10)
        self.assertIsNone(meta_loc.count_lines(path))


class CollectTest(helpers.TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        (self.root / ".claude" / "skills" / "dev-spec").mkdir(parents=True)

    def test_領域と種別ごとに集計する(self) -> None:
        (self.root / ".claude" / "skills" / "dev-spec" / "SKILL.md").write_text(
            "a\nb\n", encoding="utf-8"
        )
        (self.root / "README.md").write_text("a\n", encoding="utf-8")
        result = meta_loc.collect(self.root)
        self.assertEqual(result["by_area"]["dev-spec"].total, 2)
        self.assertEqual(result["by_area"]["(ルート直下)"].total, 1)
        self.assertEqual(result["by_ext"][".md"].files, 2)
        self.assertEqual(result["grand"].total, 3)

    def test_キャッシュとバイトコードを除外する(self) -> None:
        cache = self.root / ".claude" / "skills" / "dev-spec" / "__pycache__"
        cache.mkdir()
        (cache / "x.pyc").write_bytes(b"\x00")
        (self.root / ".claude" / "skills" / "dev-spec" / "y.pyc").write_bytes(b"\x00")
        (self.root / ".claude" / "skills" / "dev-spec" / "SKILL.md").write_text(
            "a\n", encoding="utf-8"
        )
        result = meta_loc.collect(self.root)
        self.assertEqual(result["grand"].files, 1)

    def test_バイナリを除外して別掲する(self) -> None:
        (self.root / "blob.bin").write_bytes(b"\x00\xff" * 10)
        result = meta_loc.collect(self.root)
        self.assertEqual(result["grand"].files, 0)
        self.assertEqual(result["skipped"], ["blob.bin"])


class CliTest(helpers.TempDirTestCase):
    def test_root_に_claude_が無ければ停止する(self) -> None:
        proc = run_script(LOC_PY, "--root", self.tmp)
        self.assertEqual(proc.returncode, 1)
        self.assertIn(".claude が無い", proc.stderr)

    def test_実リポジトリで集計を返す(self) -> None:
        proc = run_script(LOC_PY, "--root", helpers.REPO_ROOT, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertGreater(data["total_files"], 0)
        self.assertGreater(data["total_lines"], data["code_lines"])
        self.assertIn("dev-core", data["by_area"])


if __name__ == "__main__":
    unittest.main()
