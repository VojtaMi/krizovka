---
name: krizovka
description: Vygeneruje českou švédskou křížovku s tajenkou jako hratelnou webovou stránku. Použij, když někdo chce křížovku, křížovku s tajenkou, švédskou křížovku, tajenku do mřížky, nebo když se ptá, jestli AI umí sestavit křížovku.
---

# Česká švédská křížovka s tajenkou

## Než začneš: rozdělení práce

Jazykový model **neskládá písmena** — vidí tokeny. Každý pokus napsat mřížku
přímo v odpovědi skončí nesmyslem. Práci proto rozděl a **nikdy tohle
rozdělení neporušuj**:

| část | kdo | proč |
|---|---|---|
| slovník | `build_dict.py` nad hunspell cs_CZ | 132 tis. tvarů, žádné halucinace |
| mřížka | `solve.py`, backtracking | deterministické, buď vyjde nebo ne |
| legendy | **ty** (model), až nad hotovou mřížkou | jediná část, kde jsi silný |
| kontrola | `verify.py` | vlastní mřížku si ověřit nemůžeš |

Legendy se píšou **až po** vyřešení mřížky. Psát je dopředu znamená omezit
solver na hrstku slov a fill selže.

## Pipeline

```bash
python3 src/build_dict.py                      # jednou, pak jen po změně blacklistu
python3 src/solve.py --width 13 --height 20 \
    --tajenka "PRVNIDIL,DRUHYDIL" \
    --seconds 700 --patterns 1600 --keep 30 \
    --per-attempt 9 --nodes 42000 --band 0.4
python3 src/verify.py                          # MUSÍ projít, jinak nepokračuj
python3 src/make_page.py                        # -> web/krizovka.html
```

Tajenka se zadává **bez diakritiky a bez mezer**, rozdělená čárkou na díly.
Díl délky 10 se do třináctisloupcové mřížky vejde; delší rozděl na víc dílů.

## Iterační smyčka na kvalitu slov

Po prvním běhu **vždycky** vypiš, co solver umístil:

```bash
python3 -c "
import json; d=json.load(open('data/grid.json'))
for s in sorted(d['slots'], key=lambda s: len(s['word'])):
    if not s.get('label'): print(s['word'], '/'.join(s['src'][:2]))"
```

Projdi seznam očima. Co nejde vysvětlit legendou (citoslovce, částice,
zájmena, podivné tvary), přidej do `data/blacklist.txt`, spusť
`build_dict.py` a solver znovu. Dvě až tři kola stačí. Blacklist je trvalý
majetek — každé kolo dělá další křížovku lepší.

## Pasti, na které se přišlo draze

**`grid.json` si legendu ukládá při řešení.** Když pak upravíš `extras.json`,
stará verze v `grid.json` zůstane. Proto `make_page.py` bere pořadí
`clues.json` → `extras.json` → teprve nakonec otisk ze `slot["clue"]`.

**Titulkový korpus je jen řazení, ne zdroj slov.** Do českých titulků
prosákla angličtina (`GOT`, `OUR`, `ARE`) a překlepy (`SVĚHO`).
`--allow-corpus` nech vypnuté, pokud nechceš tohle ručně čistit.

**Stoplist porovnávej na normalizované formě.** Filtr podle tvaru
s diakritikou propustí `UZ`, protože `už` je na seznamu, ale `uz` ne.

**Dvoupísmenná políčka plní jen `extras.json`.** Hunspell má na téhle délce
skoro výhradně citoslovce (`HR`, `PS`, `OZ`). Skutečné křížovky tam dávají
chemické značky a zkratky — proto `MIN_DICT_LEN = 3` v `solve.py`.

**Vzory s nejvyšším křižováním jsou nejhůř zaplnitelné.** Řadit je sestupně
a brát shora znamená útočit pořád na ten nejtěžší a vyčerpat rozpočet.
Proto `--band` losuje z horního pásma.

**Nízký strop uzlů je lepší než vysoký.** 400 tis. uzlů a 100 s na vzor
znamená osm vzorů za celý běh. 42 tis. uzlů a 9 s jich vystřídá padesát —
a uspěje.

**Jen běžná slova nestačí.** Pokus zaplnit mřížku 12,9 tis. nejběžnějšími
formami selhal 185krát z 185. Proto má každá křížovka v časopise
„Pomůcku" — bez vzácných slov se hustá mřížka nezaplní.

