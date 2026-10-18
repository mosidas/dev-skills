"""write-doc の動詞・名詞のカタログ(forbidden_phrases.json)の整合テスト。

カタログはデータであり、破損・重複・包含(同一行での二重検出の原因)を機械検査で塞ぐ。
lint.py がカタログから検出語と severity を正しく導出することも確かめる。
Python 3 標準ライブラリのみを使用する(lint.py の import は sudachipy を要求しない)。
"""

from __future__ import annotations

import json
import sys
import unittest

import helpers

SCRIPTS = helpers.REPO_ROOT / "skills" / "write-doc" / "scripts"
CATALOG_PATH = SCRIPTS / "forbidden_phrases.json"

sys.path.insert(0, str(SCRIPTS))

import lint  # noqa: E402


class PhraseCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.phrases = cls.catalog["phrases"]

    def test_全エントリが_NG_OK_対と型と_severity_を持つ(self) -> None:
        types = self.catalog["types"]
        for entry in self.phrases:
            with self.subTest(ng=entry.get("ng")):
                self.assertIsInstance(entry["ng"], str)
                self.assertTrue(entry["ng"])
                self.assertIn(entry["type"], types)
                self.assertIn(entry["severity"], ("info", "warn"))
                self.assertIsInstance(entry["ok"], list)
                self.assertTrue(entry["ok"], "OK 例が空")
                for ok in entry["ok"]:
                    self.assertIsInstance(ok, str)

    def test_語が重複しない(self) -> None:
        ngs = [p["ng"] for p in self.phrases]
        self.assertEqual(len(ngs), len(set(ngs)))

    def test_語が他の語を包含しない(self) -> None:
        """部分文字列の包含は同一行での二重検出を生むため禁止する。"""
        ngs = [p["ng"] for p in self.phrases]
        overlaps = [(a, b) for a in ngs for b in ngs if a != b and a in b]
        self.assertEqual(overlaps, [])

    def test_活用形が文字列で他の照合文字列を包含しない(self) -> None:
        """forms(活用形)も ng と同列に照合されるため、包含の禁止を全照合文字列に広げる。"""
        variants = []
        for p in self.phrases:
            forms = p.get("forms", [])
            self.assertIsInstance(forms, list, p["ng"])
            for form in forms:
                self.assertIsInstance(form, str, p["ng"])
                self.assertTrue(form, p["ng"])
            variants.extend([p["ng"], *forms])
        overlaps = [(a, b) for a in variants for b in variants if a != b and a in b]
        self.assertEqual(overlaps, [])

    def test_削除済みの語が検出語に残っていない(self) -> None:
        ngs = {p["ng"] for p in self.phrases}
        for entry in self.catalog.get("removed", []):
            self.assertNotIn(entry["ng"], ngs)

    def test_lint_がカタログから検出語を導出する(self) -> None:
        self.assertEqual(lint.FORBIDDEN_PHRASES, [p["ng"] for p in self.phrases])
        self.assertEqual(
            lint.FORBIDDEN_PHRASES_WEAK_SIGNAL,
            {p["ng"] for p in self.phrases if p["severity"] == "info"},
        )

    def test_warn_は空虚な動詞と比喩語に限る(self) -> None:
        """severity の方針を固定する。正当な用法のある語は info、空虚な動詞と、
        システム開発の文書で字義どおりに使わない比喩語だけ warn。"""
        empty_verbs = {"掘り下げる", "深掘りする", "言語化する", "を探求する"}
        metaphors = {"壊れ", "静かに", "黙って", "沈黙", "逃が"}
        warns = {p["ng"] for p in self.phrases if p["severity"] == "warn"}
        self.assertEqual(warns, empty_verbs | metaphors)
        for ng in ("落とし込む", "を選ぶ", "チェックする"):
            self.assertIn(ng, lint.FORBIDDEN_PHRASES_WEAK_SIGNAL, ng)

    def test_型が_4_つで全エントリがその型を持つ(self) -> None:
        """型は imprecise・colloquial・loanword・pseudo_concrete の 4 つだけとする。"""
        self.assertEqual(
            set(self.catalog["types"]),
            {"imprecise", "colloquial", "loanword", "pseudo_concrete"},
        )
        for entry in self.phrases:
            self.assertIn(entry["type"], self.catalog["types"], entry["ng"])

    def test_検出が動く(self) -> None:
        findings = lint.detect_forbidden_phrases([(1, "仕様に落とし込む。")])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "forbidden_phrase")
        self.assertEqual(findings[0].severity, "info")
        warn_findings = lint.detect_forbidden_phrases([(1, "原因を掘り下げる。")])
        self.assertEqual(len(warn_findings), 1)
        self.assertEqual(warn_findings[0].severity, "warn")

    def test_yomiyasu_由来の語を検出する(self) -> None:
        """yomiyasu 由来の 41 語は、ng か forms を含む例文でカタログの severity として 1 件だけ検出される。

        36 語は info、システム開発の文書で字義どおりに使わない 5 語は warn とする。
        """
        info_sentences = [
            "画面の手触りを確かめた。",
            "現場の肌感では遅い。",
            "顧客との温度感を合わせる。",
            "チームの熱量が高い。",
            "血の通った設計にする。",
            "泥臭く手作業で直した。",
            "要件の解像度を上げた。",
            "説明に腹落ちした。",
            "残さない側に倒した。",
            "調査で時間を溶かした。",
            "警告を 1 つずつ潰していく。",
            "議論はその案に収斂した。",
            "実装の詳細まで踏み込んで説明する。",
            "応答時間が大幅に短くなった。",
            "劇的な変化があった。",
            "処理が飛躍的に速くなった。",
            "精度が格段に上がった。",
            "応答が著しく遅い。",
            "利用者が圧倒的に多い。",
            "桁違いの速さで処理する。",
            "段違いの精度で判定する。",
            "今月は土台づくりに充てる。",
            "移行の第一歩とする。",
            "大きな一歩を踏み出した。",
            "設定の管理が成否の鍵を握る。",
            "円安が追い風になった。",
            "新機能を普及の起爆剤にする。",
            "この文書を開発の羅針盤とする。",
            "利用者と開発者の架け橋になる。",
            "このサービスは事業の屋台骨である。",
            "全体の品質を底上げする。",
            "盤石な体制を作る。",
            "古い画面に息を吹き込む。",
            "試作品に命を吹き込む。",
            "障害の連鎖を断ち切る。",
            "検索に新たな地平を開いた。",
        ]
        warn_sentences = [
            "設定ファイルが壊れる。",
            "検証に失敗した行を静かに捨てる。",
            "不正な行は黙って捨てられる。",
            "プロセスが沈黙する。",
            "例外を呼び出し元へ逃がす。",
        ]
        yomiyasu = [p for p in self.phrases if "yomiyasu" in p.get("note", "")]
        self.assertEqual(len(yomiyasu), len(info_sentences) + len(warn_sentences))
        variants = {v for p in yomiyasu for v in [p["ng"], *p.get("forms", [])]}
        cases = [(s, "info") for s in info_sentences] + [(s, "warn") for s in warn_sentences]
        for sentence, severity in cases:
            with self.subTest(sentence=sentence):
                findings = lint.detect_forbidden_phrases([(1, sentence)])
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0].category, "forbidden_phrase")
                self.assertEqual(findings[0].severity, severity)
                self.assertIn(findings[0].detail.split("「")[1].split("」")[0], variants)

    def test_温度感知を巻き込まない(self) -> None:
        self.assertEqual(lint.detect_forbidden_phrases([(1, "温度感知センサーで計測する。")]), [])

    def test_最大幅にを巻き込まない(self) -> None:
        self.assertEqual(lint.detect_forbidden_phrases([(1, "列を最大幅に広げる。")]), [])

    def test_severity_が_info_か_warn_に限られる(self) -> None:
        for entry in self.phrases:
            self.assertIn(entry["severity"], ("info", "warn"), entry["ng"])


