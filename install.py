#!/usr/bin/env python3
"""dev スキル群(コア)と拡張バンドルを利用側プロジェクトへ導入・削除する。

配布物(本スクリプトのあるディレクトリ)は変更せず、利用側プロジェクトへ**ハードコピー**する。
シンボリックリンクは使わない(devcontainer 等でホスト側パスが解決できない環境でも動くように、
また利用側が導入物を自リポジトリに Git 管理できるように。D-006)。

- core:   `.claude/skills/*`(dev-* / flow-* のみ)・`.claude/agents/*.md` をコピーする。
          `meta-*` は dev-skills 自身の保守用のため配布しない。更新(再実行)では、前回コピーして
          今回の配布元に無くなったスキル・エージェント(廃止分)を削除する。記録は core lock。
- ext:    拡張バンドル(`extensions/<グループ名>/<name>/`)のスキル本体を `.claude/skills/<name>/` へ
          コピーし、同梱 `agents/` のコピー・`settings.snippet.json` のマージ(hooks・permissions.deny)・
          同梱 `ports/` のコピー(既存は上書きしない)を行い、ext lock に記録する。
- remove: ext で行った導入を lock に基づき取り消す(コピーした port は利用側資産のため削除しない)。
- status: 導入状態を表示する。

導入・削除は利用側の明示操作(本スクリプトの実行)である(DESIGN §3 規律 9)。
Python 3 標準ライブラリのみで動作する。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

CORE_LOCK_REL = ".claude/dev-core.lock.json"
LOCK_REL = ".claude/dev-extensions.lock.json"
SETTINGS_REL = ".claude/settings.json"

# meta-* は dev-skills リポジトリ自身の品質を保守する道具で、消費プロジェクトでは使わない。
# core の配布対象から除外する(D-006)。
CORE_EXCLUDE_PREFIX = "meta-"
# 拡張バンドルのうち、スキル本体としてコピーしないエントリ(別経路で扱う)。
EXT_NON_SKILL = {"agents", "ports", "settings.snippet.json"}
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def note(msg: str, dry: bool) -> None:
    print(f"{'[dry-run] ' if dry else ''}{msg}")


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"{path} を JSON として解釈できない: {e}")


def save_json(path: Path, data, dry: bool) -> None:
    if dry:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def copy_tree(src: Path, dst: Path, dry: bool) -> None:
    """src ディレクトリを dst へコピーする(既存 dst は置換。__pycache__ / *.pyc を除外)。"""
    note(f"copy   {dst}/ <- {src}/", dry)
    if dry:
        return
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=IGNORE)


def copy_file(src: Path, dst: Path, dry: bool) -> None:
    note(f"copy   {dst}", dry)
    if dry:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def remove_path(p: Path, dry: bool) -> None:
    """コピー済みのファイル/ディレクトリを削除する(lock で追跡した導入物のみに使う)。"""
    if not p.exists() and not p.is_symlink():
        return
    note(f"remove {p}", dry)
    if dry:
        return
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p)
    else:
        p.unlink()


def merge_hooks(settings: dict, snippet: dict) -> dict:
    """snippet の hooks を settings へ冪等に追記し、実際に追加した分を返す。"""
    added: dict = {}
    for event, entries in snippet.get("hooks", {}).items():
        current = settings.setdefault("hooks", {}).setdefault(event, [])
        for entry in entries:
            if entry not in current:
                current.append(entry)
                added.setdefault(event, []).append(entry)
    return added


def unmerge_hooks(settings: dict, added: dict) -> None:
    """lock に記録された追加分を settings から取り除く。"""
    hooks = settings.get("hooks", {})
    for event, entries in added.items():
        current = hooks.get(event, [])
        for entry in entries:
            if entry in current:
                current.remove(entry)
        if not current:
            hooks.pop(event, None)
    if not hooks:
        settings.pop("hooks", None)


def merge_deny(settings: dict, snippet: dict) -> list:
    """snippet の permissions.deny を settings へ冪等に追記し、実際に追加した分を返す。"""
    entries = snippet.get("permissions", {}).get("deny", [])
    if not entries:
        return []
    current = settings.setdefault("permissions", {}).setdefault("deny", [])
    added = []
    for entry in entries:
        if entry not in current:
            current.append(entry)
            added.append(entry)
    return added


def unmerge_deny(settings: dict, managed: list) -> None:
    """lock に記録された deny を settings から取り除く(利用側の既存 deny は残る)。"""
    perms = settings.get("permissions", {})
    deny = perms.get("deny", [])
    for entry in managed:
        if entry in deny:
            deny.remove(entry)
    if "deny" in perms and not deny:
        perms.pop("deny")
    if not perms:
        settings.pop("permissions", None)


def cmd_core(root: Path, target: Path, dry: bool) -> None:
    skills_src = root / ".claude" / "skills"
    agents_src = root / ".claude" / "agents"
    if not skills_src.is_dir():
        die(f"配布ルートに .claude/skills が無い: {root}")

    core_lock_path = target / CORE_LOCK_REL
    old = load_json(core_lock_path, {})
    old_skills = old.get("skills", [])
    old_agents = old.get("agents", [])

    new_skills: list[str] = []
    for d in sorted(p for p in skills_src.iterdir() if p.is_dir()):
        if d.name.startswith(CORE_EXCLUDE_PREFIX):
            continue  # meta-* は消費側へ配布しない(D-006)
        copy_tree(d, target / ".claude" / "skills" / d.name, dry)
        new_skills.append(d.name)

    new_agents: list[str] = []
    for f in sorted(agents_src.glob("*.md")):
        copy_file(f, target / ".claude" / "agents" / f.name, dry)
        new_agents.append(f".claude/agents/{f.name}")

    # 更新: 前回コピーして今回の配布元に無いスキル・エージェント(廃止分)を削除する。
    for name in old_skills:
        if name not in new_skills:
            remove_path(target / ".claude" / "skills" / name, dry)
    for rel in old_agents:
        if rel not in new_agents:
            remove_path(target / rel, dry)

    save_json(core_lock_path, {"skills": new_skills, "agents": new_agents}, dry)
    stale = len([s for s in old_skills if s not in new_skills]) + len(
        [a for a in old_agents if a not in new_agents]
    )
    print(
        f"core: スキル {len(new_skills)} 件・エージェント {len(new_agents)} 件をコピー"
        f"(meta-* は配布しない。廃止削除 {stale} 件。記録: {CORE_LOCK_REL})"
    )


def resolve_ext(root: Path, name: str) -> Path:
    """バンドル名(または <グループ名>/<バンドル名>)を extensions/ 配下のパスへ解決する。"""
    ext_root = root / "extensions"
    if "/" in name:
        ext = ext_root / name
        if not (ext / "SKILL.md").is_file():
            die(f"拡張バンドルが見つからない(SKILL.md 必須): {ext}")
        return ext
    matches = sorted(
        p for p in ext_root.glob(f"*/{name}") if (p / "SKILL.md").is_file()
    )
    if not matches:
        die(f"拡張バンドルが見つからない(SKILL.md 必須): {ext_root}/*/{name}")
    if len(matches) > 1:
        groups = ", ".join(p.parent.name for p in matches)
        die(
            f"バンドル名 {name} が複数グループに存在する({groups})。"
            f"<グループ名>/{name} で指定する"
        )
    return matches[0]


def cmd_ext(root: Path, target: Path, name: str, dry: bool) -> None:
    ext = resolve_ext(root, name)
    name = ext.name  # 導入名はグループを含まないバンドル名
    if not (target / ".claude" / "skills" / "dev-core").is_dir():
        print("warning: 対象に dev-core が未導入。先に `install.py core` の実行を推奨する")

    lock_path = target / LOCK_REL
    lock = load_json(lock_path, {})
    old = lock.get(name, {})
    if old:
        print(f"{name}: 導入済み(lock に記録あり)。上書きで更新する")
    record: dict = {
        "skill_dir": f".claude/skills/{name}",
        "agents": list(old.get("agents", [])),
        "settings_hooks": old.get("settings_hooks", {}),
        "settings_deny": old.get("settings_deny", []),
        "ports": old.get("ports", []),
    }

    # 1. スキル本体をコピーする。コピーなので相対参照 ../dev-core は導入先の実体へ解決する
    #    (シンボリックリンクのようにディレクトリごとで壊れる問題がない。D-006)。
    #    agents/ ports/ settings.snippet.json は別経路で扱うため除外し、hooks/ は同梱する。
    skill_dst = target / ".claude" / "skills" / name
    remove_path(skill_dst, dry)
    for entry in sorted(ext.iterdir()):
        if entry.name in EXT_NON_SKILL:
            continue
        if entry.is_dir():
            copy_tree(entry, skill_dst / entry.name, dry)
        else:
            copy_file(entry, skill_dst / entry.name, dry)

    # 2. 同梱 agents のコピー(命名は <拡張名>- prefix)
    agents_dir = ext / "agents"
    if agents_dir.is_dir():
        for f in sorted(agents_dir.glob("*.md")):
            if not f.stem.startswith(f"{name}-"):
                print(
                    f"warning: {f.name} は '{name}-' prefix でない(dev-* との衝突に注意)"
                )
            copy_file(f, target / ".claude" / "agents" / f.name, dry)
            if f".claude/agents/{f.name}" not in record["agents"]:
                record["agents"].append(f".claude/agents/{f.name}")

    # 3. settings.snippet.json のマージ(hooks と permissions.deny のみ)
    snippet_path = ext / "settings.snippet.json"
    if snippet_path.is_file():
        snippet = load_json(snippet_path, {})
        for key in snippet:
            if key not in ("hooks", "permissions"):
                print(
                    f"warning: settings.snippet.json の '{key}' はマージ対象外(hooks・permissions.deny のみ)"
                )
        for key in snippet.get("permissions", {}):
            if key != "deny":
                print(
                    f"warning: settings.snippet.json の 'permissions.{key}' はマージ対象外(deny のみ)"
                )
        settings_path = target / SETTINGS_REL
        settings = load_json(settings_path, {})
        added_hooks = merge_hooks(settings, snippet)
        added_deny = merge_deny(settings, snippet)
        if added_hooks or added_deny:
            save_json(settings_path, settings, dry)
            parts = []
            if added_hooks:
                parts.append(f"hooks: {', '.join(added_hooks)}")
            if added_deny:
                parts.append(f"deny: {len(added_deny)} 件")
            note(f"merge  {settings_path}({'; '.join(parts)})", dry)
        # 管理集合(record)へも同じ内容を取り込む
        merge_hooks({"hooks": record["settings_hooks"]}, snippet)
        for entry in snippet.get("permissions", {}).get("deny", []):
            if entry not in record["settings_deny"]:
                record["settings_deny"].append(entry)

    # 4. 同梱 ports のコピー(既存は上書きしない)
    ports_dir = ext / "ports"
    if ports_dir.is_dir():
        for f in sorted(p for p in ports_dir.rglob("*") if p.is_file()):
            rel = f.relative_to(ports_dir)
            dst = target / "docs" / "dev" / "ports" / name / rel
            if dst.exists():
                print(f"skip   {dst}(既存の port は上書きしない)")
                continue
            copy_file(f, dst, dry)
            rel_target = str(dst.relative_to(target))
            if rel_target not in record["ports"]:
                record["ports"].append(rel_target)

    lock[name] = record
    save_json(lock_path, lock, dry)
    print(f"ext {name}: 導入完了(記録: {LOCK_REL})")


def cmd_remove(root: Path, target: Path, name: str, dry: bool) -> None:
    lock_path = target / LOCK_REL
    lock = load_json(lock_path, {})
    if name not in lock:
        die(f"{name} は lock({LOCK_REL})に記録が無い(このスクリプトで導入されていない)")
    record = lock[name]

    remove_path(target / record["skill_dir"], dry)
    for rel in record.get("agents", []):
        remove_path(target / rel, dry)

    # 他拡張の lock が同一エントリを管理している場合は settings に温存する
    # (共有エントリを無条件に外すと、残る拡張の配線を壊すため)
    other_hooks: dict = {}
    other_deny: set = set()
    for other_name, other in lock.items():
        if other_name == name:
            continue
        for event, entries in other.get("settings_hooks", {}).items():
            other_hooks.setdefault(event, []).extend(entries)
        other_deny.update(other.get("settings_deny", []))
    added = {}
    for event, entries in record.get("settings_hooks", {}).items():
        kept = [e for e in entries if e not in other_hooks.get(event, [])]
        if kept:
            added[event] = kept
    deny = [e for e in record.get("settings_deny", []) if e not in other_deny]
    if added or deny:
        settings_path = target / SETTINGS_REL
        settings = load_json(settings_path, {})
        unmerge_hooks(settings, added)
        unmerge_deny(settings, deny)
        save_json(settings_path, settings, dry)
        parts = []
        if added:
            parts.append(f"hooks: {', '.join(added)}")
        if deny:
            parts.append(f"deny: {len(deny)} 件")
        note(f"unmerge {settings_path}({'; '.join(parts)})", dry)

    for rel in record.get("ports", []):
        print(f"keep   {target / rel}(コピー済み port は利用側資産のため削除しない)")

    del lock[name]
    if lock:
        save_json(lock_path, lock, dry)
    elif not dry:
        lock_path.unlink(missing_ok=True)
        note(f"unlink {lock_path}", False)
    print(f"ext {name}: 削除完了")


def cmd_status(root: Path, target: Path) -> None:
    core = load_json(target / CORE_LOCK_REL, {})
    skills = core.get("skills", [])
    agents = core.get("agents", [])
    print(f"core スキル(コピー): {', '.join(skills) or 'なし'}")
    print(f"core エージェント: {len(agents)} 件")
    lock = load_json(target / LOCK_REL, {})
    if not lock:
        print("拡張: なし")
        return
    for name, record in lock.items():
        parts = [f"skill={record['skill_dir']}"]
        if record.get("agents"):
            parts.append(f"agents={len(record['agents'])}")
        if record.get("settings_hooks"):
            parts.append(f"hooks={','.join(record['settings_hooks'])}")
        if record.get("settings_deny"):
            parts.append(f"deny={len(record['settings_deny'])}")
        if record.get("ports"):
            parts.append(f"ports={len(record['ports'])}")
        print(f"拡張 {name}: {'; '.join(parts)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="配布ルート(既定: 本スクリプトの位置)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_core = sub.add_parser("core", help="コア(skills・agents)をコピーする")
    p_ext = sub.add_parser("ext", help="拡張バンドルを導入する")
    p_ext.add_argument(
        "name",
        help="バンドル名(extensions/<グループ名>/ 配下。複数グループに同名がある場合は <グループ名>/<バンドル名>)",
    )
    p_remove = sub.add_parser("remove", help="導入済み拡張を削除する")
    p_remove.add_argument("name", help="削除する拡張名")
    p_status = sub.add_parser("status", help="導入状態を表示する")
    for p in (p_core, p_ext, p_remove, p_status):
        p.add_argument(
            "--target", type=Path, required=True, help="利用側プロジェクトのルート"
        )
        if p is not p_status:
            p.add_argument(
                "--dry-run", action="store_true", help="変更せずに実行内容を表示する"
            )

    args = parser.parse_args()
    root: Path = args.root.resolve()
    target: Path = args.target.resolve()
    if not target.is_dir():
        die(f"対象プロジェクトが存在しない: {target}")
    dry = getattr(args, "dry_run", False)

    if args.command == "core":
        cmd_core(root, target, dry)
    elif args.command == "ext":
        cmd_ext(root, target, args.name, dry)
    elif args.command == "remove":
        cmd_remove(root, target, args.name, dry)
    elif args.command == "status":
        cmd_status(root, target)


if __name__ == "__main__":
    main()
