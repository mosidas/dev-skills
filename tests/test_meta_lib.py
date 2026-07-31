"""meta-core/scripts/meta_lib.py の単体テスト。

frontmatter の YAML サブセット解析と、スキル群の配置の走査を対象にする。
meta_check・meta_extract・meta_loc・trigger_check が同じ解析器と同じ走査を共有するため、
ここの取りこぼしは複数のスクリプトが同じ対象について別の結論を出す状態を生む。
"""

from __future__ import annotations

import unittest

import helpers

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


class LayoutTest(helpers.TempDirTestCase):
    """配置の走査(用途グループ + `.claude`)。"""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        self.add_skill("dev", "dev-spec")
        self.add_skill(".claude", "meta-check")

    def add_skill(self, group: str, name: str) -> None:
        d = self.root / group / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: 説明\n---\n", encoding="utf-8"
        )

    def add_agent(self, group: str, name: str) -> None:
        d = self.root / group / "agents"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")

    def test_配布対象のグループにドット始まりを含めない(self) -> None:
        self.assertEqual(
            [p.name for p in meta_lib.distributed_groups(self.root)], ["dev"]
        )

    def test_走査の対象に_claude_を含める(self) -> None:
        self.assertEqual([p.name for p in meta_lib.groups(self.root)], ["dev", ".claude"])

    def test_skills_を持たないディレクトリをグループにしない(self) -> None:
        (self.root / "extensions" / "group-a").mkdir(parents=True)
        self.assertEqual(
            [p.name for p in meta_lib.distributed_groups(self.root)], ["dev"]
        )

    def test_スキルをグループ横断で名前順に返す(self) -> None:
        self.add_skill("dev", "dev-core")
        self.assertEqual(
            [p.name for p in meta_lib.skill_dirs(self.root)],
            ["dev-core", "dev-spec", "meta-check"],
        )

    def test_エージェントをグループ横断で返す(self) -> None:
        self.add_agent("dev", "dev-reviewer")
        self.assertEqual(
            [p.name for p in meta_lib.agent_files(self.root)], ["dev-reviewer.md"]
        )

    def test_分類をグループ名から決める(self) -> None:
        self.assertEqual(meta_lib.family_of(self.root / "dev"), "dev")
        self.assertEqual(meta_lib.family_of(self.root / ".claude"), "meta")

    def test_スキルからグループを引く(self) -> None:
        skill = self.root / "dev" / "skills" / "dev-spec"
        self.assertEqual(meta_lib.group_of(skill), self.root / "dev")

    def test_グループを持つディレクトリをルートとみなす(self) -> None:
        self.assertTrue(meta_lib.is_root(self.root))
        self.assertFalse(meta_lib.is_root(self.tmp))

    def test_ルートを上方向に探す(self) -> None:
        start = self.root / "dev" / "skills" / "dev-spec"
        self.assertEqual(meta_lib.find_root(start), self.root)
        self.assertIsNone(meta_lib.find_root(self.tmp))

    def test_スキル群の_Markdown_だけを集める(self) -> None:
        (self.root / "dev" / "skills" / "dev-spec" / "references").mkdir()
        (self.root / "dev" / "skills" / "dev-spec" / "references" / "x.md").write_text(
            "参照", encoding="utf-8"
        )
        (self.root / "README.md").write_text("ルート", encoding="utf-8")
        names = [p.name for p in meta_lib.group_docs(self.root)]
        self.assertEqual(names, ["SKILL.md", "SKILL.md", "x.md"])


class GroupConfigTest(helpers.TempDirTestCase):
    """グループ固有の規約(`group.json`)の読み込み(D-013)。"""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        (self.root / "dev" / "skills" / "dev-core").mkdir(parents=True)
        (self.root / "dev" / "skills" / "flow-sdd").mkdir(parents=True)
        (self.root / "writing" / "skills" / "japanese-writing").mkdir(parents=True)

    def write_config(self, group: str, text: str) -> None:
        (self.root / group / meta_lib.GROUP_CONFIG).write_text(text, encoding="utf-8")

    def test_宣言が無ければ空の規約にする(self) -> None:
        self.assertEqual(meta_lib.group_config(self.root / "writing"), {})

    def test_宣言したプレフィックスを全グループ分集める(self) -> None:
        self.write_config("dev", '{"part_prefixes": ["dev", "flow"]}')
        self.write_config("writing", '{"part_prefixes": ["japanese"]}')
        self.assertEqual(
            meta_lib.part_prefixes(self.root), ["dev", "flow", "japanese"]
        )

    def test_同じプレフィックスを重複させない(self) -> None:
        self.write_config("dev", '{"part_prefixes": ["dev"]}')
        self.write_config("writing", '{"part_prefixes": ["dev"]}')
        self.assertEqual(meta_lib.part_prefixes(self.root), ["dev"])

    def test_宣言が無いグループの語尾は空(self) -> None:
        self.assertEqual(
            meta_lib.state_suffixes(self.root / "writing" / "skills" / "japanese-writing"),
            [],
        )

    def test_レイヤーを名前の照合で割り当てる(self) -> None:
        self.write_config("dev", '{"layers": {"0": ["dev-core"], "2": ["flow-*"]}}')
        skills = self.root / "dev" / "skills"
        self.assertEqual(meta_lib.layer_of(skills / "dev-core"), 0)
        self.assertEqual(meta_lib.layer_of(skills / "flow-sdd"), 2)

    def test_割り当てが無ければ部品にする(self) -> None:
        self.write_config("dev", '{"layers": {"0": ["dev-core"]}}')
        self.assertEqual(
            meta_lib.layer_of(self.root / "dev" / "skills" / "flow-sdd"),
            meta_lib.DEFAULT_LAYER,
        )

    def test_規約を持たないグループのスキルも部品にする(self) -> None:
        self.assertEqual(
            meta_lib.layer_of(self.root / "writing" / "skills" / "japanese-writing"),
            meta_lib.DEFAULT_LAYER,
        )

    def test_壊れた_JSON_を既定に落とさず送出する(self) -> None:
        self.write_config("dev", "{壊れた")
        with self.assertRaises(meta_lib.GroupConfigError):
            meta_lib.group_config(self.root / "dev")

    def test_型が違う宣言を送出する(self) -> None:
        self.write_config("dev", '{"part_prefixes": "dev"}')
        with self.assertRaises(meta_lib.GroupConfigError):
            meta_lib.part_prefixes(self.root)

    def test_レイヤーのキーが整数でなければ送出する(self) -> None:
        self.write_config("dev", '{"layers": {"基盤": ["dev-core"]}}')
        with self.assertRaises(meta_lib.GroupConfigError):
            meta_lib.layer_of(self.root / "dev" / "skills" / "dev-core")


if __name__ == "__main__":
    unittest.main()
