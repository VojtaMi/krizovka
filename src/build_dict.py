#!/usr/bin/env python3
"""Postaví křížovkářský slovník z hunspell cs_CZ.dic + frekvenčního korpusu.

Výstup: data/words.json
  { "words": { "<forma v políčkách>": {"src": [tvary s diakritikou],
                                       "rank": <0 = nejběžnější, 999999 = neznámé>} } }

Normalizace odpovídá české křížovkářské konvenci:
  - bez diakritiky (KŮŇ -> KUN)
  - CH je jeden znak, tedy jedno políčko

Dva zdroje:
  hunspell  – 132k základních tvarů, spolehlivě česká slova, žádná frekvence
  korpus    – 50k nejčastějších slov z titulků, VČETNĚ ohnutých tvarů,
              s frekvencí; obsahuje ale i překlepy a slang, proto jen
              nad prahem četnosti
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIC = Path("/usr/share/hunspell/cs_CZ.dic")
FREQ = ROOT / "data" / "cs_50k.txt"
# Frekvenční seznam se do repozitáře nedává (644 kB, cizí data). Stáhni ho:
#   curl -sL -o data/cs_50k.txt \
#     https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/cs/cs_50k.txt
FREQ_URL = ("https://raw.githubusercontent.com/hermitdave/FrequencyWords/"
            "master/content/2018/cs/cs_50k.txt")
OUT = ROOT / "data" / "words.json"

CZECH_LOWER = "abcdefghijklmnopqrstuvwxyzáčďéěíňóřšťúůýž"
WORD_RE = re.compile(f"^[{CZECH_LOWER}]+$")

DEACCENT = str.maketrans({
    "á": "a", "č": "c", "ď": "d", "é": "e", "ě": "e", "í": "i",
    "ň": "n", "ó": "o", "ř": "r", "š": "s", "ť": "t", "ú": "u",
    "ů": "u", "ý": "y", "ž": "z",
})

MIN_LEN, MAX_LEN = 2, 12
UNKNOWN_RANK = 999_999
# pod touhle četností jsou v titulkovém korpusu převážně překlepy a slang
FREQ_MIN_COUNT = 200


def to_glyphs(word: str) -> list[str]:
    """Rozloží slovo na křížovková políčka. CH zabírá jedno políčko."""
    plain = word.translate(DEACCENT).upper()
    out, i = [], 0
    while i < len(plain):
        if plain[i] == "C" and i + 1 < len(plain) and plain[i + 1] == "H":
            out.append("CH")
            i += 2
        else:
            out.append(plain[i])
            i += 1
    return out


def glyph_len(key: str) -> int:
    return len(to_glyphs(key.lower()))


def load_hunspell() -> dict[str, set[str]]:
    forms: dict[str, set[str]] = {}
    with DIC.open(encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            base = line.strip().split("/", 1)[0].strip()
            if not base or not WORD_RE.match(base):
                continue
            glyphs = to_glyphs(base)
            if MIN_LEN <= len(glyphs) <= MAX_LEN:
                forms.setdefault("".join(glyphs), set()).add(base)
    return forms


def load_freq() -> tuple[dict[str, set[str]], dict[str, int]]:
    """Vrátí (tvary, rank). Rank 0 = nejčastější slovo korpusu."""
    forms: dict[str, set[str]] = {}
    rank: dict[str, int] = {}
    if not FREQ.exists():
        print(f"varování: {FREQ} chybí, jedu bez frekvencí.\n"
              f"  Bez něj solver nepozná běžná slova od obskurních. Stáhni:\n"
              f"  curl -sL -o {FREQ} {FREQ_URL}", file=sys.stderr)
        return forms, rank
    position = 0
    for line in FREQ.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        word, count_s = parts
        try:
            count = int(count_s)
        except ValueError:
            continue
        if count < FREQ_MIN_COUNT or not WORD_RE.match(word):
            continue
        glyphs = to_glyphs(word)
        if not (MIN_LEN <= len(glyphs) <= MAX_LEN):
            continue
        key = "".join(glyphs)
        forms.setdefault(key, set()).add(word)
        # rank drží nejčastější variantu, která na tuhle formu mapuje
        if key not in rank:
            rank[key] = position
        position += 1
    return forms, rank


STOPLIST = """
já ty on ona ono my vy oni ony ono mě mne mi tě tebe ti ho jeho jej mu jemu
ji jí je jich jim nás nám vás vám se si sebe sobě sebou
svůj svého svému svém svým svá své svou svých svými svoje svoji
můj mého mému mém mým má mé mou mých mými moje moji
tvůj tvého tvému tvém tvým tvá tvé tvou tvých tvými tvoje tvoji
náš naše našeho našemu našem naším naší našich našim našimi
váš vaše vašeho vašemu vašem vaším vaší vašich vašim vašimi
jejich jejího jejímu jejím jejich
ten ta to toho tomu tom tím tou ty ti té těch těm těmi tato tento této tomto
tyto tihle tahle tohle tenhle onen ona ono
který která které kterého kterému kterém kterým která kterou kterých kterým
jenž jež jehož jejíž což co kdo koho komu kým čeho čemu čím
nic ničeho ničemu ničím něco někdo něčeho každý každá každé všechen všechno
všichni všech všem všemi všechny veškerý sám sama samo sami samy
v ve na do od ode z ze s se k ke ku o u za po při pro před přede přes přeze
pod pode nad nade mezi bez beze kolem podle vedle kvůli díky během proti
skrz mimo krom kromě místo namísto oproti vůči stran vůkol napříč
a i ale nebo anebo či však avšak tedy tudíž proto protože poněvadž jelikož
že aby abych abys abychom abyste kdyby kdybych kdybys když jestli jestliže
pokud ač ačkoli ačkoliv přestože třebaže jakmile dokud než nežli sice buď
neboť tak jak jako totiž nýbrž
ne ano jo no ať prý snad asi možná jistě ovšem také taky též jen jenom pouze
už již ještě zase opět právě teprve dokonce alespoň aspoň přece vždyť holt
prostě zrovna aha hm hmm ach ách ech och uf úf fuj jé ej hej ou au ahoj hele jasně dobře vlastně vůbec zas nazdar čau pardon díky prosím
jsem jsi je jsme jste jsou byl byla bylo byli byly být budu budeš bude
budeme budete budou bych bys by bychom byste bývá bylo
můžu můžeš může můžeme můžete mohou mohu chci chceš chce chceme chcete
chtějí chtěl chtěla musím musíš musí musíme musíte mám máš máme máte mají
mít měl měla mělo měli
tam tady tu zde sem odsud tudy kam kde kdy proč nikdy vždy teď nyní pak
potom hned dnes včera zítra
""".split()


def load_stoplist() -> set[str]:
    """Stoplist v podobě klíčů mřížky — jinak 'už' propustí formu UZ."""
    words: list[str] = list(STOPLIST)
    for name in ("blacklist.txt", "profanity.txt"):
        extra = ROOT / "data" / name
        if not extra.exists():
            continue
        for line in extra.read_text(encoding="utf-8").splitlines():
            words.extend(line.split("#", 1)[0].split())
    return {"".join(to_glyphs(w)) for w in words}


def main() -> int:
    if not DIC.exists():
        print(f"chybí {DIC}", file=sys.stderr)
        return 1

    hun = load_hunspell()
    freq_forms, rank = load_freq()

    stop = load_stoplist()

    words: dict[str, dict] = {}
    for key, variants in hun.items():
        words[key] = {"src": sorted(variants), "rank": rank.get(key, UNKNOWN_RANK),
                      "base": True}
    added_from_corpus = 0
    for key, variants in freq_forms.items():
        if key in words:
            words[key]["src"] = sorted(set(words[key]["src"]) | variants)
        else:
            words[key] = {"src": sorted(variants), "rank": rank.get(key, UNKNOWN_RANK),
                          "base": False}
            added_from_corpus += 1

    # funkční slova nejdou zadefinovat legendou — v křížovce nemají co dělat
    dropped_stop = 0
    for key in list(words):
        if key in stop:
            del words[key]
            dropped_stop += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"words": words}, ensure_ascii=False), encoding="utf-8")

    by_len: dict[int, list[int]] = {}
    for key, rec in words.items():
        by_len.setdefault(glyph_len(key), []).append(rec["rank"])

    print(f"hunspell forem:       {len(hun)}")
    print(f"vyřazeno (stoplist):  {dropped_stop}")
    print(f"z korpusu přibylo:    {added_from_corpus} (ohnuté tvary ap.)")
    print(f"celkem forem:         {len(words)}")
    ranked = sum(1 for r in words.values() if r["rank"] != UNKNOWN_RANK)
    print(f"s frekvencí:          {ranked} ({ranked * 100 // len(words)} %)")
    print("délka: celkem / z toho s frekvencí")
    for n in sorted(by_len):
        ranks = by_len[n]
        known = sum(1 for r in ranks if r != UNKNOWN_RANK)
        print(f"  {n:2d}: {len(ranks):6d} / {known:5d}")
    print(f"zapsáno: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
