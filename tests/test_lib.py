"""dev-core/scripts/lib.py の単体テスト。

定義データの検証・中間生成物のパース・依存循環の検出・凍結を対象にする。
これらは誤動作が全利用側プロジェクトへ波及し、退行に気づきにくい箇所である。
"""

from __future__ import annotations

import copy
import unittest

import helpers  # noqa: F401  (sys.path の設定のため)

import lib


class ValidateDefTest(unittest.TestCase):
    def test_妥当な定義は問題を返さない(self) -> None:
        self.assertEqual(lib.validate_def(copy.deepcopy(helpers.WORKFLOW_DEF)), [])

    def test_name_が無い定義を検出する(self) -> None:
        defn = copy.deepcopy(helpers.WORKFLOW_DEF)
        del defn["name"]
        self.assertIn("name が未定義または文字列でない", lib.validate_def(defn))

    def test_states_が配列でない定義を検出し以降の検査を打ち切る(self) -> None:
        problems = lib.validate_def({"name": "x", "states": "abc"})
        self.assertEqual(problems, ["states が未定義または文字列配列でない"])

    def test_states_の重複を検出する(self) -> None:
        defn = copy.deepcopy(helpers.WORKFLOW_DEF)
        defn["states"].append("drafted")
        self.assertIn("states に重複がある", lib.validate_def(defn))

    def test_initial_が_states_に無い定義を検出する(self) -> None:
        defn = copy.deepcopy(helpers.WORKFLOW_DEF)
        defn["initial"] = "unknown"
        self.assertIn("initial ('unknown') が states に含まれない", lib.validate_def(defn))

    def test_final_が_states_に無い定義を検出する(self) -> None:
        defn = copy.deepcopy(helpers.WORKFLOW_DEF)
        defn["final"] = ["done"]
        self.assertIn("final の 'done' が states に含まれない", lib.validate_def(defn))

    def test_遷移の重複を検出する(self) -> None:
        defn = copy.deepcopy(helpers.WORKFLOW_DEF)
        defn["transitions"].append({"from": "initialized", "to": "drafted"})
        self.assertIn(
            "transitions に重複がある: initialized -> drafted", lib.validate_def(defn)
        )

    def test_同一の_from_と_gate_を持つ遷移が複数あると検出する(self) -> None:
        defn = copy.deepcopy(helpers.WORKFLOW_DEF)
        defn["states"].append("other")
        defn["transitions"].append({"from": "drafted", "to": "other", "gate": "draft"})
        problems = lib.validate_def(defn)
        self.assertTrue(
            any("approve の行き先が一意に決まらない" in p for p in problems), problems
        )

    def test_artifacts_のキーが_states_に無いと検出する(self) -> None:
        defn = copy.deepcopy(helpers.WORKFLOW_DEF)
        defn["artifacts"]["unknown"] = ["a.md"]
        self.assertIn(
            "artifacts のキー 'unknown' が states に含まれない", lib.validate_def(defn)
        )


class DefAccessorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.defn = copy.deepcopy(helpers.WORKFLOW_DEF)

    def test_ゲート名を出現順に重複なく返す(self) -> None:
        self.assertEqual(lib.gates_of(self.defn), ["draft"])

    def test_指定状態からの遷移だけを返す(self) -> None:
        tos = [t["to"] for t in lib.transitions_from(self.defn, "drafted")]
        self.assertEqual(sorted(tos), ["approved", "initialized"])

    def test_完了状態を判定する(self) -> None:
        self.assertTrue(lib.is_final(self.defn, "completed"))
        self.assertFalse(lib.is_final(self.defn, "drafted"))

    def test_全成果物を宣言順に重複なく返す(self) -> None:
        self.assertEqual(lib.all_artifacts(self.defn), ["spec.md"])


