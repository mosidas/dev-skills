#!/usr/bin/env python3
"""応答に読み手が持たない文脈に頼る語(名前の無い番号の並び・名前の無い識別子・調べた範囲の無い否定の断定)が
あれば、同じターンの続きで直させる Stop hook。

respond 3.5 は調べて見つからなかった事項を調べた範囲とともに書くと、3.6 は識別子の初出に名前を添えると定める。
番号・識別子だけの語と、範囲の無い否定は、前の会話を読んでいない読み手には確かめられない。当たった語と直し方を
additionalContext で返し、続きの応答で直した文だけを書かせる。判定は形だけで行い誤検知の余地が残るため、
直す点が無ければ何も書かずに終えさせる。

入出力の契約:
  標準入力  UTF-8 の Stop の JSON(`stop_hook_active`・`last_assistant_message` を読む)。
            環境の符号化(PYTHONIOENCODING・ロケール)に依らず UTF-8 のバイト列として読む
  exit 0    検査を終えたとき(検出したときもしないときも)
  exit 1    hook 自身の想定外の例外。標準エラーに例外の型名だけを 1 行書く(応答の本文は書かない)
  標準出力  検出したときだけ `{"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": <指示>}}` の
            JSON を ASCII で 1 つ書く。検出しないときは何も書かない
  標準エラー exit 1 のときだけ書く

additionalContext は `decision: block` と違い会話に hook のエラーとして出ないが、同じターンを続けさせる点は同じで
ある(Claude Code の hooks の仕様の Stop decision control)。

`stop_hook_active` はターン全体の値であり、このターンで別の Stop hook(guard_next_line.py など)が続きを求めた
後の応答でも true になる。true なら検査しない(続きの応答を再び続けさせず、1 ターンに 1 回にする)。

環境変数 `DEV_SKILLS_BUILD_ITERATION` が `1` のときは検査しない。build の loop.py が反復の `claude -p` に渡す。
反復の最後の応答は本人が読まず(本人が読むのは進捗ファイル・Implementation Notes・PR)、続きの応答は費用だけを
増やすためである。

UTF-8 の JSON の dict として読めない入力と、`last_assistant_message` が文字列でない入力は何も書かずに通す
(fail-open)。この hook は応答の書き方を直させるもので漏えいを防ぐものではなく、自分の解析の失敗で続けさせると
すべての応答に続きが付くためである。想定外の例外も exit 1(Claude Code は続けさせない)で通す。
"""

from __future__ import annotations

import bisect
import enum
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import response_text as rt  # noqa: E402

BUILD_ITERATION = "DEV_SKILLS_BUILD_ITERATION"


class Kind(enum.Enum):
    NUMBERS = "numbers"
    IDENTIFIER = "identifier"
    NEGATION = "negation"


@dataclass(frozen=True)
class Finding:
    kind: Kind
    text: str


HEAD = "respond 3.5・3.6 の検査: 読み手が持たない文脈に頼る語がある。"
# {words} に当たった語を「」で囲んで差し込む
GUIDE: dict[Kind, str] = {
    Kind.NUMBERS: "番号だけの並び({words})は何を指すかが書かれていない。番号の後に括弧で名前を書く。",
    Kind.IDENTIFIER: "名前の無い識別子({words})がある。初出の識別子の後に括弧で名前(タイトル・要約)を書く。",
    Kind.NEGATION: (
        "調べた範囲の無い否定の断定({words})がある。同じ文か直後の文に調べた範囲(ファイル・コマンドと件数)を書く。"
        "調べていなければ「〜と推定する(根拠: …)」か「〜と推測する」に直す。"
    ),
}
TAIL = (
    "前の応答の本文は繰り返さず、直した文だけを返す。"
    "前の応答の最後に「次:」の行があれば、直した文の後にその行を最後の行として書く。"
    "ほかの hook がその行の書き直しを求めていれば、書き直した行を書く。"
    "当たった語が値である・名前か範囲が既に書いてあるなど直す点が無ければ、何も書かずに終える。"
)
# 型ごとに書く当たった語の数と 1 語の長さの上限。additionalContext の上限(10,000 字)より十分短く保つ
WORDS_MAX = 3
WORD_MAX = 40

