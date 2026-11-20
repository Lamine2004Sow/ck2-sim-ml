"""Static game data needed to decode saves (trait ids, province -> county)."""
from __future__ import annotations

import re
from pathlib import Path

from .parser import parse

DEFAULT_GAME_DIR = Path.home() / "Games/crusader/Crusader Kings II/game"


def load_traits(game_dir: Path = DEFAULT_GAME_DIR) -> dict[int, str]:
    """Trait ids in saves are 1-based positions in load order
    (files sorted by name, definitions in file order)."""
    names: list[str] = []
    for f in sorted((Path(game_dir) / "common/traits").glob("*.txt")):
        names.extend(parse(f.read_bytes()).keys())
    return {i + 1: n for i, n in enumerate(names)}


def load_dynasties(game_dir: Path = DEFAULT_GAME_DIR) -> dict[str, dict]:
    """Historical dynasties (name, culture, religion). Saves only store
    dynasties created during play, and characters omit `cul`/`rel` when they
    match their dynasty's."""
    out: dict[str, dict] = {}
    for f in sorted((Path(game_dir) / "common/dynasties").glob("*.txt")):
        for k, v in parse(f.read_bytes()).items():
            if isinstance(v, dict):
                out[k] = {x: v.get(x) for x in ("name", "culture", "religion")}
    return out


_PROV_FILE =re.compile(r"^(\d+)\s*-")
_COUNTY = re.compile(rb"^\s*title\s*=\s*(c_\w+)", re.M)


def load_province_counties(game_dir: Path = DEFAULT_GAME_DIR) -> dict[str, str]:
    """Map province id (as str) -> county title, from history/provinces."""
    out: dict[str, str] = {}
    for f in (Path(game_dir) / "history/provinces").glob("*.txt"):
        m = _PROV_FILE.match(f.name)
        c = _COUNTY.search(f.read_bytes())
        if m and c:
            out[m.group(1)] = c.group(1).decode()
    return out