class ParseRequirementsTest(helpers.TempDirTestCase):
    def test_要件番号と受け入れ基準_ID_を抽出する(self) -> None:
        path = self.write(
            "spec.md",
            "### Requirement 1: A\n\n1.1. 基準\n1.2. 基準\n\n### Requirement 2: B\n\n2.1. 基準\n",
        )
        parsed = lib.parse_requirements(path)
        self.assertEqual(parsed["requirements"], [1, 2])
        self.assertEqual(parsed["criteria"], {"1.1", "1.2", "2.1"})
        self.assertEqual(parsed["duplicates"], [])

    def test_受け入れ基準_ID_の重複を返す(self) -> None:
        path = self.write("spec.md", "### Requirement 1: A\n\n1.1. 基準\n1.1. 重複\n")
        self.assertEqual(lib.parse_requirements(path)["duplicates"], ["1.1"])


class ParseTasksTest(helpers.TempDirTestCase):
    def test_タスク番号と注記と本文を抽出する(self) -> None:
        path = self.write(
            "tasks.md",
            "\n".join(
                [
                    "- [ ] 1. メイン",
                    "  - [ ] 1.1 サブ",
                    "        _Requirements: 1.1, 1.2_",
                    "        _Boundary: X_",
                    "        _Depends: 1.2_",
                    "    - 検証コマンド: `true`",
                    "  - [ ]* 1.2 テスト後回し",
                    "        _Requirements: 2.1_",
                ]
            ),
        )
        tasks = lib.parse_tasks(path)
        self.assertEqual([t["number"] for t in tasks], ["1", "1.1", "1.2"])
        self.assertEqual(tasks[1]["annotations"]["Requirements"], ["1.1", "1.2"])
        self.assertEqual(tasks[1]["annotations"]["Depends"], ["1.2"])
        self.assertIn("検証コマンド", "\n".join(tasks[1]["body"]))

    def test_コードブロックの内側をタスク定義として扱わない(self) -> None:
        path = self.write(
            "tasks.md",
            "\n".join(
                [
                    "- [ ] 1. メイン",
                    "  - [ ] 1.1 サブ",
                    "    - 検証コマンド: `true`",
                    "",
                    "```markdown",
                    "- [ ] 9. 記述例のタスク",
                    "    - 対象ファイル: `src/example.py`",
                    "```",
                ]
            ),
        )
        tasks = lib.parse_tasks(path)
        self.assertEqual([t["number"] for t in tasks], ["1", "1.1"])
        self.assertNotIn("src/example.py", "\n".join(tasks[-1]["body"]))

    def test_見出しでタスクの本文を打ち切る(self) -> None:
        path = self.write(
            "tasks.md",
            "\n".join(
                [
                    "- [ ] 1. メイン",
                    "  - [ ] 1.1 サブ",
                    "    - 対象ファイル: `src/a.py`",
                    "",
                    "## Implementation Notes",
                    "",
                    "- 対象ファイル: `src/notes.py`",
                ]
            ),
        )
        tasks = lib.parse_tasks(path)
        body = "\n".join(tasks[-1]["body"])
        self.assertIn("src/a.py", body)
        self.assertNotIn("src/notes.py", body)


class ParseTargetFilesTest(helpers.TempDirTestCase):
    def _targets(self, tasks_body: str) -> dict:
        path = self.write("tasks.md", tasks_body)
        return lib.parse_target_files(lib.parse_tasks(path))

    def test_1_行の記述からパスを抽出する(self) -> None:
        targets = self._targets(
            "- [ ] 1.1 サブ\n    - 対象ファイル: `src/a.py`(変更), `tests/test_a.py`\n"
        )
        self.assertEqual(sorted(targets), ["src/a.py", "tests/test_a.py"])
        self.assertEqual(targets["src/a.py"], ["1.1"])

    def test_折り返した記述の_2_行目以降も抽出する(self) -> None:
        targets = self._targets(
            "- [ ] 1.1 サブ\n"
            "    - 対象ファイル: `src/a.py`,\n"
            "      `src/b.py`\n"
            "    - 検証コマンド: `true`\n"
        )
        self.assertEqual(sorted(targets), ["src/a.py", "src/b.py"])

    def test_別のラベル付き項目で打ち切る(self) -> None:
        targets = self._targets(
            "- [ ] 1.1 サブ\n"
            "    - 対象ファイル: `src/a.py`\n"
            "    - 検証コマンド: `dotnet build`, `dotnet test`\n"
        )
        self.assertEqual(sorted(targets), ["src/a.py"])

    def test_空白を含むパスを抽出する(self) -> None:
        targets = self._targets("- [ ] 1.1 サブ\n    - 対象ファイル: `src/dir name/a.py`\n")
        self.assertEqual(sorted(targets), ["src/dir name/a.py"])

    def test_全角コロンの記述からも抽出する(self) -> None:
        targets = self._targets("- [ ] 1.1 サブ\n    - 対象ファイル：`src/a.py`\n")
        self.assertEqual(sorted(targets), ["src/a.py"])

    def test_区切りも拡張子も持たない字句は拾わない(self) -> None:
        targets = self._targets("- [ ] 1.1 サブ\n    - 対象ファイル: `main`, `src/a.py`\n")
        self.assertEqual(sorted(targets), ["src/a.py"])

    def test_複数タスクが同じファイルを対象にすると両方の番号を持つ(self) -> None:
        targets = self._targets(
            "- [ ] 1.1 サブ\n    - 対象ファイル: `src/a.py`\n"
            "- [ ] 1.2 サブ\n    - 対象ファイル: `src/a.py`\n"
        )
        self.assertEqual(targets["src/a.py"], ["1.1", "1.2"])


