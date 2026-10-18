"""write-doc の lint.py の検出器と前処理(textcore)の単体テスト。

検出と非検出を対で確かめる。Python 3 標準ライブラリのみを使用する
(lint.py の import は sudachipy を要求しない)。
"""

from __future__ import annotations

import sys
import unittest

import helpers

SCRIPTS = helpers.REPO_ROOT / "skills" / "write-doc" / "scripts"

sys.path.insert(0, str(SCRIPTS))

import lint  # noqa: E402


class MaskTest(unittest.TestCase):
    def masked(self, text: str, keep: bool = False) -> list[str]:
        return lint.mask_markdown_structure(text, keep_structure_text=keep).split("\n")

    def test_画像は_alt_ごと空白になり地の文は残る(self) -> None:
        line = self.masked("説明の図 ![画面](a.png) を見る。")[0]
        self.assertNotIn("画面", line)
        self.assertNotIn("a.png", line)
        self.assertIn("説明の図", line)
        self.assertEqual(len(line), len("説明の図 ![画面](a.png) を見る。"))

    def test_リンクの文字は残り_URL_だけ空白になる(self) -> None:
        line = self.masked("[手順書](https://example.com/x) を読む。")[0]
        self.assertIn("手順書", line)
        self.assertNotIn("example.com", line)

    def test_地の文の_URL_は空白になる(self) -> None:
        text = "詳細は https://example.com/x にある。"
        line = self.masked(text)[0]
        self.assertNotIn("https", line)
        self.assertIn("詳細は", line)
        self.assertEqual(len(line), len(text))

    def test_HTML_タグは空白になり中の地の文は残る(self) -> None:
        line = self.masked("<details>設定の例</details>")[0]
        self.assertNotIn("details", line)
        self.assertIn("設定の例", line)

    def test_英字だけの行は両モードで空になり行数を保つ(self) -> None:
        text = "Use the API.\n日本語の行。\n![image](a.png)\n- Use the API."
        for keep in (False, True):
            with self.subTest(keep=keep):
                lines = self.masked(text, keep)
                self.assertEqual(len(lines), 4)
                self.assertEqual(lines[0], "")
                self.assertEqual(lines[1], "日本語の行。")
                self.assertEqual(lines[2].strip(), "")
                self.assertEqual(lines[3], "")

    def test_keep_structure_text_では日本語の箇条書きが残る(self) -> None:
        self.assertEqual(self.masked("- API を使う。", keep=True)[0], "- API を使う。")


class SourceFileTest(helpers.TempDirTestCase):
    def test_BOM_付きのファイルは先頭の_BOM_を除いて読む(self) -> None:
        path = self.tmp / "bom.md"
        path.write_bytes("\ufeff# 見出し\n本文。\n".encode("utf-8"))
        text, error = lint.read_source_file(path)
        self.assertIsNone(error)
        self.assertEqual(text, "# 見出し\n本文。\n")

    def test_BOM_の無いファイルはそのまま読む(self) -> None:
        path = self.write("plain.md", "# 見出し\n本文\ufeff。\n")
        text, error = lint.read_source_file(path)
        self.assertIsNone(error)
        self.assertEqual(text, "# 見出し\n本文\ufeff。\n")

    def test_不正な_UTF8_はエラーを返す(self) -> None:
        path = self.tmp / "bad.md"
        path.write_bytes(b"\xff\xfe\x80")
        text, error = lint.read_source_file(path)
        self.assertIsNone(text)
        self.assertIn("読み込めません", error)


def _lines(text: str) -> list[tuple[int, str]]:
    return list(enumerate(text.split("\n"), start=1))


class ForbiddenBoundaryTest(unittest.TestCase):
    def phrases(self, text: str) -> list[str]:
        return [f.detail for f in lint.detect_forbidden_phrases(_lines(text))]

    def test_漢字の直後の漢字始まりの語は数えない(self) -> None:
        self.assertEqual(self.phrases("発熱量を測る。"), [])

    def test_語の境目にある漢字始まりの語は検出する(self) -> None:
        self.assertEqual(len(self.phrases("熱量が高い。")), 1)

    def test_カタカナの直後のカタカナ始まりの語は数えない(self) -> None:
        self.assertEqual(self.phrases("ダブルチェックする。"), [])

    def test_漢字の直後の手で始まる語は数えない(self) -> None:
        # 「人手」は 1 語であり、「手で修正」の語の境目ではない。
        self.assertEqual(self.phrases("人手で修正する。"), [])

    def test_1行の中の出現をすべて数える(self) -> None:
        self.assertEqual(len(self.phrases("仕様に落とし込む。仕様に落とし込む。")), 2)


