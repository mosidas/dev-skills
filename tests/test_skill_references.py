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

REFERENCE_PATH = re.compile(r"write-doc/references/([\w/.-]+?\.md)")
RELATIVE_REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_./-])(?:\.\./)*(?:references/)?(?:format/|types/)?[a-z][\w-]*\.md"
)
IGNORED_NAMES = {
    "file.md",
    "SKILL.md",
    "README.md",
    # lint.py・forbidden_phrases.json が出典として挙げる上流のコーパスの報告。本リポジトリには無い。
    "deep-analysis.md",
    "antithesis-recalibration.md",
    "sweep_nested_attributive.md",
    # retro の事例が挙げる利用側の memory のファイル名。本リポジトリには無い。
    "site-user-facing-text-polite.md",
    "no-session-url-in-pr.md",
}
IGNORED_PREFIXES = ("slop", "phrases")
# write-doc の references を前置き(`../write-doc/references/`)なしで引くことがある他スキル。
SKILLS_CITING_WRITE_DOC = (
    "write-message",
    "design-ui",
    "write-slide",
    "write-page",
    "respond",
    "retro",
    "draw-diagram",
    "specify",
)

SKILL_BASES = tuple(
    base
    for skill in sorted((REPO_ROOT / "skills").iterdir())
    if skill.is_dir()
    for base in (skill, skill / "references")
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
        for name in SKILLS_CITING_WRITE_DOC:
            skill = REPO_ROOT / "skills" / name
            targets += [skill / "SKILL.md", *sorted((skill / "references").rglob("*.md"))]
        missing = []
        for path in targets:
            if path.suffix not in {".md", ".py", ".json"} or "__pycache__" in path.parts:
                continue
            # scripts/ は references/ をスキルの直下から引き、他スキルは別のスキルの references/ を
            # 表の見出しで前置きして引くため、各スキルの直下と references/ も基準にする。
            bases = (path.parent, WRITE_DOC_REFERENCES, *SKILL_BASES)
            for ref in RELATIVE_REFERENCE.findall(_read(path)):
                name = ref.rsplit("/", 1)[-1]
                if name in IGNORED_NAMES or name.startswith(IGNORED_PREFIXES):
                    continue
                if any((base / ref).is_file() for base in bases):
                    continue
                missing.append(f"{_rel(path)}: {ref}")
        if missing:
            self.fail("存在しない相対参照:\n" + "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
