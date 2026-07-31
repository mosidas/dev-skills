#!/usr/bin/env python3
"""スキル群自体の機械的整合検査(read-only)。

スキル群自体を構成するドキュメント(用途グループの `skills/`・`agents/`・`.claude/` 群・
`.meta/`・`ports/`・README 等)を規約に照らして決定論的に検査する。ファイルを一切書き換え
ない。意味的な判断(内容の妥当性・観点レビュー)は meta-review に委ねる。設計原則の正本は
`../references/principles.md`、観点カタログは `../references/doc-perspectives.md`。

検査項目(doc-perspectives.md §3 横断観点のうち機械化できるもの + principles.md §4 依存規律):
  参照実在     SKILL・reference・template 間の相対パス参照(../ ./ で md/py/json を指す)が実在する
  frontmatter  スキル・エージェントの name が配置(ディレクトリ名・ファイル名)と一致し、description がある
               (解析は meta_lib の YAML サブセット。サブセット外の記法は warning で区別して報告する)
  inject 実在  port frontmatter の inject 先スキル名が実在する
  依存規律     配布するスキル・エージェントの本文が meta-* を参照していない(一方向依存)
  状態整合     workflow.json の状態名が、同じ部品の SKILL.md に記述されている(取り違え・陳腐化の検出)
  部品名実在   スキル群の本文が参照する dev-*/flow-*/meta-* の部品・エージェント名が実在する
  未記入       未記入マーカーが残っていない(インラインコード・コードブロック・URL は除く)

重大度:
  error   機械的に確実な規約違反(exit code 1)
  warning ヒューリスティックな指摘。最終判断は人間/meta-review が行う

回帰検出:
  --baseline に編集前の `--json` 出力を渡すと、今回新規に増えた指摘を NEW として印す。
  編集で悪化していないことを採用前に確認するために使う。

使い方:
  meta_check.py [--root <dev-skills のルート>] [--baseline <前回の JSON>] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import meta_lib  # noqa: E402

# 相対パス参照(../ か ./ で始まり md/py/json で終わる)。前が単語構成文字・< のときは除外
# (`<dev のパス>/install.py` のようなプレースホルダや語中の誤検出を避ける)。
REF_RE = re.compile(r"(?<![\w<.])(\.\.?/[\w./-]+\.(?:md|py|json))")
# バッククォートで囲まれた kebab-case トークン。
BACKTICK_TOKEN_RE = re.compile(r"`([a-z][a-z0-9-]*)`")
# 状態名らしいトークン(状態機械の命名規約: <名詞>-<過去分詞/進行>)。
STATE_LIKE_SUFFIX = ("-generated", "-approved", "-ing", "-initialized")
# 部品・エージェント名らしいトークン。
PART_TOKEN_RE = re.compile(r"\b((?:dev|flow|meta|ext)-[a-z][a-z0-9-]*)\b")
# 部品名検査の除外(リポジトリ名)。
PART_EXCLUDE = {"dev-skills"}
META_REF_RE = re.compile(r"\bmeta-(?:core|check|doc|review)\b")
# 未記入マーカー。前後が ASCII 英数のときは別語(TODOS 等)として除外し、
# 日本語に隣接する場合(「未記入TODOです」)は検出する。
PLACEHOLDER_RE = re.compile(r"(?<![A-Za-z0-9])(TODO|FIXME|TBD|XXX)(?![A-Za-z0-9])")
# 検出から除く範囲: インラインコード(規約の引用)・URL。
INLINE_CODE_RE = re.compile(r"`[^`]*`")
URL_RE = re.compile(r"https?://\S+")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")


class Report:
    def __init__(self) -> None:
        self.findings: list[dict] = []

    def add(self, severity: str, message: str) -> None:
        self.findings.append({"severity": severity, "message": message})

    def error(self, message: str) -> None:
        self.add("error", message)

    def warning(self, message: str) -> None:
        self.add("warning", message)

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f["severity"] == severity)


def die(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def load_baseline(path: Path) -> set[tuple[str, str]]:
    """前回の JSON 出力から (重大度, メッセージ) の集合を作る。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        die(f"--baseline の読み込みに失敗: {path}: {e}")
        raise AssertionError  # die は返らない
    findings = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(findings, list):
        die(f"--baseline の形式が meta_check.py --json の出力でない: {path}")
    return {
        (f.get("severity", ""), f.get("message", ""))
        for f in findings
        if isinstance(f, dict)
    }


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def iter_lines(text: str):
    return enumerate(text.splitlines(), start=1)


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# 走査対象の収集


def skill_names(root: Path) -> set[str]:
    return {p.name for p in meta_lib.skill_dirs(root)}


def agent_names(root: Path) -> set[str]:
    return {p.stem for p in meta_lib.agent_files(root)}


