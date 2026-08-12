#!/usr/bin/env python3
"""破壊的な git 操作と一括ステージングを拒否する PreToolUse hook(Bash)。

文章の規律(`git-convention.md` 6. 安全制約)を決定論的に強制する。禁止する操作は、
例外を持たず、コマンド文字列の照合だけで判定が閉じるものに限る(D-018)。

入出力の契約:
  標準入力  PreToolUse の JSON(`tool_name`・`tool_input.command`・`cwd` を読む)
  exit 0    許可(何も出力しない)
  exit 2    拒否。標準エラーへ書いた理由が Claude へ返る

判定の手順:
  1. クォートを解釈して語に分ける(クォートの内側の `;` `|` `&&` を区切りと見なさない。
     `git commit -m "wip; git reset --hard"` のようなメッセージを拒否しないため)
  2. シェルの区切り(`;` `&&` `||` `|` `&` `(` `)`)でセグメントへ分ける
  3. 各セグメントの先頭から、環境変数の代入・前置コマンド・git のグローバルオプションを
     読み飛ばし、真のコマンドとサブコマンドを判定する
  4. `rm -rf` だけは削除対象のパスも見る。正本が禁じる理由は未コミットの変更を失う
     ことにあり、リポジトリの外の削除はこの理由に当たらないため。相対パスの基点は
     `cwd` とし、セグメントを跨ぐ `cd` を追跡する

Python 3 標準ライブラリのみで動作する。
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

# コマンドの前に置かれても対象コマンドの判定を変えない語。
PREFIXES = {"sudo", "command", "nohup", "time", "env"}
# 環境変数の代入(`FOO=1 git ...`)。
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# git のグローバルオプションのうち、次の語を値として取るもの。
GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
# セグメントの区切りとして扱う記号。
PUNCTUATION = set(";&|()<>")
NAIVE_SEPARATOR = re.compile(r"&&|\|\||;|\||\n")
CONVENTION = "dev-core/references/git-convention.md 6.(安全制約)・7.(巻き戻し)"


def _segments(command: str) -> list[list[str]]:
    """クォートを解釈して語に分け、シェルの区切りでセグメントへ分ける。"""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        # クォートが閉じていない等。素朴な分割へ縮退して検査を続ける。
        return [seg.split() for seg in NAIVE_SEPARATOR.split(command)]
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token and all(c in PUNCTUATION for c in token):
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    return segments


def _strip_prefixes(tokens: list[str]) -> list[str]:
    """環境変数の代入と前置コマンドを読み飛ばす。"""
    while tokens and (tokens[0] in PREFIXES or ASSIGNMENT.match(tokens[0])):
        tokens = tokens[1:]
    return tokens


def _git_args(tokens: list[str]) -> list[str]:
    """`git` の後ろから、グローバルオプションを読み飛ばして残りを返す。"""
    args = tokens[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in GIT_VALUE_OPTS:
            i += 2
            continue
        if arg.startswith("-"):
            i += 1
            continue
        return args[i:]
    return []


def _has_flag(args: list[str], *flags: str) -> bool:
    return any(a in flags for a in args)


def _has_short(args: list[str], letter: str) -> bool:
    """`-rf` のように束ねた短縮フラグに letter が含まれるか。"""
    return any(
        a.startswith("-") and not a.startswith("--") and letter in a[1:] for a in args
    )


def _positionals(args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("-")]


def _looks_like_path(arg: str) -> bool:
    return arg == "." or arg.startswith(("./", "../")) or arg.endswith("/")


def _check_git(args: list[str]) -> str | None:
    if not args:
        return None
    sub, rest = args[0], args[1:]
    if sub == "reset" and _has_flag(rest, "--hard"):
        return "`git reset --hard` は未コミットの変更を失う"
    if sub == "checkout" and ("--" in rest or any(_looks_like_path(a) for a in _positionals(rest))):
        return "`git checkout` による作業ツリーの復元は未コミットの変更を失う"
    if sub == "restore" and not (
        _has_flag(rest, "--staged", "-S") and not _has_flag(rest, "--worktree", "-W")
    ):
        return "`git restore` による作業ツリーの復元は未コミットの変更を失う"
    if sub == "clean":
        force = _has_short(rest, "f") or _has_flag(rest, "--force")
        dry_run = _has_short(rest, "n") or _has_flag(rest, "--dry-run")
        if force and not dry_run:
            return "`git clean -f` は追跡外のファイルを失う"
    if sub == "branch":
        forced = _has_short(rest, "D")
        delete = _has_short(rest, "d") or _has_flag(rest, "--delete")
        force = _has_short(rest, "f") or _has_flag(rest, "--force")
        if forced or (delete and force):
            return "`git branch -D`(強制削除)は未マージのコミットを失う"
    if sub == "push":
        if _has_flag(rest, "--force") or _has_short(rest, "f"):
            return "強制 push は共有された履歴を書き換える"
        if any(a.startswith("+") for a in _positionals(rest)):
            return "`+` を前置した refspec は強制 push であり、共有された履歴を書き換える"
    if sub == "add" and (_has_flag(rest, "-A", "--all") or "." in _positionals(rest)):
        return "一括ステージングは無関係な変更を巻き込む"
    return None


def _resolve(target: str, cwd: str | None) -> str | None:
    """パスを cwd 基点で絶対化する(解決できなければ None)。

    変数展開・コマンド置換を含む語は展開できないため None を返す。実在しない
    パスも対象にするため、シンボリックリンクは解決せず字面の正規化にとどめる。
    """
    if not target or "$" in target or "`" in target:
        return None
    if target.startswith("~"):
        return None  # ホーム展開はシェルが行うため、この時点では確定しない
    if os.path.isabs(target):
        return os.path.normpath(target)
    if cwd is None:
        return None
    return os.path.normpath(os.path.join(cwd, target))


def _repo_root(cwd: str | None) -> str | None:
    """cwd から上へ辿って `.git` を持つディレクトリを探す。"""
    if cwd is None:
        return None
    current = os.path.normpath(cwd)
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _inside_repo(path: str, repo_root: str) -> bool:
    """リポジトリのルートそのもの、またはその配下かを判定する。"""
    return path == repo_root or path.startswith(repo_root + os.sep)


def _check_rm(args: list[str], cwd: str | None, repo_root: str | None) -> str | None:
    """再帰強制削除のうち、リポジトリの中を対象にするものを拒否する。

    正本(`git-convention.md` 6.)が `rm -rf` を禁じる理由は未コミットの変更を
    失うことにある。リポジトリの外の削除はこの理由に当たらないため、対象が
    すべてリポジトリの外だと確定できる場合に限って通す。確定できない対象
    (変数展開・`cd` の追跡が切れた相対パス・リポジトリを特定できない)は、
    復元できない操作のため拒否側に倒す。
    """
    recursive = (
        _has_short(args, "r") or _has_short(args, "R") or _has_flag(args, "--recursive")
    )
    force = _has_short(args, "f") or _has_flag(args, "--force")
    if not (recursive and force):
        return None
    targets = _positionals(args)
    if not targets:
        return None  # 削除対象が無い(実行しても何も消えない)
    if repo_root is None:
        return "`rm -rf` は復元できない削除を行う"
    for target in targets:
        resolved = _resolve(target, cwd)
        if resolved is None:
            return (
                "`rm -rf` の削除対象がリポジトリの外だと確定できない"
                f"(判定できない指定: {target})"
            )
        if _inside_repo(resolved, repo_root):
            return "`rm -rf` はリポジトリ内で復元できない削除を行う"
    return None


def _cd_target(tokens: list[str]) -> str | None:
    """`cd <path>` の行き先を返す(`cd` でなければ None)。"""
    if not tokens or tokens[0] != "cd":
        return None
    operands = _positionals(tokens[1:])
    return operands[0] if operands else None


def check(command: str, cwd: str | None = None) -> str | None:
    """拒否する理由を返す(許可なら None)。

    `cd` を追跡し、後続セグメントの相対パスをその行き先から解決する
    (`cd /tmp && rm -rf work` のように作業場所を移す用法を判定するため)。
    行き先を解決できない `cd` の後は、相対パスの基点が不明になる。
    """
    repo_root = _repo_root(cwd)
    for segment in _segments(command):
        tokens = _strip_prefixes(segment)
        if not tokens:
            continue
        destination = _cd_target(tokens)
        if destination is not None:
            cwd = _resolve(destination, cwd)
            continue
        reason = None
        if tokens[0] == "git":
            reason = _check_git(_git_args(tokens))
        elif tokens[0] == "rm":
            reason = _check_rm(tokens[1:], cwd, repo_root)
        if reason:
            return reason
    return None


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        sys.exit(0)  # 解釈できない入力で作業を止めない
    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    tool_input = payload.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str):
        sys.exit(0)
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        cwd = os.getcwd()
    reason = check(command, cwd)
    if reason is None:
        sys.exit(0)
    print(
        f"この操作は dev スキル群の安全制約で禁止されている: {reason}。\n"
        f"代替手段は {CONVENTION} を参照する"
        "(コミット済みは `git revert`、未コミットは `git stash push`、"
        "ステージングは `git add <file>` で個別に行う)。",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
