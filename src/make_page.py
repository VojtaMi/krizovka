#!/usr/bin/env python3
"""Z vyřešené mřížky a legend udělá hotovou webovou křížovku.

Vstupy:
  data/grid.json   – výstup solveru (mřížka, písmena, slova)
  data/clues.json  – legendy: {"SLOVO": "definice"}; výplňová hesla si
                     legendu nesou sama z extras.json
Výstup:
  web/krizovka.html – jedna soběstačná stránka, žádný server

Legendová políčka se dopočítají zde: vodorovné slovo má definici v políčku
vlevo od svého začátku, svislé v políčku nad ním. Jedno políčko unese dvě
definice, jednu doprava a jednu dolů — přesně jako v časopisecké předloze.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEGEND, LETTER = "L", "."
RARE_RANK = 200_000


def build_view(grid_data: dict, clues: dict[str, str], extras: dict[str, str]) -> dict:
    w, h = grid_data["width"], grid_data["height"]
    grid = [list(row) for row in grid_data["grid"]]
    letters = {tuple(int(x) for x in k.split(",")): v
               for k, v in grid_data["letters"].items()}

    cells = [[None] * w for _ in range(h)]
    tajenka_index: dict[tuple[int, int], int] = {}
    missing: list[str] = []

    for slot in grid_data["slots"]:
        if slot.get("label"):
            part = int(slot["label"].split(".")[0]) - 1
            for order, (r, c) in enumerate(slot["cells"]):
                tajenka_index[(r, c)] = part

    # Každé slovo dostane index. Stránka podle něj odvozuje směr psaní:
    # políčko ví, kterými slovy prochází, takže po kliknutí není co hádat.
    view_slots: list[dict] = []
    legend_clues: dict[tuple[int, int], list[dict]] = {}
    for si, slot in enumerate(grid_data["slots"]):
        word = slot["word"]
        r, c = slot["cells"][0]
        if slot["dir"] == "H":
            anchor, arrow = (r, c - 1), "right"
        else:
            anchor, arrow = (r - 1, c), "down"

        if slot.get("label"):
            text = slot["label"]
        else:
            text = clues.get(word) or extras.get(word) or slot.get("clue")
            if not text:
                missing.append(word)
                text = f"?? {word}"
        legend_clues.setdefault(anchor, []).append(
            {"text": text, "arrow": arrow, "word": word, "slot": si,
             "tajenka": bool(slot.get("label"))}
        )
        view_slots.append({
            "d": arrow,
            "c": [[cr, cc] for cr, cc in slot["cells"]],
            "a": [anchor[0], anchor[1]],
            "taj": bool(slot.get("label")),
        })

    cell_slots: dict[tuple[int, int], list[int]] = {}
    for si, slot in enumerate(grid_data["slots"]):
        for cr, cc in slot["cells"]:
            cell_slots.setdefault((cr, cc), []).append(si)

    for r in range(h):
        for c in range(w):
            if grid[r][c] == LEGEND:
                items = legend_clues.get((r, c), [])
                items.sort(key=lambda x: 0 if x["arrow"] == "right" else 1)
                for pos, item in enumerate(items):
                    # kolikátá definice v políčku je — kvůli zvýraznění řádku
                    view_slots[item["slot"]]["p"] = pos
                cells[r][c] = {"t": "legend", "clues": items}
            else:
                cells[r][c] = {
                    "t": "letter",
                    "s": letters.get((r, c), ""),
                    "k": tajenka_index.get((r, c)),
                    "w": cell_slots.get((r, c), []),
                }

    # Legenda se do políčka fyzicky nevejde a ořízne se, aniž by to bylo
    # z dat poznat. Rozpočet odpovídá výchozím 64 px na políčko.
    overflow: list[tuple[int, str, str]] = []
    for row in cells:
        for cell in row:
            if cell["t"] != "legend" or not cell["clues"]:
                continue
            budget = 45 if len(cell["clues"]) == 1 else 28
            for item in cell["clues"]:
                if len(item["text"]) > budget:
                    overflow.append((len(item["text"]), item["word"], item["text"]))
    overflow.sort(reverse=True)

    # Pomůcka: nejméně běžná hesla, stejně jako pod křížovkou v časopise
    hard = sorted({
        slot["src"][0] if slot.get("src") else slot["word"]
        for slot in grid_data["slots"]
        if not slot.get("label") and (slot.get("rank") or 0) >= RARE_RANK
    })

    return {
        "width": w,
        "height": h,
        "cells": cells,
        "slots": view_slots,
        "tajenka": grid_data["tajenka"],
        "pomucka": hard,
        "stats": grid_data["stats"],
        "missing": missing,
        "overflow": overflow,
    }


def main() -> int:
    grid_path = ROOT / "data" / "grid.json"
    clues_path = ROOT / "data" / "clues.json"
    if not grid_path.exists():
        print(f"chybí {grid_path} — nejdřív spusť solve.py", file=sys.stderr)
        return 1

    grid_data = json.loads(grid_path.read_text(encoding="utf-8"))
    clues = json.loads(clues_path.read_text(encoding="utf-8")) if clues_path.exists() else {}
    clues = {k: v for k, v in clues.items() if not k.startswith("_")}
    extras = {k: v for k, v in json.loads(
        (ROOT / "data" / "extras.json").read_text(encoding="utf-8")).items()
        if not k.startswith("_")}

    view = build_view(grid_data, clues, extras)

    meta_path = ROOT / "data" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    stats = grid_data["stats"]
    dict_size = len(json.loads(
        (ROOT / "data" / "words.json").read_text(encoding="utf-8"))["words"])

    # meta.json nese úvodní text a titulek. Když zůstane od minulé křížovky,
    # vyjde stránka, jejíž zadání popisuje něco úplně jiného — a z dat to
    # nijak nepoznáš. Proto se kontroluje proti tajence v mřížce.
    want = " ".join(grid_data["tajenka"])
    have = meta.get("tajenka_text", "")
    if have and have.replace(" ", "") != want.replace(" ", ""):
        print(f"POZOR: data/meta.json patří k jiné křížovce.\n"
              f"  meta.tajenka_text: {have!r}\n"
              f"  tajenka v mřížce:  {want!r}\n"
              f"  Uprav meta.json (number, title, tajenka_text, zadani_html), "
              f"jinak stránka vyjde s cizím zadáním.", file=sys.stderr)

    view["title"] = meta.get("title", "Švédská křížovka")
    view["number"] = meta.get("number", "1")
    view["tajenka_text"] = meta.get("tajenka_text", " ".join(grid_data["tajenka"]))
    view["zadani_html"] = meta.get("zadani_html", "")
    view["colophon_html"] = meta.get("colophon_html", "")
    view["facts"] = [
        {"k": "Rozměr", "v": f"{view['width']} × {view['height']}",
         "note": f"{stats['letter_cells']} písmenných políček"},
        {"k": "Slov v mřížce", "v": str(stats["words"]),
         "note": "mřížku složil solver, legendy psal model"},
        {"k": "Úplné křižování", "v": f"{stats['interlock_pct']} %",
         "note": "písmen zapojených do dvou slov naráz"},
        {"k": "Slovník", "v": f"{dict_size // 1000} tis.",
         "note": "českých tvarů, řazeno podle frekvence"},
    ]

    out_json = ROOT / "data" / "view.json"
    out_json.write_text(json.dumps(view, ensure_ascii=False), encoding="utf-8")

    # Zásobník: každá hotová křížovka dostane vlastní soubor a nic se
    # nepřepisuje. Nepovedená generace tak nemůže zničit povedenou.
    store = ROOT / "data" / "puzzles"
    store.mkdir(parents=True, exist_ok=True)
    if "--add" in sys.argv:
        used = sorted(int(f.stem) for f in store.glob("*.json") if f.stem.isdigit())
        nxt = (used[-1] + 1) if used else 1
        target = store / f"{nxt:03d}.json"
        view["number"] = str(nxt)
        target.write_text(json.dumps(view, ensure_ascii=False), encoding="utf-8")
        print(f"do zásobníku přidáno: {target}")

    puzzles = [json.loads(f.read_text(encoding="utf-8"))
               for f in sorted(store.glob("*.json"))]
    if not puzzles:
        puzzles = [view]          # zásobník je prázdný, ukaž aspoň tuhle

    template = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
    payload = json.dumps({"puzzles": puzzles}, ensure_ascii=False)
    payload = payload.replace("</script>", "<\\/script>")
    page = (template.replace("__DATA__", payload)
                    .replace("__TITLE__", puzzles[0].get("title", "Švédská křížovka")))
    out_html = ROOT / "web" / "krizovka.html"
    out_html.write_text(page, encoding="utf-8")
    print(f"křížovek v zásobníku: {len(puzzles)}")

    total_words = len(grid_data["slots"])
    print(f"slov: {total_words}, bez legendy: {len(view['missing'])}")
    if view["missing"]:
        print("CHYBÍ LEGENDA:", " ".join(sorted(set(view["missing"]))))
    if view["overflow"]:
        print(f"PŘÍLIŠ DLOUHÉ LEGENDY ({len(view['overflow'])}) — v políčku se "
              f"oříznou, zkrať je:")
        for length, word, text in view["overflow"]:
            print(f"  {length:3d} zn.  {word:<11} {text}")
    print(f"pomůcka: {', '.join(view['pomucka'])}")
    print(f"zapsáno: {out_json}\n         {out_html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
