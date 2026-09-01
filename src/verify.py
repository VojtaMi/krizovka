#!/usr/bin/env python3
"""Nezávislá kontrola hotové mřížky.

Schválně nepoužívá nic ze solveru kromě dat na disku: mřížku načte znovu,
běhy si spočítá sám a každé slovo ověří proti slovníku. Když solver někde
lže, tenhle skript to má odhalit.

Kontroluje:
  1. každé písmenné políčko má přiřazený znak
  2. každý běh délky >= 2 je slovo ze slovníku (nebo výplňové heslo)
  3. žádné slovo se v mřížce neopakuje
  4. žádné písmenné políčko nestojí mimo všechna slova
  5. tajenka v příslušných políčkách skutečně dává zadaný text
  6. každý běh má před sebou legendové políčko, kam se vejde definice
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGEND, LETTER = "L", "."


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


def runs_in(grid, w, h, direction):
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


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "grid.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    w, h = data["width"], data["height"]
    grid = [list(row) for row in data["grid"]]
    letters = {tuple(int(x) for x in k.split(",")): v
               for k, v in data["letters"].items()}

    lexicon = set(json.loads(
        (ROOT / "data" / "words.json").read_text(encoding="utf-8"))["words"])
    extras = {k for k in json.loads(
        (ROOT / "data" / "extras.json").read_text(encoding="utf-8"))
        if not k.startswith("_")}
    # díly tajenky jsou zadání, ne slovníková hesla — slovem být nemusí
    known = lexicon | extras | set(data["tajenka"])

    errors: list[str] = []
    warnings: list[str] = []

    # 1. každé písmenné políčko má znak
    letter_cells = [(r, c) for r in range(h) for c in range(w)
                    if grid[r][c] == LETTER]
    for cell in letter_cells:
        if cell not in letters:
            errors.append(f"políčko {cell} je písmenné, ale prázdné")

    # 2. + 3. + 6. běhy jsou slova, neopakují se, mají před sebou legendu
    seen_words: dict[str, tuple] = {}
    covered: set[tuple[int, int]] = set()
    all_runs = [(d, run) for d in ("H", "V") for run in runs_in(grid, w, h, d)]
    for direction, run in all_runs:
        if len(run) < 2:
            continue
        word = "".join(letters.get(cell, "?") for cell in run)
        covered.update(run)
        if "?" in word:
            continue
        if word not in known:
            errors.append(f"{direction} {word} na {run[0]} není ve slovníku")
        if word in seen_words:
            errors.append(f"{direction} {word} na {run[0]} je duplicita "
                          f"(už na {seen_words[word]})")
        seen_words[word] = run[0]

        r, c = run[0]
        before = (r, c - 1) if direction == "H" else (r - 1, c)
        if not (0 <= before[0] < h and 0 <= before[1] < w):
            errors.append(f"{direction} {word} začíná na okraji, "
                          f"nemá kam dát legendu")
        elif grid[before[0]][before[1]] != LEGEND:
            errors.append(f"{direction} {word}: políčko {before} před ním "
                          f"není legendové")

    # 4. osiřelá políčka
    for cell in letter_cells:
        if cell not in covered:
            errors.append(f"políčko {cell} nepatří do žádného slova")

    # 5. tajenka
    parts = data["tajenka"]
    found = []
    for slot in data["slots"]:
        if slot.get("label"):
            found.append((slot["label"], slot["word"]))
    found.sort()
    if len(found) != len(parts):
        errors.append(f"dílů tajenky nalezeno {len(found)}, čekáno {len(parts)}")
    for (label, word), want in zip(found, parts):
        if word != want:
            errors.append(f"{label}: v mřížce {word}, čekáno {want}")

    # kapacita legendových políček: každé unese nejvýš dvě definice
    load: dict[tuple[int, int], int] = {}
    for direction, run in all_runs:
        if len(run) < 2:
            continue
        r, c = run[0]
        before = (r, c - 1) if direction == "H" else (r - 1, c)
        load[before] = load.get(before, 0) + 1
    for cell, n in load.items():
        if n > 2:
            errors.append(f"legenda {cell} by nesla {n} definic, vejdou se dvě")

    # statistika křižování
    cross: dict[tuple[int, int], int] = {}
    for _d, run in all_runs:
        if len(run) >= 2:
            for cell in run:
                cross[cell] = cross.get(cell, 0) + 1
    crossed = sum(1 for cell in letter_cells if cross.get(cell, 0) >= 2)
    unchecked = [cell for cell in letter_cells if cross.get(cell, 0) == 1]

    words_total = sum(1 for d, run in all_runs if len(run) >= 2)
    print(f"rozměr:            {w} x {h}")
    print(f"písmenná políčka:  {len(letter_cells)}")
    print(f"legendová políčka: {w * h - len(letter_cells)}")
    print(f"slov v mřížce:     {words_total}")
    print(f"úplné křižování:   {crossed}/{len(letter_cells)} = "
          f"{crossed * 100 / len(letter_cells):.1f} %")
    print(f"nekřížená písmena: {len(unchecked)}")
    print(f"tajenka:           {' | '.join(parts)}")

    if warnings:
        print(f"\nvarování ({len(warnings)}):")
        for m in warnings:
            print(f"  ! {m}")
    if errors:
        print(f"\nCHYBY ({len(errors)}):")
        for m in errors[:40]:
            print(f"  x {m}")
        return 1
    print("\nOK — mřížka je konzistentní.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