# 番号の並び。並びの前は行頭(字下げ・箇条の印の後)か文の頭に限る(「ステップ 1・2」「幅 375・768」を通す)
DIGITS = r"[0-9０-９]+"
SEP = r"\s*(?:と|・|、|,(?![0-9]{3}(?![0-9]))|，|や|か|および|及び)\s*"
COUNTER = (
    r"(?:件|つ|個|行|点|案|本|回|か所|箇所|段|人|日|分|秒|枚|節|章|項|週|時間|号|版|年|月|%|％|px|ms|MB|KB|GB"
    r"|番目|位|色|列|文字|字|語|問|例|台|倍|度|ページ|ステップ|手順|円|歳|名|層|周|行目|枚目|件目|回目)"
)
ALNUM = r"[0-9A-Za-z_０-９Ａ-Ｚａ-ｚ]"
NUMBERS = re.compile(
    r"(?:^|(?<=[。!?！？]))[ \t]*(?:[-*+>][ \t]+|[0-9]+\.[ \t]+)?"
    r"(" + DIGITS + r"(?:" + SEP + DIGITS + r")+)"
    r"(?!" + ALNUM + r"|\.[0-9])(?!" + SEP + DIGITS + r")(?!\s*" + COUNTER + r")(?!\s*[(（])",
    re.M,
)

# 識別子。前後が語の一部(パス・ブランチ・アンカー・文字参照)のものは除く
REF = re.compile(r"(?<![0-9A-Za-z_/#&.\-])(?:TASK-[0-9]+(?:\.[0-9]+)*|#[0-9]+)(?![0-9A-Za-z_/\-]|\.[0-9])")
# respond 3.4 の状態タグ。中身の長さに上限を置き、閉じない「[」の繰り返しで行末まで読み直さない
STATUS_TAG = re.compile(
    r"\[(?:マージ済み|PR 未マージ|作業中|確認済み・未コミット|取り消し済み|main に反映済み|閉じた・未マージ|未着手)"
    r"[^\]\n]{0,100}\]"
)
# 名前の前に置ける兄弟の識別子の並び(「TASK-1.01・.02(名前)」「#2・#3(名前)」)。並びの長さに上限を置き、
# 1 行に多数の識別子が並んでも識別子ごとに行末まで読み直さない
SIBLINGS = r"(?:\s*[・、,]\s*(?:TASK-[0-9]+(?:\.[0-9]+)*|#[0-9]+|\.?[0-9]+(?:\.[0-9]+)*)){0,10}"
# 識別子の後に空白を置いて名前が続く形(「TASK-1 一覧の画面」)。名前は漢字・カタカナ・英字の 2 字以上で始まる。
# 進行や状態を表す語(「TASK-1 ステップ 2」「TASK-1 Done」)・英語の文の機能語・続く識別子は名前にしない
PROGRESS = (
    r"(?:ステップ|マージ|ブランチ|工程|完了|実装|点検|承認|計画|起票|自身|Done|done|PR"
    r"|and|or|for|to|in|is|was|the|with|on|at|as|by|from)(?![ァ-ヺーA-Za-z])"
)
# 漢字・カタカナ(中黒「・」を除く)・英字
NAME_CHARS = "一-鿿ァ-ヺー々A-Za-z"
NAME_AFTER = re.compile(
    SIBLINGS + r"[*_ \t]*[(（「:：][ \t]*\S"
    r"|[ \t]+(?!" + PROGRESS + r"|TASK-[0-9])[" + NAME_CHARS + "][" + NAME_CHARS + r"\-]"
)
# 後の出現で名前ありとみなす形は括弧だけにする(コロンや空白の後は状態の語が続きうる)
NAME_PAREN = re.compile(SIBLINGS + r"[*_ \t]*[(（「][ \t]*\S")
RANGE_AFTER = re.compile(r"\s*[〜~]\s*(?:TASK-|#|\.)?[0-9]")
RANGE_BEFORE = re.compile(r"[〜~]\s*$")
NAMED_BEFORE = re.compile(r"[)）]\s*の\s*(?:PR\s*)?$")
# 引用した文字列(返信の文面など)。閉じた対だけを、行の中で長さに上限を置いて数え、閉じない「で行末まで読み直さない
QUOTED = re.compile(r"「[^「」\n]{0,200}」|『[^『』\n]{0,200}』")
# 識別子に続く条件の形(「TASK-1 なら」「TASK-1 であれば」「#1 を閉じてよければ」)。条件は読点・句点・引用符・括弧を
# またがない 20 字以内に限る。後ろに仮名が続くもの(「ならびに」「なければならない」)は条件にしない。
# 「のとき」「たら」は過去の出来事を語る文(「#1 のときは通った」「直したら通った」)にも使うので条件にしない
CONDITION_AFTER = re.compile(r"[^、。「」『』()（）\n]{0,20}?(?:ならば?|れば)(?![ぁ-ゖ])")
# 前を見る窓の幅。前の確認を固定の長さにし、1 行に多数の識別子があっても行の長さの二乗にしない
BEFORE_WINDOW = 16
PAREN = re.compile(r"[()（）]")
LETTER = re.compile(r"[^\W\d_]")