class FillerPhraseTest(unittest.TestCase):
    def test_前置フィラーと定型クロージングを検出する(self) -> None:
        sentences = [
            "重要なのは、速度である。",
            "前置き。結論から言うと、不要だ。",
            "いかがでしたでしょうか。",
            "ぜひ試してみてください。",
            "ぜひ参考にしてみてください。",
            "本記事が参考になれば幸いです。",
            "**重要なのは**、速度である。",
            "ここで**重要なのは、速度である。",
            "ここで、重要なのは速度だ。",
            "次の章では設定を説明します。",
            "一度試してみてはいかがでしょうか。",
            "原因は設定と言っても過言ではありません。",
            "原因は設定と言っても過言ではありません!",
        ]
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                findings = lint.detect_filler_phrases([(1, sentence)])
                self.assertGreaterEqual(len(findings), 1)
                self.assertTrue(all(f.category == "filler_phrase" for f in findings))

    def test_文中の重要なのはと通常の依頼文は検出しない(self) -> None:
        for sentence in [
            "この設定で重要なのは、タイムアウトだ。",
            "ボタンを押してください。",
            "**この設定で重要なのは**、速度だ。",
            "次の章では API の一覧を表にした。",
            "次の章では説明を省く。",
        ]:
            with self.subTest(sentence=sentence):
                self.assertEqual(lint.detect_filler_phrases([(1, sentence)]), [])

    def test_箇条書きと見出しの行頭の前置フィラーを検出する(self) -> None:
        """lint.py が lex_lines を作る前処理を通しても、行頭記号を読み飛ばして検出する。"""
        for text in ["- 重要なのは、速度である。", "1. **重要なのは**、速度である。", "## 結論から言うと"]:
            with self.subTest(text=text):
                lex_lines = lint.iter_lines_with_no(lint.mask_markdown_structure(text, keep_structure_text=True))
                findings = lint.detect_filler_phrases(lex_lines)
                self.assertEqual([f.category for f in findings], ["filler_phrase"])
                self.assertNotRegex(findings[0].detail, r"「[-#*\d]")


if __name__ == "__main__":
    unittest.main()