## Psaní legend

Legenda musí být **telegrafická**, protože se tiskne do políčka 64 px:

- políčko s jednou definicí unese **~45 znaků**
- políčko se dvěma definicemi unese **~28 znaků na každou**

(platí pro výchozích 64 px na políčko; při zmenšení mřížky se text zmenší s ním)

`make_page.py` hlásí `CHYBÍ LEGENDA` pro každé neolegendované heslo.
Delší legendy se ořežou — po vygenerování zkontroluj přetečení:

```bash
python3 -c "
import json; v=json.load(open('data/view.json'))
for row in v['cells']:
  for c in row:
    if c['t']=='legend' and c['clues']:
      b = 45 if len(c['clues'])==1 else 28
      for cl in c['clues']:
        if len(cl['text'])>b: print(len(cl['text']), cl['word'], cl['text'])"
```

Konvence českých legend: zkratky uváděj typem (`chem. zn. telluru`,
`zkr. Klubu českých turistů`), ohnuté tvary pádem (`4. p. j. č. od pes`),
u dvojznačných slov nabídni obě čtení (`tučná část mléka i český skladatel`).

## Ovládání stránky: směr psaní

Rozhoduj podle toho, které slovo v políčku **začíná**, ne kterými slovy
políčko prochází. Luštitel kliká na první písmeno za definicí, ne doprostřed
slova — a tam je směr skoro vždycky jednoznačný.

Rozdíl mezi těmi dvěma metrikami je zásadní a snadno se splete (stalo se):

| metrika | výsledek na mřížce 13x20 |
|---|---|
| políček ležících v jednom slově | 17 z 182 — vypadá to beznadějně |
| políček, kde začíná právě jedno slovo | **65**, a jen **8** rohů se dvěma |

Z políček, na která se reálně kliká, je tedy **89 % jednoznačných**. Kdo měří
příslušnost místo začátku, vyvodí opačný závěr a postaví ovládání špatně.

Pravidlo výběru, v tomhle pořadí:

1. **Začíná tu právě jedno slovo** → vyber ho, i kdyby to znamenalo změnit
   dosavadní směr. Klik na začátek je jasné vyjádření záměru.
2. **Začínají tu dvě** (roh) → drž dosavadní směr, jinak vodorovně.
3. **Nezačíná tu žádné** (políčko uprostřed) → drž dosavadní směr.
4. **Opakovaný klik na totéž políčko nebo mezerník** → přepni na kolmé slovo.
5. **Klik na definici** → skok na první políčko slova, směr dán šipkou.

Vybrané slovo se celé podbarví, jinak luštitel neví, co vyplňuje.
Zvýraznění musí být **výrazné** — rozdíl o dva odstíny je na mřížce
neviditelný.

## Kontrola výsledku

`verify.py` si mřížku přepočítá **nezávisle na solveru** a hlídá: každé
písmenné políčko má znak, každý běh je slovo ze slovníku, žádná duplicita,
žádné osiřelé políčko, tajenka sedí, legendová políčka nenesou víc než dvě
definice. Když neprojde, mřížku **nepublikuj**.

Vizuální kontrola se vyplatí — legendy se můžou ořezat, aniž by to skript
poznal:

```bash
chromium --headless --disable-gpu --no-sandbox --window-size=1180,1400 \
  --virtual-time-budget=9000 --screenshot=shot.png \
  file://$PWD/web/krizovka.html
```

Tři pasti při téhle kontrole:

- **snap chromium neumí psát do `/tmp`** ani `--dump-dom` na stdout. Screenshot
  ukládej do pracovního adresáře a diagnostiku si nech vypsat **do stránky**
  (třeba do `#zadani-text`), pak ji přečti ze snímku.
- **`text-transform: uppercase` je jen CSS.** V DOM jsou legendy malými
  písmeny, takže hledání podle `'OBYTNÁ'` selže — hledej `'obytná'`.
- **Zaostření políčka odroluje stránku.** Po simulovaném kliknutí zavolej
  `window.scrollTo(0, 0)`, jinak vyfotíš prázdno.

## Co hlásit uživateli

Vždycky uveď **procento úplného křižování** a kolik písmen zůstalo
nekřížených. Podle směrnice ČSHAK (§42) má být křižování úplné; tenhle
generátor se drží kolem 90 %, takže striktní normě nevyhovuje a je poctivé
to říct, ne to zamlčet.
