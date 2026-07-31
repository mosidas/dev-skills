"""meta-* スクリプトの共通ロジック。

frontmatter(YAML のサブセット)の解析と、スキル群の配置の走査を 1 箇所に集約する。
meta_check.py・meta_extract.py・meta_loc.py・trigger_check.py が共有し、同じ対象に
対して別々の結論を出さないようにする。Python 3 標準ライブラリのみを使用する。

解釈する記法(サブセット):
  key: value            スカラー(前後の引用符を剥がす)
  key: "value"          引用符つきスカラー
  key: |  / >  / |- 等  ブロックスカラー(後続のインデント行を連結する)
  key:                  ブロックシーケンス(後続の `  - item` 行を集める)
  # comment             行コメント(無視する)

解釈できない行は捨てずに `unparsable` として返す。呼び出し側はこれを「値が違う」
と断定せず、「この解析器が解釈できない記法」として区別して報告する。

配置の走査(D-011):
  スキル本体は用途グループ(ルート直下で `skills/` を持つディレクトリ。例: `dev/`)に置く。
  `meta-*` は配布せず自リポジトリで使うため `.claude/skills/` に置く。両者を同じ関数で
  列挙し、検査・抽出・集計が配置の違いを個別に持たないようにする。

グループの機構(D-014):
  port のサンプル(`ports/`)と拡張バンドル(`extensions/`)はグループ配下に置く。
  走査側がグループの数・名前を前提にしないよう、列挙は `group_subdirs()` に集約する。

グループ固有の規約(D-013):
  グループごとに異なる規約(部品名のプレフィックス・状態名の語尾・レイヤーの割り当て)は
  グループ直下の `group.json` が宣言する。宣言を持たないグループは既定(部品名の照合を
  行わない・状態名の語尾を持たない・レイヤーは 1)で成立し、`meta-*` は特定のグループの
  構造を前提にしない。
"""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
SEQ_ITEM_RE = re.compile(r"^\s+-\s+(.*)$")
BLOCK_SCALAR_RE = re.compile(r"^([|>])([+-]?)(\d*)\s*$")

SKILLS_SUBDIR = "skills"
AGENTS_SUBDIR = "agents"
# グループの機構(port のサンプル・拡張バンドル)を収めるディレクトリ名。
PORTS_SUBDIR = "ports"
EXTENSIONS_SUBDIR = "extensions"
# 自リポジトリ保守用(meta-*)の置き場所。Claude Code がこのリポジトリで読み込む場所でもある。
LOCAL_GROUP = ".claude"
# グループ固有の規約の宣言(グループ直下。skills/・agents/ の外にあるため配布されない)。
GROUP_CONFIG = "group.json"
# 規約が割り当てないスキルのレイヤー(部品)。
DEFAULT_LAYER = 1


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _collect_indented(lines: list[str], start: int) -> tuple[list[str], int]:
    """start 以降の連続するインデント行(と空行)を集める。"""
    body: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if line.strip() and not line.startswith((" ", "\t")):
            break
        body.append(line)
        i += 1
    while body and not body[-1].strip():
        body.pop()
    return body, i


