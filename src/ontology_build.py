#!/usr/bin/env python3
"""
Ontology builder: harvest taxable categories from definitional articles.

Categories live in definitional provisions, not rate provisions. The hand-built
fixture was drawn from rate provisions alone and silently missed ten of the
twelve categories UU 1/2022 Pasal 55(1) enumerates, which is why this runs
before the norm extractor -- `applies_to` can only reference ids that exist.

`src/structure.py` has already done the parsing: an enumerated list arrives as
`huruf` objects with citations and offsets. The work here is deciding which
lists are definitions of a taxable thing, which are procedure, and which are
*exclusions* -- and then not merging across instruments.

Two outputs, and the split is by rank, not by confidence:

  categories       from national instruments. UU 1/2022 Pasal 55(1) is the
                   frozen, scoreable set the paper reports against.
  pending_review   everything a Perda or Perwal introduces, plus every
                   proposed subsumption edge. `karaoke_keluarga` under
                   `karaoke` is a legal judgement about whether a local
                   subdivision falls inside a statutory term, and nothing here
                   is entitled to make it.
"""

import argparse
import collections
import json
import re
from pathlib import Path

from slotting import canonical

# --------------------------------------------------------------- rank

# Instrument rank drives the live/pending split. Names are not uniform --
# Lhokseumawe's is a Qanun and the Perwal tier spells itself four ways -- so
# match on the filename shape rather than on any wording inside the document.
NATIONAL = re.compile(r"^(UU|PP)_", re.I)


def instrument_rank(doc_id):
    if NATIONAL.match(doc_id):
        return "national"
    if re.search(r"perwal|perwali|peraturan_wali", doc_id, re.I):
        return "perwal"
    return "perda"


# ------------------------------------------------------- the enumeration gate

# What opens a definitional list. `meliputi` (489 in the corpus) and `terdiri
# atas` (198) carry almost all of it; the rest are long-tail phrasings of the
# same move. `berupa` is deliberately absent -- its 117 occurrences are
# overwhelmingly `sanksi administratif berupa:`, which enumerates penalties,
# not taxable things.
OPENERS = re.compile(
    r"\b(meliputi|terdiri\s+atas|terdiri\s+dari|mencakup|adalah|yaitu)\s*:?\s*$", re.I)

# An exclusion list looks exactly like a definition and means the opposite.
# UU Pasal 55(2) -- `Yang dikecualikan dari Jasa Kesenian dan Hiburan ...` --
# would otherwise contribute three categories that are by definition not
# taxable.
EXCLUSION = re.compile(r"\b(dikecualikan|tidak\s+termasuk|bukan\s+merupakan|"
                       r"tidak\s+dikenakan)\b", re.I)

# Not every definitional list defines a taxable thing. `Keadaan kahar meliputi:`
# and `Wewenang penyidik meliputi:` are the same drafting move applied to
# procedure. Measured on UU 1/2022 and PP 35/2023, roughly 45% of harvested
# subjects are tax objects and the rest are procedural.
#
# This tags rather than filters, because the boundary is not always crisp and
# dropping a list makes it invisible. `applies_to` should be resolved against
# `taxable` subjects; the rest stay in the file so a later pass can reconsider
# them without re-harvesting.
TAXABLE_SUBJECT = re.compile(
    r"\b(objek\s+(pajak|retribusi|pbjt|bphtb)|jenis\s+(pajak|retribusi)|"
    r"^jasa\b|^pajak\b|merupakan\s+objek|dasar\s+pengenaan)\b", re.I)


# The chapeau's subject: what is being enumerated. Everything from the start up
# to the first cross-reference or the opener itself.
CROSSREF = re.compile(r"\s+(sebagaimana\s+dimaksud|yang\s+dipungut|yang\s+"
                      r"selanjutnya|dalam\s+Pasal)\b", re.I)

# An open-textured tail leaves the category's outer boundary undetermined. It
# does not undermine the items the drafter named -- see CLAUDE.md.
OPEN_TEXTURED = re.compile(r"\bdan\s+(sejenisnya|lain-lain|lainnya)\b", re.I)


