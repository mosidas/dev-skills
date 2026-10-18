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
        path.write_bytes("﻿# 見出し\n本文。\n".encode("utf-8"))
        text, error = lint.read_source_file(path)
        self.assertIsNone(error)
        self.assertEqual(text, "# 見出し\n本文。\n")

    def test_BOM_の無いファイルはそのまま読む(self) -> None:
        path = self.write("plain.md", "# 見出し\n本文﻿。\n")
        text, error = lint.read_source_file(path)
        self.assertIsNone(error)
        self.assertEqual(text, "# 見出し\n本文﻿。\n")

    def test_不正な_UTF8_はエラーを返す(self) -> None:
        path = self.tmp / "bad.md"
        path.write_bytes(b"\xff\xfe\x80")
        text, error = lint.read_source_file(path)
        self.assertIsNone(text)
        self.assertIn("読み込めません", error)


if __name__ == "__main__":
    unittest.main()
