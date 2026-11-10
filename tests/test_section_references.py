"""スキルの間で節を番号で指す参照が、実在する節を指し、並記した見出しと一致することの単体テスト。

節を足したり消したりして番号がずれたときに、古い番号を指す参照を見つける。
Python 3 標準ライブラリのみを使用する。
"""

from __future__ import annotations

import re
import shutil
import unittest
from pathlib import Path

from helpers import REPO_ROOT, TempDirTestCase


# 過去の版の節番号を記録として引く事例。今の節を指さないので検査しない。
EXCLUDED = {"skills/retro/references/example.md"}

FENCE = re.compile(r"^```.*?^```[^\n]*$", re.M | re.S)
HEADING = re.compile(r"^#{2,6}\s+(\d+(?:\.\d+)*)\.?\s+(.+?)\s*$", re.M)
SECTION = r"\d+\.(?:\d+\.?)*"
ITEM = re.compile(rf"({SECTION})(?:\(([^()]*)\))?")
FILE_REF = re.compile(rf"`((?:[\w.-]+/)*[\w.-]+\.md)` (?={SECTION})")


def _text(path: Path) -> str:
    """コードフェンスを空行に置き換えた本文(行番号は保つ)。"""
    text = path.read_text(encoding="utf-8")
    return FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _items(line: str, pos: int) -> list[tuple[str, str | None]]:
    """`8.・9.(見出し)` のように `・` で続く (書いた節番号, 並記した見出し) の並び。"""
    items = []
    while m := ITEM.match(line, pos):
        items.append((m.group(1), m.group(2)))
        pos = m.end()
        if not (line.startswith("・", pos) and ITEM.match(line, pos + 1)):
            break
        pos += 1
    return items


def section_reference_problems(root: Path) -> list[str]:
    """`<スキル名> <節>`・`` `<ファイル>.md` <節> `` の参照のうち、節が無いものと並記した見出しが違うものを挙げる。"""
    root = root.resolve()
    skills = root / "skills"
    names = sorted(p.name for p in skills.iterdir() if p.is_dir())
    targets = {name: skills / name / "SKILL.md" for name in names}
    targets["README"] = root / "README.md"
    name_ref = re.compile(
        rf"(?<![A-Za-z0-9_/`.-])({'|'.join(map(re.escape, targets))})"
        rf"(?: |\(`([^`]+)`\))(?={SECTION})"
    )
    skill_bases = [base for name in names for base in (skills / name, skills / name / "references")]
    headings: dict[Path, dict[str, str]] = {}

    def heading_of(path: Path, section: str) -> str | None:
        if path not in headings:
            headings[path] = dict(HEADING.findall(_text(path)))
        return headings[path].get(section.rstrip("."))

    files = sorted({*root.glob("skills/**/*.md"), *root.glob("agents/*.md")})
    files += [p for p in (root / "README.md", root / "AGENTS.md") if p.is_file()]
    problems = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        if rel in EXCLUDED:
            continue
        parts = path.relative_to(root).parts
        owner = skills / parts[1] if parts[0] == "skills" else path
        bases = [path.parent, *([owner, owner / "references"] if owner != path else []), *skill_bases, skills, root]

        def same_owner(target: Path) -> bool:
            return target == owner or owner in target.parents

        def resolve(ref: str) -> Path | None:
            return next(((b / ref).resolve() for b in bases if (b / ref).is_file()), None)

        for number, line in enumerate(_text(path).splitlines(), 1):
            found = []
            for m in name_ref.finditer(line):
                name, inner = m.groups()
                if inner is None or not inner.endswith(".md"):
                    found.append((m, targets[name], name))
                elif (target := resolve(inner)) is not None:
                    found.append((m, target, name if target == targets[name] else f"`{inner}`"))
            for m in FILE_REF.finditer(line):
                if (target := resolve(m.group(1))) is not None:
                    found.append((m, target, f"`{m.group(1)}`"))
            for m, target, label in found:
                if same_owner(target):
                    continue
                for section, given in _items(line, m.end()):
                    ref = f"{label} {section}"
                    actual = heading_of(target, section)
                    if actual is None:
                        problems.append(f"{rel}:{number}: {ref} の節が無い")
                    elif given is not None and given != actual:
                        problems.append(f"{rel}:{number}: {ref}({given}) が見出し「{actual}」と違う")
    return problems