class MarkerTest(helpers.TempDirTestCase):
    def test_残存マーカーの行番号と種別を返す(self) -> None:
        path = self.write("spec.md", "通常の行\n[要確認: 未確定]\nUNVERIFIED な事項\n")
        self.assertEqual(
            lib.find_markers(path), [(2, "[要確認:"), (3, "UNVERIFIED")]
        )

    def test_曖昧語の行番号と語を返す(self) -> None:
        path = self.write("spec.md", "適切に処理する\n通常の行\n")
        self.assertEqual(lib.find_ambiguous(path), [(1, "適切に")])

    def test_行全体が閉じタグの行をツールのマークアップ混入として返す(self) -> None:
        path = self.write(
            "tasks.md", "## Implementation Notes\n</content>\n  </invoke>\n"
        )
        self.assertEqual(
            lib.find_tool_markup(path), [(2, "</content>"), (3, "</invoke>")]
        )

    def test_インラインコードで引用した閉じタグは検出しない(self) -> None:
        path = self.write(
            "tasks.md",
            "- 末尾に混入していたマークアップ(`</content>` と `</invoke>` の 2 行)を削除した\n",
        )
        self.assertEqual(lib.find_tool_markup(path), [])

    def test_コードフェンス内の閉じタグは検出しない(self) -> None:
        path = self.write(
            "spec.md", "```xml\n</content>\n```\n</invoke>\n"
        )
        self.assertEqual(lib.find_tool_markup(path), [(4, "</invoke>")])


class DependsCycleTest(unittest.TestCase):
    def _tasks(self, graph: dict[str, list[str]]) -> list[dict]:
        return [
            {"number": n, "annotations": {"Depends": deps}} for n, deps in graph.items()
        ]

    def test_循環がなければ_None_を返す(self) -> None:
        self.assertIsNone(
            lib.detect_depends_cycle(self._tasks({"1.1": [], "1.2": ["1.1"]}))
        )

    def test_循環経路を返す(self) -> None:
        cycle = lib.detect_depends_cycle(self._tasks({"1.1": ["1.2"], "1.2": ["1.1"]}))
        self.assertIsNotNone(cycle)
        self.assertEqual(cycle[0], cycle[-1])

    def test_自己依存を循環として検出する(self) -> None:
        self.assertIsNotNone(lib.detect_depends_cycle(self._tasks({"1.1": ["1.1"]})))

    def test_実在しない依存は循環判定の対象にしない(self) -> None:
        self.assertIsNone(lib.detect_depends_cycle(self._tasks({"1.1": ["9.9"]})))


