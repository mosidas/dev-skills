"""draw-diagram の render.py(.mmd と SVG の対応照合)に対する単体テスト。

parse_mmd・parse_svg・compare は直接 import して呼び、exit code とエラー
メッセージが絡む検査はサブプロセスで確かめる(render.py は sys.exit を呼ぶため)。
実機の Chrome は起動せず、ダミーの実行ファイルを CHROME_BIN に指定して
screenshot を検査する。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import unittest
import unittest.mock

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
        self.assertEqual(nodes, {"A", "B", "C", "D"})
        self.assertEqual(edges, {("A", "B"), ("B", "C"), ("C", "D")})

    def test_1行に連なる辺を取りこぼさない(self) -> None:
        text = "flowchart LR\n    A[Start] --> B[Mid] --> C[End]\n"
        _diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(nodes, {"A", "B", "C"})
        self.assertEqual(edges, {("A", "B"), ("B", "C")})

    def test_単独の辺は連鎖の影響を受けない(self) -> None:
        text = "flowchart LR\n    A[Start] --> B[End]\n"
        _diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(nodes, {"A", "B"})
        self.assertEqual(edges, {("A", "B")})

    def test_並列記法_左側の_を展開する(self) -> None:
        text = "flowchart LR\n    A[A] & B[B] --> C[C]\n"
        _diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(nodes, {"A", "B", "C"})
        self.assertEqual(edges, {("A", "C"), ("B", "C")})

    def test_通常の単一ノードの辺は並列記法の影響を受けない(self) -> None:
        text = "flowchart LR\n    A[A] --> C[C]\n"
        _diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(nodes, {"A", "C"})
        self.assertEqual(edges, {("A", "C")})

    def test_ラベル内の_をノード区切りと誤読しない(self) -> None:
        text = "flowchart LR\n    A[Auth & Session] --> B[DB]\n"
        _diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(nodes, {"A", "B"})
        self.assertEqual(edges, {("A", "B")})


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
        self.assertEqual(nodes, {"A", "B"})
        self.assertEqual(edges, {("A", "B"), ("B", "A")})

    def test_メッセージ本文の角括弧をノード宣言と誤読しない(self) -> None:
        text = (
            "sequenceDiagram\n"
            "    participant A as Alice\n"
            "    participant B as Bob\n"
            "    A->>B: fetch data[1]\n"
        )
        _diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(nodes, {"A", "B"})
        self.assertNotIn("data", nodes)
        self.assertEqual(edges, {("A", "B")})

    def test_actor宣言のノードを抽出できる(self) -> None:
        text = (
            "sequenceDiagram\n"
            "    actor A as Alice\n"
            "    participant B as Bob\n"
            "    A->>B: Hello\n"
        )
        _diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(nodes, {"A", "B"})
        self.assertEqual(edges, {("A", "B")})


class ParseMmdStateTest(unittest.TestCase):
    def test_開始と終了の擬似状態を_start_と_endに変換する(self) -> None:
        text = (
            "stateDiagram-v2\n"
            "    [*] --> Idle\n"
            "    Idle --> Running: 開始\n"
            "    Running --> [*]\n"
        )
        _diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(nodes, {render.START_STATE_ID, "Idle", "Running", render.END_STATE_ID})
        self.assertEqual(
            edges,
            {
                (render.START_STATE_ID, "Idle"),
                ("Idle", "Running"),
                ("Running", render.END_STATE_ID),
            },
        )

    def test_擬似状態を含まない遷移は通常どおり抽出する(self) -> None:
        text = "stateDiagram-v2\n    Idle --> Running: 開始\n"
        _diagram_type, nodes, edges = render.parse_mmd(text)
        self.assertEqual(nodes, {"Idle", "Running"})
        self.assertEqual(edges, {("Idle", "Running")})


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

    def test_SVGファイルが存在しないときも日本語メッセージで検出する(self) -> None:
        ids, edges, violations = render.parse_svg(self.tmp / "not-exist.svg")
        self.assertEqual(ids, set())
        self.assertEqual(edges, set())
        self.assertTrue(any(v.startswith(render.MALFORMED_PREFIX) for v in violations))

    def test_プロトコル相対URLの外部参照を検出する(self) -> None:
        content = _svg_text(["A"], [], extra='<a href="//example.com/x"/>')
        path = self.write("d.svg", content)
        _ids, _edges, violations = render.parse_svg(path)
        self.assertTrue(any("外部参照" in v for v in violations))

    def test_ローカルなhref参照は検出しない(self) -> None:
        content = _svg_text(["A"], [], extra='<a href="#A"/>')
        path = self.write("d.svg", content)
        _ids, _edges, violations = render.parse_svg(path)
        self.assertFalse(any("外部参照" in v for v in violations))


class CompareTest(unittest.TestCase):
    def test_欠けたノードと辺を検出する(self) -> None:
        mmd = ("flowchart", {"A", "B"}, {("A", "B")})
        svg = ({"A"}, set(), [])
        findings = render.compare(mmd, svg)
        self.assertTrue(any("ノード" in f for f in findings))
        self.assertTrue(any("辺" in f for f in findings))

    def test_一致する対では何も検出しない(self) -> None:
        mmd = ("flowchart", {"A", "B"}, {("A", "B")})
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

    def test_連鎖する辺を正しく拾ったSVGはexit_0になる(self) -> None:
        mmd_path = self.write(
            "d.mmd", "flowchart LR\n    A[Start] --> B[Mid] --> C[End]\n"
        )
        svg_path = self.write(
            "d.svg", _svg_text(["A", "B", "C"], [("A", "B"), ("B", "C")])
        )
        proc = helpers.run_script(SCRIPT, mmd_path, svg_path)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr.strip(), "")

    def test_並列記法を正しく拾ったSVGはexit_0になる(self) -> None:
        mmd_path = self.write("d.mmd", "flowchart LR\n    A[A] & B[B] --> C[C]\n")
        svg_path = self.write(
            "d.svg", _svg_text(["A", "B", "C"], [("A", "C"), ("B", "C")])
        )
        proc = helpers.run_script(SCRIPT, mmd_path, svg_path)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr.strip(), "")

    def test_擬似状態を正しく拾ったSVGはexit_0になる(self) -> None:
        mmd_path = self.write(
            "d.mmd", "stateDiagram-v2\n    [*] --> Idle\n    Idle --> [*]\n"
        )
        svg_path = self.write(
            "d.svg",
            _svg_text(
                [render.START_STATE_ID, "Idle", render.END_STATE_ID],
                [(render.START_STATE_ID, "Idle"), ("Idle", render.END_STATE_ID)],
            ),
        )
        proc = helpers.run_script(SCRIPT, mmd_path, svg_path)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr.strip(), "")

    def test_メッセージ内角括弧を含むsequenceDiagramはexit_0になる(self) -> None:
        mmd_path = self.write(
            "d.mmd",
            "sequenceDiagram\n"
            "    participant A as Alice\n"
            "    participant B as Bob\n"
            "    A->>B: fetch data[1]\n",
        )
        svg_path = self.write("d.svg", _svg_text(["A", "B"], [("A", "B")]))
        proc = helpers.run_script(SCRIPT, mmd_path, svg_path)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr.strip(), "")


class ScreenshotTimeoutTest(helpers.TempDirTestCase):
    """Chrome が終了しなくても PNG の出現で撮影を早く終える検査。"""

    def _write_png_then_sleep(self, seconds: int) -> "Path":
        # IEND チャンクまで書き終えた完成品の PNG として扱われるよう、末尾に
        # 正しい IEND チャンクを持たせる(シグネチャ8バイト + 任意の内容 + IEND 12バイト)。
        return self.write(
            "dummy-chrome.sh",
            "#!/bin/sh\n"
            'for arg in "$@"; do\n'
            '  case "$arg" in\n'
            "    --screenshot=*) png=\"${arg#--screenshot=}\" ;;\n"
            "  esac\n"
            "done\n"
            'printf \'\\x89PNG\\x0d\\x0a\\x1a\\x0a\' > "$png"\n'
            'printf \'\\x00\\x00\\x00\\x00IEND\\xae\\x42\\x60\\x82\' >> "$png"\n'
            f"sleep {seconds}\n",
        )

    def _write_incomplete_png_then_sleep(self, seconds: int) -> "Path":
        # PNG シグネチャだけを書き、IEND を書かないまま眠る(撮影途中を模す)。
        return self.write(
            "dummy-chrome-incomplete.sh",
            "#!/bin/sh\n"
            'for arg in "$@"; do\n'
            '  case "$arg" in\n'
            "    --screenshot=*) png=\"${arg#--screenshot=}\" ;;\n"
            "  esac\n"
            "done\n"
            'printf \'\\x89PNG\\x0d\\x0a\\x1a\\x0a\' > "$png"\n'
            f"sleep {seconds}\n",
        )

    def test_PNGの出現でタイムアウトを待たずに終了する(self) -> None:
        dummy_chrome = self._write_png_then_sleep(30)
        dummy_chrome.chmod(0o755)
        svg_path = self.write("d.svg", _svg_text(["A"], []))
        png_path = self.tmp / "out.png"

        with unittest.mock.patch.dict(os.environ, {"CHROME_BIN": str(dummy_chrome)}):
            started = time.monotonic()
            errors = render.screenshot(str(svg_path), str(png_path), timeout=30)
            elapsed = time.monotonic() - started

        self.assertEqual(errors, [])
        self.assertTrue(png_path.exists())
        self.assertGreater(png_path.stat().st_size, 0)
        self.assertLess(elapsed, 15)

    def test_PNGが書けないダミーはタイムアウトで失敗になる(self) -> None:
        dummy_chrome = self.write("dummy-chrome-noop.sh", "#!/bin/sh\nsleep 5\n")
        dummy_chrome.chmod(0o755)
        svg_path = self.write("d.svg", _svg_text(["A"], []))
        png_path = self.tmp / "out.png"

        with unittest.mock.patch.dict(os.environ, {"CHROME_BIN": str(dummy_chrome)}):
            errors = render.screenshot(str(svg_path), str(png_path), timeout=2)

        self.assertTrue(any("タイムアウト" in e for e in errors))

    def test_古いPNGをPNGを書かないダミーの成果と誤認しない(self) -> None:
        dummy_chrome = self.write("dummy-chrome-noop.sh", "#!/bin/sh\nsleep 5\n")
        dummy_chrome.chmod(0o755)
        svg_path = self.write("d.svg", _svg_text(["A"], []))
        png_path = self.tmp / "out.png"
        png_path.write_text("古いPNG", encoding="utf-8")

        with unittest.mock.patch.dict(os.environ, {"CHROME_BIN": str(dummy_chrome)}):
            errors = render.screenshot(str(svg_path), str(png_path), timeout=2)

        self.assertTrue(any("タイムアウト" in e for e in errors))

    def test_IENDを持たない不完全なPNGは完成と判定されずタイムアウトになる(self) -> None:
        dummy_chrome = self._write_incomplete_png_then_sleep(30)
        dummy_chrome.chmod(0o755)
        svg_path = self.write("d.svg", _svg_text(["A"], []))
        png_path = self.tmp / "out.png"

        with unittest.mock.patch.dict(os.environ, {"CHROME_BIN": str(dummy_chrome)}):
            errors = render.screenshot(str(svg_path), str(png_path), timeout=2)

        self.assertTrue(any("タイムアウト" in e for e in errors))

    def test_stderrを大量に出しても撮影を妨げない(self) -> None:
        # PIPE のまま誰も読まないと、stderr がパイプのバッファ(64KB)を埋めた時点で
        # Chrome の書き込みがブロックし、撮影(PNG 書き出し)に到達できなくなる。
        dummy_chrome = self.write(
            "dummy-chrome-noisy.sh",
            "#!/bin/sh\n"
            'for arg in "$@"; do\n'
            '  case "$arg" in\n'
            "    --screenshot=*) png=\"${arg#--screenshot=}\" ;;\n"
            "  esac\n"
            "done\n"
            "head -c 262144 /dev/urandom 1>&2\n"
            'printf \'\\x89PNG\\x0d\\x0a\\x1a\\x0a\' > "$png"\n'
            'printf \'\\x00\\x00\\x00\\x00IEND\\xae\\x42\\x60\\x82\' >> "$png"\n'
            "exit 0\n",
        )
        dummy_chrome.chmod(0o755)
        svg_path = self.write("d.svg", _svg_text(["A"], []))
        png_path = self.tmp / "out.png"

        with unittest.mock.patch.dict(os.environ, {"CHROME_BIN": str(dummy_chrome)}):
            started = time.monotonic()
            errors = render.screenshot(str(svg_path), str(png_path), timeout=30)
            elapsed = time.monotonic() - started

        self.assertEqual(errors, [])
        self.assertTrue(png_path.exists())
        self.assertLess(elapsed, 15)

    def test_非ゼロ終了時はstderrの内容がメッセージに載る(self) -> None:
        dummy_chrome = self.write(
            "dummy-chrome-fail.sh",
            "#!/bin/sh\necho '想定外のエラーです' 1>&2\nexit 1\n",
        )
        dummy_chrome.chmod(0o755)
        svg_path = self.write("d.svg", _svg_text(["A"], []))
        png_path = self.tmp / "out.png"

        with unittest.mock.patch.dict(os.environ, {"CHROME_BIN": str(dummy_chrome)}):
            errors = render.screenshot(str(svg_path), str(png_path), timeout=5)

        self.assertTrue(any("想定外のエラーです" in e for e in errors))


class ScreenshotTimeoutEnvTest(helpers.TempDirTestCase):
    """DRAW_DIAGRAM_CHROME_TIMEOUT が不正値でも照合だけの実行は落ちない検査。"""

    def test_不正な環境変数でも_png無しの照合はexit_0になる(self) -> None:
        mmd_path = self.write("d.mmd", "flowchart TD\n    A[Start] --> B[End]\n")
        svg_path = self.write("d.svg", _svg_text(["A", "B"], [("A", "B")]))
        env = dict(os.environ, DRAW_DIAGRAM_CHROME_TIMEOUT="abc")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), str(mmd_path), str(svg_path)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
