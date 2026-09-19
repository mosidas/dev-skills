"""write-doc の動詞カタログ(forbidden_phrases.json)の整合テスト。

カタログはデータであり、破損・重複・包含(同一行での二重検出の原因)を機械検査で塞ぐ。
lint.py がカタログから検出語と severity を正しく導出することも確かめる。
Python 3 標準ライブラリのみを使用する(lint.py の import は sudachipy を要求しない)。
"""

from __future__ import annotations

import json
import sys
import unittest

import helpers

SCRIPTS = helpers.REPO_ROOT / "skills" / "write-doc" / "scripts"
CATALOG_PATH = SCRIPTS / "forbidden_phrases.json"

sys.path.insert(0, str(SCRIPTS))

import lint  # noqa: E402


class PhraseCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.phrases = cls.catalog["phrases"]

    def test_全エントリが_NG_OK_対と型と_severity_を持つ(self) -> None:
        types = self.catalog["types"]
        for entry in self.phrases:
            with self.subTest(ng=entry.get("ng")):
                self.assertIsInstance(entry["ng"], str)
                self.assertTrue(entry["ng"])
                self.assertIn(entry["type"], types)
                self.assertIn(entry["severity"], ("info", "warn"))
                self.assertIsInstance(entry["ok"], list)
                self.assertTrue(entry["ok"], "OK 例が空")
                for ok in entry["ok"]:
                    self.assertIsInstance(ok, str)

    def test_語が重複しない(self) -> None:
        ngs = [p["ng"] for p in self.phrases]
        self.assertEqual(len(ngs), len(set(ngs)))

    def test_語が他の語を包含しない(self) -> None:
        """部分文字列の包含は同一行での二重検出を生むため禁止する。"""
        ngs = [p["ng"] for p in self.phrases]
        overlaps = [(a, b) for a in ngs for b in ngs if a != b and a in b]
        self.assertEqual(overlaps, [])

    def test_活用形が文字列で他の照合文字列を包含しない(self) -> None:
        """forms(活用形)も ng と同列に照合されるため、包含の禁止を全照合文字列に広げる。"""
        variants = []
        for p in self.phrases:
            forms = p.get("forms", [])
            self.assertIsInstance(forms, list, p["ng"])
            for form in forms:
                self.assertIsInstance(form, str, p["ng"])
                self.assertTrue(form, p["ng"])
            variants.extend([p["ng"], *forms])
        overlaps = [(a, b) for a in variants for b in variants if a != b and a in b]
        self.assertEqual(overlaps, [])

    def test_削除済みの語が検出語に残っていない(self) -> None:
        ngs = {p["ng"] for p in self.phrases}
        for entry in self.catalog.get("removed", []):
            self.assertNotIn(entry["ng"], ngs)

    def test_lint_がカタログから検出語を導出する(self) -> None:
        self.assertEqual(lint.FORBIDDEN_PHRASES, [p["ng"] for p in self.phrases])
        self.assertEqual(
            lint.FORBIDDEN_PHRASES_WEAK_SIGNAL,
            {p["ng"] for p in self.phrases if p["severity"] == "info"},
        )

    def test_空虚な動詞だけが_warn_を持つ(self) -> None:
        """severity の方針を固定する。正当な用法のある語は info、空虚な動詞だけ warn。"""
        empty_verbs = {"掘り下げる", "深掘りする", "言語化する", "を探求する"}
        warns = {p["ng"] for p in self.phrases if p["severity"] == "warn"}
        self.assertEqual(warns, empty_verbs)
        for ng in ("落とし込む", "を選ぶ", "チェックする"):
            self.assertIn(ng, lint.FORBIDDEN_PHRASES_WEAK_SIGNAL, ng)

    def test_型が_3_つで全エントリがその型を持つ(self) -> None:
        """カタログは動詞に絞る。型は imprecise・colloquial・loanword の 3 つだけとする。"""
        self.assertEqual(set(self.catalog["types"]), {"imprecise", "colloquial", "loanword"})
        for entry in self.phrases:
            self.assertIn(entry["type"], self.catalog["types"], entry["ng"])

    def test_検出が動く(self) -> None:
        findings = lint.detect_forbidden_phrases([(1, "仕様に落とし込む。")])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "forbidden_phrase")
        self.assertEqual(findings[0].severity, "info")
        warn_findings = lint.detect_forbidden_phrases([(1, "原因を掘り下げる。")])
        self.assertEqual(len(warn_findings), 1)
        self.assertEqual(warn_findings[0].severity, "warn")

    def test_severity_が_info_か_warn_に限られる(self) -> None:
        for entry in self.phrases:
            self.assertIn(entry["severity"], ("info", "warn"), entry["ng"])


if __name__ == "__main__":
    unittest.main()