class FreezeTest(helpers.TempDirTestCase):
    def test_存在する成果物だけをハッシュで記録する(self) -> None:
        self.write("spec.md", "内容")
        defn = {"artifacts": {"completed": ["spec.md", "tasks.md"]}}
        state: dict = {}
        recorded = lib.freeze(self.tmp, defn, state)
        self.assertEqual(recorded, ["spec.md"])
        self.assertEqual(state["frozen"]["spec.md"], lib.sha256_of(self.tmp / "spec.md"))

    def test_内容が変わるとハッシュが変わる(self) -> None:
        path = self.write("spec.md", "内容")
        before = lib.sha256_of(path)
        path.write_text("別の内容", encoding="utf-8")
        self.assertNotEqual(before, lib.sha256_of(path))


class SequenceTest(helpers.TempDirTestCase):
    """workdir の連番。採番が狂うと同じ番号の workdir が並び、参照が一意でなくなる。"""

    def mkdirs(self, *names: str) -> None:
        for name in names:
            (self.tmp / name).mkdir(parents=True)

    def test_連番付きの名前から番号を取り出す(self) -> None:
        self.assertEqual(lib.sequence_of("001-user-auth"), 1)
        self.assertEqual(lib.sequence_of("1000-next"), 1000)

    def test_連番でない名前は番号を持たない(self) -> None:
        for name in ("user-auth", "01-short", "-leading", "001user-auth"):
            with self.subTest(name=name):
                self.assertIsNone(lib.sequence_of(name))

    def test_先頭の連番だけを取り除く(self) -> None:
        self.assertEqual(lib.strip_sequence("001-user-auth"), "user-auth")
        self.assertEqual(lib.strip_sequence("user-auth"), "user-auth")

    def test_空のルートでは最初の番号を返す(self) -> None:
        self.assertEqual(lib.next_sequence(self.tmp), 1)
        self.assertEqual(lib.next_sequence(self.tmp / "存在しない"), 1)

    def test_最大番号の次を返し欠番を埋めない(self) -> None:
        self.mkdirs("001-a", "005-b")
        self.assertEqual(lib.next_sequence(self.tmp), 6)

    def test_連番を持たないディレクトリとファイルを数えない(self) -> None:
        self.mkdirs("legacy-unit")
        self.write("003-notadir.md", "ファイルは対象外")
        self.assertEqual(lib.next_sequence(self.tmp), 1)

    def test_同じ_unit_の_workdir_を連番の有無を問わず見つける(self) -> None:
        self.mkdirs("002-user-auth")
        self.assertEqual(
            lib.find_unit_dir(self.tmp, "user-auth"), self.tmp / "002-user-auth"
        )

    def test_連番なしの同名ディレクトリも同じ_unit_と見なす(self) -> None:
        self.mkdirs("user-auth")
        self.assertEqual(lib.find_unit_dir(self.tmp, "user-auth"), self.tmp / "user-auth")

    def test_別の_unit_は見つけない(self) -> None:
        self.mkdirs("002-user-auth")
        self.assertIsNone(lib.find_unit_dir(self.tmp, "user-auth-2"))

    def test_既定では下位の階層を見ない(self) -> None:
        self.mkdirs("001-mvp/002-user-auth")
        self.assertIsNone(lib.find_unit_dir(self.tmp, "user-auth"))

    def test_recursive_で下位の階層の同名_unit_を見つける(self) -> None:
        self.mkdirs("001-mvp/002-user-auth")
        self.assertEqual(
            lib.find_unit_dir(self.tmp, "user-auth", recursive=True),
            self.tmp / "001-mvp" / "002-user-auth",
        )

    def test_recursive_でも別の_unit_は見つけない(self) -> None:
        self.mkdirs("001-mvp/002-user-auth")
        self.assertIsNone(
            lib.find_unit_dir(self.tmp, "user-auth-2", recursive=True)
        )

    def test_workdir_名に使える_unit_名を通す(self) -> None:
        self.assertIsNone(lib.unit_name_problem("user-auth"))

    def test_workdir_名に使えない_unit_名を検出する(self) -> None:
        for unit, needle in (
            ("", "空"),
            ("a/b", "パス区切り"),
            ("007-bond", "連番で始まっています"),
        ):
            with self.subTest(unit=unit):
                problem = lib.unit_name_problem(unit)
                self.assertIsNotNone(problem)
                self.assertIn(needle, problem)


if __name__ == "__main__":
    unittest.main()
