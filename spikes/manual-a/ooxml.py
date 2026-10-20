"""Shared OOXML helpers for the manual template-extraction spike (read-only side)."""
import hashlib
import zipfile
from copy import deepcopy

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W, "m": M}
BLOCK = ("p", "tbl", "sdt")
SLOT_PREFIX = "docfit:slot:"
# Runs inside these containers belong to drawings/text boxes, not to the paragraph's own text.
FOREIGN = {f"{{{W}}}drawing", f"{{{W}}}pict", f"{{{W}}}txbxContent",
           "{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"}
VOLATILE_ATTRS = ("rsidR", "rsidRPr", "rsidRDefault", "rsidP", "rsidDel", "rsidSect", "rsidTr")


def q(tag: str) -> str:
    return f"{{{W}}}{tag}"


def local(el) -> str:
    return etree.QName(el).localname


def sha256_file(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_document(path):
    with zipfile.ZipFile(path) as z:
        return etree.fromstring(z.read("word/document.xml"))


def block_objects(root, unwrap_slots=False):
    """Body-level block objects in order: p / tbl / sdt.

    With unwrap_slots, a block sdt carrying a docfit slot tag is replaced by its single child,
    so an extracted template lines up one-to-one with its source (A never deletes blocks, D8).
    """
    out = []
    for el in root.find("w:body", NS):
        if local(el) not in BLOCK:
            continue
        if unwrap_slots and local(el) == "sdt" and slot_tag(el):
            inner = [c for c in el.find("w:sdtContent", NS) if local(c) in BLOCK]
            assert len(inner) == 1, "slot block sdt must wrap exactly one block"
            out.append(inner[0])
        else:
            out.append(el)
    return out


def slot_tag(sdt):
    tag = sdt.find("w:sdtPr/w:tag", NS)
    val = tag.get(q("val")) if tag is not None else ""
    return val[len(SLOT_PREFIX):] if val.startswith(SLOT_PREFIX) else None


def own_runs(p):
    """Runs that carry the paragraph's own content (not those inside drawings or text boxes)."""
    runs = []
    for r in p.iter(q("r")):
        anc, foreign = r.getparent(), False
        while anc is not None and anc is not p:
            if anc.tag in FOREIGN:
                foreign = True
                break
            anc = anc.getparent()
        if not foreign:
            runs.append(r)
    return runs


def own_text(p) -> str:
    """Visible text of a paragraph: w:t joined, w:tab as a tab. Field codes excluded."""
    out = []
    for r in own_runs(p):
        for c in r:
            if c.tag == q("t"):
                out.append(c.text or "")
            elif c.tag == q("tab"):
                out.append("\t")
    return "".join(out)


def object_text(el) -> str:
    if local(el) == "p":
        return own_text(el)
    return "\n".join(own_text(p) for p in el.iter(q("p")))


def canonical(el) -> bytes:
    """Element XML with volatile revision ids removed, for equality checks and fingerprints."""
    el = deepcopy(el)
    for node in el.iter():
        for a in VOLATILE_ATTRS:
            node.attrib.pop(q(a), None)
    return etree.tostring(el, method="c14n")


def fingerprint(el) -> str:
    """Format fingerprint: paragraph/table properties + first text run's properties.

    Hint colours and highlights are example markers, not format (A R3), so they are dropped.
    """
    parts = []
    first_p = el if local(el) == "p" else el.find(".//w:p", NS)
    if local(el) == "tbl":
        tp = el.find("w:tblPr", NS)
        parts.append(canonical(tp) if tp is not None else b"")
    if first_p is not None:
        ppr = first_p.find("w:pPr", NS)
        if ppr is not None:
            ppr = deepcopy(ppr)
            for x in ppr.findall("w:sectPr", NS) + ppr.findall("w:rPr", NS):
                ppr.remove(x)
            parts.append(canonical(ppr))
        for r in own_runs(first_p):
            if r.find("w:t", NS) is not None and (r.findtext("w:t", namespaces=NS) or "").strip():
                rpr = r.find("w:rPr", NS)
                if rpr is not None:
                    parts.append(canonical(strip_hint(deepcopy(rpr))))
                break
    return hashlib.sha256(b"|".join(parts)).hexdigest()[:12]


def strip_hint(rpr):
    for tag in ("color", "highlight"):
        for x in rpr.findall(f"w:{tag}", NS):
            rpr.remove(x)
    return rpr


def has_sectpr(el) -> bool:
    return el.find("w:pPr/w:sectPr", NS) is not None


def has_field(el) -> bool:
    return el.find(".//w:fldChar", NS) is not None or el.find(".//w:fldSimple", NS) is not None


def oid(n: int) -> str:
    return f"T:body:{n:04d}"


def has_content(el) -> bool:
    """Anything a reader would see: text, a drawing, a formula, or a table."""
    return (local(el) != "p" or bool(own_text(el).strip())
            or el.find(".//w:drawing", NS) is not None or el.find(".//w:pict", NS) is not None
            or el.find(".//m:oMath", NS) is not None)
