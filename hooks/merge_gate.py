#!/usr/bin/env python3
"""gate-reviewer の判定を `${CLAUDE_PLUGIN_DATA}/merge-gate/` に記録し、gh pr merge を記録と照合する hook。

入口:
  PostToolUse(SubagentHandback)  記録。auto モード。報告は `tool_input.message` にある
  SubagentStop                     記録。default モード。報告は `last_assistant_message` にある
  PreToolUse(Bash)                 照合。`tool_input.command` の gh pr merge を `cwd`(コマンドの cd を追った先)と
                                   gh の前に書いた GH_REPO・GH_HOST・GIT_DIR・GIT_WORK_TREE の代入で照合する。
                                   照合するのは github.com の PR だけである
  記録はどちらも `agent_type` が `dev-skills:gate-reviewer` のときだけ読む。

入出力の契約:
  標準入力  UTF-8 の hook の JSON。環境の符号化に依らず UTF-8 のバイト列として読む
  exit 0    常に
  標準出力  照合で止めるか確認を求めるときだけ `permissionDecision`(deny / ask)の ASCII の JSON を 1 つ書く。
            記録と、照合で通すときは書かない
  標準エラー 書かない

報告の「## 判定」の区間の最初の行 `<マージ可 / 差し戻し> <head の SHA>` と、`- リポジトリ: <絶対パス>`・
`- PR 本文案: <絶対パス>` の行を読む。判定の語・SHA・パスの前後の `` ` `` と `**` は外してから読む。マージ可なら、作業ツリーの HEAD が判定の SHA と一致し、origin が
host/owner/name に直せて、本文案が読めるときだけ (リポジトリ, head) をキーに記録を書く。差し戻しなら同じ
キーの記録を消す。判定の区間が無い報告は何もしない。結果は `events.jsonl` に 1 イベント 1 行で追記する。
ログに本文・報告の中身・origin の URL を書かない。

記録のディレクトリはリンクでない自分所有の実際のディレクトリに限り、記録はリンクをたどらずに読み書きする。
ディレクトリを使えないときは、ログも同じディレクトリにあるため何も残せない。

照合は `gh pr view` で PR の head・本文・コミットを取り、(リポジトリ, head) の記録の本文のハッシュが一致すれば
通す。本文が違えば止める。head に記録が無く古いコミットに記録があれば、記録の作業ツリーの git で、記録の head から
今の head までが origin の base を競合なしで取り込んだマージコミットだけかを確かめる。取り込みだけなら本文のハッシュで
通すか止め、そうでなければゲートの後にコミットを足したとして止め、確かめられなければその旨を足して止める。
git は置き換え(git replace)を読まずに走らせる。
どれにも無ければ本人に確認を求める。PR を特定できない・取得できない・コマンドの読み取りや照合が途中で失敗したときも確認を求める。
-R・PR の URL・GH_REPO・GH_HOST(代入か hook の環境)の host が github.com でなければ、gh pr view を走らせずに確認を求める。
gh pr view は許可の判定の前に走り、その host へ gh の認証情報を送るためである。シェルか起動役(sh・eval・xargs・sudo など)を
先頭に書いた単純コマンドがあれば、渡した中身を読まずに確認を求める。
1 つのコマンドに複数のマージがあれば、止める > 確認 > 通すの強いほうにする。照合ごとに `events.jsonl` に
`merge_checked` を 1 行残し、確認を求めた理由の下位の分類と、main の取り込みを確かめたときの段を `detail`
(gh と git の非 0 の終了は `exit_code` も)に載せる。

脅威の範囲: この hook が止めるのは、ゲートの後の変更で判定の取り直しを省くことである。偽造(記録のファイルを
直接書く・手元の追跡 ref を書き換える・hook を避けるために組んだコマンド)は範囲の外とする。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator, Literal

GATE_AGENT = "dev-skills:gate-reviewer"
RECORD_LIMIT = 4 * 1024
# GitHub の PR 本文の上限 65,536 字 × 1 字 4 バイト
BODY_LIMIT = 256 * 1024
# shortcut: 仮に 5 秒(2 回の git が hooks.json の timeout 20 秒に収まる値), rev-parse と remote get-url の p99.9 を実測したら置き換える
GIT_TIMEOUT = 5
# `git rev-parse --local-env-vars` の一覧(git 2.55)。hook の環境にあると -C の先でなくその値のリポジトリを読む
GIT_LOCAL_ENV = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
    "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE", "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE", "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX", "GIT_SHALLOW_FILE",
    "GIT_COMMON_DIR",
}
# shortcut: main の取り込みは 20 回まで確かめる(1 回に git を 3 回), 長い PR で too_many_merges が続いたら引き上げる
MERGE_LIMIT = 20
MAIN_MERGE_ONLY = "main_merge_only"
BASE_REF = re.compile(r"(?!-)(?!.*\.\.)[A-Za-z0-9._/-]+")
# 全体の期限 30 秒は hooks.json の timeout 40 秒より短く、gh pr view の上限 15 秒は実測 0.4〜0.7 秒の約 20 倍
CHECK_DEADLINE = 30
GH_TIMEOUT = 15
ATTRIBUTION = re.compile(r"(?:🤖 ?)?Generated with \[Claude Code\]\(https://(?:claude\.com/claude-code|claude\.ai/code)\)")
VIEW_FIELDS = "headRefOid,body,url,baseRefName,commits"
GITHUB = "github.com"

HEADING = re.compile(r"^#{1,6}\s")
VERDICTS = {"マージ可": True, "差し戻し": False}
SHA = re.compile(r"[0-9a-f]{40}")
MARKUP = re.compile(r"^(?:`|\*\*)+|(?:`|\*\*)+$")
REPO_LINE = re.compile(r"^- リポジトリ:\s*(.+)$")
BODY_LINE = re.compile(r"^- PR 本文案:\s*(.+)$")
SCP_REMOTE = re.compile(r"^[^@/:]+@([^/:]+):(.+)$")
URL_REMOTE = re.compile(r"^(?:https|ssh|git)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$")
SLUG = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
DIGEST = re.compile(r"[0-9a-f]{64}")
PR_URL = re.compile(r"(https://[A-Za-z0-9.-]+/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+))/pull/([0-9]+)")
SELECTOR = re.compile(rf"[0-9]+|{PR_URL.pattern}|[A-Za-z0-9._/-]+")
REPO_FLAG = re.compile(r"(?:[A-Za-z0-9.-]+/)?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.S)
MERGE_HINT = re.compile(r"\bgh\b.*\bpr\b.*\bmerge\b")
OPERATOR_CHARS = ";&|()<>\n"
SEPARATORS = " \t\r" + OPERATOR_CHARS
OPERATORS = ("<<<", "<<-", "&&", "||", "|&", "&>", ">>", ">&", "<&", ">|", "<>", "<<")
HEREDOCS = ("<<", "<<-")
# 単純コマンドの先頭で剥がす語。OPENERS は複合コマンドを始め、RUNNERS は後ろのコマンドを起動する
OPENERS = {"{", "if", "while", "until", "for", "case", "select"}
KEYWORDS = {"!", "then", "do", "else", "elif"}
# builtin は bash と zsh の、noglob は zsh の前置き
RUNNERS = {"time", "command", "nohup", "exec", "env", "timeout", "noglob", "builtin"}
# 渡した文字列・標準入力・引数をコマンドとして走らせる。先頭にあればそのコマンドのマージを読まずに確認を求める
LAUNCHERS = {
    "sh", "bash", "zsh", "dash", "ksh", "fish", "eval", "source", ".",
    "sudo", "doas", "su", "xargs", "nice", "watch", "parallel",
}
DURATION = re.compile(r"[0-9]+(?:\.[0-9]+)?[smhd]?")
CD = ("cd", "pushd", "popd")
# gh pr view が照合する PR を変える環境変数。前置きの代入のうちこれだけを照合に渡す
REPO_ENV = {"GH_REPO", "GH_HOST", "GIT_DIR", "GIT_WORK_TREE"}
ENV_COMMANDS = {"export", "declare", "typeset", "unset", "local", "readonly"}
UNTRACKED_PATH = re.compile(r"^-|[$~`]")
FD = re.compile(r"[0-9]+")
VALUE_FLAGS = {"--author-email", "--body", "--body-file", "--subject", "--match-head-commit", "--repo"}
SHORT_VALUE_FLAGS = "AbFtR"

COMMITS_AFTER_GATE = (
    "ゲートの判定({gated})の後に head が {head} へ進んだ。{note}{gated}..{head} のコミットと PR 本文の差分を"
    " gate-reviewer に渡して判定を取り直してから、実行し直す(develop 8.)。"
)
MERGE_UNVERIFIED = "main の取り込みだけと確かめられなかった。"
BODY_CHANGED = (
    "ゲートの判定の後に PR 本文が変わった。ゲートに渡した本文案のファイルと `gh pr view {number} --json body` の差分を"
    " gate-reviewer に渡して判定を取り直してから、実行し直す(develop 8.)。"
)
NO_RECORD = "{slug}#{number} の今の head には、gate-reviewer の判定の記録がありません。このままマージしてよいか確認してください。"
UNRESOLVED = (
    "マージする PR を特定できないため、ゲートの記録と照合できませんでした。このままマージしてよいか確認してください。"
)
VIEW_FAILED = (
    "GitHub から PR の head と本文を取得できなかったため、ゲートの記録と照合できませんでした。"
    "このままマージしてよいか確認してください。"
)
INTERNAL_ERROR = "ゲートの記録との照合が途中で失敗しました({name})。このままマージしてよいか確認してください。"


@dataclass(frozen=True)
class GateRecord:
    repo: str
    head: str
    body_sha256: str
    repo_path: str
    recorded_at: str


@dataclass(frozen=True)
class Verdict:
    approved: bool
    head: str
    repo_path: Path
    body_path: Path | None


@dataclass(frozen=True)
class Target:
    """gh pr merge の 1 つ。`selector` は PR の指定、`repo` は -R、`env` は gh の前に書いた代入、
    `cwd` は cd を追った作業ディレクトリ。"""

    selector: str | None
    repo: str | None
    env: dict[str, str]
    cwd: str | None


@dataclass(frozen=True)
class Unresolved:
    """PR を特定できない gh pr merge。`detail` は events.jsonl の detail にそのまま載る。"""

    detail: str


@dataclass(frozen=True)
class PullRequest:
    repo: str
    slug: str
    number: str
    url: str
    head: str
    body: str
    base: str
    commits: tuple[str, ...]


@dataclass(frozen=True)
class Outcome:
    decision: Literal["pass", "ask", "deny"]
    kind: str
    reason: str | None = None
    pr: PullRequest | None = None
    error_type: str | None = None
    detail: str | None = None
    exit_code: int | None = None

    @property
    def level(self) -> str:
        if self.kind == "internal_error":
            return "error"
        return "info" if self.decision == "pass" else "warn"


class ViewFailed(Exception):
    """gh pr view で PR を取れなかった理由。`kind`・`detail`・`exit_code` は events.jsonl に同じ名前で載る。"""

    def __init__(self, kind: str, detail: str | None = None, exit_code: int | None = None) -> None:
        super().__init__(kind)
        self.kind, self.detail, self.exit_code = kind, detail, exit_code


class MergeUnverified(Exception):
    """記録の head から今の head までを git で確かめられなかった段。`detail`・`exit_code` は events.jsonl に同じ名前で載る。"""

    def __init__(self, detail: str, exit_code: int | None = None) -> None:
        super().__init__(detail)
        self.detail, self.exit_code = detail, exit_code


class RecordUnreadable(Exception):
    """記録のファイルが 4 KiB を超える・JSON でない・フィールドの形が違う。"""


class NotRecorded(Exception):
    """記録しなかった理由。`reason` は events.jsonl の reason にそのまま載る。"""

    def __init__(self, reason: str, repo: str | None = None, head: str | None = None) -> None:
        super().__init__(reason)
        self.reason, self.repo, self.head = reason, repo, head


def report_text(payload: object) -> str | None:
    """gate-reviewer の報告の本文を返す。対象外の入力なら None。"""
    if not isinstance(payload, dict) or payload.get("agent_type") != GATE_AGENT:
        return None
    event = payload.get("hook_event_name")
    if event == "PostToolUse" and payload.get("tool_name") == "SubagentHandback":
        tool_input = payload.get("tool_input")
        text = tool_input.get("message") if isinstance(tool_input, dict) else None
    elif event == "SubagentStop":
        # auto モードの SubagentStop には報告が入らない(キーが無いか null)
        text = payload.get("last_assistant_message")
    else:
        return None
    return text if isinstance(text, str) else None


def verdict_section(text: str) -> list[str] | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.rstrip() == "## 判定":
            section = []
            for rest in lines[i + 1 :]:
                if HEADING.match(rest):
                    break
                section.append(rest.strip())
            return [line for line in section if line]
    return None


def unwrap(value: str) -> str:
    return MARKUP.sub("", value.strip()).strip()


def parse_verdict(section: list[str]) -> Verdict:
    """「## 判定」の区間の行を読む。形が違えば NotRecorded を送出する。"""
    words = [unwrap(word) for word in section[0].split()] if section else []
    if len(words) != 2 or words[0] not in VERDICTS or not SHA.fullmatch(words[1]):
        raise NotRecorded("verdict_malformed")
    repo_path = body_path = None
    for line in section[1:]:
        if m := REPO_LINE.match(line):
            repo_path = Path(unwrap(m.group(1)))
        elif m := BODY_LINE.match(line):
            body_path = Path(unwrap(m.group(1)))
    if repo_path is None or not repo_path.is_absolute():
        raise NotRecorded("verdict_malformed")
    return Verdict(VERDICTS[words[0]], words[1], repo_path, body_path)


