"""write-doc の動詞・名詞のカタログ(forbidden_phrases.json)の整合テスト。

カタログはデータであり、破損・重複・包含(同一行での二重検出の原因)を機械検査で塞ぐ。
lint.py がカタログから検出語と severity を正しく導出することも確かめる。
Python 3 標準ライブラリのみを使用する(lint.py の import は sudachipy を要求しない)。
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

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
        cls.string_phrases = [p for p in cls.phrases if "pattern" not in p]
        cls.pattern_phrases = [p for p in cls.phrases if "pattern" in p]

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
        """部分文字列の包含は同一行での二重検出を生むため禁止する。pattern の語の ng は表示名で照合しない。"""
        ngs = [p["ng"] for p in self.string_phrases]
        overlaps = [(a, b) for a in ngs for b in ngs if a != b and a in b]
        self.assertEqual(overlaps, [])

    def test_活用形が文字列で他の照合文字列を包含しない(self) -> None:
        """forms(活用形)も ng と同列に照合されるため、包含の禁止を全照合文字列に広げる。"""
        variants = []
        for p in self.string_phrases:
            forms = p.get("forms", [])
            self.assertIsInstance(forms, list, p["ng"])
            for form in forms:
                self.assertIsInstance(form, str, p["ng"])
                self.assertTrue(form, p["ng"])
            variants.extend([p["ng"], *forms])
        overlaps = [(a, b) for a in variants for b in variants if a != b and a in b]
        self.assertEqual(overlaps, [])

    def test_pattern_の語は_forms_を持たず正規表現が読める(self) -> None:
        for p in self.pattern_phrases:
            with self.subTest(ng=p["ng"]):
                self.assertNotIn("forms", p)
                self.assertIsInstance(p["pattern"], str)
                re.compile(p["pattern"])
                for key in ("context", "exclude", "exclude_before"):
                    if key in p:
                        self.assertIsInstance(p[key], str, key)
                        re.compile(p[key])
        string_variants = {v for v, _ in lint.FORBIDDEN_PHRASE_VARIANTS}
        for p in self.pattern_phrases:
            self.assertNotIn(p["ng"], string_variants, "pattern の語は文字列で照合しない")

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

    def test_README_の推敲で足した語を活用形ごとに検出する(self) -> None:
        """TASK-198。「を入れる」は常体・敬体・否定・活用を、「にある。」は参照文を検出する。"""
        for text in (
            "Go をインストールせずに Node.js を入れる。",
            "Go 1.26 以上を入れたうえで実行する。",
            "Node.js を入れて実行する。",
            "Wails CLI を入れます。",
            "Wails CLI を入れない。",
            "Finder から開く手順は docs/finder-quick-action.md にある。",
            "Finder から開く手順は docs/finder-quick-action.md にあります。",
            "「正規表現」にチェックを入れる。",
            "原因は設定にある。",
        ):
            with self.subTest(text=text):
                findings = lint.detect_forbidden_phrases([(1, text)])
                self.assertEqual(len(findings), 1, text)
                self.assertEqual(findings[0].category, "forbidden_phrase")
                self.assertEqual(findings[0].severity, "info")
        self.assertEqual(lint.detect_forbidden_phrases([(1, "値を入力する。")]), [])

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

    def test_natural_japanese_由来の動きの動詞を検出する(self) -> None:
        for sentence in ["エラーログを吐く。", "障害でサーバーが死んだ。", "設定ファイルが育っていく。", "ナレッジが育たない。"]:
            with self.subTest(sentence=sentence):
                findings = lint.detect_forbidden_phrases([(1, sentence)])
                self.assertEqual(len(findings), 1)
                self.assertEqual(findings[0].category, "forbidden_phrase")
                self.assertEqual(findings[0].severity, "info")
        motion = [p for p in self.phrases if "MOTION_VERBS" in p.get("note", "")]
        self.assertEqual(len(motion), 3)
        self.assertEqual({p["severity"] for p in motion}, {"info"})

    def test_動きの動詞の語幹を含む別の語を巻き込まない(self) -> None:
        for sentence in [
            "死活監視を設定する。",
            "サーバーが死活監視の対象になる。",
            "チームが育成計画を立てる。",
            "ノズルが液体を吐出する。",
        ]:
            with self.subTest(sentence=sentence):
                self.assertEqual(lint.detect_forbidden_phrases([(1, sentence)]), [])

    def test_severity_が_info_か_warn_に限られる(self) -> None:
        for entry in self.phrases:
            self.assertIn(entry["severity"], ("info", "warn"), entry["ng"])


def _write_catalog(directory: str, phrases: list[dict]) -> Path:
    path = Path(directory) / "catalog.json"
    path.write_text(json.dumps({"phrases": phrases}, ensure_ascii=False), encoding="utf-8")
    return path


_STRING_ENTRY = {"ng": "落とし込む", "type": "imprecise", "severity": "info", "ok": ["反映する"]}
_PATTERN_ENTRY = {
    "ng": "根因",
    "pattern": "根因",
    "context": "障害",
    "type": "pseudo_concrete",
    "severity": "info",
    "ok": ["原因"],
}


class PhraseCatalogLoadTest(unittest.TestCase):
    def test_pattern_の語を読み込んで正規表現にする(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _, patterns = lint._load_phrase_catalog(_write_catalog(d, [_STRING_ENTRY, _PATTERN_ENTRY]))
        self.assertEqual([p.ng for p in patterns], ["根因"])
        self.assertTrue(patterns[0].pattern.search("障害の根因"))
        self.assertTrue(patterns[0].context.search("障害の根因"))
        self.assertIsNone(patterns[0].exclude)
        self.assertIsNone(patterns[0].exclude_before)

    def test_pattern_と_forms_の併記は読み込みで落ちる(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = _write_catalog(d, [{**_PATTERN_ENTRY, "forms": ["根因で"]}])
            with self.assertRaises(ValueError):
                lint._load_phrase_catalog(path)

    def test_読めない正規表現は読み込みで落ちる(self) -> None:
        for key in ("pattern", "context", "exclude", "exclude_before"):
            for value in ("(", 1):
                with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as d:
                    path = _write_catalog(d, [{**_PATTERN_ENTRY, key: value}])
                    with self.assertRaises(ValueError):
                        lint._load_phrase_catalog(path)


class PhrasePatternDetectionTest(unittest.TestCase):
    """pattern の語を文ごとに照合する。カタログの語に当たらない例文で、仮の語だけを差し替えて確かめる。"""

    def _detect(self, line: str, raw_line: str | None = None) -> list:
        pattern = lint.PhrasePattern(
            ng="根因",
            pattern=re.compile("根因|根本因"),
            context=re.compile("障害|原因"),
            exclude=re.compile("植物"),
            exclude_before=re.compile("[一-龥]$"),
        )
        raw = None if raw_line is None else {1: raw_line}
        with unittest.mock.patch.object(lint, "FORBIDDEN_PHRASE_PATTERNS", [pattern]):
            return lint.detect_forbidden_phrases([(1, line)], raw)

    def test_条件を満たす文で検出する(self) -> None:
        findings = self._detect("障害の根因を特定する。")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "forbidden_phrase")
        self.assertEqual(findings[0].severity, "warn")
        self.assertEqual(findings[0].detail, "NG/OK カタログの語ヒット: 「根因」")

    def test_exclude_の語がカギ括弧の中だけなら外さない(self) -> None:
        self.assertEqual(len(self._detect("障害の根因を「植物」と比べる。")), 1)

    def test_条件を外れる文では検出しない(self) -> None:
        for line in (
            "根因を特定する。",
            "障害と植物の根因を比べる。",
            "障害の真根因を特定する。",
            "障害の「根因」を特定する。",
            "「障害」の根因を特定する。",
            "根因を特定する。障害は別に記録する。",
        ):
            with self.subTest(line=line):
                self.assertEqual(self._detect(line), [])

    def test_1_文に_1_件で_1_行の_2_文は_2_件(self) -> None:
        self.assertEqual(len(self._detect("障害の根因と根因を特定する。")), 1)
        self.assertEqual(len(self._detect("障害の根因を特定する。原因の根因も特定する。")), 2)

    def test_excerpt_は原文の行から前後_10_字を切り出し_detail_の語は表示名(self) -> None:
        raw = "「注」記録の前に障害の根本因を `特定` する。次に手順を記録する。"
        masked = "「注」記録の前に障害の根本因を      する。次に手順を記録する。"
        findings = self._detect(masked, raw)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].excerpt, "注」記録の前に障害の根本因を `特定` する。")
        self.assertEqual(findings[0].detail.split("「")[1].split("」")[0], "根因")

    def test_2_文目に当たった語の_excerpt_は_2_文目の位置から切り出す(self) -> None:
        findings = self._detect("前置きの文を長めに書いておく。次の文で障害の根因を見る。")
        self.assertEqual([f.excerpt for f in findings], ["おく。次の文で障害の根因を見る。"])

    def test_info_の語は補足を添える(self) -> None:
        with unittest.mock.patch.object(lint, "FORBIDDEN_PHRASES_WEAK_SIGNAL", {"根因"}), unittest.mock.patch.object(
            lint, "PHRASE_NOTES", {"根因": "仮の補足"}
        ):
            findings = self._detect("障害の根因を特定する。")
        self.assertEqual([f.severity for f in findings], ["info"])
        self.assertEqual(findings[0].detail, "NG/OK カタログの語ヒット: 「根因」（仮の補足）")


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
