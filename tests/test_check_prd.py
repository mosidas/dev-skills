"""specify の check_prd.py(PRD の機械検査)に対する単体テスト。

check_prd.py は sys.exit を呼ぶため、exit code と出力はサブプロセスで確かめる。
合格の PRD は雛形を埋めた最小の例で、不合格の例はそこから 1 か所だけを変えて作る。
"""

from __future__ import annotations

import unittest

import helpers

SCRIPT = helpers.REPO_ROOT / "skills" / "specify" / "scripts" / "check_prd.py"
TEMPLATE = helpers.REPO_ROOT / "skills" / "specify" / "references" / "prd.md"

VALID = """# PRD: 予約の通知

## 1. 背景と利用者

予約を受けた店舗の担当者が、予約の入った時刻に気づけずに困っている。

## 2. 対象外

- 予約の変更と取り消し

## 3. 品質

簡易(担当者 1 人が使う社内の道具であるため)

## 4. 制約と決定事項

- 通知はメールで送る(担当者が常に見ているため)

## 5. 要求一覧

### R1. 予約の受け付け

目的: 担当者が予約を一覧で確かめられるようにする
完了条件: 予約を登録すると一覧に表示される
対象外: 予約の検索
品質: 簡易

受け入れ条件:

- 予約を 1 件登録すると一覧の件数が 1 増える

### R2. 予約の通知

目的: 担当者が予約に気づけるようにする
完了条件: 予約を登録すると担当者にメールが届く
対象外: メール以外の通知
品質: 簡易

受け入れ条件:

- 失敗時: 送信に失敗したとき、一覧の予約に「未通知」を表示し、再送のボタンで送り直せる
- 予約を登録すると 1 分以内にメールが届く

## 6. 依存と順序

| 要求 | 依存先 |
| :-- | :-- |
| R1 | なし |
| R2 | R1 |

## 7. 未決事項

なし
"""


class CheckPrdTest(helpers.TempDirTestCase):
    def run_check(self, text: str):
        path = self.write("prd.md", text)
        return path, helpers.run_script(SCRIPT, path)

    def assertProblem(self, text: str, line: int, needle: str) -> None:
        path, proc = self.run_check(text)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        hits = [l for l in proc.stdout.splitlines() if l.startswith(f"{path}:{line}: ") and needle in l]
        if not hits:
            raise AssertionError(f"{line} 行目に {needle!r} の指摘がない: {proc.stdout}")
        self.assertIn(" → ", hits[0])

    def test_雛形を埋めた最小の例は何も出力せず0で終わる(self) -> None:
        _path, proc = self.run_check(VALID)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(proc.stdout, "")

    def test_節が欠けると節の名前を指摘する(self) -> None:
        text = VALID.replace("## 3. 品質\n\n簡易(担当者 1 人が使う社内の道具であるため)\n\n", "")
        self.assertProblem(text, 1, "「## 3. 品質」")

    def test_要求の4行が欠けると要求の見出しの行で指摘する(self) -> None:
        text = VALID.replace("対象外: メール以外の通知\n", "")
        self.assertProblem(text, 32, "R2 に「対象外:」の行が無い")

    def test_受け入れ条件の箇条が無いと指摘する(self) -> None:
        text = VALID.replace("- 予約を 1 件登録すると一覧の件数が 1 増える\n", "")
        self.assertProblem(text, 21, "R1 の受け入れ条件に箇条が無い")

    def test_依存先が要求一覧に無いIDだと指摘する(self) -> None:
        text = VALID.replace("| R2 | R1 |", "| R2 | R3 |")
        self.assertProblem(text, 49, "R2 の依存先 R3 が要求一覧に無い")

    def test_依存先が依存する行より下にあると指摘する(self) -> None:
        text = VALID.replace("| R1 | なし |\n| R2 | R1 |", "| R2 | R1 |\n| R1 | なし |")
        self.assertProblem(text, 48, "R2 の依存先 R1 が R2 より下の行にある")

    def test_表に無い要求を指摘する(self) -> None:
        text = VALID.replace("| R2 | R1 |\n", "")
        self.assertProblem(text, 44, "R2 が依存と順序の表に無い")

    def test_雛形のコメントが残っていると指摘する(self) -> None:
        text = VALID.replace("## 2. 対象外\n", "## 2. 対象外\n\n<!-- 製品全体で\n作らないもの。 -->\n")
        self.assertProblem(text, 9, "雛形のコメントが残っている")

    def test_未記入が残っていると指摘する(self) -> None:
        text = VALID.replace("予約の検索", "<この要求でやらないこと>")
        self.assertProblem(text, 25, "未記入の <この要求でやらないこと>")

    def test_コードとリンクとタグの山括弧は未記入として扱わない(self) -> None:
        text = VALID.replace(
            "- 通知はメールで送る(担当者が常に見ているため)\n",
            "- 通知はメールで送る(担当者が常に見ているため)<br>\n"
            "- 型は `Array<Reservation>` とする(<https://example.com/spec>)\n"
            "\n```ts\ntype Reservations = Array<Reservation>\n```\n",
        )
        _path, proc = self.run_check(text)
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_雛形そのものはコメントと未記入で不合格になる(self) -> None:
        proc = helpers.run_script(SCRIPT, TEMPLATE)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("雛形のコメントが残っている", proc.stdout)
        self.assertIn("未記入の <タイトル>", proc.stdout)
        self.assertNotIn("の行が無い", proc.stdout)

    def test_ファイルが無いと2で終わる(self) -> None:
        proc = helpers.run_script(SCRIPT, self.tmp / "missing.md")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("PRD を読み込めない", proc.stderr)


if __name__ == "__main__":
    unittest.main()