class 実リポジトリ(TempDirTestCase):
    def test_スキルの間の節番号の参照が実在し見出しが一致する(self) -> None:
        problems = section_reference_problems(REPO_ROOT)
        if problems:
            self.fail("節番号の参照の問題:\n" + "\n".join(problems))

    def test_見出しを消した写しでは各所の参照が節の無い参照として挙がる(self) -> None:
        for name in ("skills", "agents"):
            shutil.copytree(REPO_ROOT / name, self.tmp / name)
        for name in ("README.md", "AGENTS.md"):
            shutil.copy(REPO_ROOT / name, self.tmp / name)
        for path in self.tmp.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            path.write_text(re.sub(r"^#+ .*$", "", text, flags=re.M), encoding="utf-8")
        missing = [p for p in section_reference_problems(self.tmp) if "の節が無い" in p]
        for prefix in ("agents/", "README.md:", "skills/"):
            self.assertTrue(
                any(p.startswith(prefix) for p in missing),
                f"{prefix} の参照を拾えていない(拾えないと上の実リポジトリのテストが素通りする)",
            )
        self.assertTrue(
            any("`" in p for p in missing),
            "ファイルの形の参照を拾えていない(拾えないと上の実リポジトリのテストが素通りする)",
        )


class 検査関数(TempDirTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.write("README.md", "## 6. 規範\n### 6.2. スキルを書くときの規則\n")
        self.write("skills/develop/SKILL.md", "## 6. 実装と点検のループ\n## 8. 押す\n## 9. 閉じる\n")
        self.write("skills/develop/references/parallel.md", "## 2. 並行の型\n")
        self.write("skills/build/SKILL.md", "## 4. 反復する\n")
        self.write("skills/verify/SKILL.md", "## 3. 保守する\n")
        self.write("skills/secure/SKILL.md", "## 2. 規範\n### 2.1 信頼境界と入力検証\n")

    def problems(self, text: str, rel: str = "skills/build/SKILL.md") -> list[str]:
        self.write(rel, text)
        return section_reference_problems(self.tmp)

    def test_並記した見出しが一致すれば問題が無い(self) -> None:
        self.assertEqual(self.problems("develop 6.(実装と点検のループ)に従う。\n"), [])

    def test_節番号が1つずれると見出しの不一致で落ちる(self) -> None:
        self.write("skills/develop/SKILL.md", "## 6. 新しい節\n## 7. 実装と点検のループ\n")
        problems = self.problems("前置き\ndevelop 6.(実装と点検のループ)に従う。\n")
        self.assertAnyContains(problems, "skills/build/SKILL.md:2:")
        self.assertAnyContains(problems, "見出し「新しい節」と違う")

    def test_無い節を指すと節が無いで落ちる(self) -> None:
        problems = self.problems("develop 7. に従う。\n")
        self.assertAnyContains(problems, "skills/build/SKILL.md:1: develop 7. の節が無い")

    def test_並記が無くても節があれば問題が無い(self) -> None:
        self.assertEqual(self.problems("develop 6. に従う。\n"), [])

    def test_中黒で続く番号もそれぞれ検査する(self) -> None:
        self.assertEqual(self.problems("develop 8.・9. に従う。\n"), [])
        self.write("skills/develop/SKILL.md", "## 8. 押す\n")
        self.assertAnyContains(section_reference_problems(self.tmp), "develop 9. の節が無い")

    def test_dev_skillsの名前を添えた形も検査する(self) -> None:
        self.assertEqual(self.problems("verify(`dev-skills:verify`)3. を読む。\n"), [])
        problems = self.problems("verify(`dev-skills:verify`)4. を読む。\n")
        self.assertAnyContains(problems, "の節が無い")

    def test_パスを添えた形も検査する(self) -> None:
        self.write("skills/interview/SKILL.md", "## 2. 聞き方\n")
        self.assertEqual(self.problems("interview(`../../interview/SKILL.md`)2. に従う。\n"), [])
        problems = self.problems("interview(`../../interview/SKILL.md`)3. に従う。\n")
        self.assertAnyContains(problems, "skills/build/SKILL.md:1: interview 3. の節が無い")

    def test_括弧に別のファイルのパスを書いた参照はそのファイルの節で照らす(self) -> None:
        self.write("skills/design-ui/SKILL.md", "## 4. スケール\n## 5. 仕上げ\n")
        self.write("skills/design-ui/references/session.md", "### 3.1. 1 往復で出すもの\n## 4. 確かめて終える\n")
        rel = "skills/specify/SKILL.md"
        path = "design-ui(`../design-ui/references/session.md`)"
        self.assertEqual(
            self.problems(f"{path}3.1(1 往復で出すもの)と {path}4.(確かめて終える)に従う。\n", rel=rel),
            [],
            "SKILL.md に無い節・別の見出しの節でも、参照先のファイルにあれば挙がらない",
        )
        self.assertAnyContains(
            self.problems(f"{path}5. を見る。\n", rel=rel),
            "skills/specify/SKILL.md:1: `../design-ui/references/session.md` 5. の節が無い",
        )

    def test_括弧に書いたパスのファイルの見出しと並記が違えば落ちる(self) -> None:
        self.write("skills/design-ui/SKILL.md", "## 4. スケール\n")
        self.write("skills/design-ui/references/session.md", "## 4. 確かめて終える\n")
        rel = "skills/specify/SKILL.md"
        path = "design-ui(`../design-ui/references/session.md`)"
        self.assertEqual(self.problems(f"{path}4.(確かめて終える)に従う。\n", rel=rel), [])
        problems = self.problems(f"{path}4.(スケール)に従う。\n", rel=rel)
        self.assertAnyContains(problems, "`../design-ui/references/session.md` 4.(スケール) が見出し「確かめて終える」と違う")

    def test_スキル名の前に英数字やスラッシュが付く語は参照として拾わない(self) -> None:
        rel = "skills/specify/SKILL.md"
        self.assertEqual(self.problems("rebuild 3. と skills/build 3. を見る。\n", rel=rel), [])
        self.assertAnyContains(self.problems("build 3. を見る。\n", rel=rel), "build 3. の節が無い")

    def test_READMEの節も検査する(self) -> None:
        self.assertEqual(self.problems("README 6.2(スキルを書くときの規則)に従う。\n"), [])
        self.assertAnyContains(self.problems("README 6.3 に従う。\n"), "README 6.3 の節が無い")

    def test_ほかのスキルのreferencesの節の実在を検査する(self) -> None:
        self.assertEqual(self.problems("develop の `references/parallel.md` 2. に従う。\n"), [])
        problems = self.problems("develop の `references/parallel.md` 3. に従う。\n")
        self.assertAnyContains(problems, "skills/build/SKILL.md:1: `references/parallel.md` 3. の節が無い")

    def test_同じスキルの中の参照は無い節でも落ちない(self) -> None:
        text = "develop 5. と `references/parallel.md` 9. に従う。\n"
        self.assertEqual(self.problems(text, rel="skills/develop/references/kinds.md"), [])
        self.assertEqual(len(self.problems(text)), 2)

    def test_コードフェンスの中の参照と見出しは数えない(self) -> None:
        fence = "```markdown\n## 9. 偽\ndevelop 7. に従う。\n```\n"
        self.assertEqual(self.problems(fence), [])
        self.write("skills/develop/SKILL.md", "## 6. 実装と点検のループ\n" + fence)
        problems = self.problems("develop 9. に従う。\n")
        self.assertAnyContains(problems, "develop 9. の節が無い")

    def test_回数の数字は参照として拾わない(self) -> None:
        self.assertEqual(self.problems("build 3 回で止める。\n", rel="skills/specify/SKILL.md"), [])
        problems = self.problems("build 3. に従う。\n", rel="skills/specify/SKILL.md")
        self.assertAnyContains(problems, "build 3. の節が無い")

    def test_過去の版を引く事例のファイルは検査しない(self) -> None:
        text = "develop 7. を直した。\n"
        self.assertEqual(self.problems(text, rel="skills/retro/references/example.md"), [])
        self.assertAnyContains(self.problems(text, rel="skills/retro/references/other.md"), "の節が無い")

    def test_後ろのドットの無い見出しと参照が一致する(self) -> None:
        self.assertEqual(self.problems("secure 2.1(信頼境界と入力検証)に従う。\n"), [])
        problems = self.problems("secure 2.1(入力検証)に従う。\n")
        self.assertAnyContains(problems, "見出し「信頼境界と入力検証」と違う")

    def test_UTF_8でないファイルは例外のまま止まる(self) -> None:
        (self.tmp / "skills/build/SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (self.tmp / "skills/build/SKILL.md").write_bytes("develop 6. に従う。\n".encode("cp932"))
        with self.assertRaises(UnicodeDecodeError):
            section_reference_problems(self.tmp)


if __name__ == "__main__":
    unittest.main()
