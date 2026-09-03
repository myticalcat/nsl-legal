#!/usr/bin/env python3
"""
Cross-reference resolution for Indonesian legal text.

Indonesian legal drafting cites other provisions constantly --
`sebagaimana dimaksud pada ayat (1)`, `sebagaimana dimaksud dalam Pasal 55
ayat (1) huruf l`. A norm extracted from a single Pasal in isolation is
often meaningless without resolving these: the panti pijat conflict only
exists because Pasal 58 (the tax band) and Pasal 55 (the category
enumeration) are different Pasal.

This module resolves references BEFORE extraction, not after: build_index()
segments a whole document into Pasal/ayat/huruf spans, and
resolve_references() looks up what a citation inside one Pasal actually
points to, so a cross-Pasal citation's text can be handed to the LLM as
extra context. A same-Pasal citation needs no such fetch -- the model
already sees the whole Pasal -- so resolve_references() still resolves it
fully (which Pasal, which ayat) but leaves its text unfetched.
"""

import re

PASAL_HEADER = re.compile(r"(?m)^[ \t]*Pasal[ \t]+(\d+[A-Za-z]?)[ \t]*$")
PENJELASAN_HEADING = re.compile(r"(?m)^[ \t]*PENJELASAN[ \t]*$")
AYAT_MARKER = re.compile(r"(?m)^[ \t]*\((\d+)\)[ \t]+")
HURUF_MARKER = re.compile(r"(?m)^[ \t]*([a-z])\.[ \t]+")


def _index_huruf(text):
    markers = list(HURUF_MARKER.finditer(text))
    huruf = {}
    for i, m in enumerate(markers):
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        huruf[m.group(1)] = {"start": start, "end": end, "text": text[start:end]}
    return huruf


def _index_ayat(pasal_text):
    markers = list(AYAT_MARKER.finditer(pasal_text))
    ayat = {}
    for i, m in enumerate(markers):
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(pasal_text)
        ayat_text = pasal_text[start:end]
        ayat[m.group(1)] = {
            "start": start, "end": end, "text": ayat_text,
            "huruf": _index_huruf(ayat_text),
        }
    return ayat


def build_index(document_text):
    """Segment one document's operative text into a Pasal -> ayat -> huruf
    lookup of spans, stopping before any PENJELASAN appendix. Single
    document / single instrument scoped -- call once per document."""
    boundary = PENJELASAN_HEADING.search(document_text)
    body = document_text[:boundary.start()] if boundary else document_text

    headers = list(PASAL_HEADER.finditer(body))
    index = {}
    for i, h in enumerate(headers):
        pasal_num = h.group(1)
        start = h.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        pasal_text = body[start:end]
        ayat = _index_ayat(pasal_text)
        index[pasal_num] = {
            "start": start, "end": end, "text": pasal_text,
            "ayat": ayat,
            "huruf": {} if ayat else _index_huruf(pasal_text),
        }
    return index