def all_docs(root: Path) -> list[Path]:
    """参照実在検査の対象(スキル群・`.meta`・`ports`・`extensions`・`tests`・ルート直下の md)。"""
    docs: list[Path] = list(meta_lib.group_docs(root))
    for sub in (".meta", "ports", "extensions", "tests"):
        d = root / sub
        if d.is_dir():
            docs.extend(p for p in d.rglob("*.md") if p.is_file())
    docs.extend(p for p in root.glob("*.md") if p.is_file())
    return sorted(set(docs))


# ---------------------------------------------------------------------------
# 検査


def check_references(root: Path, report: Report) -> None:
    """相対パス参照が実在するか。

    ルート内を指す参照は実在必須(error)。ルート外へ抜ける参照(前身プロジェクト等への
    外部引用)は検証できないため warning に留める。ルート内外の判定は解決済みのパス同士で
    行う(呼び出し側が未解決のルートを渡してもルート内の参照を外部と誤判定しない)。
    """
    base = root.resolve()
    for path in all_docs(root):
        text = read_text(path)
        if text is None:
            continue
        for line_no, line in iter_lines(text):
            for token in REF_RE.findall(line):
                target = (path.parent / token).resolve()
                if target.exists():
                    continue
                if target.is_relative_to(base):
                    report.error(
                        f"{rel(root, path)}:{line_no} の参照先が存在しない: {token}"
                    )
                else:
                    report.warning(
                        f"{rel(root, path)}:{line_no} の外部参照が検証できない"
                        f"(ルート外): {token}"
                    )


def _parse_inject(text: str) -> list[str]:
    """frontmatter の inject リストを返す(解析は meta_lib のサブセット)。"""
    parsed = meta_lib.parse_frontmatter(text)
    if parsed is None:
        return []
    value = parsed[0].get("inject")
    return list(value) if isinstance(value, list) else []


def check_inject_targets(root: Path, skills: set[str], report: Report) -> None:
    """port frontmatter の inject 先スキルが実在するか。

    `ports/templates/` は新規 port の雛形でプレースホルダを持つため対象外にする。
    """
    ports_dir = root / "ports"
    if not ports_dir.is_dir():
        return
    for path in sorted(ports_dir.rglob("*.md")):
        if "templates" in path.relative_to(ports_dir).parts:
            continue
        text = read_text(path)
        if text is None:
            continue
        for name in _parse_inject(text):
            if name not in skills:
                report.error(
                    f"{rel(root, path)} の inject 先スキルが存在しない: {name}"
                )


def check_dependency_discipline(root: Path, report: Report) -> None:
    """配布するスキルの本文が meta-* を参照していないか(principles.md §4)。

    対象は配布グループのスキルとエージェントすべてとする(名前のプレフィックスで
    選ばない。プレフィックスを持たないスキルも配布する以上、同じ一方向依存を要求する)。
    """
    targets: list[Path] = []
    for skill in meta_lib.distributed_skill_dirs(root):
        # dev-core も含む(Layer 0 の汎用正本にも同じ一方向依存を要求する)。
        targets.extend(p for p in skill.rglob("*.md") if p.is_file())
    targets.extend(meta_lib.agent_files(root))
    for path in sorted(set(targets)):
        text = read_text(path)
        if text is None:
            continue
        for line_no, line in iter_lines(text):
            if META_REF_RE.search(line):
                report.error(
                    f"{rel(root, path)}:{line_no} が meta-* を参照している"
                    "(依存規律違反: 配布するスキルは meta-* を参照しない)"
                )


