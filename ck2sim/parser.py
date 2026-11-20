"""Parser for the Clausewitz text format used by Crusader Kings II saves.

Only the top-level sections we need are tokenized, which keeps a 25+ MB
save around a few seconds per section instead of parsing everything.

Representation:
  - `key=value`        -> dict entry (values are str)
  - `key={...}`        -> nested dict, or list if the block has no `=`
  - duplicated keys    -> `Multi` (a list subclass), e.g. several `law=` lines
"""
from __future__ import annotations

import gzip
import re

TOKEN = re.compile(rb'"[^"]*"|#[^\n]*|[{}=]|[^\s{}="#]+')
ENCODING = "latin-1"  # CK2 saves are windows-1252; latin-1 never fails to decode


class Multi(list):
    """Values of a key that appears several times in the same block."""


def as_list(value):
    """Normalise a value that may be missing, single or repeated into a list."""
    if value is None:
        return []
    if isinstance(value, Multi):
        return list(value)
    return [value]


class _Tokens:
    __slots__ = ("_it", "_buf")

    def __init__(self, data: bytes):
        self._it = (t for t in (m.group() for m in TOKEN.finditer(data))
                    if t[:1] != b"#")  # drop comments
        self._buf = None

    def next(self):
        if self._buf is not None:
            tok, self._buf = self._buf, None
            return tok
        return next(self._it, None)

    def peek(self):
        if self._buf is None:
            self._buf = next(self._it, None)
        return self._buf


def _scalar(tok: bytes) -> str:
    if tok[:1] == b'"':
        tok = tok[1:-1]
    return tok.decode(ENCODING)


def _put(d: dict, key: str, value):
    if key in d:
        old = d[key]
        if isinstance(old, Multi):
            old.append(value)
        else:
            d[key] = Multi([old, value])
    else:
        d[key] = value


def _parse_value(toks: _Tokens):
    tok = toks.next()
    if tok == b"{":
        return _parse_block(toks)
    return _scalar(tok)


def _parse_block(toks: _Tokens):
    """Parse after an opening `{` up to its matching `}`."""
    d: dict = {}
    items: list = []
    while True:
        tok = toks.next()
        if tok is None or tok == b"}":
            break
        if tok == b"{":
            items.append(_parse_block(toks))
            continue
        if toks.peek() == b"=":
            toks.next()
            _put(d, _scalar(tok), _parse_value(toks))
        else:
            items.append(_scalar(tok))
    if d and items:
        d["_items"] = items
        return d
    return d if d else items


def parse(data: bytes):
    """Parse a whole Clausewitz document (bytes) into a dict."""
    toks = _Tokens(data)
    d: dict = {}
    while True:
        tok = toks.next()
        if tok is None:
            break
        if tok in (b"{", b"}"):
            continue
        if toks.peek() == b"=":
            toks.next()
            _put(d, _scalar(tok), _parse_value(toks))
    return d


_SECTION = re.compile(rb"\n\t([a-z_]+)=\n\t\{")


def read_sections(path, wanted: set[str]) -> dict:
    """Return {section: parsed} for the requested top-level save sections,
    plus header fields `date`, `version` and `start_date`."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as f:
        data = f.read()
    if not data.startswith(b"CK2txt"):
        raise ValueError(f"{path}: not an uncompressed CK2 text save "
                         "(set compress_autosaves=no, no ironman)")
    out: dict = {}
    for key in (b"date", b"version", b"start_date"):
        m = re.search(rb'\n\t' + key + rb'="([^"]*)"', data)
        if m:
            out[key.decode()] = m.group(1).decode(ENCODING)
    for m in _SECTION.finditer(data):
        name = m.group(1).decode()
        if name not in wanted:
            continue
        start = m.end()
        end = data.find(b"\n\t}\n", start)  # top-level blocks close at one tab
        _put(out, name, _parse_block(_Tokens(data[start:end] + b"}")))  # repeated sections (active_war) -> Multi
    return out
