#!/usr/bin/env python3
"""gate-reviewer の判定を `${CLAUDE_PLUGIN_DATA}/merge-gate/` に記録する hook。

入口:
  PostToolUse(SubagentHandback)  auto モード。報告は `tool_input.message` にある
  SubagentStop                     default モード。報告は `last_assistant_message` にある
  どちらも `agent_type` が `dev-skills:gate-reviewer` のときだけ読む。

入出力の契約:
  標準入力  UTF-8 の hook の JSON。環境の符号化に依らず UTF-8 のバイト列として読む
  exit 0    常に(止めない)
  標準出力  書かない
  標準エラー 書かない

報告の「## 判定」の区間の最初の行 `<マージ可 / 差し戻し> <head の SHA>` と、`- リポジトリ: <絶対パス>`・
`- PR 本文案: <絶対パス>` の行を読む。判定の語・SHA・パスの前後の `` ` `` と `**` は外してから読む。マージ可なら、作業ツリーの HEAD が判定の SHA と一致し、origin が
host/owner/name に直せて、本文案が読めるときだけ (リポジトリ, head) をキーに記録を書く。差し戻しなら同じ
キーの記録を消す。判定の区間が無い報告は何もしない。結果は `events.jsonl` に 1 イベント 1 行で追記する。
ログに本文・報告の中身・origin の URL を書かない。

記録のディレクトリはリンクでない自分所有の実際のディレクトリに限り、記録はリンクをたどらずに読み書きする。
ディレクトリを使えないときは、ログも同じディレクトリにあるため何も残せない。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

GATE_AGENT = "dev-skills:gate-reviewer"
RECORD_LIMIT = 4 * 1024
# GitHub の PR 本文の上限 65,536 字 × 1 字 4 バイト
BODY_LIMIT = 256 * 1024
# shortcut: 仮に 5 秒(2 回の git が hooks.json の timeout 20 秒に収まる値), rev-parse と remote get-url の p99.9 を実測したら置き換える
GIT_TIMEOUT = 5
ATTRIBUTION = "Generated with [Claude Code]"

HEADING = re.compile(r"^#{1,6}\s")
VERDICTS = {"マージ可": True, "差し戻し": False}
SHA = re.compile(r"[0-9a-f]{40}")
MARKUP = re.compile(r"^(?:`|\*\*)+|(?:`|\*\*)+$")
REPO_LINE = re.compile(r"^- リポジトリ:\s*(.+)$")
BODY_LINE = re.compile(r"^- PR 本文案:\s*(.+)$")
SCP_REMOTE = re.compile(r"^[^@/:]+@([^/:]+):(.+)$")
URL_REMOTE = re.compile(r"^(?:https|ssh|git)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$")
SLUG = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


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


def git(repo_path: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            stdin=subprocess.DEVNULL,
        )
    # ValueError: パスの NUL・対になっていないサロゲート、出力の復号の失敗
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def body_digest(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    kept = "\n".join(line for line in lines if ATTRIBUTION not in line).strip("\n")
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


def read_record(path: Path) -> object:
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as f:
            return json.loads(f.read(RECORD_LIMIT + 1).decode("ascii"))
    except (OSError, ValueError):
        return None


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
    existing = read_record(path)
    unchanged = isinstance(existing, dict) and {**existing, "recorded_at": ""} == {**asdict(record), "recorded_at": ""}
    if not unchanged:
        write_record(path, record)
    return "gate_recorded", repo


def log_event(
    store: Path,
    level: str,
    event: str,
    reason: str | None,
    repo: str | None,
    head: str | None,
    error_type: str | None = None,
) -> None:
    entry: dict[str, str | None] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "level": level,
        "event": event,
        "reason": reason,
        "repo": repo,
        "pr": None,
        "head": head,
    }
    if error_type is not None:
        entry["error_type"] = error_type
    line = (json.dumps(entry, ensure_ascii=True) + "\n").encode("ascii")
    try:
        fd = os.open(store / "events.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(line)
    except OSError:
        pass


# shortcut: 記録とログを掃除しない, 記録は 1 件 4 KiB 以下・ログは 1 行 200 バイトほどで増え続ける。容量が問題になったらマージ済みの記録と古いログを消す
# shortcut: 記録の失敗をゲートの時点で統括に知らせない, 失敗はマージの照合で初めて分かる。照合で記録なしが続いたらゲートの時点で知らせる
def main(stdin: BinaryIO) -> None:
    try:
        payload = json.loads(stdin.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    text = report_text(payload)
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    section = verdict_section(text) if text is not None else None
    if section is None or not data:
        return
    store = open_store(data)
    if store is None:
        return
    try:
        verdict = parse_verdict(section)
        event, repo = apply_verdict(store, verdict)
    except NotRecorded as e:
        log_event(store, "warn", "gate_not_recorded", e.reason, e.repo, e.head)
        return
    # 例外の中身は報告やパスを含みうるので型名だけを残す
    except Exception as e:  # noqa: BLE001  hook 自身の不具合でサブエージェントの終了を妨げない
        log_event(store, "error", "gate_not_recorded", "hook_error", None, None, type(e).__name__)
        return
    log_event(store, "info", event, None, repo, verdict.head)


if __name__ == "__main__":
    try:
        main(sys.stdin.buffer)
    except Exception:  # noqa: BLE001  hook 自身の不具合でサブエージェントの終了を妨げない
        pass
    sys.exit(0)
