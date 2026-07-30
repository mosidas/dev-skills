"""meta-core/scripts/meta_lib.py の単体テスト。

frontmatter の YAML サブセット解析を対象にする。meta_check・meta_extract・
trigger_check が同じ解析器を共有するため、ここの取りこぼしは複数のスクリプトが
同じフィールドについて別の結論を出す状態を生む。
"""

from __future__ import annotations

import unittest

import helpers  # noqa: F401  (sys.path の設定のため)

import meta_lib


class ParseFrontmatterTest(unittest.TestCase):
    def parse(self, text: str):
        return meta_lib.parse_frontmatter(text)

    def test_frontmatter_が無ければ_None(self) -> None:
        self.assertIsNone(self.parse("# 見出し\n本文\n"))

    def test_閉じの区切りが無ければ_None(self) -> None:
        self.assertIsNone(self.parse("---\nname: x\n"))

    def test_スカラーを取り出す(self) -> None:
        data, unparsable = self.parse("---\nname: dev-spec\nmodel: opus\n---\n本文\n")
        self.assertEqual(data, {"name": "dev-spec", "model": "opus"})
        self.assertEqual(unparsable, [])

    def test_引用符を剥がす(self) -> None:
        data, _ = self.parse("---\nname: \"dev-spec\"\nother: 'x'\n---\n")
        self.assertEqual(data["name"], "dev-spec")
        self.assertEqual(data["other"], "x")

    def test_ブロックスカラーを連結する(self) -> None:
        data, unparsable = self.parse(
            "---\ndescription: >-\n  1 行目\n  2 行目\n---\n"
        )
        self.assertEqual(data["description"], "1 行目 2 行目")
        self.assertEqual(unparsable, [])

    def test_改行を保つブロックスカラーを解釈する(self) -> None:
        data, _ = self.parse("---\ndescription: |\n  1 行目\n  2 行目\n---\n")
        self.assertEqual(data["description"], "1 行目\n2 行目")

    def test_ブロックシーケンスを配列にする(self) -> None:
        data, _ = self.parse(
            "---\nname: x\ninject:\n  - dev-spec\n  - dev-implement\ncondition: 常時\n---\n"
        )
        self.assertEqual(data["inject"], ["dev-spec", "dev-implement"])
        self.assertEqual(data["condition"], "常時")

    def test_値の無いキーは空文字にする(self) -> None:
        data, _ = self.parse("---\nname: x\nempty:\n---\n")
        self.assertEqual(data["empty"], "")

    def test_コメント行を無視する(self) -> None:
        data, unparsable = self.parse("---\n# 説明\nname: x\n---\n")
        self.assertEqual(data, {"name": "x"})
        self.assertEqual(unparsable, [])

    def test_解釈できない行を別に返す(self) -> None:
        data, unparsable = self.parse("---\nname: x\n  だたのインデント行\n---\n")
        self.assertEqual(data["name"], "x")
        self.assertEqual(len(unparsable), 1)

    def test_ネストしたマップを解釈できない記法として返す(self) -> None:
        data, unparsable = self.parse(
            "---\nname: x\nnested:\n  key: value\n---\n"
        )
        self.assertNotIn("nested", data)
        self.assertEqual(len(unparsable), 1)

    def test_本文の区切りより後ろを読まない(self) -> None:
        data, _ = self.parse("---\nname: x\n---\n\nname: 本文の記述\n")
        self.assertEqual(data["name"], "x")


class ScalarTest(unittest.TestCase):
    def test_スカラーを返す(self) -> None:
        self.assertEqual(meta_lib.scalar({"a": "x"}, "a"), "x")

    def test_リストは_None_にする(self) -> None:
        self.assertIsNone(meta_lib.scalar({"a": ["x"]}, "a"))

    def test_未定義のキーは_None(self) -> None:
        self.assertIsNone(meta_lib.scalar({}, "a"))


if __name__ == "__main__":
    unittest.main()
