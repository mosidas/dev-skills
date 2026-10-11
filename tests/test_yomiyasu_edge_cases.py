"""yomiyasu 由来の語と定型句が、日常語の境界値コーパスに発火しないことのテスト。

コーパスは nanaism/yomiyasu の tests/corpus/edge_cases(MIT、LICENSE 同梱)をそのまま取り込んだもの。
お握り・主導権を握る・卒倒など、比喩動詞の語幹を含むが正当な文を集めている。
Python 3 標準ライブラリのみを使用する(lint.py の import は sudachipy を要求しない)。
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import helpers

SCRIPTS = helpers.REPO_ROOT / "skills" / "write-doc" / "scripts"
CORPUS = helpers.REPO_ROOT / "tests" / "corpus" / "yomiyasu_edge_cases"

sys.path.insert(0, str(SCRIPTS))

import lint  # noqa: E402

# 字義どおりの「壊れる」(給紙ローラーが壊れた等)を含む境界値。上流は残す判断だが、
# 本リポジトリはシステム開発の文書で字義どおりの用法がほぼ無いとして「壊れ」を
# 禁止語(warn)にしたため、検出しないことの固定から外し、検出することを固定する。
# 取り込んだコーパスは LICENSE とともにそのまま保つため、ファイルは削除しない。
LITERAL_KOWARERU = {
    "edge_kowareru_38.md",
    "edge_kowareru_40.md",
    "edge_kowareru_41.md",
    "edge_kowareru_42.md",
    "edge_kowareru_44.md",
}


def _lex_lines(path: Path) -> list[tuple[int, str]]:
    """run_lint が語彙系の検出器へ渡す lex_lines と同じ前処理。"""
    text = path.read_text(encoding="utf-8")
    return lint.iter_lines_with_no(lint.mask_markdown_structure(text, keep_structure_text=True))


class YomiyasuEdgeCasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.files = sorted(CORPUS.glob("*.md"))

    def test_境界値コーパスが_48_本ある(self) -> None:
        self.assertEqual(len(self.files), 48)

    def test_yomiyasu_由来の語が境界値に発火しない(self) -> None:
        # 既存の語(「効く」など)は境界値に反応するため、yomiyasu 由来の語に絞る。
        yomiyasu_ngs = {
            p["ng"] for p in lint.PHRASE_CATALOG["phrases"] if "yomiyasu" in p.get("note", "")
        }
        self.assertTrue(yomiyasu_ngs)
        dict_forms = dict(lint.FORBIDDEN_PHRASE_VARIANTS)
        for path in self.files:
            with self.subTest(file=path.name):
                hits = [
                    (f.line, dict_forms[re.search(r"「(.+?)」", f.detail).group(1)])
                    for f in lint.detect_forbidden_phrases(_lex_lines(path))
                ]
                expected = [(3, "壊れ")] if path.name in LITERAL_KOWARERU else []
                self.assertEqual([h for h in hits if h[1] in yomiyasu_ngs], expected)

    def test_前置フィラーと定型クロージングが境界値に発火しない(self) -> None:
        for path in self.files:
            with self.subTest(file=path.name):
                self.assertEqual(lint.detect_filler_phrases(_lex_lines(path)), [])


if __name__ == "__main__":
    unittest.main()