class TranslationeseTest(unittest.TestCase):
    def categories(self, text: str) -> list[str]:
        return [f.category for f in lint.detect_translationese(_lines(text))]

    def test_することができるは正規表現では検出しない(self) -> None:
        self.assertEqual(self.categories("変更することができる。"), [])

    def test_という点では検出する(self) -> None:
        self.assertEqual(self.categories("性能という点で優れている。"), ["translationese"])


class NegationRepetitionTest(unittest.TestCase):
    def findings(self, text: str) -> list:
        return lint.detect_negation_repetition(_lines(text))

    def test_文末の打ち消しが4文あれば全文を検出する(self) -> None:
        text = (
            "A は必須ではない。B は対象ではありません。"
            "C は不要というわけではない。D は速さの問題ではない。"
        )
        found = self.findings(text)
        self.assertEqual(len(found), 4)
        self.assertEqual({f.severity for f in found}, {"warn"})
        self.assertEqual({f.category for f in found}, {"negation_repetition"})

    def test_3文なら検出しない(self) -> None:
        text = "A は必須ではない。B は対象ではありません。C は不要というわけではない。"
        self.assertEqual(self.findings(text), [])

    def test_問いかけと推量は数えない(self) -> None:
        text = (
            "A は必須ではない。B は対象ではありません。C は不要というわけではない。"
            "D は速さの問題ではないか。E は誤りではないでしょうか。"
        )
        self.assertEqual(self.findings(text), [])

    def test_じゃないと文末ののだのですも数える(self) -> None:
        text = (
            "A は必須じゃない。B は対象ではないのだ。"
            "C は不要というわけではないのです。D は速さの問題ではない。"
        )
        self.assertEqual(len(self.findings(text)), 4)


class BoldDensityTest(unittest.TestCase):
    def bold(self, text: str) -> list:
        findings, _ = lint.detect_structural_ai_habits(text)
        return [f for f in findings if f.category == "high_bold_density"]

    def test_文中の太字が閾値以上なら1件(self) -> None:
        text = "設定は**必ず**保存する。値は**半角**で書く。期限は**月末**とする。\n"
        found = self.bold(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].severity, "info")

    def test_行頭のラベルの太字は数えない(self) -> None:
        text = "".join(f"- **項目{c}**: 説明を書く。\n" for c in "ABCDE") + "**名前**：値を書く。\n"
        self.assertEqual(self.bold(text), [])

    def test_既定で有効でありジャンルでも無効にしない(self) -> None:
        self.assertNotIn("high_bold_density", lint.EXPERIMENTAL_CATEGORIES)
        self.assertNotIn("high_bold_density", lint.GENRE_PROFILES["business"]["disabled_categories"])


class _Morpheme:
    def __init__(self, surface: str, pos: tuple[str, ...]) -> None:
        self._surface = surface
        self._pos = pos

    def surface(self) -> str:
        return self._surface

    def part_of_speech(self) -> tuple[str, ...]:
        return self._pos


class LeadRepetitionTest(unittest.TestCase):
    def leads(self, first: _Morpheme) -> list[lint.Finding]:
        tokenized = [
            lint.TokenizedSentence(
                line=no,
                text="",
                morphemes=[first, _Morpheme("、", ("補助記号", "読点")), _Morpheme(c, ("名詞", "普通名詞"))],
                raw_text=f"{first.surface()}、{c} を直した。",
            )
            for no, c in enumerate("ABCDEF", start=1)
        ]
        findings, _ = lint.detect_ngram_repetition(tokenized)
        return [f for f in findings if f.category == "repeated_sentence_lead"]

    def test_同じ書き出しの反復は1件にまとめる(self) -> None:
        findings = self.leads(_Morpheme("そして", ("接続詞", "*")))
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "info")
        self.assertEqual(findings[0].related_lines, [1, 2, 3, 4, 5, 6])

    def test_数詞で始まる文は数えない(self) -> None:
        self.assertEqual(self.leads(_Morpheme("三", ("名詞", "数詞"))), [])


class IdentifierTest(unittest.TestCase):
    def test_英字の識別子を拾う(self) -> None:
        self.assertEqual(
            lint._IDENTIFIER_RE.findall("React の useState と config.yaml を使う"),
            ["React", "useState", "config.yaml"],
        )


if __name__ == "__main__":
    unittest.main()