# 否定の断定。後ろが文の終わりか断定の語のもの(「問題なければ」「問題ないか」を除く)
NEGATION = re.compile(
    r"(?:影響(?:しな(?:い|かった)|は(?:無|な)(?:い|かった)|(?:が|も)(?:無|な)(?:い|かった))"
    r"|問題(?:は|も)?(?:無|な)(?:い|かった)"
    r"|支障(?:は|も)?(?:無|な)(?:い|かった)"
    r"|差(?:は|も)?(?:出な(?:い|かった)|(?:無|な)(?:い|かった)))"
    r"(?=\s*(?:。|$|です|でした|だ|と判断|と結論))"
)
# 件数の始まりを数字の並びの先頭に限る(並びの途中の各位置から末尾まで読み直さない)
SCOPE = re.compile(r"(?<![0-9０-９])[0-9０-９]+\s*件|根拠|確か(?:め|認)|確認し|調べ|照合|grep|テスト|実行し|読ん|通っ|推定|推測")


def numbers(lines: list[tuple[str, str]]) -> list[Finding]:
    return [
        Finding(Kind.NUMBERS, line[m.start(1):m.end(1)])
        for line, prose in lines
        for m in NUMBERS.finditer(prose)
    ]


def table_name_cells(line: str) -> tuple[list[int], list[bool], int]:
    """表の行なら、セルの区切りの位置・各セルに識別子以外の文字があるか・その数を返す。表の行でなければ空。"""
    if not line.lstrip().startswith("|"):
        return [], [], 0
    bars = [i for i, c in enumerate(line) if c == "|"]
    plain = rt.blank(line, REF)
    lettered = [bool(LETTER.search(plain, a + 1, b)) for a, b in zip(bars, bars[1:] + [len(line)])]
    return bars, lettered, sum(lettered)


def identifiers(lines: list[tuple[str, str]]) -> list[Finding]:
    """語ごとに応答の中の初出で名前の有無を見て、名前の無いものを返す。

    初出に名前が無くても、同じ応答の後の出現に括弧で名前を書いていれば、読み手は名前を得るので返さない。
    「」『』の中(引用した文字列)と、識別子に続く条件の節の中の出現は、指している対象を読み手に伝える文で
    ないので、名前の有無に依らず初出にも後の出現にも数えない。
    """
    found: list[Finding] = []
    seen: set[str] = set()
    named_later: set[str] = set()
    for _, prose in lines:
        line = rt.blank(prose, STATUS_TAG)
        quoted = [(q.start(), q.end()) for q in QUOTED.finditer(line)]
        table = None
        letter = LETTER.search(rt.blank(line, REF))
        first_letter = letter.start() if letter else len(line)
        parens = PAREN.finditer(line)
        opened: list[int] = []
        pending = next(parens, None)
        for m in REF.finditer(line):
            while pending is not None and pending.start() < m.start():
                if pending.group(0) in "(（":
                    opened.append(pending.start())
                elif opened:
                    opened.pop()
                pending = next(parens, None)
            q = bisect.bisect_right(quoted, (m.start(), len(line))) - 1
            if (q >= 0 and m.end() <= quoted[q][1]) or CONDITION_AFTER.match(line, m.end()):
                continue
            word = m.group(0)
            if word in seen:
                if NAME_PAREN.match(line, m.end()):
                    named_later.add(word)
                continue
            before = line[max(0, m.start() - BEFORE_WINDOW):m.start()]
            named = bool(
                NAME_AFTER.match(line, m.end())
                or (opened and first_letter < opened[-1])
                or NAMED_BEFORE.search(before)
                or RANGE_AFTER.match(line, m.end())
                or RANGE_BEFORE.search(before)
            )
            if not named:
                if table is None:
                    table = table_name_cells(line)
                bars, lettered, named_cells = table
                own = bisect.bisect_left(bars, m.start()) - 1
                named = named_cells - (1 if own >= 0 and lettered[own] else 0) > 0
            seen.add(word)
            if not named:
                found.append(Finding(Kind.IDENTIFIER, word))
    return [f for f in found if f.text not in named_later]