def check_state_consistency(root: Path, report: Report) -> None:
    """workflow.json の状態名と、同じ部品 SKILL.md の記述の整合。"""
    workflows = sorted(
        (wf for skill in meta_lib.skill_dirs(root) for wf in skill.glob("workflow.json")),
        key=lambda p: p.parent.name,
    )
    for wf in workflows:
        try:
            defn = json.loads(wf.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            report.error(f"{rel(root, wf)} の読み込みに失敗: {e}")
            continue
        states = set(defn.get("states", []))
        skill_md = wf.parent / "SKILL.md"
        text = read_text(skill_md)
        if text is None:
            report.warning(f"{rel(root, wf.parent)} に SKILL.md が無い")
            continue
        # 定義された状態が SKILL.md で言及されているか(陳腐化の検出)。
        for state in sorted(states):
            if state not in text:
                report.warning(
                    f"{rel(root, skill_md)} に workflow.json の状態 {state!r} の記述が無い"
                )
        # SKILL.md の状態名らしいトークンが定義に存在するか(取り違えの検出)。
        mentioned = {
            t
            for t in BACKTICK_TOKEN_RE.findall(text)
            if t.endswith(STATE_LIKE_SUFFIX)
        }
        for token in sorted(mentioned - states):
            report.warning(
                f"{rel(root, skill_md)} の状態名 `{token}` が workflow.json に無い"
                "(取り違え・改名漏れの疑い)"
            )


def check_frontmatter(root: Path, report: Report) -> None:
    """スキル・エージェントの frontmatter の必須項目と、name と配置の一致を検査する。

    name が配置(スキルはディレクトリ名、エージェントはファイル名)と食い違うと、
    Skill / Task ツールからの起動が解決できない。Agent Skills 標準も一致を要求する。
    解析は YAML のサブセット(`meta_lib`)で行い、サブセット外の記法は「一致しない」
    と断定せず、解析できない記法として別に報告する。
    """
    targets: list[tuple[Path, str]] = [
        (skill / "SKILL.md", skill.name)
        for skill in meta_lib.skill_dirs(root)
        if (skill / "SKILL.md").is_file()
    ]
    targets.extend((p, p.stem) for p in meta_lib.agent_files(root))

    for path, expected in targets:
        text = read_text(path)
        if text is None:
            continue
        parsed = meta_lib.parse_frontmatter(text)
        if parsed is None:
            report.error(
                f"{rel(root, path)} に frontmatter が無い(閉じの --- も含めて確認する)"
            )
            continue
        data, unparsable = parsed
        for raw in unparsable:
            report.warning(
                f"{rel(root, path)} の frontmatter に解析できない記法がある"
                f"(この検査は YAML のサブセットのみを解釈する): {raw.strip()}"
            )
        if "name" not in data:
            report.error(f"{rel(root, path)} の frontmatter に name が無い")
        else:
            name = meta_lib.scalar(data, "name")
            if name is None:
                report.error(
                    f"{rel(root, path)} の frontmatter の name がスカラーでない"
                )
            elif name != expected:
                report.error(
                    f"{rel(root, path)} の name {name!r} が配置 {expected!r} と一致しない"
                    "(起動時に解決できない)"
                )
        if not (meta_lib.scalar(data, "description") or "").strip():
            report.error(f"{rel(root, path)} の frontmatter に description が無い")


def check_placeholders(root: Path, report: Report) -> None:
    """未記入マーカーが残っていないか。

    マーカー名を説明する記述と区別するため、インラインコード・コードブロック・
    URL は対象から除く。日本語に隣接するマーカー(「未記入TODOです」)は検出する。
    """
    for path in all_docs(root):
        text = read_text(path)
        if text is None:
            continue
        in_fence = False
        for line_no, line in iter_lines(text):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            stripped = URL_RE.sub("", INLINE_CODE_RE.sub("", line))
            for token in PLACEHOLDER_RE.findall(stripped):
                report.warning(
                    f"{rel(root, path)}:{line_no} に未記入マーカー {token} が残っている"
                )


def check_part_names(root: Path, skills: set[str], agents: set[str], report: Report) -> None:
    """スキル群の本文が参照する部品・エージェント名が実在するか。"""
    known = skills | agents | PART_EXCLUDE
    for path in meta_lib.group_docs(root):
        text = read_text(path)
        if text is None:
            continue
        for line_no, line in iter_lines(text):
            for token in PART_TOKEN_RE.findall(line):
                if token in known:
                    continue
                report.warning(
                    f"{rel(root, path)}:{line_no} が参照する部品/エージェント名が実在しない: {token}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="スキル群自体の機械的整合検査(read-only)")
    parser.add_argument(
        "--root", help="dev-skills のルート(既定: スキルのグループを上方向に探索)"
    )
    parser.add_argument(
        "--baseline",
        help="編集前に取得した JSON 出力。今回新規に増えた指摘を NEW として印す(回帰検出)",
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

    skills = skill_names(root)
    agents = agent_names(root)

    report = Report()
    check_references(root, report)
    check_frontmatter(root, report)
    check_inject_targets(root, skills, report)
    check_dependency_discipline(root, report)
    check_state_consistency(root, report)
    check_part_names(root, skills, agents, report)
    check_placeholders(root, report)

    baseline = load_baseline(Path(args.baseline)) if args.baseline else None
    if baseline is not None:
        for f in report.findings:
            f["new"] = (f["severity"], f["message"]) not in baseline

    errors, warnings = report.count("error"), report.count("warning")
    new_count = sum(1 for f in report.findings if f.get("new"))
    if args.json:
        payload = {"errors": errors, "warnings": warnings, "findings": report.findings}
        if baseline is not None:
            payload["new"] = new_count
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        icons = {"error": "🔴", "warning": "🟡"}
        for f in report.findings:
            mark = "NEW " if f.get("new") else ""
            print(f"{mark}{icons.get(f['severity'], '🔵')} {f['severity']}: {f['message']}")
        summary = f"結果: error {errors} 件 / warning {warnings} 件"
        if baseline is not None:
            summary += f"(うち基準から新規 {new_count} 件)"
        print(summary)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
