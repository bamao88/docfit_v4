"""Manual A⑧: apply a hand-written spec to a school original, emit the template asset.

usage: python -I build.py specs/<school>.yaml
writes assets/<school>/<version>/{clean-template.docx, fill-contract.json, unit-table.json, manifest.json, review.json}
"""
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import edit  # noqa: E402
from ooxml import (block_objects, fingerprint, has_field, has_sectpr, load_document, local,  # noqa: E402
                   object_text, oid, sha256_file)
from spec import REPO, handling, load_spec, load_tables, placeholder, resolve_segments  # noqa: E402

from lxml import etree  # noqa: E402


def header(artifact, spec, tables, step="A8-manual"):
    rev = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    return {"artifact": artifact, "schema_version": "0", "step": step,
            "code_version": f"{rev}+spikes/manual-a",
            "inputs": [{"name": "source", "path": str(spec.source), "sha256": sha256_file(spec.source)}],
            "datatables_version": tables["version"]["datatables_version"],
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def slot_used(d):
    if d.kind in ("slot", "block"):
        return [(d.slot, d.kind)]
    if d.kind == "segments":
        return [(s, op) for op, s, _ in d.segments if op in ("slot", "label")]
    return []


def check(spec, tables, objs):
    """Completeness/uniqueness only (A④⑦): units are typed, decisions stay in fill units, slots exist once."""
    for u in spec.units:
        u["handling"] = handling(u["type"], tables)
        seen = set()
        for i in range(u["start"], u["end"] + 1):
            d = spec.decisions.get(i)
            if d is None or d.kind == "keep":
                continue
            if u["handling"] == "keep":
                raise ValueError(f"{oid(i)}: decision in keep unit {u['id']}")
            sk = tables["skeletons"][u["type"]]
            if d.kind == "clear" and d.slot and d.slot not in sk:
                raise ValueError(f"{oid(i)}: unknown role note {d.slot}")
            for s, _ in slot_used(d):
                if s not in sk:
                    raise ValueError(f"{oid(i)}: slot {s} not in skeleton {u['type']}")
                if s in seen:
                    raise ValueError(f"{oid(i)}: slot {s} used twice in {u['id']}")
                seen.add(s)
            if d.kind in ("segments", "slot") and local(objs[i - 1]) != "p":
                raise ValueError(f"{oid(i)}: text slot on non-paragraph")
            if d.kind == "block" and local(objs[i - 1]) == "p" and has_sectpr(objs[i - 1]):
                raise ValueError(f"{oid(i)}: cannot wrap a section-ending paragraph")
        if u["handling"] == "fill" and not any(
                tables["skeletons"][u["type"]][s]["kind"] in ("field", "structure") for s in seen):
            raise ValueError(f"{u['id']}: fill unit without any field/structure slot (would downgrade)")


def build(spec_path):
    tables = load_tables()
    root = load_document_from(spec_path)
    objs = block_objects(root)
    spec = load_spec(spec_path, len(objs))
    check(spec, tables, objs)
    fps = {i: fingerprint(objs[i - 1]) for i, d in spec.decisions.items() if d.kind != "keep"}

    units_out, roles_seen, conflicts, generated = [], {}, {}, []
    for u in spec.units:
        uid, utype = u["id"], u["type"]
        slots, region_start, protos = [], None, {}
        for i in range(u["start"], u["end"] + 1):
            d, el = spec.decisions.get(i), objs[i - 1]
            if d is None or d.kind == "keep":
                continue
            region_start = region_start or (i if d.kind != "segments" else None)
            sk = tables["skeletons"].get(utype, {})
            if d.kind == "clear":
                if d.slot:
                    conflicts.setdefault(sk[d.slot]["ref"], []).append((oid(i), fps[i]))
                edit.clear(el)
                continue
            if d.kind == "segments":
                segs = resolve_segments(d.segments, object_text(el))
                meta = {}
                for op, s, text in segs:
                    entry = {"slot_id": f"{uid}.{s}", "skeleton_slot": s, "kind": sk[s]["kind"],
                             "object": oid(i)}
                    if op == "label":
                        entry["text"] = text
                    else:
                        meta[s] = (entry["slot_id"], s, placeholder(utype, s, tables))
                        entry.update(ref=sk[s]["ref"], optional=sk[s]["optional"],
                                     tag=f"docfit:slot:{entry['slot_id']}", wrap="run")
                    if op in ("label", "slot"):
                        slots.append(entry)
                edit.apply_segments(el, segs, meta)
                continue
            s = d.slot
            entry = {"slot_id": f"{uid}.{s}", "skeleton_slot": s, "kind": sk[s]["kind"],
                     "ref": sk[s]["ref"], "optional": sk[s]["optional"], "object": oid(i),
                     "tag": f"docfit:slot:{uid}.{s}", "wrap": "run" if d.kind == "slot" else "block"}
            slots.append(entry)
            if sk[s]["kind"] == "structure":
                protos[sk[s]["ref"]] = entry["slot_id"]
                roles_seen[sk[s]["ref"]] = (entry["slot_id"], fps[i])
            if d.kind == "slot":
                edit.slot_whole(el, entry["slot_id"], s, placeholder(utype, s, tables))
            else:
                edit.wrap_block(el, entry["slot_id"], s)
        if protos:
            inner = range(region_start, u["end"])
            brk = ("section" if any(has_sectpr(objs[k - 1]) for k in inner) else "none")
            slots.insert(0, {"slot_id": f"{uid}.content", "skeleton_slot": "*", "kind": "structure",
                             "ref": utype, "region": [oid(region_start), oid(u["end"])],
                             "prototypes": protos, "repeat_break": brk,
                             "remove_prototypes_after_fill": True})
        if utype in ("toc", "list_of_figures", "list_of_tables"):
            fld = [oid(k) for k in range(u["start"], u["end"] + 1) if has_field(objs[k - 1])]
            generated.append({"unit_id": uid, "kind": utype, "field_objects": fld,
                              "mechanism": "word_field" if fld else "static_text"})
        units_out.append({"unit_id": uid, "type": utype, "handling": u["handling"],
                          "range": [oid(u["start"]), oid(u["end"])],
                          "display_name": u["name"], "slots": slots})

    roles_out = []
    body_roles = [s["ref"] for s in tables["skeletons"]["body"].values()] + ["reference_entry"]
    for role in body_roles:
        if role in roles_seen:
            sid, fp = roles_seen[role]
            others = sorted({(o, f) for o, f in conflicts.get(role, []) if f != fp})
            roles_out.append({"role": role, "source": "school", "prototype": sid, "fingerprint": fp,
                              "conflicts": [{"object": o, "fingerprint": f} for o, f in others]})
        else:
            roles_out.append({"role": role, "source": "preset",
                              "prototype": f"preset:general-style@pending/{role}"})

    out = REPO / "assets" / spec.school_id / spec.asset_version
    out.mkdir(parents=True, exist_ok=True)
    write_docx(spec.source, root, out / "clean-template.docx")
    contract = header("fill-contract", spec, tables) | {
        "school_id": spec.school_id, "asset_version": spec.asset_version,
        "source_sha256": sha256_file(spec.source), "units": units_out, "roles": roles_out,
        "generated": generated}
    dump(out / "fill-contract.json", contract)
    dump(out / "unit-table.json", header("unit-table", spec, tables, "A4-manual") | {"units": [
        {"unit_id": u["id"], "type": u["type"], "handling": u["handling"], "display_name": u["name"],
         "range": [oid(u["start"]), oid(u["end"])],
         "starts_with": first_words(objs_text_cache[spec.school_id], u)} for u in spec.units]})
    dump(out / "manifest.json", {
        "school_id": spec.school_id, "asset_version": spec.asset_version,
        "source": str(spec.source), "source_sha256": sha256_file(spec.source),
        "datatables_version": tables["version"]["datatables_version"],
        "code_version": contract["code_version"], "produced_by": "manual (spikes/manual-a), not the A pipeline",
        "spec": str(Path(spec_path).resolve().relative_to(REPO))})
    review = out / "review.json"
    if not review.exists():
        dump(review, {"status": "pending", "reviewer": None, "date": None,
                      "style_conflict_choices": {}, "notes": spec.notes})
    print(f"{spec.school_id}: {len(objs)} objects, {len(spec.units)} units -> {out.relative_to(REPO)}")


objs_text_cache = {}


def load_document_from(spec_path):
    import yaml
    raw = yaml.safe_load(Path(spec_path).read_text())
    root = load_document(raw["source"])
    objs_text_cache[raw["school_id"]] = [object_text(o) for o in block_objects(root)]
    return root


def first_words(texts, u):
    for k in range(u["start"], u["end"] + 1):
        t = texts[k - 1].strip()
        if t:
            return t[:20]
    return ""


def write_docx(src, root, dst):
    data = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            zout.writestr(item, data if item.filename == "word/document.xml" else zin.read(item.filename))


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        build(p)