def negations(lines: list[tuple[str, str]]) -> list[Finding]:
    """同じ文にも直後の文にも調べた範囲の印が無い否定の断定を返す。

    範囲の印は、インラインのコード・URL・パス・ファイル名(前処理で空白にした部分)と SCOPE の語である。
    文は「。」と改行で分け、空の文は数えない(直後の文は、次の行や空行の後の文でもよい)。
    """
    # (元の文, 前処理の後の文, 範囲の印があるか)
    sentences: list[tuple[str, str, bool]] = []
    for line, prose in lines:
        start = 0
        for end in [i + 1 for i, c in enumerate(prose) if c == "。"] + [len(prose)]:
            raw, text = line[start:end], prose[start:end]
            if raw.strip():
                sentences.append((raw, text, raw != text or bool(SCOPE.search(raw))))
            start = end
    found: list[Finding] = []
    for i, (raw, text, marked) in enumerate(sentences):
        if marked or (i + 1 < len(sentences) and sentences[i + 1][2]):
            continue
        depth = pos = 0
        for m in NEGATION.finditer(text):
            for c in text[pos:m.start()]:
                depth += (c == "「") - (c == "」")
            pos = m.start()
            if depth <= 0:
                found.append(Finding(Kind.NEGATION, raw[:m.end()].strip()))
                break
    return found


def findings(message: str) -> list[Finding]:
    """当たった語を、型ごとに応答の中の順で返す。"""
    lines = [
        (line, rt.blank(rt.blank(rt.blank(rt.blank_code_spans(line), rt.URL), rt.PATH), rt.FILENAME))
        for line in rt.prose_lines(message)
        if line is not None
    ]
    return numbers(lines) + identifiers(lines) + negations(lines)


def shown(finding: Finding) -> str:
    """当たった語を WORD_MAX 字で切る。否定の断定は否定の語を残すため先頭を切る。"""
    text = finding.text
    if len(text) <= WORD_MAX:
        return text
    return "…" + text[-WORD_MAX:] if finding.kind is Kind.NEGATION else text[:WORD_MAX] + "…"


def feedback(found: list[Finding]) -> str:
    parts = [HEAD]
    for kind, guide in GUIDE.items():
        words = [shown(f) for f in found if f.kind is kind][:WORDS_MAX]
        if words:
            parts.append(guide.format(words="・".join(f"「{w}」" for w in words)))
    parts.append(TAIL)
    return "".join(parts)


def main() -> int:
    payload = rt.read_payload(sys.stdin.buffer)
    if payload is None or payload.get("stop_hook_active") or os.environ.get(BUILD_ITERATION) == "1":
        return 0
    message = payload.get("last_assistant_message")
    if not isinstance(message, str):
        return 0
    found = findings(message)
    if found:
        json.dump({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": feedback(found)}}, sys.stdout)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # noqa: BLE001  hook 自身の不具合で応答に続きを付けない(fail-open)。本文は書かない
        print(f"guard_reader_context: 内部エラー {type(e).__name__}", file=sys.stderr)
        code = 1
    sys.exit(code)