def repo_key(url: str) -> str | None:
    """origin の URL(ssh・https)を小文字の host/owner/name にする。直せなければ None。"""
    m = SCP_REMOTE.match(url) or URL_REMOTE.match(url)
    slug = SLUG.match(m.group(2)) if m else None
    if slug is None:
        return None
    return f"{m.group(1)}/{slug.group(1)}/{slug.group(2)}".lower()


def run_git(repo_path: Path, *args: str, timeout: float = GIT_TIMEOUT) -> subprocess.CompletedProcess[str]:
    """repo_path で git を走らせる。起動の失敗(OSError・ValueError)と時間切れはそのまま送出する。"""
    env = {key: value for key, value in os.environ.items() if key not in GIT_LOCAL_ENV}
    return subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        env=env,
    )


def git(repo_path: Path, *args: str) -> str | None:
    try:
        proc = run_git(repo_path, *args)
    # ValueError: パスの NUL・対になっていないサロゲート、出力の復号の失敗
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def body_digest(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    kept = "\n".join(line for line in lines if not ATTRIBUTION.fullmatch(line)).strip("\n")
    return hashlib.sha256(kept.encode("utf-8", "surrogatepass")).hexdigest()


def read_body(path: Path) -> str | None:
    """本文案を読む。通常のファイルで BODY_LIMIT 以下の UTF-8 でなければ None を返す。"""
    try:
        # O_NONBLOCK: 名前付きパイプを開いても書き手を待たない
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    # ValueError: パスの NUL・対になっていないサロゲート
    except (OSError, ValueError):
        return None
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        return None
    try:
        with os.fdopen(fd, "rb") as f:
            data = f.read(BODY_LIMIT + 1)
    except OSError:
        return None
    if len(data) > BODY_LIMIT:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def owned_dir(path: Path) -> bool:
    """path がリンクでない実際のディレクトリで、この利用者が所有するときだけ True。"""
    st = os.lstat(path)
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid()


def open_store(data: str) -> Path | None:
    store = Path(data) / "merge-gate"
    try:
        store.mkdir(mode=0o700, parents=True, exist_ok=True)
        return store if owned_dir(store) else None
    except OSError:
        return None


def record_path(store: Path, repo: str, head: str) -> Path:
    return store / (hashlib.sha256((repo + "\n" + head).encode()).hexdigest() + ".json")


def refuse_link(path: Path, repo: str, head: str) -> None:
    """記録のパスに通常のファイル以外(リンクなど)があれば NotRecorded を送出する。"""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    except OSError:
        raise NotRecorded("store_write_failed", repo, head) from None
    if not stat.S_ISREG(st.st_mode):
        raise NotRecorded("store_write_failed", repo, head)


def read_record(path: Path) -> GateRecord | None:
    """記録を読む。無ければ None を返し、読めないか壊れていれば RecordUnreadable を送出する。"""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        raise RecordUnreadable from None
    try:
        with os.fdopen(fd, "rb") as f:
            data = f.read(RECORD_LIMIT + 1)
        value = json.loads(data.decode("ascii"))
    except (OSError, ValueError):
        raise RecordUnreadable from None
    names = {field.name for field in fields(GateRecord)}
    if (
        len(data) > RECORD_LIMIT
        or not isinstance(value, dict)
        or set(value) != names
        or not all(isinstance(v, str) for v in value.values())
    ):
        raise RecordUnreadable
    record = GateRecord(**value)
    if not SHA.fullmatch(record.head) or not DIGEST.fullmatch(record.body_sha256):
        raise RecordUnreadable
    return record


def write_record(path: Path, record: GateRecord) -> None:
    data = json.dumps(asdict(record), ensure_ascii=True).encode("ascii")
    if len(data) > RECORD_LIMIT:
        raise NotRecorded("store_write_failed", record.repo, record.head)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise NotRecorded("store_write_failed", record.repo, record.head) from None


def apply_verdict(store: Path, verdict: Verdict) -> tuple[str, str]:
    """判定を記録に反映し、(event, repo) を返す。記録しないときは NotRecorded を送出する。"""
    origin = git(verdict.repo_path, "remote", "get-url", "origin")
    repo = repo_key(origin) if origin else None
    if repo is None:
        raise NotRecorded("repo_unresolved", None, verdict.head)
    path = record_path(store, repo, verdict.head)
    refuse_link(path, repo, verdict.head)
    if not verdict.approved:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            raise NotRecorded("store_write_failed", repo, verdict.head) from None
        return "gate_record_removed", repo
    current = git(verdict.repo_path, "rev-parse", "HEAD")
    if current is None:
        raise NotRecorded("repo_unresolved", repo, verdict.head)
    if current != verdict.head:
        raise NotRecorded("head_moved", repo, verdict.head)
    if verdict.body_path is None or not verdict.body_path.is_absolute():
        raise NotRecorded("verdict_malformed", repo, verdict.head)
    body = read_body(verdict.body_path)
    if body is None:
        raise NotRecorded("body_unreadable", repo, verdict.head)
    record = GateRecord(
        repo=repo,
        head=verdict.head,
        body_sha256=body_digest(body),
        repo_path=str(verdict.repo_path),
        recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    try:
        existing = read_record(path)
    except RecordUnreadable:
        existing = None
    if existing is None or replace(existing, recorded_at="") != replace(record, recorded_at=""):
        write_record(path, record)
    return "gate_recorded", repo


def log_event(
    store: Path,
    level: str,
    event: str,
    reason: str | None,
    repo: str | None,
    head: str | None,
    pr: str | None = None,
    **extra: str | int | None,
) -> None:
    """1 行を追記する。`extra`(error_type・detail・exit_code)は値があるときだけ載せる。"""
    entry: dict[str, str | int | None] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "level": level,
        "event": event,
        "reason": reason,
        "repo": repo,
        "pr": pr,
        "head": head,
    }
    entry.update((key, value) for key, value in extra.items() if value is not None)
    line = (json.dumps(entry, ensure_ascii=True) + "\n").encode("ascii")
    try:
        fd = os.open(store / "events.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(line)
    except OSError:
        pass


def read_flag(words: list[str], i: int) -> tuple[str, str | None, int]:
    """words[i] のフラグの名前・値・次の位置を返す。値を取らないフラグの値は None。"""
    word = words[i]
    following = words[i + 1] if i + 1 < len(words) else ""
    if word.startswith("--"):
        name, eq, value = word.partition("=")
        if eq:
            return name, value, i + 1
        return (name, following, i + 2) if name in VALUE_FLAGS else (name, None, i + 1)
    for j, ch in enumerate(word[1:], 1):
        if ch in SHORT_VALUE_FLAGS:
            rest = word[j + 1 :]
            if j == 1 and rest.startswith("="):
                rest = rest[1:]
            return ("-" + ch, rest, i + 1) if rest else ("-" + ch, following, i + 2)
    return word, None, i + 1


def parse_merge(words: list[str], env: dict[str, str], cwd: str | None) -> Target | Unresolved | Literal[False]:
    """gh で始まる単純コマンドを読む。gh pr merge でなければ False を返す。"""
    repo = None
    selectors: list[str] = []
    expected = ["pr", "merge"]
    i, positional = 1, False
    while i < len(words):
        word = words[i]
        if expected:
            if word == expected[0]:
                expected.pop(0)
                i += 1
                continue
            if not word.startswith("-"):
                return False
            name, value, i = read_flag(words, i)
            if name in ("-R", "--repo"):
                repo = value
            continue
        if positional or not word.startswith("-"):
            selectors.append(word)
            i += 1
            continue
        if word == "--":
            positional = True
            i += 1
            continue
        name, value, i = read_flag(words, i)
        if name == "--disable-auto":
            return False
        if name in ("-R", "--repo"):
            repo = value
    if expected:
        return False
    # gh 自身が PR の指定の 2 つ目を拒む
    if len(selectors) > 1:
        return Unresolved("shape")
    return Target(selectors[0] if selectors else None, repo, env, cwd)


def unresolved(target: Target, cd_lost: bool, ran_other: bool, env_lost: bool) -> str | None:
    """PR を特定できない理由を返す。特定できれば None。"""
    gh_repo = target.env.get("GH_REPO")
    values = [v for v in (target.selector, target.repo, *target.env.values()) if v is not None]
    if any("$" in v or "`" in v for v in values):
        return "dollar"
    # 照合に渡さない代入は、照合する PR を変えうる(GIT_CONFIG_*・GH_CONFIG_DIR・HOME)か、
    # gh pr view の起動を変える(PATH・DYLD_*)。どちらも照合の外なので確認を求める
    if env_lost or not REPO_ENV.issuperset(target.env):
        return "env"
    if (target.selector is not None and not SELECTOR.fullmatch(target.selector)) or any(
        v is not None and not REPO_FLAG.fullmatch(v) for v in (target.repo, gh_repo)
    ):
        return "shape"
    if foreign_host(target):
        return "host"
    # 現在のブランチの PR は、前のコマンド(git switch・gh pr checkout など)がブランチを変えうる
    if target.selector is None and ran_other:
        return "no_selector_after_command"
    if cd_lost and target.repo is None and gh_repo is None and not PR_URL.fullmatch(target.selector or ""):
        return "cd"
    return None


# shortcut: github.com だけを照合する(GitHub Enterprise の PR は確認になる), Enterprise で確認が続いたら照合する host の一覧を設定から読む
# shortcut: -R・URL・GH_REPO・GH_HOST の無いマージの host は cwd の git remote から gh が決め、hook は確かめない, remote が github.com 以外の作業で問題になったら remote の host も読む
def foreign_host(target: Target) -> bool:
    """gh pr view が github.com 以外の host へ要求を送りうるとき True。環境は view_pr が渡すものと同じに重ねる。"""
    env = {**os.environ, **target.env}
    hosts = [env.get("GH_HOST")]
    if url := PR_URL.fullmatch(target.selector or ""):
        hosts.append(url.group(1).split("/")[2])
    for repo in (target.repo, env.get("GH_REPO")):
        if repo is not None and not REPO_FLAG.fullmatch(repo):
            return True
        if repo is not None and repo.count("/") == 2:
            hosts.append(repo.split("/")[0])
    return any(host is not None and host.lower() != GITHUB for host in hosts)


class Scanner:
    """コマンドを (演算子か, 文字列) の列に読む。引用符と `\\` を外し、`<`・`>` に接した数字(fd)を落とす。

    引用符の中の区切り文字と空の引用符は語になる。`$(...)` と `` `...` `` は中身を `substitutions` に読み分け、
    語には `$`・`` ` `` を含む元の字面を残す。ヒアドキュメントの本文はコマンドとして読まず、区切りの語を
    引用符で囲んでいなければ本文の `$(...)` と `` `...` `` だけを読む。引用符・置換・ヒアドキュメントが
    閉じていなければ ValueError を送出する。
    """

    def __init__(self, text: str) -> None:
        self.text, self.i = text, 0
        self.substitutions: list[list[tuple[bool, str]]] = []

    def words(self, nested: bool = False) -> list[tuple[bool, str]]:
        """位置 i から読む。nested なら `$(` の中として、対になる `)` の次で止まる。"""
        text = self.text
        tokens: list[tuple[bool, str]] = []
        word: str | None = None
        start = depth = 0
        quoted = False
        pending: str | None = None  # 区切りの語を待つ `<<`・`<<-`
        heredocs: list[tuple[str, bool, bool]] = []  # 次の改行の後に本文を読む (区切りの語, タブを外すか, 展開するか)
        while True:
            ch = text[self.i : self.i + 1]
            if word is None:
                start, quoted = self.i, False
            if ch == "\\":
                if text[self.i + 1 : self.i + 2] != "\n":
                    word, quoted = (word or "") + text[self.i + 1 : self.i + 2], True
                self.i += 2
            elif ch == "'":
                end = text.index("'", self.i + 1)
                word, quoted = (word or "") + text[self.i + 1 : end], True
                self.i = end + 1
            elif ch == '"':
                self.i += 1
                word, quoted = (word or "") + self.double_quoted(), True
            elif ch == "`":
                word = (word or "") + self.backquoted()
            elif text.startswith("$(", self.i):
                word = (word or "") + self.substitution()
            elif text.startswith("$'", self.i):
                # $'...' の中の `\'` は引用符を閉じない。語には `$` を含む元の字面を残す
                end = self.i + 2
                while text[end : end + 1] != "'":
                    if not text[end : end + 1]:
                        raise ValueError("引用符が閉じていない")
                    end += 2 if text[end] == "\\" else 1
                word, quoted = (word or "") + text[self.i : end + 1], True
                self.i = end + 1
            elif ch == "#" and word is None:
                end = text.find("\n", self.i)
                self.i = len(text) if end < 0 else end
            elif ch and ch not in SEPARATORS:
                word = (word or "") + ch
                self.i += 1
            else:
                op = next((o for o in OPERATORS if text.startswith(o, self.i)), ch)
                if word is not None:
                    if pending is not None:
                        heredocs.append((word, pending == "<<-", not quoted))
                        pending = None
                    if not (op[:1] in ("<", ">") and FD.fullmatch(text[start : self.i])):
                        tokens.append((False, word))
                    word = None
                if not ch:
                    if nested or pending is not None or heredocs:
                        raise ValueError("置換かヒアドキュメントが閉じていない")
                    return tokens
                self.i += len(op)
                if op in " \t\r":
                    continue
                if pending is not None:
                    raise ValueError("ヒアドキュメントの区切りの語が無い")
                if nested and op == ")" and depth == 0:
                    if heredocs:
                        raise ValueError("ヒアドキュメントが閉じていない")
                    return tokens
                depth += {"(": 1, ")": -1}.get(op, 0)
                tokens.append((True, op))
                if op in HEREDOCS:
                    pending = op
                elif op == "\n":
                    for heredoc in heredocs:
                        self.heredoc(*heredoc)
                    heredocs = []

    def double_quoted(self) -> str:
        """`"` の次から閉じる `"` の次まで読み、中身を返す。"""
        text, chars = self.text, []
        while True:
            ch = text[self.i : self.i + 1]
            if not ch:
                raise ValueError("引用符が閉じていない")
            if ch == '"':
                self.i += 1
                return "".join(chars)
            if ch == "`":
                chars.append(self.backquoted())
            elif text.startswith("$(", self.i):
                chars.append(self.substitution())
            elif ch == "\\" and text[self.i + 1 : self.i + 2] in ("\\", '"', "$", "`", "\n"):
                chars.append(text[self.i + 1].replace("\n", ""))
                self.i += 2
            else:
                chars.append(ch)
                self.i += 1

    def substitution(self) -> str:
        """`$(` から対になる `)` の次まで読み、中身を substitutions に足して元の字面を返す。"""
        start = self.i
        self.i += 2
        self.substitutions.append(self.words(nested=True))
        return self.text[start : self.i]

    def backquoted(self) -> str:
        """`` ` `` から閉じる `` ` `` の次まで読み、中身を substitutions に足して元の字面を返す。"""
        text, start, chars = self.text, self.i, []
        self.i += 1
        while text[self.i : self.i + 1] != "`":
            if not text[self.i : self.i + 1]:
                raise ValueError("バッククォートが閉じていない")
            # バッククォートの中の `\\` は `$`・`` ` ``・`\\` の前でだけ外れる
            if text[self.i] == "\\" and text[self.i + 1 : self.i + 2] in ("$", "`", "\\"):
                self.i += 1
            chars.append(text[self.i])
            self.i += 1
        self.i += 1
        inner = Scanner("".join(chars))
        tokens = inner.words()
        self.substitutions += [tokens, *inner.substitutions]
        return text[start : self.i]

    def heredoc(self, delimiter: str, strip_tabs: bool, expands: bool) -> None:
        """改行の次から区切りの語だけの行の次まで本文を読み飛ばす。"""
        text = self.text
        while self.i < len(text):
            end = text.find("\n", self.i)
            end = len(text) if end < 0 else end
            line = text[self.i : end]
            if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                self.i = min(end + 1, len(text))
                return
            if not expands:
                self.i = end + 1
                continue
            while self.i < len(text) and text[self.i] != "\n":
                if text[self.i] == "`":
                    self.backquoted()
                elif text.startswith("$(", self.i):
                    self.substitution()
                else:
                    self.i += 2 if text[self.i] == "\\" else 1
            self.i += 1
        raise ValueError("ヒアドキュメントの区切りの行が無い")


def simple_commands(tokens: list[tuple[bool, str]]) -> Iterator[tuple[list[str], str | None, str]]:
    """単純コマンドごとに (語, 前の区切り, 後の区切り) を返す。リダイレクトの演算子と対象の語は除く。"""
    words: list[str] = []
    before: str | None = None
    redirect = False
    for is_op, text in [*tokens, (True, "\n")]:
        if not is_op:
            if redirect:
                redirect = False
            else:
                words.append(text)
        elif text[0] in "<>" or text == "&>":
            redirect = True
        else:
            yield words, before, text
            words, before, redirect = [], text, False


def cd_dest(words: list[str], cwd: str | None) -> str | None:
    """cd・pushd の行き先の絶対パスを返す。引数が 1 つの実在するディレクトリでなければ None。"""
    if words[0] == "popd" or len(words) != 2 or UNTRACKED_PATH.search(words[1]):
        return None
    # CDPATH があると、`/` か `.`・`..` で始まらない行き先は CDPATH の下から探される
    if os.environ.get("CDPATH") and not words[1].startswith("/") and words[1].split("/")[0] not in (".", ".."):
        return None
    path = os.path.join(cwd or "", words[1])
    # シェルの cd は既定で `..` を字面で畳む(cd -L)
    return os.path.normpath(path) if os.path.isabs(path) and os.path.isdir(path) else None


# shortcut: LAUNCHERS を先頭に書いた単純コマンドがあれば、渡した中身(-c の引数・ヒアドキュメントの本文・xargs の入力)を読まずに確認を求める。
#   関数・alias・"$SHELL" -c・find -exec・ほかの言語(python -c など)・スクリプトのファイルの中の gh は読まない, 取りこぼしが起きたらその形を読む
#   LAUNCHERS と RUNNERS に無い起動役(caffeinate・coproc・stdbuf・ssh など)の後ろの gh は読まない
#   展開するヒアドキュメントの本文の中の $( やバッククォートが閉じないときは区切りの行を越えて読み、quote の確認になる
# shortcut: 引用符の外の $(...)・$X の展開の結果の語の分割を読まない(`-b $(cat f)` の中身の -R を読まない), 誤った PR で照合したら引用符の外の展開を確認にする
# shortcut: $(...) の中の case の `)` で置換が閉じたと読み、$((...)) の `<<` をヒアドキュメントと読む(区切りの行が無く quote の確認になる), 取りこぼしか誤検出が起きたら case と算術式を読む
# shortcut: 前置き(代入・OPENERS・KEYWORDS・RUNNERS)を剥がした先頭の gh だけを読む。set -a・関数で変えた環境は追わない, 取りこぼしが起きたらその形を読む
# shortcut: cd は書かれた順に、リストの先頭か追えた cd の後の && で前景のものだけを追う。サブシェル・<(...)・if・ループ・関数が現れた後の cd と、ほかの &&・|| の後の cd は cwd を不明にする, 不明で確認が続いたら制御の流れを読み分ける
def merge_targets(command: str, cwd: str | None) -> list[Target | Unresolved]:
    """コマンドの gh pr merge を返す。cwd は hook の入力の作業ディレクトリ。"""
    scanner = Scanner(command)
    try:
        tokens = scanner.words()
    except ValueError:
        return [Unresolved("quote")]
    targets = list(list_targets(tokens, cwd))
    # shortcut: 置換の中のマージは置換の位置の cwd と環境を追わずに確認を求める, 確認が続いたら置換の位置で照合する
    for substituted in scanner.substitutions:
        targets += [Unresolved("substitution") for _ in list_targets(substituted, None)]
    if any(launches(stream) for stream in (tokens, *scanner.substitutions)):
        targets.append(Unresolved("nested"))
    return targets


def strip_prefix(words: list[str]) -> tuple[list[str], dict[str, str], bool, bool]:
    """単純コマンドの前置き(代入・OPENERS・KEYWORDS・RUNNERS)を剥がし、(残りの語, 代入, OPENERS があったか,
    RUNNERS があったか) を返す。"""
    env: dict[str, str] = {}
    opened = runner = False
    while words:
        head = words[0]
        if m := ASSIGNMENT.fullmatch(head):
            env[m.group(1)] = m.group(2)
        elif head in OPENERS:
            opened = True
        elif (name := os.path.basename(head)) in RUNNERS:
            runner = True
            if name == "timeout" and len(words) > 1 and DURATION.fullmatch(words[1]):
                words = words[1:]
        elif head not in KEYWORDS:
            break
        words = words[1:]
    return words, env, opened, runner


def launches(tokens: list[tuple[bool, str]]) -> bool:
    """単純コマンドのどれかが LAUNCHERS で始まれば True。RUNNERS の後ろにオプション(`env -i`・`timeout -s KILL 60`)が
    あれば、オプションの値を読み分けずに残りの語のどれかが LAUNCHERS なら True とする。"""
    for words, _, _ in simple_commands(tokens):
        rest, _, _, runner = strip_prefix(words)
        candidates = rest if runner and rest[:1] and rest[0].startswith("-") else rest[:1]
        if any(os.path.basename(word) in LAUNCHERS for word in candidates):
            return True
    return False


def list_targets(tokens: list[tuple[bool, str]], cwd: str | None) -> Iterator[Target | Unresolved]:
    """単純コマンドの列の gh pr merge を前から順に返す。"""
    cd_lost = compound = ran_other = tracked_cd = env_lost = False
    for words, before, after in simple_commands(tokens):
        words, env, opened, runner = strip_prefix(words)
        compound = compound or opened
        # 代入だけの行と export などは、後ろのマージの環境の GH_REPO などを変えうる
        if not words or words[0] in ENV_COMMANDS:
            names = set(env) | {word.partition("=")[0] for word in words[1:]}
            env_lost = env_lost or not REPO_ENV.isdisjoint(names)
        # 追えた cd の後の && の cd は、前の cd が成功したときだけ走るので追える
        runs = before in (None, ";", "&", "\n") or (before == "&&" and tracked_cd)
        tracked_cd = False
        if words and words[0] in CD:
            foreground = runs and after not in ("|", "|&", "&")
            dest = cd_dest(words, None if cd_lost else cwd) if foreground and not compound else None
            cwd, cd_lost, tracked_cd = (cwd, True, False) if dest is None else (dest, False, True)
        elif words:
            target = parse_merge(words, env, cwd) if os.path.basename(words[0]) == "gh" else False
            if isinstance(target, Target):
                # `(` で終わるマージは <(...) で語が切れ、後ろの -R などを読めていない
                detail = "shape" if after == "(" else unresolved(target, cd_lost, ran_other, env_lost)
                yield target if detail is None else Unresolved(detail)
            elif target is not False:
                yield target
            elif runner and words[0].startswith("-") and MERGE_HINT.search(" ".join(words)):
                yield Unresolved("prefix_option")
            ran_other = True
        if after == "(":
            compound = True


def parse_pr(data: object) -> PullRequest:
    """gh pr view の JSON を確かめて PullRequest にする。形が違えば ViewFailed を送出する。"""
    if not isinstance(data, dict):
        raise ViewFailed("view_malformed")
    head, body, url, base, commits = (data.get(k) for k in ("headRefOid", "body", "url", "baseRefName", "commits"))
    m = PR_URL.fullmatch(url) if isinstance(url, str) else None
    repo = repo_key(m.group(1)) if m else None
    if (
        repo is None
        or not isinstance(head, str)
        or not SHA.fullmatch(head)
        or not isinstance(body, str)
        or not isinstance(base, str)
        or not isinstance(commits, list)
        or not all(isinstance(c, dict) and isinstance(c.get("oid"), str) and SHA.fullmatch(c["oid"]) for c in commits)
    ):
        raise ViewFailed("view_malformed")
    return PullRequest(repo, m.group(2), m.group(3), url, head, body, base, tuple(c["oid"] for c in commits))


def view_pr(target: Target, deadline: float) -> PullRequest:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ViewFailed("view_timeout")
    args = ["gh", "pr", "view"]
    if target.repo is not None:
        args += ["-R", target.repo]
    args += ["--json", VIEW_FIELDS]
    # `--` の後は `-` で始まる指定もフラグでなく PR の指定になる(gh pr merge -- --web と同じ読み方)
    if target.selector is not None:
        args += ["--", target.selector]
    env = {**os.environ, **target.env, "GH_PROMPT_DISABLED": "1"}
    try:
        proc = subprocess.run(
            args,
            cwd=target.cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=min(GH_TIMEOUT, remaining),
        )
    except subprocess.TimeoutExpired:
        raise ViewFailed("view_timeout") from None
    # OSError: gh が無い・cwd に入れない。ValueError: cwd や引数の NUL
    except (OSError, ValueError):
        raise ViewFailed("view_failed", "spawn_failed") from None
    if proc.returncode != 0:
        raise ViewFailed("view_failed", "exit_nonzero", proc.returncode)
    try:
        data = json.loads(proc.stdout.decode("utf-8"))
    except ValueError:
        raise ViewFailed("view_malformed") from None
    return parse_pr(data)


def find_record(store: Path | None, pr: PullRequest, head: str) -> GateRecord | None:
    """(PR のリポジトリ, head) の記録を返す。無い・置き場が無い・壊れていれば None。壊れていれば警告を残す。"""
    if store is None:
        return None
    try:
        record = read_record(record_path(store, pr.repo, head))
        if record is not None and (record.repo, record.head) != (pr.repo, head):
            raise RecordUnreadable
    except RecordUnreadable:
        log_event(store, "warn", "record_unreadable", None, pr.repo, head, pr=pr.url)
        return None
    return record


def merge_git(repo_path: Path, deadline: float, *args: str) -> tuple[bool, str]:
    """git を期限の内側で走らせ、(終了コードが 0 か, 標準出力) を返す。終了コード 0・1 のほか(版が古く引数を知らない
    129・オブジェクトが無い 128 など)・起動の失敗・時間切れは MergeUnverified を送出する。"""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise MergeUnverified("timeout")
    try:
        proc = run_git(repo_path, *args, timeout=min(GIT_TIMEOUT, remaining))
    except subprocess.TimeoutExpired:
        raise MergeUnverified("timeout") from None
    except (OSError, ValueError):
        raise MergeUnverified("git_failed") from None
    if proc.returncode not in (0, 1):
        raise MergeUnverified("git_failed", proc.returncode)
    return proc.returncode == 0, proc.stdout


# shortcut: 第 2 親は手元の追跡 ref refs/remotes/origin/<base> の祖先かで確かめ、その ref を信じる, 追跡 ref が古いか書き換わって誤って通したら gh で取った base の head と照合する
def main_merge_stage(record: GateRecord, head: str, base: str, deadline: float) -> str:
    """record.head から head までの first-parent の各コミットが、origin の base を競合なしで取り込んだマージだけかを
    確かめる。取り込みだけなら MAIN_MERGE_ONLY を、違えば外れた段(not_ancestor・too_many_merges・not_merge・not_base・
    conflict・tree_mismatch)を返す。確かめられなければ MergeUnverified を送出する。"""
    repo = Path(record.repo_path)
    if not repo.is_absolute() or not repo.is_dir():
        raise MergeUnverified("missing_repo")
    if not BASE_REF.fullmatch(base):
        raise MergeUnverified("base_shape")
    for oid in (record.head, head):
        if not merge_git(repo, deadline, "rev-parse", "--verify", "--quiet", f"{oid}^{{commit}}")[0]:
            raise MergeUnverified("missing_commit")
    if not merge_git(repo, deadline, "merge-base", "--is-ancestor", record.head, head)[0]:
        return "not_ancestor"
    ok, out = merge_git(
        repo, deadline, "rev-list", "--first-parent", "--parents", f"--max-count={MERGE_LIMIT + 1}", f"{record.head}..{head}"
    )
    if not ok:
        raise MergeUnverified("git_failed", 1)
    rows = [line.split() for line in out.splitlines()]
    if len(rows) > MERGE_LIMIT:
        return "too_many_merges"
    if not rows or any(len(row) != 3 or not all(SHA.fullmatch(oid) for oid in row) for row in rows):
        return "not_merge"
    for merge, first, second in rows:
        if not merge_git(repo, deadline, "merge-base", "--is-ancestor", second, f"refs/remotes/origin/{base}")[0]:
            return "not_base"
        clean, merged_tree = merge_git(repo, deadline, "merge-tree", "--write-tree", first, second)
        if not clean:
            return "conflict"
        ok, tree = merge_git(repo, deadline, "rev-parse", "--verify", "--quiet", f"{merge}^{{tree}}")
        if not ok:
            raise MergeUnverified("git_failed", 1)
        if merged_tree.split("\n", 1)[0] != tree.strip():
            return "tree_mismatch"
    return MAIN_MERGE_ONLY


def body_outcome(record: GateRecord, pr: PullRequest, detail: str | None = None) -> Outcome:
    if record.body_sha256 == body_digest(pr.body):
        return Outcome("pass", "pass", pr=pr, detail=detail)
    return Outcome("deny", "body_changed", BODY_CHANGED.format(number=pr.number), pr, detail=detail)


def after_gate(record: GateRecord, pr: PullRequest, deadline: float) -> Outcome:
    """ゲートの後に head が進んだ PR を、main の取り込みだけかで判定する。"""
    try:
        stage = main_merge_stage(record, pr.head, pr.base, deadline)
    except MergeUnverified as e:
        reason = COMMITS_AFTER_GATE.format(gated=record.head[:7], head=pr.head[:7], note=MERGE_UNVERIFIED)
        return Outcome("deny", "merge_unverified", reason, pr, detail=e.detail, exit_code=e.exit_code)
    if stage == MAIN_MERGE_ONLY:
        return body_outcome(record, pr, stage)
    reason = COMMITS_AFTER_GATE.format(gated=record.head[:7], head=pr.head[:7], note="")
    return Outcome("deny", "commits_after_gate", reason, pr, detail=stage)


def check(target: Target | Unresolved, deadline: float, store: Path | None) -> Outcome:
    if isinstance(target, Unresolved):
        return Outcome("ask", "target_unresolved", UNRESOLVED, detail=target.detail)
    try:
        pr = view_pr(target, deadline)
    except ViewFailed as e:
        return Outcome("ask", e.kind, VIEW_FAILED, detail=e.detail, exit_code=e.exit_code)
    record = find_record(store, pr, pr.head)
    if record is not None:
        return body_outcome(record, pr)
    for oid in reversed(pr.commits):
        gated = find_record(store, pr, oid) if oid != pr.head else None
        if gated is not None:
            return after_gate(gated, pr, deadline)
    return Outcome("ask", "no_record", NO_RECORD.format(slug=pr.slug, number=pr.number), pr)


def internal_error(e: Exception) -> Outcome:
    name = type(e).__name__
    return Outcome("ask", "internal_error", INTERNAL_ERROR.format(name=name), error_type=name)


def combine(outcomes: list[Outcome]) -> Outcome:
    rank = {"pass": 0, "ask": 1, "deny": 2}
    return max(outcomes, key=lambda outcome: rank[outcome.decision])


def emit(outcome: Outcome) -> None:
    if outcome.decision == "pass":
        return
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": outcome.decision,
            "permissionDecisionReason": outcome.reason,
        }
    }
    sys.stdout.write(json.dumps(output, ensure_ascii=True))