def chapeau_of(container, children, doc_start_key="start"):
    """The container's own text, up to where its first huruf child begins."""
    offset = children[0][doc_start_key] - container[doc_start_key]
    text = canonical(container["text"][:offset])
    # `structure.py` puts the huruf marker outside the child's span, so the
    # chapeau ends with a dangling `a.` that has to come off.
    return re.sub(r"\s*[a-zA-Z][.)]\s*$", "", text)


def subject_of(chapeau):
    """The defined term a list expands. `Jasa Kesenian dan Hiburan ... meliputi:`
    -> `Jasa Kesenian dan Hiburan`."""
    head = OPENERS.sub("", chapeau).strip()
    head = CROSSREF.split(head)[0].strip()
    head = re.sub(r"^\(\d+\)\s*", "", head)
    head = head.strip(" ,.:;")
    return head or None


# ------------------------------------------------------------------ splitting

# A huruf may name one service or several. `diskotek, karaoke, kelab malam,
# bar, dan mandi uap/spa` is five; `tontonan film atau bentuk tontonan audio
# visual lainnya yang dipertontonkan secara langsung di suatu lokasi tertentu`
# is one long noun phrase and splitting it on commas would invent categories.
#
# The discriminator is subordination. A flat list has no clause markers and
# short members; anything carrying `yang`, `dengan`, `untuk` or a trailing
# `lainnya` is a single qualified concept.
SUBORDINATOR = re.compile(
    r"\b(yang|dengan|untuk|dalam|secara|atas|dari|pada|lainnya|sejenisnya|"
    r"berdasarkan|melalui|terhadap)\b", re.I)
SPLIT_ON = re.compile(r"\s*,\s*|\s+dan/atau\s+|\s+dan\s+|\s+atau\s+", re.I)
LEADING_CONJ = re.compile(r"^(dan/atau|dan|atau)\s+", re.I)
MAX_MEMBER_WORDS = 4


def split_services(text):
    """Members of a flat enumerated huruf, or None if it is one concept.

    Returns (members, reason). `reason` explains a refusal so the coverage log
    can say why a huruf produced only itself.
    """
    body = canonical(text).strip().rstrip(".;")
    body = re.sub(r"[;,]?\s*(dan|atau|dan/atau)\s*$", "", body, flags=re.I).strip()
    if not body:
        return None, "empty"
    if SUBORDINATOR.search(body):
        return None, "qualified_by_subordinate_clause"
    # A comma matches before ` dan ` in the alternation, so the final member of
    # `bar, dan mandi uap/spa` arrives with its conjunction attached. Strip it
    # per member rather than reordering the alternation, which would split
    # `dan/atau` inconsistently.
    members = [LEADING_CONJ.sub("", m).strip(" .;,")
               for m in SPLIT_ON.split(body) if m.strip(" .;,")]
    members = [m for m in members if m]
    if len(members) < 2:
        return None, "single_member"
    if any(len(m.split()) > MAX_MEMBER_WORDS for m in members):
        return None, "member_too_long_to_be_a_bare_term"
    return members, None


# `pergelaran kesenian, musik, tari, dan/atau busana` does not name a category
# `musik`; it names `pergelaran musik`. The head distributes across the list,
# and 3 of the 5 splits in UU Pasal 55(1) do it -- huruf b (pergelaran), f
# (pertunjukan) and j (rekreasi). Distributing it automatically would be a
# reading of the provision, and getting it wrong invents categories, so the
# split is emitted as found and flagged for a human.
def distributive_head(members):
    """The candidate head if the first member looks like it carries one."""
    if len(members) < 3:
        return None
    first = members[0].split()
    if len(first) < 2:
        return None
    if all(len(m.split()) < len(first) for m in members[1:]):
        return first[0]
    return None


# ------------------------------------------------------------------------ ids

MAX_ID_WORDS = 5

# A huruf's text sometimes runs past the end of the provision, because a
# section heading or a missed sibling marker was swallowed into the unit -- the
# ~89 known segmentation leaks. `Pajak Sarang Burung Walet. Bagian Kedua
# Rincian ...` is one huruf plus the heading that follows it. Cut at the
# heading rather than dropping the huruf, and refuse a label that is still
# implausibly long afterwards.
HEADING_BLEED = re.compile(r"\s*\b(BAB|Bagian|Paragraf|Pasal)\b\s+[A-Z0-9]")
MAX_LABEL_WORDS = 40


