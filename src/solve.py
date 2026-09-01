#!/usr/bin/env python3
"""Generátor švédské křížovky s tajenkou.

Model mřížky
------------
Políčko je buď LEGENDA (nese definici a šipku) nebo PÍSMENO.
Slovo = souvislý běh písmenných políček délky >= 2, vodorovný nebo svislý.
Před každým během stojí legenda: vlevo u vodorovného, nahoře u svislého.
Proto je celý sloupec 0 a celý řádek 0 legendový, stejně jako v předloze.

Legenda může nést až dvě definice (jednu doprava, jednu dolů) — přesně
jak to dělají políčka se dvěma texty v časopisecké předloze.

Tajenka se pokládá první: je to pevně zadaný běh, kolem kterého se
zbytek mřížky musí vejít.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import multiprocessing
import os
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS = ROOT / "data" / "words.json"

LEGEND, LETTER = "L", "."
UNKNOWN_RANK = 999_999


def to_glyphs(word: str) -> list[str]:
    out, i = [], 0
    up = word.upper()
    while i < len(up):
        if up[i] == "C" and i + 1 < len(up) and up[i + 1] == "H":
            out.append("CH")
            i += 2
        else:
            out.append(up[i])
            i += 1
    return out


# Pořadí preferencí solveru. Nižší číslo = solver sáhne dřív.
#   běžný základní tvar  ->  rank z korpusu (0..50 000)
#   křížovkářská výplň   ->  hned za nimi, jsou to legitimní hesla
#   vzácný základní tvar ->  spisovná čeština, ale luštitel ji nezná
#   jen z korpusu        ->  ohnuté tvary, poslední záchrana
MIN_DICT_LEN = 3
EXTRAS_RANK = 60_000
RARE_BASE_RANK = 200_000
CORPUS_ONLY_PENALTY = 500_000


class Lexicon:
    """Slova seskupená podle délky, s indexem (pozice, znak) -> množina slov."""

    def __init__(self, path: Path, max_rank: int, extras_path: Path | None = None,
                 allow_corpus: bool = False):
        raw = json.loads(path.read_text(encoding="utf-8"))["words"]
        self.by_len: dict[int, list[tuple[str, ...]]] = {}
        self.rank: dict[int, list[int]] = {}
        self.src: dict[int, list[list[str]]] = {}
        self.clue: dict[int, list[str | None]] = {}
        self.index: dict[int, dict[tuple[int, str], set[int]]] = {}
        seen: set[str] = set()

        extras: dict[str, str] = {}
        if extras_path and extras_path.exists():
            extras = {
                k: v for k, v in json.loads(
                    extras_path.read_text(encoding="utf-8")).items()
                if not k.startswith("_")
            }

        def add(glyphs, rank, src, clue):
            n = len(glyphs)
            self.by_len.setdefault(n, []).append(glyphs)
            self.rank.setdefault(n, []).append(rank)
            self.src.setdefault(n, []).append(src)
            self.clue.setdefault(n, []).append(clue)

        # výplňová hesla mají přednost před vzácnými tvary — mají hotovou legendu
        for key, clue in extras.items():
            glyphs = tuple(to_glyphs(key))
            add(glyphs, EXTRAS_RANK, [key], clue)
            seen.add("".join(glyphs))

        for key, rec in raw.items():
            if key in seen:
                continue
            # Dvoupísmenná políčka plní jen značky a zkratky z extras.json.
            # Hunspell má na téhle délce skoro výhradně citoslovce a částice
            # (HR, PS, OZ), ke kterým se legenda napsat nedá.
            if len(to_glyphs(key)) < MIN_DICT_LEN:
                continue
            rank, is_base = rec["rank"], rec.get("base", True)
            if not is_base and not allow_corpus:
                continue  # titulkový korpus propouští angličtinu a překlepy
            if rank == UNKNOWN_RANK:
                rank = RARE_BASE_RANK
            if not is_base:
                rank += CORPUS_ONLY_PENALTY
            if rank > max_rank:
                continue
            add(tuple(to_glyphs(key)), rank, rec["src"], None)

        for n, words in self.by_len.items():
            idx: dict[tuple[int, str], set[int]] = {}
            for i, w in enumerate(words):
                for pos, g in enumerate(w):
                    idx.setdefault((pos, g), set()).add(i)
            self.index[n] = idx
        self.all_of_len = {n: set(range(len(w))) for n, w in self.by_len.items()}

    def matches(self, length: int, constraints: list[tuple[int, str]]) -> set[int]:
        if length not in self.by_len:
            return set()
        if not constraints:
            return self.all_of_len[length]
        idx = self.index[length]
        sets = []
        for pos, g in constraints:
            s = idx.get((pos, g))
            if not s:
                return set()
            sets.append(s)
        sets.sort(key=len)
        out = sets[0]
        for s in sets[1:]:
            out = out & s
            if not out:
                break
        return out


class Slot:
    __slots__ = ("cells", "direction", "length", "fixed", "label")

    def __init__(self, cells, direction, fixed=None, label=None):
        self.cells = cells
        self.direction = direction
        self.length = len(cells)
        self.fixed = fixed
        self.label = label


def build_pattern(w: int, h: int, tajenka_rows: dict[int, int],
                  legend_prob: float, max_run: int, rng: random.Random):
    """Vrátí mřížku typů políček. tajenka_rows: {řádek: délka tajenkového běhu}."""
    grid = [[LETTER] * w for _ in range(h)]
    for c in range(w):
        grid[0][c] = LEGEND
    for r in range(h):
        grid[r][0] = LEGEND

    # tajenkové řádky: běh délky L začíná ve sloupci 1, hned za ním legenda
    for row, length in tajenka_rows.items():
        for c in range(1, w):
            grid[row][c] = LETTER
        end = 1 + length
        if end < w:
            grid[row][end] = LEGEND

    protected_rows = set(tajenka_rows)
    for r in range(1, h):
        if r in protected_rows:
            continue
        for c in range(1, w):
            if rng.random() < legend_prob:
                grid[r][c] = LEGEND
    return grid


def runs_in(grid, w, h, direction):
    """Najde souvislé běhy písmenných políček v daném směru."""
    out = []
    if direction == "H":
        for r in range(h):
            c = 0
            while c < w:
                if grid[r][c] == LETTER:
                    start = c
                    while c < w and grid[r][c] == LETTER:
                        c += 1
                    out.append([(r, x) for x in range(start, c)])
                else:
                    c += 1
    else:
        for c in range(w):
            r = 0
            while r < h:
                if grid[r][c] == LETTER:
                    start = r
                    while r < h and grid[r][c] == LETTER:
                        r += 1
                    out.append([(y, c) for y in range(start, r)])
                else:
                    r += 1
    return out


def repair(grid, w, h, max_run, tajenka_rows, rng: random.Random):
    """Rozbije příliš dlouhé běhy a zruší políčka, která nepatří do žádného slova."""
    protected = set()
    for row, length in tajenka_rows.items():
        for c in range(1, 1 + length):
            protected.add((row, c))

    for _ in range(200):
        changed = False
        for direction in ("H", "V"):
            for run in runs_in(grid, w, h, direction):
                if len(run) <= max_run:
                    continue
                inner = [cell for cell in run[1:-1] if cell not in protected]
                if not inner:
                    continue
                # řež zhruba uprostřed, ať nevznikne běh délky 1
                candidates = inner[max(0, len(inner) // 2 - 1): len(inner) // 2 + 2]
                r, c = rng.choice(candidates or inner)
                grid[r][c] = LEGEND
                changed = True
        if not changed:
            break

    # políčko, které není ani ve vodorovném, ani ve svislém slově, je slepé
    for _ in range(50):
        h_len = {}
        v_len = {}
        for run in runs_in(grid, w, h, "H"):
            for cell in run:
                h_len[cell] = len(run)
        for run in runs_in(grid, w, h, "V"):
            for cell in run:
                v_len[cell] = len(run)
        orphans = [
            cell for cell, n in h_len.items()
            if n < 2 and v_len.get(cell, 0) < 2 and cell not in protected
        ]
        if not orphans:
            break
        for r, c in orphans:
            grid[r][c] = LEGEND
    return grid


def extract_slots(grid, w, h, tajenka_rows, tajenka_text):
    slots: list[Slot] = []
    for direction in ("H", "V"):
        for run in runs_in(grid, w, h, direction):
            if len(run) >= 2:
                slots.append(Slot(run, direction))
    for i, (row, length) in enumerate(sorted(tajenka_rows.items())):
        want = [(row, c) for c in range(1, 1 + length)]
        for slot in slots:
            if slot.direction == "H" and slot.cells == want:
                slot.fixed = tajenka_text[i]
                slot.label = f"{i + 1}. DÍL TAJENKY"
                break
        else:
            return None  # tajenkový běh se nedochoval, vzor je k ničemu
    return slots


class Filler:
    """Backtracking s MRV a dopředným ořezem.

    Klíč k rychlosti: kandidáti se drží jako množina indexů a NIKDY se
    kvůli výběru nejnadějnějšího slotu nematerializují do seznamu. Už
    použitá slova se odečítají až ve chvíli, kdy se ze slotu opravdu
    vybírá — je jich řádově sto, na velikost množiny nemají vliv.
    """

    TRIES_PER_SLOT = 40

    def __init__(self, lex: Lexicon, slots: list[Slot], rng: random.Random):
        self.lex = lex
        self.slots = slots
        self.rng = rng
        self.values: dict[tuple[int, int], str] = {}
        self.assigned: dict[int, tuple[str, ...]] = {}
        self.used: set[tuple[str, ...]] = set()
        self.nodes = 0

        # kdo s kým se kříží: po dosazení stačí přepočítat jen sousedy
        cell_owners: dict[tuple[int, int], list[int]] = {}
        for si, slot in enumerate(slots):
            for cell in slot.cells:
                cell_owners.setdefault(cell, []).append(si)
        self.neighbours: list[set[int]] = [set() for _ in slots]
        for owners in cell_owners.values():
            for a in owners:
                for b in owners:
                    if a != b:
                        self.neighbours[a].add(b)

    def constraints_for(self, si: int) -> list[tuple[int, str]]:
        vals = self.values
        return [(pos, vals[cell])
                for pos, cell in enumerate(self.slots[si].cells) if cell in vals]

    def candidate_ids(self, si: int) -> set[int]:
        slot = self.slots[si]
        return self.lex.matches(slot.length, self.constraints_for(si))

    def place(self, si: int, word: tuple[str, ...]) -> list[tuple[int, int]]:
        written = []
        for pos, cell in enumerate(self.slots[si].cells):
            if cell not in self.values:
                self.values[cell] = word[pos]
                written.append(cell)
        self.assigned[si] = word
        self.used.add(word)
        return written

    def unplace(self, si: int, word: tuple[str, ...], written) -> None:
        for cell in written:
            del self.values[cell]
        del self.assigned[si]
        self.used.discard(word)

    def solve(self, deadline: float, node_budget: int) -> bool:
        for si, slot in enumerate(self.slots):
            if slot.fixed:
                word = tuple(to_glyphs(slot.fixed))
                if len(word) != slot.length:
                    return False
                for pos, cell in enumerate(slot.cells):
                    if self.values.get(cell, word[pos]) != word[pos]:
                        return False
                self.place(si, word)
        return self._search(deadline, node_budget)

    def _search(self, deadline: float, node_budget: int) -> bool:
        if time.monotonic() > deadline or self.nodes > node_budget:
            return False

        best_si, best_ids, best_n = None, None, None
        for si in range(len(self.slots)):
            if si in self.assigned:
                continue
            ids = self.candidate_ids(si)
            n = len(ids)
            if n == 0:
                return False  # mrtvá větev
            if best_n is None or n < best_n:
                best_si, best_ids, best_n = si, ids, n
                if n == 1:
                    break
        if best_si is None:
            return True  # nic neobsazeného, mřížka je plná

        length = self.slots[best_si].length
        ranks = self.lex.rank[length]
        words = self.lex.by_len[length]
        jitter = self.rng.random
        pick = heapq.nsmallest(
            self.TRIES_PER_SLOT * 2, best_ids,
            key=lambda i: ranks[i] + jitter() * 5_000,
        )
        tried = 0
        for i in pick:
            word = words[i]
            if word in self.used:
                continue
            tried += 1
            if tried > self.TRIES_PER_SLOT:
                break
            self.nodes += 1
            written = self.place(best_si, word)
            if self._search(deadline, node_budget):
                return True
            self.unplace(best_si, word, written)
            if time.monotonic() > deadline or self.nodes > node_budget:
                return False
        return False


def blind_cells(grid, w, h, slots):
    """Legendová políčka, která neobsluhují žádné slovo.

    Pár jich vznikne vždycky, ale když se shluknou, udělají v mřížce
    prázdnou díru — v časopise je na tom místě ilustrace, tady jen fleky.
    """
    used = set()
    for slot in slots:
        r, c = slot.cells[0]
        used.add((r, c - 1) if slot.direction == "H" else (r - 1, c))
    return sum(1 for r in range(h) for c in range(w)
               if grid[r][c] == LEGEND and (r, c) not in used)


def interlock_stats(grid, w, h, slots):
    counts: dict[tuple[int, int], int] = {}
    for slot in slots:
        for cell in slot.cells:
            counts[cell] = counts.get(cell, 0) + 1
    letters = [(r, c) for r in range(h) for c in range(w) if grid[r][c] == LETTER]
    crossed = sum(1 for cell in letters if counts.get(cell, 0) >= 2)
    return len(letters), crossed


def dictionary_fingerprint() -> str:
    """Otisk slovníku, se kterým mřížka vznikla.

    Verifikátor podle něj pozná, že se slovník od vyřešení změnil, a řekne
    to rovnou — místo aby vypsal seznam slov, která "nejsou ve slovníku".
    """
    return hashlib.sha1(WORDS.read_bytes()).hexdigest()[:16]


def ensure_dictionary() -> None:
    """Přegeneruje slovník, když je starší než jeho vstupy.

    Bez tohohle je snadné upravit blacklist, zapomenout na build_dict.py a
    divit se, proč vyhozené slovo pořád leze do mřížky.
    """
    words = ROOT / "data" / "words.json"
    sources = [ROOT / "data" / "blacklist.txt", ROOT / "src" / "build_dict.py"]
    present = [p for p in sources if p.exists()]
    if words.exists() and all(
            words.stat().st_mtime >= p.stat().st_mtime for p in present):
        return
    why = "chybí" if not words.exists() else "je starší než blacklist"
    print(f"slovník {why}, generuji znovu...", file=sys.stderr)
    result = subprocess.run(
        [sys.executable, str(ROOT / "src" / "build_dict.py")],
        capture_output=True, text=True)
    sys.stderr.write(result.stdout)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit("build_dict.py selhal")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=13)
    ap.add_argument("--height", type=int, default=20)
    ap.add_argument("--tajenka", default="NAPSALSINA,TOPROGRAM")
    ap.add_argument("--legend-prob", type=float, default=0.17)
    ap.add_argument("--max-run", type=int, default=8)
    ap.add_argument("--max-rank", type=int, default=UNKNOWN_RANK)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--attempts", type=int, default=None,
                    help="strop pokusů; ve výchozím stavu se projdou všechny "
                         "vzory, dokud nedojde čas nebo --keep")
    ap.add_argument("--per-attempt", type=float, default=15.0,
                    help="sekund na jeden vzor, než se jde na další")
    ap.add_argument("--nodes", type=int, default=60_000,
                    help="strop uzlů na jeden vzor")
    ap.add_argument("--blind-weight", type=float, default=1.2,
                    help="jak silně se trestají legendy bez definice")
    ap.add_argument("--band", type=float, default=0.25,
                    help="jak velké horní pásmo vzorů se před výběrem zamíchá")
    ap.add_argument("--keep", type=int, default=8,
                    help="kolik hotových mřížek vyrobit, než se vybere nejlepší")
    ap.add_argument("--patterns", type=int, default=400,
                    help="kolik vzorů vygenerovat a seřadit podle křižování")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=0,
                    help="kolik hledání pustit naráz; 0 = podle volných jader")
    ap.add_argument("--allow-corpus", action="store_true",
                    help="povolit ohnuté tvary z titulků (nese s sebou smetí)")
    ap.add_argument("--out", default=str(ROOT / "data" / "grid.json"))
    args = ap.parse_args()

    parts = [p.strip().upper() for p in args.tajenka.split(",") if p.strip()]
    # Běh tajenky začíná ve sloupci 1, takže se do řádku musí vejít i s ním.
    for part in parts:
        n = len(to_glyphs(part))
        if n > args.width - 1:
            raise SystemExit(
                f"díl tajenky {part!r} má {n} znaků, do šířky {args.width} se "
                f"nevejde (strop je {args.width - 1}, pohodlně {args.width - 3}). "
                f"Rozděl tajenku na víc dílů.")
    ensure_dictionary()

    jobs = auto_jobs(args.jobs)
    if jobs == 1:
        found = search_worker((vars(args), args.seed))
    else:
        # Běhy jsou na sobě nezávislé, liší se jen semínkem. Paralelizace tak
        # nemění chování solveru, jen jich pustí víc naráz — na rozdíl od
        # zrychlování samotného prohledávání tady není co pokazit.
        print(f"pouštím {jobs} hledání paralelně "
              f"({len(os.sched_getaffinity(0))} jader, zátěž "
              f"{os.getloadavg()[0]:.1f})", file=sys.stderr)
        payload = [(vars(args), args.seed + 1000 * i) for i in range(jobs)]
        with multiprocessing.Pool(jobs) as pool:
            found = [r for chunk in pool.map(search_worker, payload) for r in chunk]

    if not found:
        print("nepodařilo se vyplnit mřížku", file=sys.stderr)
        return 1
    found.sort(key=lambda r: (r["rare"], -r["stats"]["interlock_pct"]))
    best = found[0]
    print(f"vybrána mřížka: křižování {best['stats']['interlock_pct']} %, "
          f"neznámých hesel {best['rare']} (z {len(found)} hotových mřížek)",
          file=sys.stderr)
    Path(args.out).write_text(json.dumps(best["out"], ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(f"zapsáno: {args.out}", file=sys.stderr)
    return 0


def auto_jobs(requested: int) -> int:
    """Kolik hledání pustit naráz.

    Pevný default nedává smysl: na vytíženém notebooku si čtyři workery
    konkurují a nezrychlí nic (naměřeno 6 mřížek proti 5), zatímco dva na
    tomtéž stroji daly 7 proti 4. Rozhoduje volná kapacita, ne počet jader.
    """
    cores = len(os.sched_getaffinity(0))
    if requested > 0:
        return max(1, min(requested, cores))
    try:
        load = os.getloadavg()[0]
    except OSError:
        load = 0.0
    return max(1, min(cores, int(cores - load)))


def search_worker(payload) -> list[dict]:
    """Jedno nezávislé hledání. Vrací hotové mřížky jako čistá data."""
    cfg, seed = payload
    args = argparse.Namespace(**cfg)
    parts = [p.strip().upper() for p in args.tajenka.split(",") if p.strip()]
    lex = Lexicon(WORDS, args.max_rank, ROOT / "data" / "extras.json",
                  allow_corpus=args.allow_corpus)
    rng = random.Random(seed)
    deadline = time.monotonic() + args.seconds
    results: list[dict] = []
    patterns = []
    for _ in range(args.patterns):
        rows = pick_tajenka_rows(args.height, parts, rng)
        tajenka_rows = {row: len(to_glyphs(p)) for row, p in zip(rows, parts)}
        grid = build_pattern(args.width, args.height, tajenka_rows,
                             args.legend_prob, args.max_run, rng)
        repair(grid, args.width, args.height, args.max_run, tajenka_rows, rng)
        slots = extract_slots(grid, args.width, args.height, tajenka_rows, parts)
        if slots is None:
            continue
        total, crossed = interlock_stats(grid, args.width, args.height, slots)
        if total == 0:
            continue
        blind = blind_cells(grid, args.width, args.height, slots)
        score = crossed / total - args.blind_weight * (blind / (args.width * args.height))
        patterns.append((score, grid, slots, total, crossed))
    # Vzory s nejvyšším křižováním jsou zároveň nejtěsnější, a tedy nejhůř
    # zaplnitelné. Brát je striktně shora znamená útočit pořád na ten
    # nejtěžší z nich. Beru proto horní pásmo a uvnitř něj zamíchám.
    patterns.sort(key=lambda x: -x[0])
    band = max(12, int(len(patterns) * args.band))
    head = patterns[:band]
    rng.shuffle(head)
    patterns = head + patterns[band:]

    # Dřív tu byl default --attempts 60, který tiše přebíjel --keep i --seconds:
    # při úspěšnosti fillu ~1:34 doběhl běh po pěti mřížkách místo třiceti.
    limit = args.attempts if args.attempts is not None else len(patterns)
    for attempt, (ratio, grid, slots, _t, _c) in enumerate(patterns[:limit]):
        if time.monotonic() > deadline:
            break

        filler = Filler(lex, slots, rng)
        attempt_deadline = min(deadline, time.monotonic() + args.per_attempt)
        if not filler.solve(attempt_deadline, node_budget=args.nodes):
            continue

        total, crossed = interlock_stats(grid, args.width, args.height, slots)
        rare = sum(1 for si in range(len(slots))
                   if not slots[si].fixed
                   and meta(lex, filler.assigned[si])[2] is not None
                   and meta(lex, filler.assigned[si])[2] >= RARE_BASE_RANK)
        print(f"[seed {seed}] mřížka {len(results) + 1}: {len(slots)} slov, "
              f"křižování {crossed * 100 // total} %, neznámých hesel {rare}",
              file=sys.stderr)
        results.append({
            "rare": rare,
            "out": {
                "dict_sha": dictionary_fingerprint(),
                "width": args.width,
                "height": args.height,
                "tajenka": parts,
                "grid": ["".join(row) for row in grid],
                "letters": {f"{r},{c}": g for (r, c), g in filler.values.items()},
                "slots": [
                    {
                        "cells": [[r, c] for r, c in sl.cells],
                        "dir": sl.direction,
                        "word": "".join(filler.assigned[i]),
                        "src": meta(lex, filler.assigned[i])[0],
                        "clue": meta(lex, filler.assigned[i])[1],
                        "rank": meta(lex, filler.assigned[i])[2],
                        "label": sl.label,
                    }
                    for i, sl in enumerate(slots)
                ],
                "stats": {"letter_cells": total, "crossed": crossed,
                          "interlock_pct": round(crossed * 100 / total, 1),
                          "words": len(slots)},
            },
        })
        results[-1]["stats"] = results[-1]["out"]["stats"]
        if len(results) >= args.keep:
            break
    return results


def meta(lex: Lexicon, word: tuple[str, ...]):
    """Vrátí (tvary, hotová legenda nebo None, rank) pro umístěné slovo."""
    n = len(word)
    try:
        i = lex.by_len[n].index(word)
    except ValueError:
        return [], None, None
    return lex.src[n][i], lex.clue[n][i], lex.rank[n][i]


def pick_tajenka_rows(h: int, parts, rng: random.Random) -> list[int]:
    """Každý díl tajenky do vlastního pásma, ať dva nepadnou na týž řádek.

    Dřív tu byla natvrdo dvě pásma, která se cyklila — tři a víc dílů se
    tak mohly potkat v jednom řádku a vzor pak nešel použít.
    """
    lo, hi = 2, h - 3
    n = len(parts)
    if hi - lo + 1 < n:
        raise SystemExit(f"mřížka vysoká {h} řádků neunese {n} dílů tajenky")
    band = (hi - lo + 1) / n
    rows = []
    for i in range(n):
        a = lo + int(i * band)
        b = lo + int((i + 1) * band) - 1
        rows.append(rng.randint(a, max(a, b)))
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