# shortcut: --auto は有効にした時点だけを照合する, 有効にした後のコミットで自動マージされる。問題になったら --auto を止める
# shortcut: gh api の merge は照合しない, gh pr merge だけを読む。gh api で回避されたら API の経路も読む
def guard_merge(payload: dict) -> None:
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if payload.get("tool_name") != "Bash" or not isinstance(command, str):
        return
    # posix のシェルは行継続の `\` + 改行を消してから読む。MERGE_HINT は 1 行の中だけを見る
    if not MERGE_HINT.search(command.replace("\\\n", "")):
        return
    cwd = payload.get("cwd")
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    store = open_store(data) if data else None
    try:
        targets = merge_targets(command, cwd if isinstance(cwd, str) else None)
    except Exception as e:  # noqa: BLE001  MERGE_HINT に当たった後の不具合で黙ってマージを通さない
        outcomes = [internal_error(e)]
    else:
        deadline = time.monotonic() + CHECK_DEADLINE
        outcomes = []
        for target in targets:
            try:
                outcomes.append(check(target, deadline, store))
            except Exception as e:  # noqa: BLE001  対象と判定した後の不具合で黙ってマージを通さない
                outcomes.append(internal_error(e))
    if not outcomes:
        return
    for outcome in outcomes:
        if store is not None:
            pr = outcome.pr
            log_event(
                store,
                outcome.level,
                "merge_checked",
                outcome.kind,
                pr.repo if pr else None,
                pr.head if pr else None,
                pr=pr.url if pr else None,
                error_type=outcome.error_type,
                detail=outcome.detail,
                exit_code=outcome.exit_code,
            )
    emit(combine(outcomes))


