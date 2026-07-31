#!/usr/bin/env python3
"""dev スキル群(コア)と拡張バンドルを利用側プロジェクトへ導入・削除する。

配布物(本スクリプトのあるディレクトリ)は変更せず、利用側プロジェクトへ**ハードコピー**する。
シンボリックリンクは使わない(devcontainer 等でホスト側パスが解決できない環境でも動くように、
また利用側が導入物を自リポジトリに Git 管理できるように。D-006)。

- core:   用途グループ(配布ルート直下で `skills/` を持つディレクトリ。例: `dev/`)の
          `skills/*`・`agents/*.md` を `.claude/skills/`・`.claude/agents/` へコピーする。
          グループ名を並べると、そのグループだけを配布する(省略時は全グループ)。
          `meta-*` は dev-skills 自身の保守用で `.claude/skills/` に置き、グループ外のため
          配布されない(D-006・D-011)。更新(再実行)では、前回コピーして今回の配布元に
          無くなったスキル・エージェント(廃止分)を削除する。グループを絞った実行では、
          触らないグループの導入物を削除しない。記録は core lock(グループごと。D-012)。
- ext:    拡張バンドル(`<用途グループ>/extensions/<バンドル群>/<バンドル名>/`)のスキル本体を
          `.claude/skills/<バンドル名>/` へコピーし、同梱 `agents/` のコピー・`settings.snippet.json` の
          マージ(hooks・permissions.deny)・同梱 `ports/` のコピー(既存は上書きしない)を行い、
          ext lock に記録する。指定は末尾から照合し、短い指定で一意に定まらなければ前の階層を足す。
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

# 用途グループ配下でスキル・エージェント・拡張バンドルを収めるディレクトリ名。
SKILLS_SUBDIR = "skills"
AGENTS_SUBDIR = "agents"
EXTENSIONS_SUBDIR = "extensions"
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


def core_groups(root: Path) -> list[Path]:
    """配布対象の用途グループを列挙する(ルート直下で `skills/` を持つディレクトリ)。

    ドットで始まるディレクトリは対象外にする。`meta-*` を置く `.claude/` はこれにより
    配布対象から外れる(名前による除外を持たない。D-011)。
    """
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / SKILLS_SUBDIR).is_dir()
    )


def load_core_lock(path: Path) -> dict[str, dict]:
    """core lock を「グループ名 -> {skills, agents}」で読む。

    グループ名を持たない旧形式(トップレベルの `skills`・`agents`)は、どのグループの
    導入物か判別できないため空文字のキーに入れる。全グループを配布する実行でだけ
    廃止判定の対象にし、グループを絞った実行では触らない。
    """
    data = load_json(path, {})
    groups = data.get("groups")
    if isinstance(groups, dict):
        return {
            name: {
                "skills": list(rec.get("skills", [])),
                "agents": list(rec.get("agents", [])),
            }
            for name, rec in groups.items()
        }
    if data.get("skills") or data.get("agents"):
        return {
            "": {"skills": list(data.get("skills", [])), "agents": list(data.get("agents", []))}
        }
    return {}


def select_groups(root: Path, names: list[str]) -> list[Path]:
    """配布するグループを決める(名前の指定が無ければ全グループ)。"""
    available = core_groups(root)
    if not available:
        die(f"配布ルートに用途グループ(<グループ>/{SKILLS_SUBDIR})が無い: {root}")
    if not names:
        return available
    by_name = {g.name: g for g in available}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        die(
            f"配布ルートに無いグループ: {', '.join(unknown)}"
            f"(利用できる: {', '.join(by_name)})"
        )
    return [by_name[n] for n in dict.fromkeys(names)]


def cmd_core(root: Path, target: Path, names: list[str], dry: bool) -> None:
    groups = select_groups(root, names)
    lock = load_core_lock(target / CORE_LOCK_REL)
    selected = {g.name for g in groups}
    # 廃止判定の範囲。全グループを配布する実行では、前回の記録すべて(グループ名を
    # 持たない旧形式を含む)を対象にする。絞った実行では選んだグループだけを対象にし、
    # 触らないグループの導入物を消さない。
    scope = selected if names else selected | set(lock)
    # 廃止判定の範囲外(今回触らない)グループが導入済みの名前。導入先は平坦なため、
    # 上書きの検出に使うとともに、廃止判定でこれらを削除対象から外す。
    kept_skills = {
        s: name for name, rec in lock.items() if name not in scope for s in rec["skills"]
    }
    kept_agents = {
        a: name for name, rec in lock.items() if name not in scope for a in rec["agents"]
    }

    new: dict[str, dict] = {}
    owner_skill: dict[str, str] = {}
    owner_agent: dict[str, str] = {}
    for group in groups:
        record: dict[str, list[str]] = {"skills": [], "agents": []}
        for d in sorted(p for p in (group / SKILLS_SUBDIR).iterdir() if p.is_dir()):
            owner = owner_skill.get(d.name) or kept_skills.get(d.name)
            if owner:
                die(
                    f"スキル名 {d.name} が {owner} と {group.name} で重複する"
                    "(導入先で衝突する)"
                )
            owner_skill[d.name] = group.name
            copy_tree(d, target / ".claude" / "skills" / d.name, dry)
            record["skills"].append(d.name)
        agents_src = group / AGENTS_SUBDIR
        if agents_src.is_dir():
            for f in sorted(agents_src.glob("*.md")):
                rel_agent = f".claude/agents/{f.name}"
                owner = owner_agent.get(rel_agent) or kept_agents.get(rel_agent)
                if owner:
                    die(
                        f"エージェント名 {f.name} が {owner} と {group.name} で重複する"
                        "(導入先で衝突する)"
                    )
                owner_agent[rel_agent] = group.name
                copy_file(f, target / ".claude" / "agents" / f.name, dry)
                record["agents"].append(rel_agent)
        new[group.name] = record

    # 更新: 廃止判定の範囲の前回記録のうち、今回どのグループからもコピーしなかったもの
    # (グループ間の移動でコピー済みのものは残す)を削除する。
    copied_skills = set(owner_skill)
    copied_agents = set(owner_agent)
    stale = 0
    for name in scope:
        prev = lock.get(name)
        if not prev:
            continue
        for s in prev["skills"]:
            if s not in copied_skills and s not in kept_skills:
                remove_path(target / ".claude" / "skills" / s, dry)
                stale += 1
        for rel in prev["agents"]:
            if rel not in copied_agents and rel not in kept_agents:
                remove_path(target / rel, dry)
                stale += 1

    for name in scope:
        lock.pop(name, None)
    lock.update(new)
    save_json(target / CORE_LOCK_REL, {"groups": lock}, dry)
    print(
        f"core: グループ {', '.join(g.name for g in groups)} から"
        f"スキル {len(copied_skills)} 件・エージェント {len(copied_agents)} 件をコピー"
        f"(廃止削除 {stale} 件。記録: {CORE_LOCK_REL})"
    )


def resolve_ext(root: Path, name: str) -> Path:
    """バンドルの指定を `<用途グループ>/extensions/<バンドル群>/<バンドル名>` へ解決する。

    指定は末尾から照合する。`<バンドル名>` だけなら全用途グループの全バンドル群から探し、
    一意に定まらなければ `<バンドル群>/<バンドル名>`・`<用途グループ>/<バンドル群>/<バンドル名>`
    と前の階層を足して絞る。用途グループの判定は core と同じ(`skills/` を持つルート直下の
    ディレクトリ)ため、拡張バンドルの置き場所も用途グループ配下に限られる。
    """
    parts = [p for p in name.split("/") if p]
    if not parts or len(parts) > 3:
        die(
            f"バンドルの指定は <バンドル名>・<バンドル群>/<バンドル名>・"
            f"<用途グループ>/<バンドル群>/<バンドル名> のいずれかにする: {name}"
        )
    group = parts[-3] if len(parts) == 3 else None
    bundle_group = parts[-2] if len(parts) >= 2 else None
    pattern = f"{bundle_group or '*'}/{parts[-1]}"
    matches: list[Path] = []
    for g in core_groups(root):
        if group is not None and g.name != group:
            continue
        matches.extend(
            p
            for p in sorted((g / EXTENSIONS_SUBDIR).glob(pattern))
            if (p / "SKILL.md").is_file()
        )
    spec = f"{group or '*'}/{EXTENSIONS_SUBDIR}/{pattern}"
    if not matches:
        die(f"拡張バンドルが見つからない(SKILL.md 必須): {root}/{spec}")
    if len(matches) > 1:
        found = ", ".join(str(p.relative_to(root)) for p in matches)
        die(
            f"指定 {name} に複数のバンドルが一致する({found})。"
            "前の階層を足して一意にする"
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
    core = load_core_lock(target / CORE_LOCK_REL)
    if not core:
        print("core: 導入なし")
    for name, record in sorted(core.items()):
        label = name or "(グループ名の記録なし)"
        skills = ", ".join(record["skills"]) or "なし"
        print(f"core {label}: スキル {skills} / エージェント {len(record['agents'])} 件")
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
    p_core.add_argument(
        "groups",
        nargs="*",
        help="配布する用途グループ名(省略時は全グループ)。複数指定できる",
    )
    p_ext = sub.add_parser("ext", help="拡張バンドルを導入する")
    p_ext.add_argument(
        "name",
        help=(
            "バンドル名(<用途グループ>/extensions/<バンドル群>/ 配下)。"
            "複数一致する場合は <バンドル群>/<バンドル名>・<用途グループ>/<バンドル群>/<バンドル名> で絞る"
        ),
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
        cmd_core(root, target, args.groups, dry)
    elif args.command == "ext":
        cmd_ext(root, target, args.name, dry)
    elif args.command == "remove":
        cmd_remove(root, target, args.name, dry)
    elif args.command == "status":
        cmd_status(root, target)


if __name__ == "__main__":
    main()
