#!/usr/bin/env python3
"""description のトリガ検査(read-only)。

スキルの `description` が「呼ばれるべきときに選ばれ、紛らわしい依頼では選ばれない」
かを決定論的に検査する。判定は description と依頼文の語彙の重なり(文字 bigram の
コサイン類似度)で行い、意味の理解は行わない。したがって指摘は warning であり、
最終判断は人間/meta-review が行う(principles.md §5 の分担)。

検査項目:
  肯定例   should_trigger: true の依頼文で、対象スキルが類似度 1 位になる
  否定例   should_trigger: false の依頼文(語彙が近い near-miss)で、対象スキルが 1 位にならない
  近接衝突 2 つの description の類似度が閾値以上(選択が安定しない疑い)
  ケース網羅 description を持つスキルに肯定例・否定例が 1 件も無い(仕様ファイルの追随漏れ)

結果の読み方(限界):
  全ケースの通過は「description が実際の起動で選ばれる」ことを意味しない。ケース文が
  description の語彙を借りていれば通過するため、通過は「意図した語彙が description に
  含まれる」ことだけを示す。判別力を測るには、description の語を借りずに書いた依頼文を
  加える。実際の選択は harness の LLM が行うため、この指標は近似にすぎない。

閾値:
  近接衝突の既定は 0.30 とする。役割が近いことが設計上意図されている組(検査系の部品
  同士など)の実測値のすぐ上に置き、それより近い組を検出できる位置にする。分布を調べる
  ときは --collision-threshold を下げて実行する。

仕様ファイル(既定 `<meta-core>/trigger-cases.json`):
  {"cases": [{"id": "...", "skill": "dev-spec", "prompt": "...", "should_trigger": true}]}

使い方:
  trigger_check.py [--root <dev-skills のルート>] [--cases <JSON>]
                   [--collision-threshold 0.30] [--json]
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import meta_lib  # noqa: E402

# 語彙の単位にしない文字(記号・空白)。日本語は分かち書きしないため文字 bigram を使う。
NON_WORD_RE = re.compile(r"[^0-9a-z぀-ヿ一-鿿]+")


def die(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def bigrams(text: str) -> set[str]:
    """文字 bigram の集合を返す(記号・空白は除去する)。"""
    s = NON_WORD_RE.sub("", text.lower())
    return {s[i : i + 2] for i in range(len(s) - 1)}


def similarity(a: set[str], b: set[str]) -> float:
    """コサイン類似度。長い description が一方的に有利にならないよう正規化する。"""
    if not a or not b:
        return 0.0
    return len(a & b) / math.sqrt(len(a) * len(b))


def load_descriptions(root: Path) -> dict[str, str]:
    """各スキルの SKILL.md の frontmatter から {name: description} を作る。

    解析は `meta_lib` の YAML サブセット(引用符つきスカラー・ブロックスカラーを含む)。
    meta_check.py と同じ解析器を使い、同じフィールドで別の結論を出さないようにする。
    """
    result: dict[str, str] = {}
    for skill in meta_lib.skill_dirs(root):
        path = skill / "SKILL.md"
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        parsed = meta_lib.parse_frontmatter(text)
        if parsed is None:
            continue
        data = parsed[0]
        name = meta_lib.scalar(data, "name")
        description = meta_lib.scalar(data, "description")
        if name and description and description.strip():
            result[name] = description.strip()
    return result


def rank(prompt: str, grams: dict[str, set[str]]) -> list[tuple[str, float]]:
    p = bigrams(prompt)
    scored = [(name, similarity(p, g)) for name, g in grams.items()]
    return sorted(scored, key=lambda kv: (-kv[1], kv[0]))


def main() -> None:
    parser = argparse.ArgumentParser(description="description のトリガ検査(read-only)")
    parser.add_argument(
        "--root", help="dev-skills のルート(既定: スキルのグループを上方向に探索)"
    )
    parser.add_argument("--cases", help="仕様ファイル(既定: meta-core/trigger-cases.json)")
    parser.add_argument(
        "--collision-threshold",
        type=float,
        default=0.30,
        help="description 同士の近接衝突とみなす類似度(既定 0.30)",
    )
    parser.add_argument("--json", action="store_true", help="JSON で出力する")
    args = parser.parse_args()

    if args.root:
        root = Path(args.root).resolve()
        if not meta_lib.is_root(root):
            die(f"--root にスキルのグループが無い: {root}")
    else:
        found = meta_lib.find_root(Path.cwd())
        if found is None:
            die("スキルのグループを含むルートが見つからない(--root で指定する)")
        root = found

    # 既定の仕様ファイルは本スクリプトと同じスキル(meta-core)の直下から解決する
    # (スキルの配置が変わってもスキル内の相対関係は変わらない)。
    cases_path = (
        Path(args.cases)
        if args.cases
        else Path(__file__).resolve().parent.parent / "trigger-cases.json"
    )
    try:
        spec = json.loads(cases_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        die(f"仕様ファイルを読めない: {cases_path}: {e}")
        raise AssertionError  # die は返らない

    descriptions = load_descriptions(root)
    if not descriptions:
        die(f"description を持つスキルが見つからない: {root}")
    grams = {name: bigrams(desc) for name, desc in descriptions.items()}

    cases = spec.get("cases") if isinstance(spec, dict) else None
    if not isinstance(cases, list) or not all(isinstance(c, dict) for c in cases):
        die(
            f"仕様ファイルの形式が不正: {cases_path}"
            '(トップレベルに {"cases": [ {...}, ... ]} が必要)'
        )
        raise AssertionError  # die は返らない

    findings: list[dict] = []
    passed = 0
    covered: set[str] = set()
    for case in cases:
        skill, prompt = case.get("skill"), case.get("prompt", "")
        expect = bool(case.get("should_trigger"))
        cid = case.get("id", "(id なし)")
        if skill not in descriptions:
            findings.append(
                {
                    "severity": "error",
                    "message": f"{cid}: 対象スキル {skill!r} が実在しない",
                }
            )
            continue
        covered.add(skill)
        ranked = rank(prompt, grams)
        top, top_score = ranked[0]
        position = [n for n, _ in ranked].index(skill) + 1
        own = dict(ranked)[skill]
        if expect and top != skill:
            findings.append(
                {
                    "severity": "warning",
                    "message": (
                        f"{cid}: 肯定例で {skill} が 1 位にならない"
                        f"(順位 {position}・類似度 {own:.3f}。1 位は {top}・{top_score:.3f})"
                    ),
                }
            )
        elif not expect and top == skill:
            findings.append(
                {
                    "severity": "warning",
                    "message": (
                        f"{cid}: 否定例で {skill} が 1 位になる"
                        f"(類似度 {own:.3f}。2 位は {ranked[1][0]}・{ranked[1][1]:.3f})"
                    ),
                }
            )
        else:
            passed += 1

    names = sorted(grams)
    for name in names:
        if name not in covered:
            findings.append(
                {
                    "severity": "warning",
                    "message": (
                        f"{name} の検査ケースが仕様ファイルに 1 件も無い"
                        "(部品の追加・改名に仕様ファイルが追随していない)"
                    ),
                }
            )
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            score = similarity(grams[a], grams[b])
            if score >= args.collision_threshold:
                findings.append(
                    {
                        "severity": "warning",
                        "message": (
                            f"description が近接している: {a} と {b}(類似度 {score:.3f}"
                            f" ≧ {args.collision_threshold})"
                        ),
                    }
                )

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    total = len(cases)
    if args.json:
        print(
            json.dumps(
                {
                    "cases": total,
                    "passed": passed,
                    "errors": errors,
                    "warnings": warnings,
                    "findings": findings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        icons = {"error": "🔴", "warning": "🟡"}
        for f in findings:
            print(f"{icons.get(f['severity'], '🔵')} {f['severity']}: {f['message']}")
        print(
            f"結果: ケース {passed}/{total} 通過 / error {errors} 件 / warning {warnings} 件"
        )
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