def _split_frontmatter(text: str) -> list[str] | None:
    """先頭 frontmatter の本体行を返す。開始・終了の `---` が無ければ None。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    body: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return body
        body.append(line)
    return None


def parse_frontmatter(text: str) -> tuple[dict, list[str]] | None:
    """frontmatter を解析する。

    返り値: `(値の辞書, 解析できなかった行の一覧)`。frontmatter が無い(または
    閉じの `---` が無い)場合は None。値は str(スカラー・ブロックスカラー)または
    list[str](ブロックシーケンス)。
    """
    body = _split_frontmatter(text)
    if body is None:
        return None
    data: dict = {}
    unparsable: list[str] = []
    i = 0
    while i < len(body):
        line = body[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        m = KEY_RE.match(line)
        if not m:
            unparsable.append(line.rstrip())
            i += 1
            continue
        key, raw = m.group(1), m.group(2).strip()
        block = BLOCK_SCALAR_RE.match(raw)
        if block:
            chunk, i = _collect_indented(body, i + 1)
            joiner = "\n" if block.group(1) == "|" else " "
            data[key] = joiner.join(s.strip() for s in chunk if s.strip())
            continue
        if raw == "":
            chunk, nxt = _collect_indented(body, i + 1)
            items = [SEQ_ITEM_RE.match(s) for s in chunk if s.strip()]
            if chunk and all(items):
                data[key] = [_unquote(m2.group(1).strip()) for m2 in items if m2]
                i = nxt
                continue
            if chunk:
                unparsable.append(line.rstrip())
                i = nxt
                continue
            data[key] = ""
            i += 1
            continue
        data[key] = _unquote(raw)
        i += 1
    return data, unparsable


def scalar(data: dict, key: str) -> str | None:
    """スカラー値を取り出す(リスト等の非スカラーは None)。"""
    value = data.get(key)
    return value if isinstance(value, str) else None


# ---------------------------------------------------------------------------
# 配置の走査


def distributed_groups(root: Path) -> list[Path]:
    """配布対象の用途グループを列挙する(ルート直下で `skills/` を持つディレクトリ)。

    ドットで始まるディレクトリは対象外にする(`.claude` は配布しない meta-* の置き場所)。
    """
    if not root.is_dir():
        return []
    return sorted(
        p
        for p in root.iterdir()
        if p.is_dir()
        and not p.name.startswith(".")
        and (p / SKILLS_SUBDIR).is_dir()
    )


def groups(root: Path) -> list[Path]:
    """スキルを収めるグループを列挙する(配布対象のグループ + `.claude`)。"""
    found = distributed_groups(root)
    local = root / LOCAL_GROUP
    if (local / SKILLS_SUBDIR).is_dir():
        found.append(local)
    return found


def skill_dirs(root: Path) -> list[Path]:
    """スキル 1 件ごとのディレクトリを列挙する(全グループ横断)。"""
    return sorted(
        (
            skill
            for group in groups(root)
            for skill in (group / SKILLS_SUBDIR).iterdir()
            if skill.is_dir()
        ),
        key=lambda p: p.name,
    )


def distributed_skill_dirs(root: Path) -> list[Path]:
    """配布対象のグループに属するスキルを列挙する(`.claude` の `meta-*` を除く)。"""
    return sorted(
        (
            skill
            for group in distributed_groups(root)
            for skill in (group / SKILLS_SUBDIR).iterdir()
            if skill.is_dir()
        ),
        key=lambda p: p.name,
    )


def group_subdirs(root: Path, subdir: str) -> list[Path]:
    """各グループ直下の `<subdir>/` のうち実在するものを列挙する(全グループ横断)。

    `ports/`・`extensions/` はグループの機構であり、グループ配下に置く(D-014)。
    """
    return [group / subdir for group in groups(root) if (group / subdir).is_dir()]


def agent_files(root: Path) -> list[Path]:
    """エージェント定義の Markdown を列挙する(全グループ横断)。"""
    return sorted(
        (
            f
            for group in groups(root)
            if (group / AGENTS_SUBDIR).is_dir()
            for f in (group / AGENTS_SUBDIR).glob("*.md")
        ),
        key=lambda p: p.name,
    )


class GroupConfigError(Exception):
    """グループの規約宣言を読めない(構文が壊れている・型が違う)。"""


def group_config(group: Path) -> dict:
    """グループの規約宣言(`group.json`)を読む。

    宣言が無いグループは空の規約として扱う(既定で成立させる)。読めない宣言は
    黙って既定に落とさず `GroupConfigError` を送出し、呼び出し側が報告する。
    """
    path = group / GROUP_CONFIG
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise GroupConfigError(f"{path} を JSON として読めない: {e}") from e
    if not isinstance(data, dict):
        raise GroupConfigError(f"{path} の最上位がオブジェクトでない")
    return data


def _string_list(config: dict, key: str) -> list[str]:
    value = config.get(key)
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise GroupConfigError(f"{key} は文字列のリストでなければならない")
    return list(value)


def part_prefixes(root: Path) -> list[str]:
    """全グループが宣言する部品名のプレフィックスを集める(重複を除く)。

    部品名らしいトークンの判定に使う。宣言しないグループのスキルは、この判定の
    対象にならない(実在しない名前を見つけられない代わりに、誤検出も出さない)。
    """
    found: list[str] = []
    for group in groups(root):
        for prefix in _string_list(group_config(group), "part_prefixes"):
            if prefix not in found:
                found.append(prefix)
    return found


def state_suffixes(skill: Path) -> list[str]:
    """スキルが属するグループが宣言する、状態名らしいトークンの語尾。"""
    return _string_list(group_config(group_of(skill)), "state_suffixes")


def layer_of(skill: Path) -> int:
    """スキルのレイヤーを、属するグループの規約から決める(既定は部品)。"""
    layers = group_config(group_of(skill)).get("layers")
    if layers is None:
        return DEFAULT_LAYER
    if not isinstance(layers, dict):
        raise GroupConfigError("layers はオブジェクトでなければならない")
    for layer, patterns in sorted(layers.items()):
        if not isinstance(patterns, list):
            raise GroupConfigError(f"layers.{layer} は配列でなければならない")
        if any(fnmatch.fnmatchcase(skill.name, str(p)) for p in patterns):
            try:
                return int(layer)
            except ValueError as e:
                raise GroupConfigError(f"layers のキー {layer!r} が整数でない") from e
    return DEFAULT_LAYER


def family_of(group: Path) -> str:
    """グループのディレクトリから分類名を返す(`.claude` は meta-* を収めるため "meta")。"""
    return "meta" if group.name == LOCAL_GROUP else group.name


def group_of(path: Path) -> Path:
    """スキルディレクトリ・エージェントファイルから、それを収めるグループを返す。"""
    return path.parent.parent


def is_root(path: Path) -> bool:
    """dev-skills のルートか(スキルを収めるグループを 1 つ以上持つか)。"""
    return bool(groups(path))


def find_root(start: Path) -> Path | None:
    """スキルを収めるグループを持つディレクトリを start から上方向に探す。"""
    for d in (start, *start.parents):
        if is_root(d):
            return d
    return None


def group_docs(root: Path) -> list[Path]:
    """スキル群を構成する Markdown を列挙する(SKILL・references・templates・agents)。"""
    docs: list[Path] = []
    for group in groups(root):
        for sub in (SKILLS_SUBDIR, AGENTS_SUBDIR):
            d = group / sub
            if d.is_dir():
                docs.extend(p for p in d.rglob("*.md") if p.is_file())
    return sorted(set(docs))