def trim_label(text):
    """Strip a swallowed heading and the trailing conjunction. Returns
    (label, bled) so the caller can log a leak rather than hide it."""
    lab = canonical(text).strip().rstrip(".;")
    m = HEADING_BLEED.search(lab)
    bled = bool(m)
    if m:
        lab = lab[:m.start()].rstrip(" .;,:")
    lab = re.sub(r"[;,]?\s*(dan|atau|dan/atau)\s*$", "", lab, flags=re.I).strip()
    return lab, bled


def slug(label):
    s = canonical(label).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")[:60]


def citation_slug(doc_id, citation):
    """A stable id for a node whose text is a list or a long qualified phrase.

    `diskotek, karaoke, kelab malam, bar, dan mandi uap/spa` is a statutory
    bracket, not a term -- Pasal 58(2)'s band applies to exactly this huruf --
    so it needs a node, but sluggifying the whole sentence produces an id no
    one can cite. Name it by where it is instead.
    """
    doc = re.sub(r"[^a-z0-9]+", "_", doc_id.lower())[:24].strip("_")
    cite = re.sub(r"[^a-z0-9]+", "_", citation.lower()).strip("_")
    return f"{doc}__{cite}"


def is_term_like(label):
    """Short enough, and not a list, to serve as its own id."""
    return len(canonical(label).split()) <= MAX_ID_WORDS


# -------------------------------------------------------------------- harvest

def containers(pasal):
    """Every unit that can own a huruf list, with its children."""
    out = []
    if pasal.get("huruf"):
        out.append((pasal, pasal["huruf"]))
    for a in pasal.get("ayat") or []:
        if a.get("huruf"):
            out.append((a, a["huruf"]))
    return out


def harvest_document(doc):
    """Categories and notes from one structured document."""
    cats, notes = [], []
    rank = instrument_rank(doc["doc_id"])

    for p in doc["pasal"]:
        if p["section"] != "body":
            continue
        for container, kids in containers(p):
            chap = chapeau_of(container, kids)
            # The exclusion test comes first, and deliberately does not depend
            # on a recognised opener. UU Pasal 55(2) opens with `... yang
            # semata-mata untuk:`, which is not in OPENERS, so gating on the
            # opener would drop it silently instead of recording that a list of
            # non-taxable things was seen and refused.
            if EXCLUSION.search(chap):
                notes.append({"citation": container["citation"],
                              "doc_id": doc["doc_id"],
                              "reason": "exclusion_list_not_a_category",
                              "chapeau": chap[-110:]})
                continue
            if not OPENERS.search(chap):
                continue
            subject = subject_of(chap)
            if not subject or len(subject.split()) > 12:
                notes.append({"citation": container["citation"],
                              "doc_id": doc["doc_id"],
                              "reason": "subject_not_identifiable",
                              "chapeau": chap[-110:]})
                continue

            parent_id = slug(subject)
            taxable = bool(TAXABLE_SUBJECT.search(subject))
            cats.append({"id": parent_id, "label": subject, "parent": None,
                         "origin_citation": container["citation"],
                         "doc_id": doc["doc_id"], "rank": rank, "level": "subject",
                         "taxable_subject": taxable})

            for h in kids:
                huruf_label, bled = trim_label(h["text"])
                if bled:
                    notes.append({"citation": h["citation"], "doc_id": doc["doc_id"],
                                  "reason": "heading_bled_into_huruf",
                                  "chapeau": huruf_label[:110]})
                if len(huruf_label.split()) > MAX_LABEL_WORDS:
                    notes.append({"citation": h["citation"], "doc_id": doc["doc_id"],
                                  "reason": "label_implausibly_long_segmentation_suspect",
                                  "chapeau": huruf_label[:110]})
                    continue
                members, reason = split_services(huruf_label)
                if members or not is_term_like(huruf_label):
                    huruf_id = citation_slug(doc["doc_id"], h["citation"])
                else:
                    huruf_id = slug(huruf_label)
                if not huruf_id:
                    continue
                entry = {"id": huruf_id, "label": huruf_label, "parent": parent_id,
                         "origin_citation": h["citation"], "doc_id": doc["doc_id"],
                         "rank": rank, "level": "huruf", "taxable_subject": taxable}
                if OPEN_TEXTURED.search(huruf_label):
                    entry["open_textured"] = True
                cats.append(entry)

                if members:
                    head = distributive_head(members)
                    if head:
                        notes.append({"citation": h["citation"],
                                      "doc_id": doc["doc_id"],
                                      "reason": "distributive_head_suspected",
                                      "chapeau": f"head {head!r} may distribute "
                                                 f"across {members[1:]}"})
                    for m in members:
                        entry = {"id": slug(m), "label": m, "parent": huruf_id,
                                 "origin_citation": h["citation"],
                                 "doc_id": doc["doc_id"], "rank": rank,
                                 "level": "service", "taxable_subject": taxable}
                        if head:
                            entry["distributive_head_suspected"] = head
                        cats.append(entry)
                else:
                    notes.append({"citation": h["citation"], "doc_id": doc["doc_id"],
                                  "reason": f"huruf_not_split:{reason}",
                                  "chapeau": huruf_label[:110]})
    return cats, notes


