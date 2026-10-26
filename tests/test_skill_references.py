"""スキルの規範ファイルへの参照が実在することの単体テスト。

write-doc の references を移動・分割したときに、他のスキル・hooks・README に古いパスや
存在しないファイル名が残らないことを確かめる。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from helpers import REPO_ROOT

WRITE_DOC = REPO_ROOT / "skills" / "write-doc"
WRITE_DOC_REFERENCES = WRITE_DOC / "references"

SKILLS = REPO_ROOT / "skills"
SKILL_NAMES = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())

REFERENCE_PATH = re.compile(r"write-doc/references/([\w/.-]+?\.md)")
# 自スキル内の参照(`sentence.md`・`../readers.md`)と、他スキルの SKILL.md・references への参照
# (`../draw-diagram/references/svg.md`・`../../../draw-diagram/references/svg.md`)を拾う。
RELATIVE_REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_./-])(?:\.\./)*"
    rf"(?:(?:{'|'.join(map(re.escape, SKILL_NAMES))})/)?"
    r"(?:references/)?(?:format/|types/)?(?:[a-z][\w-]*|SKILL|README)\.md"
)
# スキル名もディレクトリも付かない SKILL.md・README.md は、どのスキルのものか決まらない。
UNQUALIFIED_NAMES = {"SKILL.md", "README.md"}
IGNORED_NAMES = {
    "file.md",
    # lint.py・forbidden_phrases.json が出典として挙げる上流のコーパスの報告。本リポジトリには無い。
    "deep-analysis.md",
    "antithesis-recalibration.md",
    "sweep_nested_attributive.md",
    # retro の事例が挙げる利用側の memory のファイル名。本リポジトリには無い。
    "site-user-facing-text-polite.md",
    "no-session-url-in-pr.md",
}
IGNORED_PREFIXES = ("slop", "phrases")
SKILL_BASES = tuple(
    base for name in SKILL_NAMES for base in (SKILLS / name, SKILLS / name / "references")
)


def _repo_files() -> list[Path]:
    patterns = [
        "skills/**/*.md",
        "agents/*.md",
        "hooks/*.json",
        "hooks/*.py",
        "skills/*/scripts/*.py",
        "skills/*/scripts/*.json",
        "README.md",
        "tests/README.md",
    ]
    files = {p for pattern in patterns for p in REPO_ROOT.glob(pattern)}
    results = REPO_ROOT / "evals" / "results"
    files |= {
        p
        for p in (REPO_ROOT / "evals").rglob("*")
        if p.is_file() and results not in p.parents
    }
    return sorted(files)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


class SkillReferencesTest(unittest.TestCase):
    def test_write_docのreferencesへのパスが実在する(self) -> None:
        missing = [
            f"{_rel(path)}: {ref}"
            for path in _repo_files()
            for ref in REFERENCE_PATH.findall(_read(path))
            if not (WRITE_DOC_REFERENCES / ref).is_file()
        ]
        if missing:
            self.fail("存在しない write-doc の references への参照:\n" + "\n".join(missing))

    def test_相対参照が実在する(self) -> None:
        targets = sorted(WRITE_DOC.rglob("*"))
        for skill in sorted((REPO_ROOT / "skills").iterdir()):
            if skill.is_dir() and skill != WRITE_DOC:
                targets += [skill / "SKILL.md", *sorted((skill / "references").rglob("*.md"))]
        missing = []
        for path in targets:
            if path.suffix not in {".md", ".py", ".json"} or "__pycache__" in path.parts:
                continue
            # write-doc の scripts/ は references/ をスキルの直下から引く。他スキルは write-doc や
            # 別のスキルの references/ を表の見出しで前置きして引くため、全スキルを基準にする。
            if WRITE_DOC in path.parents:
                bases = (path.parent, WRITE_DOC_REFERENCES, WRITE_DOC, SKILLS)
            else:
                bases = (path.parent, WRITE_DOC_REFERENCES, *SKILL_BASES, SKILLS)
            for ref in RELATIVE_REFERENCE.findall(_read(path)):
                name = ref.rsplit("/", 1)[-1]
                if ref in UNQUALIFIED_NAMES or name in IGNORED_NAMES or name.startswith(IGNORED_PREFIXES):
                    continue
                if any((base / ref).is_file() for base in bases):
                    continue
                missing.append(f"{_rel(path)}: {ref}")
        if missing:
            self.fail("存在しない相対参照:\n" + "\n".join(missing))

    def test_write_slideのSKILL_mdが60行以下(self) -> None:
        # 規則の正本は write-doc に置き、write-slide は読む表と形式固有の工程だけを持つ。
        path = REPO_ROOT / "skills" / "write-slide" / "SKILL.md"
        lines = len(_read(path).splitlines())
        self.assertLessEqual(lines, 60, f"{_rel(path)} が {lines} 行ある")

    def test_write_pageのSKILL_mdが60行以下(self) -> None:
        # 規則の正本は write-doc に置き、write-page は読む表と HTML 固有の工程だけを持つ。
        path = REPO_ROOT / "skills" / "write-page" / "SKILL.md"
        lines = len(_read(path).splitlines())
        self.assertLessEqual(lines, 60, f"{_rel(path)} が {lines} 行ある")


if __name__ == "__main__":
    unittest.main()
