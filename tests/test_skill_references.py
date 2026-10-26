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
    r"(?<![\w.-])(?:\.\./)*(?:references/)?(?:format/|types/)?[a-z]+\.md"
)
IGNORED_NAMES = {"file.md", "SKILL.md", "README.md"}
IGNORED_PREFIXES = ("slop", "phrases")


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

    def test_write_doc内の相対参照が実在する(self) -> None:
        missing = []
        for path in sorted(WRITE_DOC.rglob("*")):
            if path.suffix not in {".md", ".py", ".json"} or "__pycache__" in path.parts:
                continue
            for ref in RELATIVE_REFERENCE.findall(_read(path)):
                name = ref.rsplit("/", 1)[-1]
                if name in IGNORED_NAMES or name.startswith(IGNORED_PREFIXES):
                    continue
                # scripts/ は references/ をスキルの直下から引くため、スキルの直下も基準にする。
                if any((base / ref).is_file() for base in (path.parent, WRITE_DOC_REFERENCES, WRITE_DOC)):
                    continue
                missing.append(f"{_rel(path)}: {ref}")
        if missing:
            self.fail("存在しない write-doc 内の相対参照:\n" + "\n".join(missing))


if __name__ == "__main__":
    unittest.main()