# ------------------------------------------------------------ cross-instrument

def propose_alignments(live, local):
    """Propose, never merge.

    A local label that contains a statutory label as a whole-word prefix is a
    candidate subdivision -- `karaoke keluarga` under `karaoke`. Whether the
    subdivision actually falls inside the statutory term is a legal judgement,
    so this only ever emits a proposal with the evidence attached.
    """
    by_label = {}
    for c in live:
        if c.get("taxable_subject"):
            by_label.setdefault(c["label"].lower(), c)
    out = []
    for c in local:
        if not c.get("taxable_subject"):
            continue
        lab = c["label"].lower()
        if lab in by_label:
            out.append({"local_id": c["id"], "local_label": c["label"],
                        "doc_id": c["doc_id"], "origin_citation": c["origin_citation"],
                        "proposed_relation": "same_as",
                        "statutory_id": by_label[lab]["id"],
                        "statutory_origin": by_label[lab]["origin_citation"],
                        "basis": "label matches a statutory label exactly"})
            continue
        for slab, sc in by_label.items():
            if len(slab) < 3:
                continue
            if re.match(rf"^{re.escape(slab)}\b", lab) and lab != slab:
                out.append({"local_id": c["id"], "local_label": c["label"],
                            "doc_id": c["doc_id"],
                            "origin_citation": c["origin_citation"],
                            "proposed_relation": "subclass_of",
                            "statutory_id": sc["id"],
                            "statutory_origin": sc["origin_citation"],
                            "basis": f"label extends the statutory term {slab!r}"})
                break
    return out


# ------------------------------------------------------------------- the check

GOLD_PASAL_55 = "Pasal 55 ayat (1)"


