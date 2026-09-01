# Generátor české švédské křížovky

Odpověď na tvrzení, že jazykový model křížovku sestavit nedokáže. Nedokáže —
neskládá písmena, vidí tokeny. Proto je práce rozdělená tak, aby každou část
dělal ten, kdo na ni má:

| část | kdo | proč |
|---|---|---|
| slovník | skript nad `hunspell cs_CZ` | 132 tis. českých tvarů, žádné halucinace |
| pořadí slov | frekvenční korpus titulků | aby v mřížce byla slova, která luštitel zná |
| mřížka | backtracking solver | deterministické, buď vyjde nebo ne |
| legendy | jazykový model | jediná část, kde je model doopravdy silný |
| kontrola | samostatný verifikátor | model si vlastní mřížku ověřit nemůže |

## Pipeline

```bash
python3 src/build_dict.py     # hunspell + korpus -> data/words.json
python3 src/solve.py          # -> data/grid.json
python3 src/verify.py         # nezávislá kontrola mřížky
python3 src/make_page.py      # + data/clues.json -> web/krizovka.html
```

## České konvence zadrátované do solveru

- **bez diakritiky** — `KŮŇ` se do políček píše `KUN`; jinak se `Ý` a `Y`
  nikdy nezkříží a solver ztratí většinu možností
- **CH je jedno políčko** — je to písmeno české abecedy, takže `MNICH`
  zabere čtyři políčka, ne pět
- **legenda v mřížce** — vodorovné slovo má definici v políčku vlevo od
  začátku, svislé v políčku nad ním; jedno políčko unese dvě definice
- **tajenka se pokládá první** — je to zadání, ne výsledek

## Parametry solveru

Nejdůležitější zjištění z ladění: **vzory s nejvyšším křižováním jsou
zároveň nejhůř zaplnitelné.** Řadit je striktně sestupně znamená útočit
pořád na ten nejtěžší a vyčerpat rozpočet. Proto se z horního pásma
(`--band`) losuje.

| přepínač | co dělá |
|---|---|
| `--patterns` | kolik vzorů mřížky vygenerovat a ohodnotit křižováním |
| `--band` | jak velké horní pásmo vzorů se před výběrem zamíchá |
| `--per-attempt`, `--nodes` | strop času a uzlů na jeden vzor |
| `--keep` | kolik hotových mřížek vyrobit, než se vybere nejlepší |
| `--max-rank` | strop vzácnosti slov (nižší = běžnější slova, těžší fill) |
| `--allow-corpus` | povolit ohnuté tvary z titulků; nese s sebou smetí |

## Kvalita slovníku

Titulkový korpus přidává ohnuté tvary, které hunspell nemá, ale zároveň
propouští anglická slova (`GOT`, `OUR`) a překlepy (`SVĚHO`). Proto slouží
jen jako **řazení**, ne jako zdroj slov (`--allow-corpus` je vypnuté).

`data/blacklist.txt` a stoplist v `build_dict.py` vyhazují funkční slova a
tvary, ke kterým nejde napsat rozumná legenda.

`data/extras.json` je kurátorovaná databáze zkratek, chemických značek,
římských číslic a zeměpisných názvů — každá s hotovou legendou. Bez ní není
čím zaplnit dvou- a třípísmenné mezery, protože hunspell má jen 124
dvoupísmenných hesel.

## Co zatím není hotové

- solver umí jednu mřížku na zadání; napojení na frontend jako generátor je
  připravené (data jsou oddělená od vykreslování), ale neudělané
- křižování se drží kolem 92 %, ne 100 % — viz `verify.py`, který nekřížená
  písmena vypíše
