"""Load a hand-written extraction spec and the data tables, normalised into per-object decisions.

A spec is the manual stand-in for A③ (unit table) and A⑥ (in-unit decisions). Decision forms:
  keep                          leave the object untouched (default)
  clear | [clear, <slot>]       delete all text in the object; <slot> notes which role it exemplified
  [slot, <slot>]                the whole paragraph becomes slot <slot> (placeholder in a content control)
  [block, <slot>]               composite prototype (figure/table/equation): wrapped untouched in a block content control
  [[op, ...], ...]              segments covering the paragraph text in order:
                                [keep, text] [del, text] [label, <slot>, text] [slot, <slot>, text]; text "*" = the rest
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"


@dataclass
class Decision:
    kind: str                      # keep | clear | slot | block | segments
    slot: str | None = None        # skeleton slot name (for clear: role it exemplified)
    segments: list = field(default_factory=list)  # [(op, slot|None, text)]


@dataclass
class Spec:
    school_id: str
    source: Path
    asset_version: str
    units: list
    decisions: dict                # object index -> Decision
    unit_of: dict                  # object index -> unit dict
    notes: list


def load_tables():
    def y(p):
        return yaml.safe_load((DATA / p).read_text())
    fields = {f["id"]: f for f in y("registry/fields.yaml")["fields"]}
    roles = {r["id"]: r for r in y("registry/roles.yaml")["roles"]}
    unit_types = {u["id"]: u for u in y("unit-types.yaml")["unit_types"]}
    skeletons = {p.stem: {s["name"]: s for s in yaml.safe_load(p.read_text())["slots"]}
                 for p in (DATA / "skeletons").glob("*.yaml")}
    version = y("version.yaml")
    return dict(fields=fields, roles=roles, unit_types=unit_types, skeletons=skeletons, version=version)


def handling(unit_type: str, tables) -> str:
    """Handling comes from the table, never from the spec (00-product.md §4.7)."""
    t = tables["unit_types"].get(unit_type)
    if t is None or t["handling"] != "fill" or unit_type not in tables["skeletons"]:
        return "keep"
    return "fill"


def parse_decision(raw) -> Decision:
    if raw in (None, "keep"):
        return Decision("keep")
    if raw == "clear":
        return Decision("clear")
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        segs = []
        for s in raw:
            if s[0] in ("keep", "del"):
                segs.append((s[0], None, s[1]))
            elif s[0] in ("label", "slot"):
                segs.append((s[0], s[1], s[2]))
            else:
                raise ValueError(f"bad segment op {s}")
        return Decision("segments", segments=segs)
    if isinstance(raw, list) and raw[0] in ("clear", "slot", "block"):
        return Decision(raw[0], slot=raw[1])
    raise ValueError(f"bad decision {raw!r}")


def load_spec(path, n_objects: int) -> Spec:
    raw = yaml.safe_load(Path(path).read_text())
    units, unit_of = raw["units"], {}
    for u in units:
        for i in range(u["start"], u["end"] + 1):
            if i in unit_of:
                raise ValueError(f"object {i} in two units")
            unit_of[i] = u
    missing = [i for i in range(1, n_objects + 1) if i not in unit_of]
    if missing:
        raise ValueError(f"objects not in any unit: {missing[:10]}")
    decisions = {i: parse_decision(v) for i, v in (raw.get("decisions") or {}).items()}
    for u in units:
        default = u.get("default")
        if default:
            for i in range(u["start"], u["end"] + 1):
                decisions.setdefault(i, parse_decision(default))
    return Spec(raw["school_id"], Path(raw["source"]), raw["asset_version"], units,
                decisions, unit_of, raw.get("notes") or [])


def placeholder(unit_type: str, slot: str, tables) -> str:
    sk = tables["skeletons"][unit_type][slot]
    ref = sk.get("ref")
    name = (tables["fields"].get(ref) or tables["roles"].get(ref) or {}).get("name", slot)
    return f"【{name}】"


def resolve_segments(segs, text: str):
    """Expand '*' and check the segments cover the paragraph text exactly, in order."""
    out, pos = [], 0
    for op, slot, t in segs:
        if t == "*":
            t = text[pos:]
        if text[pos:pos + len(t)] != t:
            raise ValueError(f"segment {t!r} does not match text at {pos}: {text[pos:pos + 40]!r}")
        out.append((op, slot, t))
        pos += len(t)
    if pos != len(text):
        raise ValueError(f"segments leave text uncovered: {text[pos:]!r}")
    return out