def verify_pasal_55(cats, gold_path=Path("data/gold/ontology.json")):
    """Compare what the builder recovers from UU Pasal 55(1) against the fixture.

    Both directions are reported. A miss means the builder is too narrow. An
    extra may mean the fixture is incomplete -- which is the expected outcome
    here, since the fixture was drawn from rate provisions and only ever saw
    huruf k and huruf l.
    """
    gold = json.loads(Path(gold_path).read_text())["categories"]
    gold_55 = {k: v for k, v in gold.items()
               if "Pasal 55" in (v.get("origin") or "")}

    mine = [c for c in cats
            if c["doc_id"].startswith("UU_") and GOLD_PASAL_55 in c["origin_citation"]]
    huruf = [c for c in mine if c["level"] == "huruf"]
    service = [c for c in mine if c["level"] == "service"]
    mine_ids = {c["id"] for c in mine}

    print(f"UU 1/2022 {GOLD_PASAL_55}")
    print(f"  huruf-level categories recovered : {len(huruf)}  (statute enumerates 12)")
    print(f"  service-level categories split   : {len(service)}")
    for c in huruf:
        kids = [s["label"] for s in service if s["parent"] == c["id"]]
        mark = "*" if c["id"] in gold_55 else " "
        print(f"   {mark} {c['origin_citation'][-7:]}  {c['label'][:58]:<58}"
              + (f"  -> {', '.join(kids)}" if kids else ""))

    matched = sorted(set(gold_55) & mine_ids)
    extra = sorted(mine_ids - set(gold_55))

    # An id built by slugifying the statute's own wording will not equal a
    # hand-shortened fixture id even when both name the same category: gold
    # calls `Jasa Kesenian dan Hiburan` simply `jasa_hiburan`. Compare labels
    # before declaring a miss, so "named differently" is not reported as "not
    # found" -- the two need different fixes.
    mine_labels = {canonical(c["label"]).lower(): c for c in mine}
    renamed, missed = [], []
    for gid in sorted(set(gold_55) - mine_ids):
        glabel = canonical(gold_55[gid].get("label", "")).lower()
        hit = mine_labels.get(glabel)
        if hit:
            renamed.append((gid, hit["id"], gold_55[gid].get("label")))
        else:
            missed.append(gid)

    print(f"\n  gold categories with a Pasal 55 origin : {len(gold_55)}")
    print(f"  matched by id    : {len(matched)}  {matched}")
    print(f"  matched by label : {len(renamed)}")
    for gid, mid, lab in renamed:
        print(f"                     gold {gid!r} == built {mid!r}   ({lab})")
    print(f"  MISSED           : {len(missed)}  {missed}")
    print(f"  extra   : {len(extra)}")
    for e in extra:
        c = next(x for x in mine if x["id"] == e)
        print(f"            {c['origin_citation'][-7:]}  {e}")
    return matched, missed, extra


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--structured", type=Path, default=Path("data/structured"))
    ap.add_argument("--out", type=Path, default=Path("out/ontology.json"))
    ap.add_argument("--verify", action="store_true", help="Pasal 55 check only")
    args = ap.parse_args()

    all_cats, all_notes = [], []
    for path in sorted(args.structured.glob("*.json")):
        if path.name == "manifest.json":
            continue
        doc = json.loads(path.read_text())
        c, n = harvest_document(doc)
        all_cats.extend(c)
        all_notes.extend(n)

    live = [c for c in all_cats if c["rank"] == "national"]
    local = [c for c in all_cats if c["rank"] != "national"]

    if args.verify:
        verify_pasal_55(all_cats)
        return

    matched, missed, extra = verify_pasal_55(all_cats)

    pending = propose_alignments(live, local)
    unique_live = {c["id"] for c in live}
    unique_local = {c["id"] for c in local}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "_comment": "Generated by src/ontology_build.py. `categories` are from "
                    "national instruments and are live. Everything a Perda or "
                    "Perwal introduces is a proposal in `pending_review` and is "
                    "never auto-merged: a local subdivision falling inside a "
                    "statutory term is a legal judgement.",
        "categories": live,
        "pending_review": {
            "local_categories": local,
            "proposed_alignments": pending,
        },
        "coverage_log": all_notes,
    }, indent=1, ensure_ascii=False))

    tax_live = [c for c in live if c.get("taxable_subject")]
    tax_local = [c for c in local if c.get("taxable_subject")]
    print(f"\n{'-'*66}\ncorpus")
    print(f"  national categories (live)     : {len(live):>5}  ({len(unique_live)} unique ids)")
    print(f"    of which taxable subjects    : {len(tax_live):>5}  "
          f"({len({c['id'] for c in tax_live})} unique ids)")
    print(f"  local categories (pending)     : {len(local):>5}  ({len(unique_local)} unique ids)")
    print(f"    of which taxable subjects    : {len(tax_local):>5}  "
          f"({len({c['id'] for c in tax_local})} unique ids)")
    print(f"  proposed alignments (pending)  : {len(pending):>5}")
    print(f"  coverage-log entries           : {len(all_notes):>5}")
    print("\n  coverage-log reasons:")
    for r, n in collections.Counter(x["reason"].split(":")[0] for x in all_notes).most_common():
        print(f"    {n:>5}  {r}")
    print("\n  proposed relations:")
    for r, n in collections.Counter(x["proposed_relation"] for x in pending).most_common():
        print(f"    {n:>5}  {r}")
    print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    main()
