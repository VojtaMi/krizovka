---
name: krizovka
description: Vygeneruje českou švédskou křížovku s tajenkou jako hratelnou webovou stránku. Použij, když někdo chce křížovku, křížovku s tajenkou, švédskou křížovku, tajenku do mřížky, nebo když se ptá, jestli AI umí sestavit křížovku.
---

# Česká švédská křížovka s tajenkou

Mřížku skládá solver, legendy píšeš ty. Nikdy nepiš mřížku ani její písmena
přímo v odpovědi — vidíš tokeny, ne znaky, a vyjde nesmysl.

## Postup

**1. Rozděl tajenku a uprav `data/meta.json`.**

**Díl smí mít nejvýš 10 znaků** (u šířky 13). Dílů může být kolik potřebuješ,
nejen dva — dvacetiznaková tajenka se na dva nevejde a chce tři.

Dělení vybíráš ty, podle smyslu: `KDOSIHRAJE`/`NEZLOBI` dělí přísloví na
čárce, `KDOSIHRA`/`JENEZLOBI` splňuje stejná formální pravidla a v odkrytí
čte jako nesmysl.

V `meta.json` přepiš `title`, `tajenka_text`, `zadani_html` a `colophon_html`
(ten drží počet slov ve slovníku — po přegenerování nesouhlasí s panelem na
stránce). `number` neřeš, přepíše ho krok 6.
**Zůstane-li meta.json od minulé křížovky, vyjde stránka s cizím zadáním.**

**2. Spusť solver.**

```bash
python3 src/solve.py --width 13 --height 20 --tajenka "PRVNIDIL,DRUHYDIL" \
    --seconds 300 --patterns 6000 --max-rank 100000
```

`--max-rank 100000` je nejdůležitější přepínač celého postupu. Ustřihne
nefrekvenční ocas slovníku (132 tis. forem -> 12,8 tis.), a protože **všechno
smetí žije právě tam**, odpadá tím většina ručního čištění. Naměřený rozdíl:

| | plný slovník | `--max-rank 100000` |
|---|---|---|
| vzácná slova v mřížce | 16–25 | **0** |
| legend k napsání ze 132 tis. slovníku | 56 | 44 |
| kola čištění blacklistu | 2–11 | zpravidla žádné |
| křižování | 90–93 % | ~90 % |
| běh solveru | ~25 s | 1,5–2 min |

Bez něj se do křížovky dostanou hesla jako `IPSACE` nebo `ESESMAN` —
slovníkově regulérní, takže je filtr vulgarismů nechytí. (Menší počet legend
je z větší části zásluha rostoucí `clues.json`, ne jen tohohle přepínače.)

Pozor: s takhle malým slovníkem projdou jen řidší vzory, takže je potřeba
hodně `--patterns`. Křižování vychází o pár bodů níž než s plným slovníkem.

Trvá jednotky minut a skončí sám, jakmile má dost mřížek. Slovník se
dogeneruje sám, když je zastaralý (potřebuje systémový `hunspell cs_CZ`).
Ostatní přepínače neměň, jsou vyladěné měřením.

Když křižování vyjde nízké, **zkus jiný `--seed`** — při stejném slovníku je
běh deterministický, takže bez něj dostaneš totéž.

**3. Projdi umístěná slova.**

```bash
python3 src/verify.py --words
```

Verifikátor musí projít, jinak nepokračuj. Pak si přečti výpis slov a
vyhoď, co nejde vysvětlit legendou → `data/blacklist.txt` → zpět na krok 2.

S `--max-rank` tu obvykle není smetí, ale **vkusový soud pořád musíš udělat** —
filtry chytají hrubé případy, ne to, že se heslo nehodí k *téhle* tajence.
Počítej s tím, že mřížka po blacklistu může vyjít **horší**; když se to
stane, vrať se k předchozí. Bez `--max-rank` smyčka
**nekonverguje** — každá nová mřížka nabere čerstvé smetí a dvě nezávislá
měření skončila na osmi a jedenácti kolech, ne na dvou. Když se do třetího
kola pořád objevuje smetí, nesnaž se ho vyblacklistovat; sniž `--max-rank`.

**4. Zjisti, které legendy chybí.**

```bash
python3 src/make_page.py
```

Vypíše `CHYBÍ LEGENDA: …` — a **jen ty piš**. `data/clues.json` je společná
databáze, která roste s každou křížovkou, takže velká část hesel legendu už
má. Psát je podle výpisu z kroku 3 znamená napsat je zbytečně dvakrát.

**5. Napiš chybějící legendy** do `data/clues.json`, pak spusť `make_page.py`
znovu. Hlásí i příliš dlouhé legendy a nesoulad `meta.json` s tajenkou.

**6. Ulož křížovku do zásobníku**, až je čistá:

```bash
python3 src/make_page.py --add
```

Bez `--add` se stránka jen překreslí a nová křížovka nikam nepřibude.
Se `--add` dostane vlastní soubor v `data/puzzles/` a na stránce se
objeví v přepínači vedle předchozích — nic se nepřepisuje, takže
nepovedená generace nemůže zničit hotovou.

## Legendy

**Piš do 28 znaků a máš pokoj.** Políčko s jedinou definicí unese 45, ale
kolik definic které políčko ponese, se dozvíš až po `make_page.py`.

**Než začneš, přečti si pár existujících legend v `clues.json`** a drž se
jejich stylu. Ušetří to víc času než cokoliv jiného v tomhle návodu —
najdeš tam i vzory pro těžké případy (`ZES` → „spojka že jsi“).

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
