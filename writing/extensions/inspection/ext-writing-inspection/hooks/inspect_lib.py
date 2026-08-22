"""日本語 Markdown 検査 hook の共通処理(ext-writing-inspection)。

`inspect_write.py`(PostToolUse)と `inspect_stop.py`(Stop)が共有する、設定の読み込み・
検査対象の判定・lint.py の実行・検出の絞り込み・警告文の組み立て・セッション状態の
記録をまとめる。検査の実体は japanese-writing スキルの `scripts/lint.py`(導入先の
`.claude/skills/japanese-writing/scripts/lint.py`)であり、本ライブラリは検出器を持たない。

hook 自身は Python 3 標準ライブラリのみで動作する。lint.py の実行だけは uv に委ねる
(sudachipy 依存のため)。uv・lint.py・設定のいずれかが欠けている場合は検査を諦めて
許可側に倒す(hook 自身の不具合や環境差で書き込み・完了を止めない)。
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PATH_KEYS = ("file_path", "notebook_path", "path")
MARKDOWN_SUFFIXES = {".md", ".markdown"}
SEVERITY_ORDER = {"info": 0, "warn": 1, "critical": 2}
LINT_REL = ".claude/skills/japanese-writing/scripts/lint.py"
GENRES = {"essay", "tech", "business"}
# テストと利用側での差し替え用。設定するとコマンド(shlex 分割)が
# ["uv", "run", <lint.py>] の代わりに使われる。
LINT_CMD_ENV = "WRITING_INSPECTION_LINT_CMD"
OVERRIDE_REL = ".claude/ext-writing-inspection.config.json"
STATE_DIR_NAME = "claude-ext-writing-inspection"

_JAPANESE_RE = re.compile(r"[぀-ヿ㐀-鿿]")

DEFAULT_CONFIG: dict = {
    "min_japanese_chars": 30,
    "exclude": [],
    "lint_timeout_seconds": 120,
    "stop_max_blocks": 3,
    "max_findings_in_warning": 10,
    "blocking": [],
    "doctypes": [],
    "default_doctype": {"genre": None, "disabled_categories": [], "inspect": True},
}


# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_config(hook_dir: Path, project_dir: Path | None) -> dict:
    """バンドル同梱の設定に、利用側の上書き設定を浅いマージで重ねて返す。

    上書き設定(`.claude/ext-writing-inspection.config.json`)は利用側の資産であり、
    バンドルの再導入(スキルディレクトリの置換)で消えない場所に置く。
    """
    config = dict(DEFAULT_CONFIG)
    config.update(_load_json(hook_dir / "inspection.config.json"))
    if project_dir is not None:
        config.update(_load_json(project_dir / OVERRIDE_REL))
    return config


def project_dir(payload: dict) -> Path | None:
    """hook の実行対象プロジェクトのルート。環境変数を第一、入力の cwd を第二とする。"""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    cwd = payload.get("cwd")
    return Path(cwd) if isinstance(cwd, str) and cwd else None


# ---------------------------------------------------------------------------
# 検査対象の判定
# ---------------------------------------------------------------------------


def target_path(tool_input: dict, cwd: str | None) -> Path | None:
    """書き込み先のパス(絶対化済み)。取れなければ None。"""
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            path = Path(value)
            if not path.is_absolute() and cwd:
                path = Path(cwd) / path
            return path
    return None


def relative_to_project(path: Path, project: Path | None) -> str:
    """判定に使うプロジェクト相対パス(POSIX 形式)。外側のファイルは絶対パスのまま。"""
    if project is not None:
        try:
            return path.resolve().relative_to(project.resolve()).as_posix()
        except (OSError, ValueError):
            pass
    return path.as_posix()


def matches_any(rel: str, patterns: list) -> bool:
    return any(
        isinstance(pat, str) and fnmatch.fnmatch(rel, pat) for pat in patterns
    )


def japanese_char_count(text: str) -> int:
    return len(_JAPANESE_RE.findall(text))


def resolve_doctype(rel: str, config: dict) -> dict:
    """相対パスに最初に一致した文書種別を返す(一致しなければ default_doctype)。"""
    for doctype in config.get("doctypes", []):
        if isinstance(doctype, dict) and matches_any(rel, doctype.get("paths", [])):
            return doctype
    default = config.get("default_doctype")
    return default if isinstance(default, dict) else dict(DEFAULT_CONFIG["default_doctype"])


def should_inspect(path: Path, config: dict, project: Path | None) -> tuple[bool, dict]:
    """検査するかどうかと、適用する文書種別を返す。

    判定の順序: Markdown 拡張子 → 除外パターン → 文書種別の inspect フラグ →
    日本語文字数のしきい値。読めないファイル(未作成・バイナリ等)は検査しない。
    """
    no = (False, {})
    if path.suffix.lower() not in MARKDOWN_SUFFIXES:
        return no
    rel = relative_to_project(path, project)
    if matches_any(rel, config.get("exclude", [])):
        return no
    doctype = resolve_doctype(rel, config)
    if not doctype.get("inspect", True):
        return no
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return no
    if japanese_char_count(text) < int(config.get("min_japanese_chars", 30)):
        return no
    return True, doctype


# ---------------------------------------------------------------------------
# lint.py の実行
# ---------------------------------------------------------------------------


def lint_command(project: Path | None) -> list[str] | None:
    """lint.py を実行するコマンド。環境変数の差し替えを優先し、無ければ uv run とする。"""
    override = os.environ.get(LINT_CMD_ENV)
    if override:
        try:
            return shlex.split(override)
        except ValueError:
            return None
    if project is None:
        return None
    lint_py = project / LINT_REL
    if not lint_py.is_file():
        return None
    return ["uv", "run", str(lint_py)]


def run_lint(path: Path, genre: str | None, config: dict, project: Path | None) -> list[dict] | None:
    """lint.py を `--json` で実行して findings を返す。実行できなければ None(検査を諦める)。"""
    cmd = lint_command(project)
    if cmd is None:
        return None
    args = list(cmd) + [str(path), "--json"]
    if genre in GENRES:
        args += ["--genre", genre]
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=float(config.get("lint_timeout_seconds", 120)),
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if proc.returncode != 0:
        return None
    try:
        output = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    findings = output.get("findings")
    if not isinstance(findings, list):
        return None
    return [f for f in findings if isinstance(f, dict)]


def filter_findings(findings: list[dict], doctype: dict) -> list[dict]:
    """文書種別で無効化されたカテゴリを取り除く。"""
    disabled = set(doctype.get("disabled_categories", []))
    return [f for f in findings if f.get("category") not in disabled]


def blocking_findings(findings: list[dict], config: dict) -> list[dict]:
    """重大カテゴリの宣言(config の blocking)に該当する検出だけを返す。"""
    rules = {}
    for rule in config.get("blocking", []):
        if isinstance(rule, dict) and isinstance(rule.get("category"), str):
            rules[rule["category"]] = SEVERITY_ORDER.get(rule.get("min_severity", "warn"), 1)
    matched = []
    for f in findings:
        threshold = rules.get(f.get("category"))
        if threshold is None:
            continue
        if SEVERITY_ORDER.get(f.get("severity", "info"), 0) >= threshold:
            matched.append(f)
    return matched


# ---------------------------------------------------------------------------
# 警告文の組み立て
# ---------------------------------------------------------------------------


def load_guides(hook_dir: Path) -> dict:
    guides = _load_json(hook_dir / "rewrite_guides.json")
    return guides if isinstance(guides, dict) else {}


def sort_findings(findings: list[dict]) -> list[dict]:
    return sorted(
        findings,
        key=lambda f: (
            -SEVERITY_ORDER.get(f.get("severity", "info"), 0),
            f.get("line", 0),
        ),
    )


def _finding_line(f: dict) -> str:
    severity = f.get("severity", "info")
    excerpt = str(f.get("excerpt", "")).strip()
    return f"- L{f.get('line', '?')} [{severity}] {f.get('category', '?')}: {excerpt}"


def _guide_lines(categories: list[str], guides: dict) -> list[str]:
    lines = []
    for cat in categories:
        guide = guides.get(cat)
        if not isinstance(guide, dict):
            continue
        line = f"- {cat}: {guide.get('instruction', '')}"
        example = guide.get("example")
        if isinstance(example, dict) and example.get("before"):
            line += f" 例:「{example['before']}」→「{example['after']}」"
        lines.append(line)
    return lines


def format_warning(
    path: Path, findings: list[dict], config: dict, guides: dict, blocking: list[dict]
) -> str:
    """PostToolUse でエージェントへ返す警告文。

    語の置換でなく文単位の書き直しを求め、カテゴリごとの言い換え指針を同梱する。
    機械検出に出ない不自然さの判定(LLM 判定)もここで指示する。
    """
    ordered = sort_findings(findings)
    limit = int(config.get("max_findings_in_warning", 10))
    shown = ordered[:limit]
    lines = [
        f"japanese-writing 検査: {path} に {len(findings)} 件の検出。",
        "検出箇所を含む文を丸ごと書き直すこと。指摘された語だけを類語に置き換えて済ませない"
        "(文の構造ごと組み替える)。",
        "",
        "検出:",
    ]
    lines += [_finding_line(f) for f in shown]
    if len(ordered) > limit:
        lines.append(f"- ほか {len(ordered) - limit} 件(全件は lint.py の再実行で確認する)")
    categories = list(dict.fromkeys(f.get("category", "") for f in shown))
    guide_lines = _guide_lines(categories, guides)
    if guide_lines:
        lines += ["", "書き直しの指針(カテゴリ別):"]
        lines += guide_lines
    lines += [
        "",
        "機械検出は表層しか見ない。書き直しの際は該当段落を読み直し、検出に出ない不自然さ"
        "(文脈のねじれ・冗長・常体と敬体の混在・意味の薄い強調)も自分で判定して直すこと。"
        "規範は導入先の .claude/skills/japanese-writing/references/(sentence.md 7.〜8. ほか)にある。",
    ]
    if blocking:
        lines.append(
            f"このうち {len(blocking)} 件は重大カテゴリであり、解消するまでセッションの完了がブロックされる。"
        )
    return "\n".join(lines)


def format_stop_reason(remaining: dict[str, list[dict]], guides: dict) -> str:
    """Stop でエージェントへ返すブロック理由。ファイルごとの重大検出を列挙する。"""
    lines = [
        "japanese-writing 検査: 重大カテゴリの検出が残っているため完了できない。"
        "以下の各箇所について、検出箇所を含む文を丸ごと書き直してから完了すること。",
        "",
    ]
    categories: list[str] = []
    for file, findings in remaining.items():
        lines.append(f"{file}:")
        lines += [_finding_line(f) for f in sort_findings(findings)]
        for f in findings:
            cat = f.get("category", "")
            if cat not in categories:
                categories.append(cat)
    guide_lines = _guide_lines(categories, guides)
    if guide_lines:
        lines += ["", "書き直しの指針(カテゴリ別):"]
        lines += guide_lines
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# セッション状態(Stop での再検査対象)
# ---------------------------------------------------------------------------


def state_path(project: Path | None, session_id: str) -> Path:
    """セッションごとの状態ファイル。プロジェクトとセッション ID の組で分ける。"""
    digest = hashlib.sha1(str(project or "").encode("utf-8")).hexdigest()[:12]
    safe_session = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")
    return Path(tempfile.gettempdir()) / STATE_DIR_NAME / f"{digest}-{safe_session}.json"


def load_state(path: Path) -> dict:
    state = _load_json(path)
    files = state.get("files")
    return {
        "files": [f for f in files if isinstance(f, str)] if isinstance(files, list) else [],
        "stop_blocks": int(state.get("stop_blocks", 0) or 0),
    }


def save_state(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except OSError:
        pass


def record_inspected(path: Path, project: Path | None, session_id: str) -> None:
    state_file = state_path(project, session_id)
    state = load_state(state_file)
    abs_path = str(path.resolve())
    if abs_path not in state["files"]:
        state["files"].append(abs_path)
        save_state(state_file, state)


def emit(decision: dict) -> None:
    """hook の JSON 出力(decision: block / reason)を書き出す。"""
    json.dump(decision, sys.stdout, ensure_ascii=False)
