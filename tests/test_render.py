"""draw-diagram の render.py(.mmd と SVG の対応照合)に対する単体テスト。

parse_mmd・parse_svg・compare は直接 import して呼び、exit code とエラー
メッセージが絡む検査はサブプロセスで確かめる(render.py は sys.exit を呼ぶため)。
Chrome を起動するテスト(screenshot・--png)は書かない。
"""

from __future__ import annotations

import sys
import unittest

import helpers

SCRIPTS = helpers.REPO_ROOT / "skills" / "draw-diagram" / "scripts"
SCRIPT = SCRIPTS / "render.py"

sys.path.insert(0, str(SCRIPTS))

import render  # noqa: E402


def _svg_text(node_ids: list[str], edges: list[tuple[str, str]], extra: str = "") -> str:
    node_els = "".join(f'<rect data-id="{n}" x="0" y="0" width="1" height="1"/>' for n in node_ids)
    edge_els = "".join(f'<path data-edge="{s}->{d}"/>' for s, d in edges)
    return f'<svg xmlns="http://www.w3.org/2000/svg">{node_els}{edge_els}{extra}</svg>'


class ParseMmdFlowchartTest(unittest.TestCase):
    def test_flowchart_の辺とノードを抽出できる(self) -> None:
        text = (
            "flowchart TD\n"
            "    A[Start] --> B{Decision}\n"
            "    B -->|Yes| C[End]\n"
            "    subgraph Sub\n"
            "        D[Inner]\n"
            "    end\n"
            "    C --> D\n"
        )
        diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(diagram_type, "flowchart")
        self.assertEqual(set(nodes.keys()), {"A", "B", "C", "D"})
        self.assertEqual(nodes["A"], "Start")
        self.assertEqual(nodes["D"], "Inner")
        self.assertEqual(edges, {("A", "B"), ("B", "C"), ("C", "D")})


class ParseMmdSequenceTest(unittest.TestCase):
    def test_sequenceDiagram_の矢印と_participant_as_を抽出できる(self) -> None:
        text = (
            "sequenceDiagram\n"
            "    participant A as Alice\n"
            "    participant B as Bob\n"
            "    A->>B: Hello\n"
            "    B-->>A: Hi\n"
        )
        diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(diagram_type, "sequenceDiagram")
        self.assertEqual(nodes, {"A": "Alice", "B": "Bob"})
        self.assertEqual(edges, {("A", "B"), ("B", "A")})


class ParseSvgTest(helpers.TempDirTestCase):
    def test_data_id_と_data_edge_を抽出できる(self) -> None:
        path = self.write("d.svg", _svg_text(["A", "B"], [("A", "B")]))
        ids, edges, violations = render.parse_svg(path)
        self.assertEqual(ids, {"A", "B"})
        self.assertEqual(edges, {("A", "B")})
        self.assertEqual(violations, [])

    def test_foreignObject_を検出する(self) -> None:
        content = _svg_text(["A"], [], extra="<foreignObject><div>x</div></foreignObject>")
        path = self.write("d.svg", content)
        _ids, _edges, violations = render.parse_svg(path)
        self.assertTrue(any("foreignObject" in v for v in violations))

    def test_非整形式のSVGを検出する(self) -> None:
        path = self.write("d.svg", "<svg><rect></svg>")
        ids, edges, violations = render.parse_svg(path)
        self.assertEqual(ids, set())
        self.assertEqual(edges, set())
        self.assertTrue(any(v.startswith(render.MALFORMED_PREFIX) for v in violations))


class CompareTest(unittest.TestCase):
    def test_欠けたノードと辺を検出する(self) -> None:
        mmd = ("flowchart", {"A": "", "B": ""}, {("A", "B")})
        svg = ({"A"}, set(), [])
        findings = render.compare(mmd, svg)
        self.assertTrue(any("ノード" in f for f in findings))
        self.assertTrue(any("辺" in f for f in findings))

    def test_一致する対では何も検出しない(self) -> None:
        mmd = ("flowchart", {"A": "", "B": ""}, {("A", "B")})
        svg = ({"A", "B"}, {("A", "B")}, [])
        self.assertEqual(render.compare(mmd, svg), [])


class CliTest(helpers.TempDirTestCase):
    def test_辺が欠けたSVGで検出する(self) -> None:
        mmd_path = self.write("d.mmd", "flowchart TD\n    A[Start] --> B[End]\n")
        svg_path = self.write("d.svg", _svg_text(["A", "B"], []))
        proc = helpers.run_script(SCRIPT, mmd_path, svg_path)
        self.assertEqual(proc.returncode, 1)
        self.assertAnyContains([proc.stderr], "SVG に無い辺")

    def test_一致する対ではexit_0になる(self) -> None:
        mmd_path = self.write("d.mmd", "flowchart TD\n    A[Start] --> B[End]\n")
        svg_path = self.write("d.svg", _svg_text(["A", "B"], [("A", "B")]))
        proc = helpers.run_script(SCRIPT, mmd_path, svg_path)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr.strip(), "")

    def test_非整形式のSVGでexit_1になる(self) -> None:
        mmd_path = self.write("d.mmd", "flowchart TD\n    A[Start] --> B[End]\n")
        svg_path = self.write("d.svg", "<svg><rect></svg>")
        proc = helpers.run_script(SCRIPT, mmd_path, svg_path)
        self.assertEqual(proc.returncode, 1)
        self.assertAnyContains([proc.stderr], render.MALFORMED_PREFIX)

    def test_foreignObjectでexit_1になる(self) -> None:
        mmd_path = self.write("d.mmd", "flowchart TD\n    A[Start] --> B[End]\n")
        svg_content = _svg_text(["A", "B"], [("A", "B")], extra="<foreignObject/>")
        svg_path = self.write("d.svg", svg_content)
        proc = helpers.run_script(SCRIPT, mmd_path, svg_path)
        self.assertEqual(proc.returncode, 1)
        self.assertAnyContains([proc.stderr], "foreignObject")

    def test_classDiagramは照合を飛ばしてexit_0になる(self) -> None:
        mmd_path = self.write(
            "d.mmd",
            "classDiagram\n    class Animal\n    Animal <|-- Dog\n",
        )
        svg_path = self.write("d.svg", _svg_text([], []))
        proc = helpers.run_script(SCRIPT, mmd_path, svg_path)
        self.assertEqual(proc.returncode, 0)
        self.assertAnyContains([proc.stdout], "照合対象外")


if __name__ == "__main__":
    unittest.main()
