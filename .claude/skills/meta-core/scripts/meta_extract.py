#!/usr/bin/env python3
"""DESIGN.md 構造層の素材抽出(read-only)。

スキル群の定義(SSoT)から、DESIGN.md の構造層(部品一覧・レイヤー構成・状態機械・
inject グラフ・エージェント)を決定論的に抽出し、JSON で出力する。分類とレイヤーは
グループの規約(`group.json`)が決め、規約を持たないグループは全スキルを部品として扱う。meta-doc が
この JSON をもとに構造層の散文を生成する。判断層(根拠・トレードオフ)は含まない
(それは `.meta/decisions/` の担当。principles.md §3)。ファイルを書き換えない。

使い方:
  meta_extract.py [--root <dev-skills のルート>] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import meta_lib  # noqa: E402


def die(msg: str) -> None:
    print(f"エラー: {msg}", file=sys.stderr)
    sys.exit(1)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter_scalars(text: str) -> dict:
    """frontmatter からスカラー値(name・description・model 等)を取り出す。

    解析は `meta_lib` の YAML サブセット。非スカラー(ブロックシーケンス)は除く。
    """
    parsed = meta_lib.parse_frontmatter(text)
    if parsed is None:
        return {}
    return {k: v for k, v in parsed[0].items() if isinstance(v, str) and v.strip()}


def classify(skill: Path) -> tuple[str, int]:
    """スキルのディレクトリから (分類, レイヤー番号) を決める。

    分類はスキルを収めるグループ名(`.claude` に置く meta-* は "meta")。レイヤーは
    グループの規約(`group.json` の layers)が割り当て、割り当てが無ければ部品(1)と
    する。レイヤー構造を持たないグループは規約を書かず、全スキルが部品になる(D-013)。
    """
    return meta_lib.family_of(meta_lib.group_of(skill)), meta_lib.layer_of(skill)


def extract_parts(root: Path) -> list[dict]:
    parts: list[dict] = []
    for skill in meta_lib.skill_dirs(root):
        skill_md = skill / "SKILL.md"
        fm = parse_frontmatter_scalars(read_text(skill_md)) if skill_md.is_file() else {}
        family, layer = classify(skill)
        parts.append(
            {
                "name": skill.name,
                "family": family,
                "layer": layer,
                "kind": "スキル",
                "has_skill_md": skill_md.is_file(),
                "has_workflow": (skill / "workflow.json").is_file(),
                "role": fm.get("description", ""),
            }
        )
    return parts


def _module_doc_first_line(text: str) -> str:
    """モジュール docstring の最初の非空行を返す。"""
    m = re.search(r'"""(.*?)"""', text, re.S)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        s = line.strip()
        if s:
            return s
    return ""


def extract_scripts(root: Path) -> list[dict]:
    """各スキルの `scripts/*.py` を抽出する(分類・レイヤー・役割)。"""
    scripts: list[dict] = []
    for skill in meta_lib.skill_dirs(root):
        family, layer = classify(skill)
        for py in sorted((skill / "scripts").glob("*.py")):
            if py.name == "__init__.py":
                continue
            scripts.append(
                {
                    "name": f"{skill.name}/scripts/{py.name}",
                    "family": family,
                    "layer": layer,
                    "kind": "スクリプト",
                    "role": _module_doc_first_line(read_text(py)),
                }
            )
    return scripts


def extract_state_machines(root: Path) -> list[dict]:
    machines: list[dict] = []
    workflows = sorted(
        (wf for skill in meta_lib.skill_dirs(root) for wf in skill.glob("workflow.json")),
        key=lambda p: p.parent.name,
    )
    for wf in workflows:
        try:
            defn = json.loads(read_text(wf))
        except (OSError, json.JSONDecodeError) as e:
            machines.append({"owner": wf.parent.name, "error": str(e)})
            continue
        gates: list[str] = []
        for t in defn.get("transitions", []):
            g = t.get("gate")
            if g and g not in gates:
                gates.append(g)
        machines.append(
            {
                "owner": wf.parent.name,
                "name": defn.get("name"),
                "states": defn.get("states", []),
                "initial": defn.get("initial"),
                "final": defn.get("final", []),
                "gates": gates,
                "transitions": [
                    {"from": t.get("from"), "to": t.get("to"), "gate": t.get("gate")}
                    for t in defn.get("transitions", [])
                ],
                "artifacts": defn.get("artifacts", {}),
            }
        )
    return machines


def extract_inject_graph(root: Path) -> dict:
    """port name -> {inject: [skills], condition, description}。

    `ports/templates/` は新規 port の雛形(プレースホルダ)のため除く。
    """
    ports_dir = root / "ports"
    graph: dict = {}
    if not ports_dir.is_dir():
        return graph
    for path in sorted(ports_dir.rglob("*.md")):
        if "templates" in path.relative_to(ports_dir).parts:
            continue
        parsed = meta_lib.parse_frontmatter(read_text(path))
        if parsed is None:
            continue
        data = parsed[0]
        injects = data.get("inject")
        key = meta_lib.scalar(data, "name") or path.stem
        graph[key] = {
            "inject": list(injects) if isinstance(injects, list) else [],
            "condition": meta_lib.scalar(data, "condition"),
            "description": meta_lib.scalar(data, "description"),
        }
    return graph


def extract_agents(root: Path) -> list[dict]:
    """エージェント定義を抽出する。

    エージェントはグループの実行資源であり、スキルから名前で参照される。属する
    グループの基盤(レイヤー 0)として扱う。
    """
    agents: list[dict] = []
    for path in meta_lib.agent_files(root):
        fm = parse_frontmatter_scalars(read_text(path))
        agents.append(
            {
                "name": fm.get("name", path.stem),
                "family": meta_lib.family_of(meta_lib.group_of(path)),
                "layer": 0,
                "kind": "エージェント",
                "model": fm.get("model", ""),
                "role": fm.get("description", ""),
            }
        )
    return agents


def main() -> None:
    parser = argparse.ArgumentParser(description="DESIGN.md 構造層の素材抽出(read-only)")
    parser.add_argument(
        "--root", help="dev-skills のルート(既定: スキルのグループを上方向に探索)"
    )
    parser.add_argument(
        "--json", action="store_true", help="JSON で出力する(既定でも JSON)"
    )
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

    inventory = {
        "parts": extract_parts(root),
        "scripts": extract_scripts(root),
        "state_machines": extract_state_machines(root),
        "inject_graph": extract_inject_graph(root),
        "agents": extract_agents(root),
    }
    print(json.dumps(inventory, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
