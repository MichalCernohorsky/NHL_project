# Automatika: denní provoz NHL (launchd na macOS)

> **Od 2. 10. 2026 vypnuto — provoz běží v cloudu (`docs/cloud.md`).**
> Úlohy jsou odinstalované; soubory zůstávají jako záloha
> (`make automation-install` je vrátí). Živé snímky kurzů z Macu nahradil
> nákup den poté z archivu (dodatek D4 plánu), protože Mac je ve spánku
> ztrácel.

Tři úlohy se na Macu spouští samy, stejně jako v NBA_tool (převzatá
obálka `scripts/daily_wrapper.sh` a instalátor `scripts/install_automation.sh`).
Když krok selže, vyskočí notifikace a do `logs/` se zapíše, co se stalo.

**Co automatika NEdělá:** nerozhoduje o sázkách a ve fázi 0 ani nevyrábí
tipy (pravidlo ještě neexistuje). Jen sbírá data a kurzy.

## Co se kdy spustí (místní čas Macu)

| čas CZ | ET | úloha | příkaz | co dělá |
|---|---|---|---|---|
| 12:30 | 06:30 | `com.nhltool.daily` | `make daily` | rozpis, box score, čas na ledě, jména, střely za 60 min — jen nové odehrané zápasy |
| 16:00 | 10:00 | `com.nhltool.odds-morning` | `make odds-morning` | ranní snímek kurzů všech dnešních zápasů (~3 kredity na zápas) |
| 17:00 | 11:00 | `com.nhltool.odds-closing` | `make odds-closing` | watcher: kurz 10 min před každým zápasem, spí mezi nimi, končí po posledním (typicky 4–5 h ráno) |

**Proč 12:30:** poslední zápasy ze západního pobřeží končí kolem 7:30 CZ;
v 12:30 je celá noc dohraná i s opravami statistik.
**Proč 16:00:** ranní kotva 10:00 ET je zapsaná v plánu fáze 0 (stejná
jako v NBA) — nemění se.
**Proč 17:00:** nejdřívější víkendové zápasy začínají 12:30 ET = 18:30 CZ.

**Kredity:** jen dva kurzové snímky, ~50 kreditů za herní den (~1 500
měsíčně). Pod 2 000 kredity na účtu se sběr sám zastaví (`odds.reserve_live`).

## Instalace (jednorázově)

```bash
make automation-install
```

## Kontrola, že běží

```bash
make automation-status
```

Rozhodující je řádek s datem posledního logu, ne návratový kód (launchd
hlásí 0 i u úlohy, která nikdy neběžela).

## Kde jsou logy

`logs/<úloha>_<datum>.log` — každý krok s časem začátku, návratovým kódem
a délkou. Logy nejdou do gitu.

## Vypnutí

```bash
make automation-uninstall
```

## Známá omezení

- Mac musí být zapnutý a nespat. `caffeinate` drží Mac vzhůru jen během
  closingového watcheru; uspaný nebo vypnutý Mac nevzbudí. Úloha zmeškaná
  ve spánku se spustí po probuzení — closing watcher spuštěný pozdě už ale
  zmeškané zápasy neocení (a to je správně: kurz z průběhu zápasu není
  closing).
- Přechod na zimní čas: Evropa 25. 10., USA 1. 11. V tom týdnu je 16:00 CZ
  = 11:00 ET. Kotva se kvůli pár dnům neposouvá (stejně jako NBA).
