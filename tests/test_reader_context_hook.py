"""Stop hook(`guard_reader_context.py`)の単体テスト。

hook は `sys.exit` を呼ぶため、すべてサブプロセスで起動し、標準入力に UTF-8 のバイト列を渡す。
検出する応答と検出しない応答を対で書く。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import unittest

import helpers

GUARD = helpers.REPO_ROOT / "hooks" / "guard_reader_context.py"
RESPOND = helpers.REPO_ROOT / "skills" / "respond" / "SKILL.md"
HEAD = "respond 3.5・3.6 の検査:"
NUMBERS = "番号だけの並び"
IDENTIFIER = "名前の無い識別子"
NEGATION = "調べた範囲の無い否定の断定"
KINDS = (NUMBERS, IDENTIFIER, NEGATION)
BUILD_ITERATION = "DEV_SKILLS_BUILD_ITERATION"
# 出力の書き出しを失敗させ、hook の想定外の例外を起こす
BROKEN_DUMP = (
    "import json, runpy, sys\n"
    "def broken(*args, **kwargs):\n"
    "    raise RuntimeError('dump failed')\n"
    "json.dump = broken\n"
    "runpy.run_path(sys.argv[1], run_name='__main__')\n"
)
DETECTED = "TASK-250.15 を Done にした。"


def stop_payload(message: object, active: bool = False) -> bytes:
    payload = {
        "session_id": "s1",
        "hook_event_name": "Stop",
        "stop_hook_active": active,
        "last_assistant_message": message,
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class GuardReaderContextTest(unittest.TestCase):
    def run_raw(
        self, stdin: bytes, env: dict[str, str] | None = None, launcher: tuple[str, ...] = ()
    ) -> subprocess.CompletedProcess:
        base = {k: v for k, v in os.environ.items() if k != BUILD_ITERATION}
        return subprocess.run(
            [sys.executable, *launcher, str(GUARD)],
            input=stdin,
            capture_output=True,
            env={**base, **(env or {})},
            timeout=30,
        )

    def run_message(
        self, message: object, active: bool = False, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess:
        return self.run_raw(stop_payload(message, active), env)

    def context_of(self, proc: subprocess.CompletedProcess, message: object) -> str:
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        self.assertTrue(proc.stdout.strip(), f"検出すべき応答を通した: {message!r}")
        proc.stdout.decode("ascii")
        out = json.loads(proc.stdout)
        self.assertEqual(set(out), {"hookSpecificOutput"}, "decision を含めない")
        self.assertEqual(set(out["hookSpecificOutput"]), {"hookEventName", "additionalContext"})
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "Stop")
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(context.startswith(HEAD), context)
        self.assertNotIn("\n", context)
        return context

    def assertDetected(self, message: str, kind: str, *words: str, absent: tuple[str, ...] = ()) -> str:
        """型 kind だけを検出し、当たった語 words を「」で書き、absent を書かない。"""
        context = self.context_of(self.run_message(message), message)
        for k in KINDS:
            if k == kind:
                self.assertIn(k, context)
            else:
                self.assertNotIn(k, context, f"当たっていない型を書いた: {message!r}")
        for word in words:
            self.assertIn(f"「{word}」", context)
        for word in absent:
            self.assertNotIn(word, context, f"当たっていない語を書いた: {message!r}")
        return context

    def assertPassed(self, message: object, active: bool = False, env: dict[str, str] | None = None) -> None:
        self.assertPassedProc(self.run_message(message, active, env), message)

    def assertPassedProc(self, proc: subprocess.CompletedProcess, message: object = None) -> None:
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, b"", f"検出しない応答で書いた: {message!r}")
        self.assertEqual(proc.stderr, b"")

    # 検出する

    def test_名前の無い番号の並びを検出する(self) -> None:
        for message, word in (
            ("1 と 2 は直した。", "1 と 2"),
            ("05 と 19 の列幅を直した。", "05 と 19"),
            ("- 1・2・3 は本人の確認。", "1・2・3"),
            ("1と2は直した。", "1と2"),
            ("表を見た。3 か 4 を消す。", "3 か 4"),
            ("README.md 1 と 2 を比べる。", "1 と 2"),
        ):
            with self.subTest(message=message):
                self.assertDetected(message, NUMBERS, word)

    def test_名前の無い識別子を検出する(self) -> None:
        for message, word in (
            ("TASK-250.15 を Done にした。", "TASK-250.15"),
            ("PR #143 をマージした。", "#143"),
            ("色は #333 にした。", "#333"),
            ("TASK-901を直した。", "TASK-901"),
            ("TASK-901 ステップ 1/2 を実装した。", "TASK-901"),
            ("TASK-901 Done。", "TASK-901"),
            ("PR #5 マージ済み。", "#5"),
            ("PR #5 マージ・Done にした。", "#5"),
            ("TASK-901 分の変更を直した。", "TASK-901"),
            ("TASK-901・902 と同じ結論になった。", "TASK-901"),
            ("| PR #48 | |", "#48"),
        ):
            with self.subTest(message=message):
                self.assertDetected(message, IDENTIFIER, word)

    def test_名前のある識別子の後の名前の無い識別子を検出する(self) -> None:
        self.assertDetected(
            "TASK-999(名前)の後に出た TASK-998 を直した。", IDENTIFIER, "TASK-998", absent=("TASK-999",)
        )

    def test_後の出現に括弧の名前が無ければ検出する(self) -> None:
        for message in (
            "TASK-901 を直した。TASK-902(検査の試し)の PR を作る。",
            "TASK-901 を直した。TASK-901: 承認済み。",
            "TASK-901 を直した。\n- TASK-901 一覧の画面",
        ):
            with self.subTest(message=message):
                self.assertDetected(message, IDENTIFIER, "TASK-901", absent=("TASK-902",))

    def test_引用符と条件の節の外の識別子を検出する(self) -> None:
        for message in (
            "TASK-901 へ進めた。",
            "「一覧」の TASK-901 を直した。",
            "「TASK-901 を直した。",
            "「TASK-901 を先に」と書いた。TASK-901 を直した。",
            "TASK-901 ならびに表を直した。",
            "TASK-901 を直さなければならない。",
            "TASK-901 を直したら通った。",
            "TASK-901 のときは通っていた。",
            "TASK-901 を直した。問題があれば戻す。",
            "TASK-901 を直し、問題があれば戻す。",
            "保留なら TASK-901 を閉じる。",
            "「TASK-901(返信例)」と返す。TASK-901 を直した。",
            "TASK-901 を直した。「TASK-901(返信例)」と返す。",
            "TASK-901 一覧の画面なら閉じる。TASK-901 を直した。",
        ):
            with self.subTest(message=message):
                self.assertDetected(message, IDENTIFIER, "TASK-901")

    def test_調べた範囲の無い否定の断定を検出する(self) -> None:
        for message, word in (
            ("並行の走査は結果には影響しなかった。", "並行の走査は結果には影響しなかった"),
            ("並行の走査は結果に影響しなかった。次は表を直す。", "並行の走査は結果に影響しなかった"),
            ("並行の走査は結果に影響しなかった。\n次は表を直す。\n`diff` を見た。", "並行の走査は結果に影響しなかった"),
        ):
            with self.subTest(message=message):
                self.assertDetected(message, NEGATION, word)

    def test_型ごとに当たった語を書く(self) -> None:
        context = self.context_of(
            self.run_message("1 と 2 は直した。\nPR #143 をマージした。\n並行の走査は結果に影響しなかった。"), "3 型"
        )
        for kind, word in ((NUMBERS, "1 と 2"), (IDENTIFIER, "#143"), (NEGATION, "並行の走査は結果に影響しなかった")):
            self.assertIn(kind, context)
            self.assertIn(f"「{word}」", context)

    # 検出しない

    def test_値と名前のある番号と識別子を検出しない(self) -> None:
        for message in (
            "ステップ 1・2 は承認された。",
            "幅 375・768・1440 で撮った。",
            "Node 18 と 20 で通った。",
            "9・15・24 枚目を開く。",
            "9・15枚目を開く。",
            "3.1 と 3.2 は守る。",
            "11,252 個の頂点",
            "429・5xx の応答",
            "ブランチ feat/TASK-250.15-response-checks に push した。",
            "artifacts/dev-skills/TASK-250_orchestrator-checks/ を読んだ。",
            "https://github.com/mosidas/dev-skills/pull/40 を開く。",
            "PR #40(design-ui の追加)をマージした。",
            "**TASK-252.02**(design-ui の点検)を直した。",
            "verify の初回の運用(TASK-246)で見つかった欠陥を直した。",
            "名前の例(#40・#41)を足した。",
            "TASK-900(一覧の画面)の PR #4 を作った。",
            "PR #7〜#18 はマージ済み。",
            "| 一覧の画面 | #48 |",
            "[マージ済み #24] TASK-024(design-ui スキルの追加)",
            "`TASK-250.15` を検索する。",
            "TASK-250.15.md を読んだ。",
            "TASK-901(検査の試し)を直した。",
            "TASK-901(検査の試し)を直した。TASK-901 の PR を作る。",
            "TASK-901 を直した。TASK-901(検査の試し)の PR を作る。",
            "PR #9 を作った。\n\n- PR #9(一覧の画面)",
            "- TASK-901 検査の試し",
            "TASK-901 検査の試し、TASK-902 一覧の画面を起票した。",
            "**TASK-901 検査の試し**(計画中)",
            "TASK-903 lint-rules の追加。",
            "TASK-904 マージソートの例を直した。",
            "TASK-901〜905 を起票した。",
            "子タスク TASK-901.01〜.03 を起票した。",
            "TASK-901.01・.02(検査の試し)を直した。",
            "PR #7・#8(一覧の画面)をマージした。",
            "例を示す。\n```\n1 と 2 は直した。\n```",
        ):
            with self.subTest(message=message):
                self.assertPassed(message)

    def test_引用符と条件の節の中の識別子を検出しない(self) -> None:
        for message in (
            "返事は「TASK-901 を先に」でよい。",
            "『TASK-901 へ』と書いた。",
            "同意するときは「PR #77 を閉じて」と書く。",
            "TASK-901 なら表を直す。",
            "TASK-901 ならば、表を直す。",
            "TASK-901 であれば、表を直す。",
            "PR #77 を閉じてもよければ、そう伝える。",
        ):
            with self.subTest(message=message):
                self.assertPassed(message)

    def test_条件と範囲のある否定を検出しない(self) -> None:
        for message in (
            "問題なければ「OK」と返す。",
            "問題ないかを確かめる。",
            "並行の走査は結果に影響しなかった(`diff -r a b` が 0 件)。",
            "`diff -r a b` が 0 件で、並行の走査は結果に影響しなかった。",
            "並行の走査は結果に影響しなかった。`diff -r out1 out2` の出力は空だった。",
            "並行の走査は結果に影響しなかった。\n`diff -r out1 out2` の出力は空だった。",
            "並行の走査は結果に影響しなかった。\n\n`diff -r out1 out2` の出力は空だった。",
            "並行の走査は結果に影響しなかった。\n`diff -r out1 out2`",
            "影響しなかったと推測する。",
            "「問題ない」と書いた。",
            "「影響しなかった。」と書いた。",
            "表は影響しなかった。3 件を確かめた。",
            "影響しなかった。根拠は表である。",
        ):
            with self.subTest(message=message):
                self.assertPassed(message)

    # 実物の respond の良い例

    def test_respondの良い例を検出しない(self) -> None:
        text = RESPOND.read_text(encoding="utf-8")
        examples = re.findall(r"^良い例: 「(.*)」$", text, re.M)
        section = text.split("### 3.5.", 1)[1].split("### 3.6.", 1)[0]
        self.assertTrue(any(e in section for e in examples), "3.5 の良い例を読んだ")
        for example in examples:
            with self.subTest(example=example):
                self.assertPassed(example)

    def test_respondの36の良い例の全体を検出しない(self) -> None:
        text = RESPOND.read_text(encoding="utf-8")
        section = text.split("### 3.6.", 1)[1].split("### 3.7.", 1)[0]
        block = re.search(r"良い例:\n```\n(.*?)\n```", section, re.S)
        self.assertIsNotNone(block, "3.6 の良い例のコードブロックがある")
        self.assertPassed(block.group(1))

    # 回数と環境

    def test_stop_hook_activeなら書かない(self) -> None:
        self.assertDetected(DETECTED, IDENTIFIER, "TASK-250.15")
        self.assertPassed(DETECTED, active=True)

    def test_buildの反復では書かない(self) -> None:
        self.assertPassed(DETECTED, env={BUILD_ITERATION: "1"})
        for value in ("0", "", "true"):
            with self.subTest(value=value):
                self.context_of(self.run_message(DETECTED, env={BUILD_ITERATION: value}), DETECTED)

    # 出力の契約

    def test_符号化が日本語を表せなくてもASCIIのJSONを書く(self) -> None:
        proc = self.run_raw(stop_payload(DETECTED), env={"PYTHONIOENCODING": "ascii"})
        self.assertIn("「TASK-250.15」", self.context_of(proc, DETECTED))

    def test_当たった語は型ごとに3件まで(self) -> None:
        message = " ".join(f"TASK-{n}" for n in range(1, 201)) + " を直した。"
        context = self.assertDetected(message, IDENTIFIER, "TASK-1", "TASK-2", "TASK-3", absent=("TASK-4",))
        self.assertLess(len(context), 2000)

    def test_当たった語は40字で切る(self) -> None:
        context = self.assertDetected("1・" * 5000 + "1 は直した。", NUMBERS, "1・" * 20 + "…")
        self.assertLess(len(context), 2000)
        negation = "あ" * 10000 + "影響しなかった。"
        context = self.assertDetected(negation, NEGATION, "…" + "あ" * 33 + "影響しなかった")
        self.assertLess(len(context), 2000)

    # 境界

    def test_読めない入力は書かない(self) -> None:
        for stdin in (b"{not json", b"\xff\xfe{}", b"[]", b'"text"'):
            with self.subTest(stdin=stdin):
                self.assertPassedProc(self.run_raw(stdin))

    def test_応答が文字列でなければ書かない(self) -> None:
        for message in (None, 3, ""):
            with self.subTest(message=message):
                self.assertPassed(message)
        payload = json.dumps({"hook_event_name": "Stop", "stop_hook_active": False}).encode("utf-8")
        self.assertPassedProc(self.run_raw(payload))

    def test_1MBの応答を5秒以内に通す(self) -> None:
        paragraph = ("本文の行に 1 と 2 と `code` と docs/a/b と TASK-1 を書く。影響しなかった。" * 4 + "\n") * 10
        long_line = "本文に `code` と docs/a/b と (1) と TASK-2 を書く。" * 20000
        for message in (
            paragraph * 450,
            paragraph + long_line,
            "1・" * 500_000,
            "TASK-1 " * 200_000,
            "TASK-1(名前) " * 150_000,
            "TASK-1" * 200_000,
            " ".join(f"TASK-{n}" for n in range(150_000)),
            "・".join(f"TASK-{n}" for n in range(150_000)),
            " ".join(f"TASK-{n} ア" for n in range(100_000)),
            "名前(" + " ".join(f"#{n}" for n in range(150_000)),
            "「" + " ".join(f"#{n}" for n in range(150_000)),
            "「TASK-1 " * 150_000,
            "「" + "あ" * 400_000 + "」",
            " ".join(f"TASK-{n} を直して表と図を書き換えた後に" for n in range(30_000)),
            "（" * 400_000,
            "(" * 1_100_000,
            "1" * 1_100_000,
            "影響しなかった。" + "1" * 1_100_000,
            "影響しなかった。" * 50_000,
            "「" + "影響しなかっただ" * 50_000,
            "[マージ済み " * 100_000,
            "| a " * 300_000 + "| #1 |",
            "| a " + " | ".join(f"#{n}" for n in range(150_000)) + " |",
        ):
            with self.subTest(head=message[:20]):
                self.assertGreater(len(message.encode("utf-8")), 1_000_000)
                start = time.monotonic()
                proc = self.run_message(message)
                self.assertLess(time.monotonic() - start, 5.0)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stderr, b"")

    # 内部エラー

    def test_内部エラーは型名だけを1行書いてexit1(self) -> None:
        proc = self.run_raw(stop_payload(DETECTED), launcher=("-c", BROKEN_DUMP))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, b"")
        err = proc.stderr.decode("utf-8")
        self.assertEqual(err.splitlines(), ["guard_reader_context: 内部エラー RuntimeError"])


class RegistrationTest(unittest.TestCase):
    def setUp(self) -> None:
        hooks = json.loads((helpers.REPO_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        self.commands = [hook["command"] for entry in hooks["hooks"]["Stop"] for hook in entry["hooks"]]

    def test_Stopにhookを登録し第1段とinspect_stopも残す(self) -> None:
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guard_reader_context.py"', self.commands)
        for name in ("guard_next_line.py", "inspect_stop.py"):
            with self.subTest(name=name):
                self.assertTrue(any(f"${{CLAUDE_PLUGIN_ROOT}}/hooks/{name}" in c for c in self.commands), self.commands)


if __name__ == "__main__":
    unittest.main()
