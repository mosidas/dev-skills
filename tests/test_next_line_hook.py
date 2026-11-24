"""Stop hook(`guard_next_line.py`)の単体テスト。

hook は `sys.exit` を呼ぶため、すべてサブプロセスで起動し、標準入力に UTF-8 のバイト列を渡す。
止める応答と通す応答を対で書く。
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

GUARD = helpers.REPO_ROOT / "hooks" / "guard_next_line.py"
RESPOND = helpers.REPO_ROOT / "skills" / "respond" / "SKILL.md"
REASON_HEAD = "respond 3.2 の検査:"
# 出力の書き出しを失敗させ、hook の想定外の例外を起こす
BROKEN_DUMP = (
    "import json, runpy, sys\n"
    "def broken(*args, **kwargs):\n"
    "    raise RuntimeError('dump failed')\n"
    "json.dump = broken\n"
    "runpy.run_path(sys.argv[1], run_name='__main__')\n"
)
BLOCKED = "本文。\n次: 案 A と案 B のどちらにするか返す。"


def stop_payload(message: object, active: bool = False) -> bytes:
    payload = {
        "session_id": "s1",
        "hook_event_name": "Stop",
        "stop_hook_active": active,
        "last_assistant_message": message,
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class GuardNextLineTest(unittest.TestCase):
    def run_raw(
        self, stdin: bytes, env: dict[str, str] | None = None, launcher: tuple[str, ...] = ()
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, *launcher, str(GUARD)],
            input=stdin,
            capture_output=True,
            env={**os.environ, **(env or {})},
            timeout=30,
        )

    def run_message(self, message: object, active: bool = False) -> subprocess.CompletedProcess:
        return self.run_raw(stop_payload(message, active))

    def assertBlocked(self, message: str) -> dict:
        proc = self.run_message(message)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        self.assertTrue(proc.stdout.strip(), f"止めるべき応答を通した: {message!r}")
        out = json.loads(proc.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertTrue(out["reason"].startswith(REASON_HEAD), out["reason"])
        self.assertNotIn("\n", out["reason"])
        return out

    def assertPassed(self, message: object, active: bool = False) -> None:
        proc = self.run_message(message, active)
        self.assertPassedProc(proc, message)

    def assertPassedProc(self, proc: subprocess.CompletedProcess, message: object = None) -> None:
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, b"", f"通すべき応答を止めた: {message!r}")
        self.assertEqual(proc.stderr, b"")

    # 止める

    def test_handoffの実例の案Bと案Aの選択を止める(self) -> None:
        self.assertBlocked(
            "API の ID の扱いを調べた。\n"
            "次: API ID の一意の範囲を、案 B(バージョンの中で一意・複製で ID を保つ)と案 A(…)のどちらにするか返す。"
        )

    def test_記号で名付けた案の選択を止める(self) -> None:
        for line in (
            "次: 案 A と案 B のどちらにするかを返す。",
            "次: A 案か B 案の変形のどちらで進めるか返す。",
            "次: 案 B の変形で進めてよいか返す。",
            "次: 案 1 で進めてよいか返す。",
            "次: 第 2 案で進めてよいか返す。",
            "次: 案 4.1 で進めてよいか返す。",
            "次: 案 1〜3 のどれにするか返す。",
            "次: 案 (a) で進めてよいか返す。",
            "次: 案②で進めてよいか返す。",
            "次: (a) か (b) で返す。",
            "次: (a) or (b) で返す。",
            "次: 案 A/案 B のどちらにするか返す。",
            "次: 上の 3 案から採用する番号を返す。",
            "次: 案 A/B のどちらで進めるか返す。",
            "次: 案A/案B のどちらで進めるか返す。",
            "次: 案 1/2 のどちらで進めるか返す。",
            "次: 案 1.1/1.2 のどちらで進めるか返す。",
            "次: B 案の変形で進めるか返す。",
            "次: 案A/案Bのどちらで進めるか返す。",
            "次: 案 1/2/3 のどれで進めるか返す。",
            "次: 案 A/B/C のどれで進めるか返す。",
            "次: A/B 案のどちらで進めるか返す。",
            "次: (案 A/B)のどちらで進めるか返す。",
            "次: 「案 A/B」のどちらで進めるか返す。",
            "次: 案 A/B、どちらで進めるか返す。",
            "次: 案 A/B: どちらで進めるか返す。",
            "次: 案 A/B, どちらで進めるか返す。",
            "次: 案 A/B.で進めるか返す。",
            "次: 案 A1 と案 B1 のどちらにするか返す。",
            "次: A1 案と B1 案のどちらにするか返す。",
            "次: 案A12 で進めてよいか返す。",
            "次: 案 A1/B1 のどちらで進めるか返す。",
            "次: 案A1/案B1 のどちらで進めるか返す。",
            "次: 案 1.2 で進めてよいか返す。",
            "次: ``案 A` で進めるか返す。",
            "次: 案Aの内容をnotes.mdに書いてよいか返す。",
        ):
            with self.subTest(line=line):
                self.assertBlocked("結果を書いた。\n" + line)

    def test_括弧書きが長くても止める(self) -> None:
        self.assertBlocked("次:案A(長い括弧書き" + "あ" * 200 + ")で進めるか返す。")

    def test_全角のコロンの次の行も止める(self) -> None:
        self.assertBlocked("次： 案 A か B を返す。")

    def test_後ろにコードフェンスが続く次の行を止める(self) -> None:
        self.assertBlocked("本文\n```\nコード\n```\n次: 案 A か B を返す。\n```sh\nls\n```")

    def test_直す前の32の良い例を止める(self) -> None:
        self.assertBlocked("次: 上の 3 案を読み、採用する案の番号を返す。")

    def test_理由に当たった部分を書く(self) -> None:
        out = self.assertBlocked("次: 第 2 案で進めてよいか返す。")
        self.assertIn("「第 2 案」", out["reason"])

    def test_理由に書く当たった部分は40字で切る(self) -> None:
        out = self.assertBlocked("次: 案" + " " * 500_000 + "A を返す。")
        self.assertIn("「案" + " " * 39 + "…」", out["reason"])
        self.assertLess(len(out["reason"]), 300)

    # 通す

    def test_中身を書いた選択と識別子の次の行を通す(self) -> None:
        for message in (
            "次: キャッシュの層を追加するか、N+1 のクエリを直すかを返す。",
            "次: PR #40(design-ui の追加)をマージしてよいか返す。",
            "5 手順中 3 完了: スキーマを更新した。残り: 新しい列への値の補充。\n次: 補充のスクリプトを実行してよいか返す。",
        ):
            with self.subTest(message=message):
                self.assertPassed(message)

    def test_35の良い例を本文と次の行のどちらに置いても通す(self) -> None:
        sentence = "TTL の設定は `src/` に無かった(`grep -rni 'ttl' src/` が 0 件)。"
        self.assertPassed(sentence)
        self.assertPassed("次: " + sentence)

    def test_止めない形の次の行を通す(self) -> None:
        for line in (
            "次: (a) ログだけ消す、(b) キャッシュも含めて全部消す、(c) 何も消さない、のどれにするかを返す。",
            "次: 手順 3 を実行する。",
            "次: 手順 (1) と (2) を行う。",
            "次: 完了条件 (1)・(3) を確かめる。",
            "次: 手順 (1)〜(3) を行う。",
            "次: この案で進めてよいか返す。",
            "次: 改善案 3 件を起票してよいか返す。",
            "次: 改善案 12 件を起票してよいか返す。",
            "次: 改善案 10 件と課題 1.5 件を確かめる。",
            "次: 改善案 1.5 件分の工数を見積もる。",
            "次: 2 案を比べた表を読み、キャッシュの層を足すかを返す。",
            "次: 案内に従って設定する。",
            "次: 名前の案 `foo-app` でサービスを作る。",
            "次: 1 案を選んで返す。",
            "次: `案 A` の文字列を検索する。",
            "次: https://example.com/案A を開く。",
            "次: docs/案A.md を開く。",
            "次: docs/案A.md:12 を見る。",
            "次: docs/案A.md, docs/x.md を開く。",
            "次: docs/案A.mdを開く。",
            "次: ./案A/x を開く。",
            "次: 案A/x.md を開く。",
            "次: docs/案A を開く。",
            "次: docs/案A.md#L3 を見る。",
            "次: docs/案A/ を開く。",
            "次: TASK-250.01/案A を開く。",
            "次: artifacts/x/TASK-250_案A を開く。",
            "次: docs/案A_v1.2 を開く。",
            "次: docs/案A.md; を開く。",
            "次: docs/案A.md. を開く。",
            "次: docs/案A.md! を開く。",
            "次: docs/案A.md\" を開く。",
            "次: B 案件の PR をマージしてよいか返す。",
            "次: A 案内に従って設定する。",
            "次: この案の PR 番号を確かめる。",
            "次: 改善案のタスク番号を確かめる。",
            "次: 草案の節番号を 4.1 に直してよいか返す。",
            "次: 答案 3 号を採点する。",
            "次: 法案 3 号の条文を読む。",
            "次: 原案 1.2 版を読む。",
            "次: 案 2027 年版を読む。",
            "次: 案 PR を確かめる。",
            "次: 案 API の仕様を読む。",
            "次: ``案 A`` の文字列を検索する。",
            "次: `` 案 `A` `` の文字列を検索する。",
            "次: 案A.md を開く。",
            "次: 案A.md:12 を見る。",
            "次: 案A.mdを開く。",
            "次: (案A.md)を開く。",
        ):
            with self.subTest(line=line):
                self.assertPassed("結果を書いた。\n" + line)

    def test_次の行より前の本文にだけある案Aは止めない(self) -> None:
        self.assertPassed("案 A と案 B を比べた。\n次: キャッシュの層を追加するか返す。")

    def test_最後の行でない次の行は止めない(self) -> None:
        self.assertPassed("次: 案 A か B を返す。\n- 案 A: 層を足す")

    def test_フェンスの中だけの次の行は止めない(self) -> None:
        self.assertPassed("例を示す。\n```\n次: 案 A を返す。\n```")
        self.assertPassed("例を示す。\n~~~\n次: 案 A を返す。\n~~~")
        self.assertPassed("例を示す。\n```\n~~~\n次: 案 A を返す。\n```")
        self.assertPassed("例を示す。\n````\n```\n次: 案 A を返す。\n````")
        self.assertPassed("例を示す。\n```\n```sh\n次: 案 A を返す。\n```")

    def test_閉じないフェンスの後の次の行は止めない(self) -> None:
        self.assertPassed("例を示す。\n```text\n本文\n次: 案 A を返す。")

    # 実物の respond の良い例

    def test_respondの良い例を止めない(self) -> None:
        lines = RESPOND.read_text(encoding="utf-8").splitlines()
        examples: list[str] = []
        in_fence = good_fence = after_good = False
        for line in lines:
            if line.startswith("```"):
                in_fence = not in_fence
                good_fence = in_fence and after_good
                continue
            if in_fence:
                if good_fence and "次:" in line:
                    examples.append(line)
                continue
            after_good = line.startswith("良い例:")
            quoted = re.fullmatch(r"良い例: 「(.*)」", line)
            if quoted:
                examples.append(quoted.group(1))
        next_lines = [e for e in examples if e.startswith("次:")]
        self.assertGreaterEqual(len(next_lines), 2, examples)
        for example in examples:
            with self.subTest(example=example):
                self.assertPassed(example)

    def test_respondの36の良い例の全体を止めない(self) -> None:
        text = RESPOND.read_text(encoding="utf-8")
        section = text.split("### 3.6.", 1)[1].split("### 3.7.", 1)[0]
        block = re.search(r"良い例:\n```\n(.*?)\n```", section, re.S)
        self.assertIsNotNone(block, "3.6 の良い例のコードブロックがある")
        self.assertPassed(block.group(1))

    # 回数

    def test_stop_hook_activeなら止めない(self) -> None:
        self.assertBlocked(BLOCKED)
        self.assertPassed(BLOCKED, active=True)

    # 境界

    def test_読めない入力は通す(self) -> None:
        for stdin in (b"{not json", b"\xff\xfe{}", b"[]", b'"text"'):
            with self.subTest(stdin=stdin):
                self.assertPassedProc(self.run_raw(stdin))

    def test_応答が文字列でなければ通す(self) -> None:
        for message in (None, 3, ""):
            with self.subTest(message=message):
                self.assertPassed(message)
        payload = json.dumps({"hook_event_name": "Stop", "stop_hook_active": False}).encode("utf-8")
        self.assertPassedProc(self.run_raw(payload))

    def test_1MBの応答を5秒以内に通す(self) -> None:
        paragraph = ("本文の行に案 A と `code` と docs/a/b を書く。" * 4 + "\n") * 10
        fenced = paragraph + "```sh\n次: 案 A を返す。\n```\n"
        long_line = "次: " + "キャッシュの層を追加し `code` と docs/a/b と (1) を直す。" * 20000 + "を返す。"
        unbroken = (
            "次: " + "a" * 1_000_000 + " を返す。",
            "次: " + "【" * 400_000,
            "次: " + "『x" * 300_000,
            "次: " + "".join("`" * n + "a" for n in range(1, 1500)),
            "次: " + "a." * 500_000,
            "次: " + "a.1" * 340_000,
        )
        for message in (fenced * 450 + "次: キャッシュの層を追加するかを返す。", paragraph + long_line, *unbroken):
            with self.subTest(last=message[-20:]):
                self.assertGreater(len(message.encode("utf-8")), 1_000_000)
                start = time.monotonic()
                proc = self.run_message(message)
                self.assertLess(time.monotonic() - start, 5.0)
                self.assertPassedProc(proc)

    def test_符号化が日本語を表せなくても止めASCIIのJSONを書く(self) -> None:
        proc = self.run_raw(stop_payload(BLOCKED), env={"PYTHONIOENCODING": "ascii"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")
        proc.stdout.decode("ascii")
        out = json.loads(proc.stdout)
        self.assertEqual(out["decision"], "block")
        self.assertTrue(out["reason"].startswith(REASON_HEAD))

    # 内部エラー

    def test_内部エラーは型名だけを1行書いてexit1(self) -> None:
        proc = self.run_raw(stop_payload(BLOCKED), launcher=("-c", BROKEN_DUMP))
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, b"")
        err = proc.stderr.decode("utf-8")
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertIn("RuntimeError", err)
        self.assertNotIn("案 A", err)
        self.assertNotIn("dump failed", err)


if __name__ == "__main__":
    unittest.main()