def record_verdict(payload: object) -> None:
    text = report_text(payload)
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    section = verdict_section(text) if text is not None else None
    if section is None or not data:
        return
    store = open_store(data)
    if store is None:
        return
    verdict = None
    try:
        verdict = parse_verdict(section)
        event, repo = apply_verdict(store, verdict)
    except NotRecorded as e:
        log_event(store, "warn", "gate_not_recorded", e.reason, e.repo, e.head)
        return
    except Exception as e:  # noqa: BLE001  hook 自身の不具合でサブエージェントの終了を妨げない
        head = verdict.head if verdict else None
        log_event(store, "error", "gate_not_recorded", "hook_error", None, head, error_type=type(e).__name__)
        return
    log_event(store, "info", event, None, repo, verdict.head)


# shortcut: 記録とログを掃除しない, 記録は 1 件 4 KiB 以下・ログは 1 行 200 バイトほどで増え続ける。容量が問題になったらマージ済みの記録と古いログを消す
# shortcut: 記録の失敗をゲートの時点で統括に知らせない, 失敗はマージの照合で初めて分かる。照合で記録なしが続いたらゲートの時点で知らせる
def main(stdin: BinaryIO) -> None:
    try:
        payload = json.loads(stdin.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if isinstance(payload, dict) and payload.get("hook_event_name") == "PreToolUse":
        guard_merge(payload)
    else:
        record_verdict(payload)


if __name__ == "__main__":
    try:
        main(sys.stdin.buffer)
    except Exception:  # noqa: BLE001  hook 自身の不具合でサブエージェントの終了と、対象と判定する前の Bash を妨げない
        pass
    sys.exit(0)
