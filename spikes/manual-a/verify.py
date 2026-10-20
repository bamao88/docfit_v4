"""Manual A⑨: re-read the clean template and diff it against the original, object by object.

The receipt comes from the diff, not from build.py (P12). Checks:
  1. same block objects in the same order (nothing deleted or created, D8);
  2. untouched objects are XML-identical to the original;
  3. edited objects keep their paragraph/table properties, page breaks and section properties,
     and their visible text equals what the spec implies (kept text + placeholders);
  4. every slot tag is unique and matches the fill contract;
  5. every zip part other than word/document.xml is byte-identical.
usage: python -I verify.py specs/<school>.yaml
"""
import json
import sys
import zipfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from ooxml import (NS, block_objects, canonical, load_document, local, object_text, oid, q,  # noqa: E402
                   slot_tag)
from spec import REPO, load_spec, load_tables, placeholder, resolve_segments  # noqa: E402


def expected_text(d, unit_type, orig_text, tables):
    if d is None or d.kind in ("keep", "block"):
        return orig_text
    if d.kind == "clear":
        return "\n".join("" for _ in orig_text.split("\n"))
    if d.kind == "slot":
        return placeholder(unit_type, d.slot, tables)
    out = []
    for op, s, t in resolve_segments(d.segments, orig_text):
        out.append(t if op in ("keep", "label") else
                   "" if op == "del" else None)
        if op == "slot" and placeholder(unit_type, s, tables) not in out:
            out[-1] = placeholder(unit_type, s, tables)
        elif op == "slot":
            out[-1] = ""
    return "".join(out)


def structure_marks(el):
    """Things A must never move: page breaks, section properties, paragraph/table properties."""
    breaks = sum(1 for b in el.iter(q("br")) if b.get(q("type")) == "page")
    sect = [canonical(s) for s in el.iter(q("sectPr"))]
    props = [canonical(x) for x in el.iter(q("pPr"), q("tblPr"), q("trPr"), q("tcPr"))]
    return breaks, sect, props


def verify(spec_path):
    tables = load_tables()
    raw = yaml.safe_load(Path(spec_path).read_text())
    asset = REPO / "assets" / raw["school_id"] / raw["asset_version"]
    orig = block_objects(load_document(raw["source"]))
    spec = load_spec(spec_path, len(orig))
    out_root = load_document(asset / "clean-template.docx")
    out = block_objects(out_root, unwrap_slots=True)
    errors = []
    if len(orig) != len(out):
        errors.append(f"object count {len(orig)} -> {len(out)}")
    for i, (a, b) in enumerate(zip(orig, out), 1):
        d, u = spec.decisions.get(i), spec.unit_of[i]
        if local(a) != local(b):
            errors.append(f"{oid(i)} kind {local(a)} -> {local(b)}")
            continue
        if d is None or d.kind in ("keep", "block"):
            if canonical(a) != canonical(b):
                errors.append(f"{oid(i)} untouched object changed")
            continue
        if structure_marks(a) != structure_marks(b):
            errors.append(f"{oid(i)} structure (breaks/sections/properties) changed")
        want = expected_text(d, u["type"], object_text(a), tables)
        if object_text(b) != want:
            errors.append(f"{oid(i)} text {object_text(b)!r} != expected {want!r}")

    tags = [slot_tag(s) for s in out_root.iter(q("sdt")) if slot_tag(s)]
    contract = json.loads((asset / "fill-contract.json").read_text())
    want_tags = [s["slot_id"] for un in contract["units"] for s in un["slots"] if "tag" in s]
    if len(tags) != len(set(tags)):
        errors.append("duplicate slot tags")
    if sorted(tags) != sorted(want_tags):
        errors.append(f"slot tags differ from contract: {sorted(set(tags) ^ set(want_tags))}")

    with zipfile.ZipFile(raw["source"]) as za, zipfile.ZipFile(asset / "clean-template.docx") as zb:
        if sorted(za.namelist()) != sorted(zb.namelist()):
            errors.append("zip part list changed")
        for n in za.namelist():
            if n != "word/document.xml" and za.read(n) != zb.read(n):
                errors.append(f"part changed: {n}")

    edited = sum(1 for d in spec.decisions.values() if d.kind != "keep")
    status = "PASS" if not errors else "FAIL"
    print(f"{raw['school_id']}: {status} — {len(orig)} objects, {edited} edited, {len(tags)} slots")
    for e in errors[:30]:
        print("  ", e)
    return not errors


if __name__ == "__main__":
    ok = all([verify(p) for p in sys.argv[1:]])
    sys.exit(0 if ok else 1)
