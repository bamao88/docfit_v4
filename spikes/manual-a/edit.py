"""In-place edit primitives for the spike: clear text, replace text with a slot, wrap a prototype.

Only the three A⑧ operations exist here (keep / delete text / replace with placeholder); no block is
ever removed or created (D8). Slots are Word content controls tagged docfit:slot:<id> (D15).
"""
import itertools
from copy import deepcopy

from lxml import etree

from ooxml import NS, SLOT_PREFIX, local, own_runs, q, strip_hint

_ids = itertools.count(0x5D0C0001)
KEEP_IN_CLEAR = {q("rPr"), q("lastRenderedPageBreak")}
DROP_ALWAYS = {q("t"), q("tab"), q("sym"), q("instrText"), q("fldChar"), q("drawing"), q("pict"),
               q("object"), q("delText"), q("noBreakHyphen"), q("softHyphen"),
               "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"}


def _sdt_pr(slot_id: str, alias: str):
    pr = etree.Element(q("sdtPr"))
    etree.SubElement(pr, q("alias")).set(q("val"), alias)
    etree.SubElement(pr, q("tag")).set(q("val"), SLOT_PREFIX + slot_id)
    etree.SubElement(pr, q("id")).set(q("val"), str(next(_ids)))
    return pr


def _slot_run_sdt(slot_id: str, alias: str, text: str, rpr):
    sdt = etree.Element(q("sdt"))
    sdt.append(_sdt_pr(slot_id, alias))
    content = etree.SubElement(sdt, q("sdtContent"))
    r = etree.SubElement(content, q("r"))
    if rpr is not None:
        r.append(strip_hint(deepcopy(rpr)))
    t = etree.SubElement(r, q("t"))
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return sdt


def _strip_paragraph(p):
    """Remove every piece of visible content; keep runs' page breaks, bookmarks, section props."""
    for m in list(p.iter(f"{{{NS['m']}}}oMathPara")) + list(p.iter(f"{{{NS['m']}}}oMath")):
        if m.getparent() is not None:
            m.getparent().remove(m)
    for fs in list(p.iter(q("fldSimple"))):
        fs.getparent().remove(fs)
    for r in own_runs(p):
        for c in list(r):
            if c.tag in DROP_ALWAYS or (c.tag == q("br") and c.get(q("type")) != "page"):
                r.remove(c)
        if all(c.tag in KEEP_IN_CLEAR for c in r) and r.find("w:lastRenderedPageBreak", NS) is None:
            r.getparent().remove(r)


def clear(el):
    for p in ([el] if local(el) == "p" else list(el.iter(q("p")))):
        _strip_paragraph(p)


def _first_text_rpr(p):
    for r in own_runs(p):
        t = r.findtext("w:t", namespaces=NS)
        if t and t.strip():
            return r.find("w:rPr", NS)
    for r in own_runs(p):
        if r.find("w:t", NS) is not None:
            return r.find("w:rPr", NS)
    return None


def _anchor(p):
    """Position for an inserted slot: before the first own text run, else at the paragraph end."""
    for r in own_runs(p):
        if r.find("w:t", NS) is not None or r.find("w:tab", NS) is not None:
            return r.getparent(), r.getparent().index(r)
    return p, len(p)


def slot_whole(p, slot_id, alias, text):
    rpr = deepcopy(_first_text_rpr(p))
    parent, idx = _anchor(p)
    marker = etree.Element("marker")
    parent.insert(idx, marker)
    _strip_paragraph(p)
    parent = marker.getparent()
    parent.replace(marker, _slot_run_sdt(slot_id, alias, text, rpr))


def wrap_block(el, slot_id, alias):
    sdt = etree.Element(q("sdt"))
    sdt.append(_sdt_pr(slot_id, alias))
    el.addprevious(sdt)
    etree.SubElement(sdt, q("sdtContent")).append(el)


def _atomize(p):
    """Split own runs so each carries one content child, and each w:t one character."""
    atoms = []
    for r in own_runs(p):
        rpr = r.find("w:rPr", NS)
        children = [c for c in r if c.tag != q("rPr")]
        pieces = []
        for c in children:
            if c.tag == q("t"):
                pieces += [("t", ch) for ch in (c.text or "")]
            else:
                pieces.append(("x", c))
        new_runs = []
        for kind, val in pieces:
            nr = etree.Element(q("r"))
            if rpr is not None:
                nr.append(deepcopy(rpr))
            if kind == "t":
                t = etree.SubElement(nr, q("t"))
                t.text = val
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                atoms.append((nr, val))
            else:
                nr.append(val)
                atoms.append((nr, "\t" if val.tag == q("tab") else None))
            new_runs.append(nr)
        for nr in new_runs:
            r.addprevious(nr)
        r.getparent().remove(r)
    return atoms


def apply_segments(p, segments, slot_meta):
    """segments: resolved [(op, slot, text)]; slot_meta: slot -> (slot_id, alias, placeholder)."""
    atoms = _atomize(p)
    ops = []
    for op, slot, text in segments:
        ops += [(op, slot)] * len(text)
    text_atoms = [a for a in atoms if a[1] is not None]
    assert len(text_atoms) == len(ops), "atom/text length mismatch"
    placed = set()
    for (run, _), (op, slot) in zip(text_atoms, ops):
        if op in ("keep", "label"):
            continue
        if op == "slot" and slot not in placed:
            slot_id, alias, ph = slot_meta[slot]
            run.addprevious(_slot_run_sdt(slot_id, alias, ph, run.find("w:rPr", NS)))
            placed.add(slot)
        run.getparent().remove(run)
    _merge_runs(p)


def _merge_runs(p):
    """Re-join adjacent single-text runs with identical properties (cosmetic, keeps XML small)."""
    for parent in {r.getparent() for r in own_runs(p)}:
        prev = None
        for r in list(parent):
            if r.tag != q("r") or len([c for c in r if c.tag != q("rPr")]) != 1 or r.find("w:t", NS) is None:
                prev = None
                continue
            if prev is not None:
                a, b = prev.find("w:rPr", NS), r.find("w:rPr", NS)
                same = (a is None and b is None) or (a is not None and b is not None
                                                     and etree.tostring(a) == etree.tostring(b))
                if same:
                    prev.find("w:t", NS).text += r.find("w:t", NS).text
                    parent.remove(r)
                    continue
            prev = r
