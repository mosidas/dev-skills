"""write-doc の lint.py の検出器と前処理(textcore)の単体テスト。

検出と非検出を対で確かめる。Python 3 標準ライブラリのみを使用する
(lint.py の import は sudachipy を要求しない)。
"""

from __future__ import annotations

import json
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

    def test_と言えるでしょうを検出する(self) -> None:
        self.assertEqual(self.categories("この方式は有効と言えるでしょう。"), ["translationese"])

    def test_と言えるだけなら検出しない(self) -> None:
        self.assertEqual(self.categories("この方式は有効と言える。"), [])


class ThinEvaluationTest(unittest.TestCase):
    def findings(self, text: str) -> list:
        lines = lint.iter_lines_with_no(lint.mask_markdown_structure(text, keep_structure_text=True))
        return lint.detect_thin_evaluation(lines)

    def test_評価を言い直すだけの文を検出する(self) -> None:
        cases = [
            ("操作性が高い。", "操作性"),
            ("この画面は操作性が非常に高いです。", "操作性"),
            ("設定画面の視認性も良い。", "視認性"),
            ("- 保守性が高い。", "保守性"),
        ]
        for text, noun in cases:
            with self.subTest(text=text):
                found = self.findings(text)
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0].category, "thin_evaluation")
                self.assertEqual(found[0].severity, "info")
                self.assertIn(noun, found[0].detail)

    def test_読点の前置き_変化の形_に_括弧の中は検出しない(self) -> None:
        for text in [
            "ログが少ないので、可読性が高い。",
            "信頼性が高まった。",
            "可読性に優れている。",
            "「操作性が高い。」と書かない。",
            "- Before: 「操作性が高い。」",
        ]:
            with self.subTest(text=text):
                self.assertEqual(self.findings(text), [])

    def test_製品レビュー向けの組は取り込まない(self) -> None:
        for text in ["座り心地が快適だ。", "携帯性が高い。", "保温性が高い。"]:
            with self.subTest(text=text):
                self.assertEqual(self.findings(text), [])
        self.assertEqual(len(lint.THIN_EVALUATION_PAIRS), 15)

    def test_重大カテゴリに入れない(self) -> None:
        config = json.loads((helpers.REPO_ROOT / "hooks" / "inspection.config.json").read_text(encoding="utf-8"))
        categories = {rule["category"] for rule in config["blocking"]}
        self.assertNotIn("thin_evaluation", categories)
        self.assertNotIn("translationese", categories)


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


class SplitUnitsTest(unittest.TestCase):
    TEXT = "\n".join(
        [
            "---",
            "title: 試験",
            "---",
            "# 見出しの行",
            "",
            "- 一つ目の項目",
            "  続きの行",
            "- 二つ目の項目",
            "",
            "| 列 | 説明 |",
            "| --- | --- |",
            "| 値 | 中身 |",
            "",
            "```python",
            "# コードの中の見出し",
            "```",
            "",
            "一つ目の段落。",
            "同じ段落の二行目。",
            "",
            "Use the API.",
            "",
            "二つ目の段落。",
        ]
    )

    def test_単位の種類と行番号を並べる(self) -> None:
        units = lint.split_units(self.TEXT)
        self.assertEqual(
            [(u["kind"], u["line"]) for u in units],
            [("見出し", 4), ("箇条書き", 6), ("箇条書き", 8), ("表", 10), ("表", 12), ("段落", 18), ("段落", 23)],
        )
        self.assertEqual([u["no"] for u in units], list(range(1, 8)))
        self.assertEqual(units[1]["text"], "- 一つ目の項目\n  続きの行")
        self.assertEqual(units[5]["text"], "一つ目の段落。\n同じ段落の二行目。")

    def test_コードとフロントマターと英字だけの段落は出さない(self) -> None:
        body = "\n".join(u["text"] for u in lint.split_units(self.TEXT))
        for absent in ["title", "コードの中", "Use the API", "---"]:
            with self.subTest(absent=absent):
                self.assertNotIn(absent, body)


if __name__ == "__main__":
    unittest.main()


class ReviewDelegationNoticeTest(unittest.TestCase):
    def test_見出しが10を超えると分担の通知を出す(self) -> None:
        text = "\n".join(f"## {i}. 節\n\n本文。\n" for i in range(1, 12))
        self.assertEqual(lint.count_headings(text), 11)
        notice = lint.review_delegation_notice(lint.count_headings(text))
        self.assertIsNotNone(notice)
        self.assertIn("別のエージェント", notice)

    def test_見出しが10以下なら通知を出さない(self) -> None:
        text = "\n".join(f"## {i}. 節\n\n本文。\n" for i in range(1, 11))
        self.assertEqual(lint.count_headings(text), 10)
        self.assertIsNone(lint.review_delegation_notice(lint.count_headings(text)))

    def test_コードブロックの中の井桁は見出しに数えない(self) -> None:
        text = "## 1. 節\n\n```sh\n# コメント\n## これも見出しではない\n```\n"
        self.assertEqual(lint.count_headings(text), 1)

    def test_インデントコードの井桁は見出しに数えない(self) -> None:
        text = "## 1. 節\n\n本文。\n\n    # コメント\n    ## これも見出しではない\n\t# タブのコード\n"
        self.assertEqual(lint.count_headings(text), 1)
