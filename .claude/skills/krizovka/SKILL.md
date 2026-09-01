---
name: krizovka
description: Vygeneruje českou švédskou křížovku s tajenkou jako hratelnou webovou stránku. Použij, když někdo chce křížovku, křížovku s tajenkou, švédskou křížovku, tajenku do mřížky, nebo když se ptá, jestli AI umí sestavit křížovku.
---

# Česká švédská křížovka s tajenkou

Mřížku skládá solver, legendy píšeš ty. Nikdy nepiš mřížku ani její písmena
přímo v odpovědi — vidíš tokeny, ne znaky, a vyjde nesmysl.

## Postup

**1. Rozděl tajenku a uprav `data/meta.json`.**
Každý díl musí být kratší než šířka mřížky (13 sloupců → pohodlně 10 znaků;
solver delší odmítne). Dělení vybíráš ty, podle smyslu: `KDOSIHRAJE`/`NEZLOBI`
dělí přísloví na čárce, `KDOSIHRA`/`JENEZLOBI` splňuje stejná formální
pravidla a v odkrytí čte jako nesmysl.

V `meta.json` přepiš `title`, `number`, `tajenka_text` a `zadani_html`.
**Zůstane-li od minulé křížovky, vyjde stránka s cizím zadáním.**

**2. Spusť solver.** Trvá desítky sekund.

```bash
python3 src/solve.py --width 13 --height 20 \
    --tajenka "PRVNIDIL,DRUHYDIL" --seconds 300 --patterns 2000
```

Slovník se dogeneruje sám, když je zastaralý. Počet paralelních hledání si
solver zvolí podle volných jader. Defaulty jsou vyladěné a podložené
měřením — neupravuj je naslepo, zvlášť `--nodes`, `--band` a `--keep`.
Zvyšovat `--keep` se nevyplácí: osmá mřížka zachytí prakticky celý užitek,
třicátá koupí jedno slovo za trojnásobek času. A hlavně nezvyšuj `--nodes`:
84 % vzorů se zaplnit nedá a na nich se strop vyplýtvá celý. Naměřeno
8–10 mřížek za 90 s při 2500 uzlech, ale jen dvě při 42000.

**3. Projdi umístěná slova.**

```bash
python3 src/verify.py --words
```

Verifikátor musí projít, jinak nepokračuj. Pak si přečti výpis slov a
vyhoď, co nejde vysvětlit legendou → `data/blacklist.txt` → zpět na krok 2.

Počítej se **dvěma až třemi koly**, každé je další desetiminutový běh. Smyčka
nekonverguje sama: každá nová mřížka nabere čerstvé smetí ze 166 tisíc tvarů.
Tohle je hlavní časová položka celé práce.

**4. Napiš legendy** do `data/clues.json` ke každému heslu z výpisu.

**5. Postav stránku a zkontroluj hlášení.**

```bash
python3 src/make_page.py
```

Hlásí chybějící legendy, příliš dlouhé legendy a nesoulad `meta.json`
s tajenkou. Všechno oprav a spusť znovu.

**6. Ulož křížovku do zásobníku**, až je čistá:

```bash
python3 src/make_page.py --add
```

Bez `--add` se stránka jen překreslí a nová křížovka nikam nepřibude.
Se `--add` dostane vlastní soubor v `data/puzzles/` a na stránce se
objeví v přepínači vedle předchozích — nic se nepřepisuje, takže
nepovedená generace nemůže zničit hotovou.

## Legendy

Rozpočet na políčko, jinak se text ořízne:

- **jedna definice v políčku: ~45 znaků**
- **dvě definice: ~28 znaků na každou**

Konvence: zkratky uváděj typem (`chem. zn. telluru`), ohnuté tvary pádem
(`4. p. j. č. od pes`), u setřených tvarů definuj obě čtení naráz
(`UKAZ` = ukaž i úkaz → „zjev na nebi i rozkaz“). Hlídej, ať osmdesát legend
nezačíná osmdesátkrát „část něčeho“.

## Co musí udělat model, protože to skript neumí

- **Legendy** — včetně rozhodnutí, které čtení setřeného tvaru definovat.
- **Vkusový soud nad slovy.** Filtr vulgarismů a blacklist berou hrubé případy,
  ale jestli je slovo tónově vhodné *pro tuhle křížovku* (dětské přísloví v
  tajence snese jiná hesla než vtip pro dospělé), rozhodneš jen ty.
- **Dělení tajenky** podle smyslu, ne podle délky.
- **Úvodní text**, který z mřížky dělá hádanku.

## Co hlásit uživateli

Vždycky **procento úplného křižování** a kolik písmen zůstalo nekřížených.
Směrnice ČSHAK (§42) žádá křižování úplné; tenhle generátor se drží kolem
90 %, takže striktní normě nevyhovuje. Řekni to, nezamlčuj to.

## Vizuální kontrola

```bash
chromium --headless --disable-gpu --no-sandbox --window-size=1180,1400 \
  --virtual-time-budget=9000 --screenshot=shot.png \
  file://$PWD/web/krizovka.html
```

Snap chromium neumí psát do `/tmp` — ukládej do pracovního adresáře.
Stránka nemá `</body>`, takže obvyklá injekce ladicího skriptu selže **tiše**;
připoj ho na konec souboru a výstup si nech vypsat do `#zadani-text`.
