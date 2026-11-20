"""Turn CK2 saves into tidy CSV tables.

Tables (every row carries run_id and snapshot_date):
  characters     one row per character (alive and dead)
  edges          character -> character links (family, liege, lover, killer...)
  titles         one row per title at snapshot time
  title_history  every holder change of every title (reigns, for survival analysis)
  realms         one row per independent realm (top liege) at snapshot time
  provinces      one row per province at snapshot time

Usage:
  python -m ck2sim.extract SAVE [SAVE...] --run-id run_001 --out data/processed
  python -m ck2sim.extract ~/ck2_dataset/run_001/*.ck2 --run-id run_001 --out data/processed
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from .gamedata import DEFAULT_GAME_DIR, load_dynasties, load_province_counties, load_traits
from .parser import Multi, as_list, read_sections

SECTIONS = {"dynasties", "character", "title", "provinces", "active_war"}
UNITS = ["li", "hi", "pi", "lc", "hc", "ar", "ha", "ca", "wa", "gs"]  # troop types in battle losses
ATTRS = ["diplomacy", "martial", "stewardship", "intrigue", "learning"]
EDGE_FIELDS = {  # save key -> edge type
    "fat": "father", "mot": "mother", "rfat": "real_father", "spouse": "spouse",
    "lge": "liege", "lover": "lover", "killer": "killer", "guardian": "guardian",
    "consort_of": "consort_of", "emp": "employer",
}
TIERS = {"b": "barony", "c": "county", "d": "duchy", "k": "kingdom", "e": "empire"}


def year_frac(date: str | None) -> float | None:
    """'1066.9.15' -> 1066.70 (fractional year), None if missing/invalid."""
    if not date:
        return None
    try:
        y, m, d = (int(x) for x in date.split(".")[:3])
    except ValueError:
        return None
    return round(y + (m - 1) / 12 + (d - 1) / 365, 3)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ref(v):
    """A title reference can be a string or a {title=...} block."""
    if isinstance(v, dict):
        return v.get("title")
    if isinstance(v, Multi):
        return ref(v[0])
    return v


class TableWriter:
    """Appends rows to one CSV per table, writing headers once."""

    def __init__(self, out: Path):
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self._files, self._writers = {}, {}

    def write(self, table: str, rows: list[dict]):
        if not rows:
            return
        if table not in self._writers:
            path = self.out / f"{table}.csv"
            new = not path.exists()
            f = open(path, "a", newline="", encoding="utf-8")
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            if new:
                w.writeheader()
            self._files[table], self._writers[table] = f, w
        self._writers[table].writerows(rows)

    def close(self):
        for f in self._files.values():
            f.close()


def extract(save: Path, run_id: str, traits: dict[int, str],
            prov_county: dict[str, str], with_characters: bool,
            game_dynasties: dict[str, dict] | None = None) -> dict[str, list[dict]]:
    s = read_sections(save, SECTIONS)
    date = s["date"]
    now = year_frac(date)
    base = {"run_id": run_id, "snapshot_date": date}
    # Save dynasties override game ones field by field (the save often only
    # stores a coat of arms for historical dynasties).
    dyns = {k: dict(v) for k, v in (game_dynasties or {}).items()}
    for k, v in s.get("dynasties", {}).items():
        if isinstance(v, dict):
            d = dyns.setdefault(k, {})
            d.update({x: y for x, y in v.items() if y is not None})
            coa = v.get("coat_of_arms")
            if not d.get("religion") and isinstance(coa, dict):
                d["religion"] = coa.get("religion")
    chars = s.get("character", {})
    titles = s.get("title", {})
    tables: dict[str, list[dict]] = defaultdict(list)

    # ---- titles & who holds what
    held = defaultdict(list)
    for tid, t in titles.items():
        if not isinstance(t, dict):
            continue
        holder = t.get("holder")
        if holder:
            held[holder].append(tid)
        tables["titles"].append({
            **base, "title": tid, "tier": TIERS.get(tid[:1], "other"),
            "holder": holder, "liege_title": ref(t.get("liege")),
            "de_jure_liege": ref(t.get("de_jure_liege")),
            "succession": t.get("succession"), "gender_law": t.get("gender"),
            "laws": ";".join(as_list(t.get("law"))),
            "last_change": t.get("last_change"),
        })
        hist = t.get("history")
        if isinstance(hist, dict):
            for hdate, entries in hist.items():
                for e in as_list(entries):
                    if not isinstance(e, dict) or "holder" not in e:
                        continue
                    h = e["holder"]
                    who, how = (h.get("who"), h.get("type")) if isinstance(h, dict) else (h, None)
                    tables["title_history"].append({
                        **base, "title": tid, "date": hdate, "year": year_frac(hdate),
                        "holder": who, "change_type": how,
                    })

    # ---- characters & edges
    def char_culture(c):
        d = dyns.get(c.get("dnt"), {}) if c.get("dnt") else {}
        d = d if isinstance(d, dict) else {}
        return c.get("cul") or d.get("culture"), c.get("rel") or d.get("religion")

    if with_characters:
        for cid, c in chars.items():
            if not isinstance(c, dict):
                continue
            att = as_list(c.get("att"))
            att = att[0] if att and isinstance(att[0], list) else att
            tr = c.get("tr") if isinstance(c.get("tr"), list) else []
            b, d = year_frac(c.get("b_d")), year_frac(c.get("d_d"))
            cul, rel = char_culture(c)
            dyn = dyns.get(c.get("dnt")) if c.get("dnt") else None
            my_titles = held.get(cid, [])
            row = {
                **base, "id": cid, "name": c.get("bn"),
                "female": c.get("fem") == "yes", "birth": c.get("b_d"),
                "death": c.get("d_d"), "alive": d is None,
                "age": round(((d if d is not None else now) - b), 2) if b is not None else None,
                "dynasty": c.get("dnt"),
                "dynasty_name": dyn.get("name") if isinstance(dyn, dict) else None,
                "culture": cul, "religion": rel, "government": c.get("gov"),
                "father": c.get("fat"), "mother": c.get("mot"),
                "real_father": c.get("rfat"), "liege": c.get("lge"),
                "killer": c.get("killer"), "nickname": c.get("nick"),
                "job": c.get("job"), "prestige": num(c.get("prs")),
                "piety": num(c.get("piety")), "wealth": num(c.get("wealth")),
                "health": num(c.get("health")), "fertility": num(c.get("fer")),
                "n_titles": len(my_titles),
                "top_tier": max((t[:1] for t in my_titles), key="bcdke".find, default=None),
                "traits": ";".join(traits.get(int(t), f"trait_{t}") for t in tr if t.isdigit()),
            }
            for i, a in enumerate(ATTRS):
                row[a] = int(att[i]) if i < len(att) and str(att[i]).lstrip("-").isdigit() else None
            tables["characters"].append(row)
            for key, etype in EDGE_FIELDS.items():
                for dst in as_list(c.get(key)):
                    if isinstance(dst, str) and dst not in ("0", ""):
                        tables["edges"].append({**base, "src": cid, "dst": dst, "type": etype})

    # ---- realms (top liege of every county)
    def top_of(tid):
        seen = set()
        while tid in titles and tid not in seen:
            seen.add(tid)
            lg = ref(titles[tid].get("liege")) if isinstance(titles[tid], dict) else None
            if not lg or lg == tid:
                return tid
            tid = lg
        return tid

    # ---- wars in progress (+ their battles)
    def side(cid):
        cid = (as_list(cid) or [None])[0]  # main belligerent if listed several times
        c = chars.get(cid, {}) if isinstance(cid, str) else {}
        c = c if isinstance(c, dict) else {}
        cul, rel = char_culture(c)
        mine = held.get(cid, [])
        top = max(mine, key=lambda t: "bcdke".find(t[:1]), default=None)
        return {"id": cid, "culture": cul, "religion": rel, "gov": c.get("gov"),
                "realm": top_of(top) if top else None}

    def losses(block):
        """Battle losses are {lost initial} per troop type."""
        lost = total = 0.0
        ls = block.get("losses", {}) if isinstance(block, dict) else {}
        for u in ls.values() if isinstance(ls, dict) else []:
            vals = u if isinstance(u, list) else [u]
            lost += num(vals[0]) or 0
            total += num(vals[1]) or 0 if len(vals) > 1 else 0
        return round(lost, 1), round(total, 1)

    for w in as_list(s.get("active_war")):
        if not isinstance(w, dict):
            continue
        cb = w.get("casus_belli", {}) if isinstance(w.get("casus_belli"), dict) else {}
        hist = w.get("history", {}) if isinstance(w.get("history"), dict) else {}
        dates = sorted(hist, key=lambda x: year_frac(x) or 0)
        start = dates[0] if dates else None
        att, dfn = side(w.get("attacker")), side(w.get("defender"))
        war_id = f"{run_id}:{start}:{att['id']}:{dfn['id']}"
        n_att = n_def = n_battles = 0
        for hdate in dates:
            for e in as_list(hist[hdate]):
                if not isinstance(e, dict):
                    continue
                n_att += len(as_list(e.get("add_attacker")))
                n_def += len(as_list(e.get("add_defender")))
                for b in as_list(e.get("battle")):
                    if not isinstance(b, dict):
                        continue
                    n_battles += 1
                    a, d = b.get("attacker", {}), b.get("defender", {})
                    (al, at), (dl, dt) = losses(a), losses(d)
                    tables["battles"].append({
                        "run_id": run_id, "war_id": war_id, "date": hdate,
                        "year": year_frac(hdate), "location": b.get("location"),
                        "attacker_won": b.get("result") == "yes",
                        "attacker_owner": a.get("owner") if isinstance(a, dict) else None,
                        "defender_owner": d.get("owner") if isinstance(d, dict) else None,
                        "attacker_leader": a.get("leader") if isinstance(a, dict) else None,
                        "defender_leader": d.get("leader") if isinstance(d, dict) else None,
                        "attacker_troops": at, "attacker_losses": al,
                        "defender_troops": dt, "defender_losses": dl,
                        "score": num(b.get("score")),
                    })
        tables["wars"].append({
            "run_id": run_id, "war_id": war_id, "observed": date, "name": w.get("name"),
            "casus_belli": cb.get("casus_belli"), "target_title": cb.get("landed_title"),
            "start": start, "start_year": year_frac(start),
            **{f"attacker_{k}": v for k, v in att.items()},
            **{f"defender_{k}": v for k, v in dfn.items()},
            "same_culture": att["culture"] == dfn["culture"],
            "same_religion": att["religion"] == dfn["religion"],
            "n_attackers": n_att, "n_defenders": n_def, "n_battles": n_battles,
        })

    # ---- provinces
    for pid, p in s.get("provinces", {}).items():
        if not isinstance(p, dict) or "name" not in p:
            continue
        county = prov_county.get(pid)
        tables["provinces"].append({
            **base, "province": pid, "name": p.get("name"), "county": county,
            "realm": top_of(county) if county in titles else None,
            "culture": p.get("culture"), "religion": p.get("religion"),
            "n_holdings": sum(1 for k in p if k.startswith("b_")),
            "max_settlements": p.get("max_settlements"),
            "has_trade_post": "trade_post" in p, "has_hospital": "hospital" in p,
        })

    tables["realms"] = realm_features(base, now, titles, chars, held, top_of,
                                      char_culture, tables["provinces"],
                                      tables["wars"], traits)
    return tables


REALM_LAWS = ["centralization", "tribal_organization", "status_of_women",
              "vassal_wars_law", "revoke_title_law", "out_of_realm_inheritance_law",
              "tax_levy_law_feudal", "law_voting_power", "war_voting_power"]


def _entropy(counts: Counter) -> float:
    n = sum(counts.values())
    return round(-sum(c / n * math.log2(c / n) for c in counts.values()), 3) if n else 0.0


def realm_features(base, now, titles, chars, held, top_of, char_culture,
                   provinces, wars, traits) -> list[dict]:
    """One row per independent realm: size, structure, diversity, laws,
    ruler and dynasty, military activity."""
    # An independent ruler can hold several top titles (a kingdom plus a duchy
    # outside it): merge them under his highest-tier one.
    tier_rank = "bcdke".find
    primary: dict[str, str] = {}
    for tid, t in titles.items():
        if isinstance(t, dict) and t.get("holder") and top_of(tid) == tid:
            h = t["holder"]
            if h not in primary or tier_rank(tid[:1]) > tier_rank(primary[h][:1]):
                primary[h] = tid

    def realm_of(tid):
        top = top_of(tid)
        t = titles.get(top)
        return primary.get(t.get("holder"), top) if isinstance(t, dict) else top

    titles_of = defaultdict(list)          # realm -> held titles inside it
    for tid, t in titles.items():
        if isinstance(t, dict) and t.get("holder"):
            titles_of[realm_of(tid)].append(tid)
    provs_of = defaultdict(list)
    for p in provinces:
        if p["county"] in titles:
            provs_of[realm_of(p["county"])].append(p)
    children, dyn_alive = Counter(), Counter()
    for c in chars.values():
        if not isinstance(c, dict):
            continue
        for parent in (c.get("fat"), c.get("mot")):
            if isinstance(parent, str):
                children[parent] += 1
        if "d_d" not in c and c.get("dnt"):
            dyn_alive[c["dnt"]] += 1
    wars_att = Counter(w["attacker_realm"] for w in wars)
    wars_def = Counter(w["defender_realm"] for w in wars)

    rows = []
    for top, mine in titles_of.items():
        counties = [x for x in mine if x.startswith("c_")]
        if not counties:
            continue  # titular titles and landless realms
        t = titles.get(top, {})
        holder = t.get("holder")
        c = chars.get(holder, {}) if holder else {}
        c = c if isinstance(c, dict) else {}
        cul, rel = char_culture(c)
        holders = {titles[x]["holder"] for x in mine}
        own = set(held.get(holder, []))
        direct = {titles[x]["holder"] for x in mine
                  if ref(titles[x].get("liege")) in own and titles[x]["holder"] != holder}
        provs = provs_of.get(top, [])
        pcul = Counter(p["culture"] for p in provs if p["culture"])
        prel = Counter(p["religion"] for p in provs if p["religion"])
        n_p = max(len(provs), 1)
        laws = {}
        for law in as_list(t.get("law")):
            name, _, lvl = law.rpartition("_")
            if name in REALM_LAWS and lvl.isdigit():
                laws[name] = int(lvl)
        hist = t.get("history") if isinstance(t.get("history"), dict) else {}
        hdates = sorted((year_frac(d) for d in hist), key=lambda x: x or 0)
        att = as_list(c.get("att"))
        att = att[0] if att and isinstance(att[0], list) else att
        tr = c.get("tr") if isinstance(c.get("tr"), list) else []
        b = year_frac(c.get("b_d"))
        row = {
            **base, "realm": top, "tier": TIERS.get(top[:1], "other"),
            # size & structure
            "n_counties": len(counties),
            "n_duchies": sum(x.startswith("d_") for x in mine),
            "n_kingdoms": sum(x.startswith("k_") for x in mine),
            "n_baronies": sum(x.startswith("b_") for x in mine),
            "n_provinces": len(provs),
            "n_holdings": sum(p["n_holdings"] for p in provs),
            "demesne_counties": sum(x.startswith("c_") for x in own),
            "demesne_share": round(sum(x.startswith("c_") for x in own) / len(counties), 3),
            "n_vassals": len(holders - {holder}),
            "n_direct_vassals": len(direct),
            # diversity
            "n_cultures": len(pcul), "n_religions": len(prel),
            "culture_entropy": _entropy(pcul), "religion_entropy": _entropy(prel),
            "main_culture": pcul.most_common(1)[0][0] if pcul else None,
            "main_religion": prel.most_common(1)[0][0] if prel else None,
            "ruler_culture_share": round(pcul.get(cul, 0) / n_p, 3),
            "ruler_religion_share": round(prel.get(rel, 0) / n_p, 3),
            "n_trade_posts": sum(p["has_trade_post"] for p in provs),
            "n_hospitals": sum(p["has_hospital"] for p in provs),
            # laws
            "succession": t.get("succession"), "gender_law": t.get("gender"),
            **{"law_" + n.removeprefix("law_").removesuffix("_law"): laws.get(n) for n in REALM_LAWS},
            "title_first_year": hdates[0] if hdates else None,
            "reign_start_year": hdates[-1] if hdates else None,
            "reign_years": round(now - hdates[-1], 2) if hdates and hdates[-1] else None,
            # ruler
            "holder": holder, "holder_female": c.get("fem") == "yes",
            "holder_age": round(now - b, 2) if b is not None else None,
            "holder_culture": cul, "holder_religion": rel, "government": c.get("gov"),
            "holder_dynasty": c.get("dnt"),
            "dynasty_alive_members": dyn_alive.get(c.get("dnt"), 0) if c.get("dnt") else 0,
            "holder_children": children.get(holder, 0),
            "wealth": num(c.get("wealth")), "prestige": num(c.get("prs")),
            "piety": num(c.get("piety")), "holder_health": num(c.get("health")),
            **{f"holder_{a}": (int(att[i]) if i < len(att) and str(att[i]).lstrip("-").isdigit()
                               else None) for i, a in enumerate(ATTRS)},
            "holder_traits": ";".join(traits.get(int(x), f"trait_{x}") for x in tr if x.isdigit()),
            # military
            "wars_as_attacker": wars_att.get(top, 0),
            "wars_as_defender": wars_def.get(top, 0),
        }
        rows.append(row)
    return rows


EVOLUTION_COLS = ["n_counties", "n_vassals", "n_direct_vassals", "demesne_share",
                  "n_cultures", "culture_entropy", "religion_entropy",
                  "ruler_culture_share", "wealth", "prestige", "piety"]


def add_evolution(realms: list[dict], title_history: list[dict], window: float = 10,
                  tolerance: float = 1.5) -> None:
    """Add past-looking evolution features over `window` years to each realm row
    (in place). Only data from snapshots <= the row's date is used, so the
    features are safe for forecasting (no look-ahead).

    The reference row is the same realm's snapshot closest to `window` years
    earlier, within +-tolerance years; if none exists the deltas are empty."""
    by_realm = defaultdict(list)
    for r in realms:
        r["_y"] = year_frac(r["snapshot_date"])
        by_realm[r["realm"]].append(r)
    changes = defaultdict(list)  # title -> holder-change years
    for h in title_history:
        if h["year"] is not None:
            changes[h["title"]].append(h["year"])

    p = f"_{int(window)}y"
    for rows in by_realm.values():
        rows.sort(key=lambda r: r["_y"])
        first_year = rows[0]["_y"]
        for r in rows:
            y = r["_y"]
            past = [q for q in rows if abs((y - q["_y"]) - window) <= tolerance]
            ref = min(past, key=lambda q: abs((y - q["_y"]) - window)) if past else None
            win = [q for q in rows if y - window < q["_y"] <= y]
            r["years_observed"] = round(y - first_year, 2)
            r[f"has_past{p}"] = ref is not None
            for c in EVOLUTION_COLS:
                now_v, old_v = r.get(c), ref.get(c) if ref else None
                ok = isinstance(now_v, (int, float)) and isinstance(old_v, (int, float))
                r[f"{c}_change{p}"] = round(now_v - old_v, 3) if ok else None
            old_n = ref["n_counties"] if ref else None
            r[f"n_counties_growth{p}"] = (round(r["n_counties"] / old_n - 1, 3)
                                          if old_n else None)
            r[f"same_holder{p}"] = (ref["holder"] == r["holder"]) if ref else None
            r[f"same_dynasty{p}"] = (ref["holder_dynasty"] == r["holder_dynasty"]) if ref else None
            r[f"holder_changes{p}"] = sum(y - window < c <= y for c in changes.get(r["realm"], []))
            # wars per snapshot in the window (snapshots may be irregular)
            r[f"wars_attacker_mean{p}"] = round(sum(q["wars_as_attacker"] for q in win) / len(win), 3)
            r[f"wars_defender_mean{p}"] = round(sum(q["wars_as_defender"] for q in win) / len(win), 3)
    for r in realms:
        del r["_y"]


def save_date(path: Path) -> str:
    """Read the in-game date from the save header without parsing the file."""
    import gzip
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as f:
        head = f.read(300).decode("latin-1")
    i = head.find('date="')
    return head[i + 6: head.find('"', i + 6)] if i >= 0 else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("saves", nargs="+", type=Path)
    ap.add_argument("--run-id", required=True, help="one id per simulated game")
    ap.add_argument("--out", type=Path, default=Path("data/processed"))
    ap.add_argument("--game-dir", type=Path, default=DEFAULT_GAME_DIR)
    ap.add_argument("--characters", choices=["last", "all"], default="last",
                    help="extract characters/edges from the last save only (default) or every save")
    ap.add_argument("--window", type=float, default=10,
                    help="years for realm evolution features (default 10)")
    args = ap.parse_args(argv)

    saves = sorted(args.saves, key=lambda p: year_frac(save_date(p)) or 0)
    traits = load_traits(args.game_dir)
    prov_county = load_province_counties(args.game_dir)
    game_dyns = load_dynasties(args.game_dir)
    out = TableWriter(args.out / args.run_id)
    wars: dict[str, dict] = {}       # war_id -> latest observation
    battles: dict[tuple, dict] = {}  # (war_id, date, location) -> battle
    realms: list[dict] = []          # written at the end, with evolution features
    title_history: list[dict] = []
    for i, save in enumerate(saves):
        t0 = time.time()
        with_chars = args.characters == "all" or i == len(saves) - 1
        tables = extract(save, args.run_id, traits, prov_county, with_chars, game_dyns)
        # title_history is cumulative: keep it from the last save only
        if i != len(saves) - 1:
            tables.pop("title_history", None)
        # A war spans several snapshots: keep first/last time it was seen.
        # It ended between `last_seen` and the next snapshot.
        for w in tables.get("wars", []):
            first = wars.get(w["war_id"], {}).get("first_seen", w["observed"])
            wars[w["war_id"]] = {**w, "first_seen": first, "last_seen": w.pop("observed")}
        for b in tables.get("battles", []):
            battles[(b["war_id"], b["date"], b["location"])] = b
        realms.extend(tables.get("realms", []))
        title_history.extend(tables.get("title_history", []))
        for name, rows in tables.items():
            if name in ("wars", "battles", "realms"):
                continue
            out.write(name, rows)
        sizes = ", ".join(f"{k}={len(v)}" for k, v in tables.items())
        print(f"[{i + 1}/{len(saves)}] {save.name}: {sizes} ({time.time() - t0:.1f}s)",
              file=sys.stderr)
    add_evolution(realms, title_history, window=args.window)
    out.write("realms", realms)
    out.write("wars", list(wars.values()))
    out.write("battles", list(battles.values()))
    out.close()


if __name__ == "__main__":
    main()
