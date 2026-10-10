"""Phase 0 checklist shown on the overview page.

Hand-maintained on purpose: each status is a decision written after the
evidence (docs/tipsport_k1_log.md, reports), never computed from odds on
the fly. Update together with the plan and the log, in the same commit.
"""

UPDATED = "10. 10. 2026"

# The verdict of phase 0 (docs/phase0_report.md), written after the one run
# of the pre-committed evaluation on the stage A purchase.
VERDICT = ("Střely hráče NEPOSTUPUJÍ: naivní model na 330 zápasech sezóny 2025-26 prodělal za "
           "simulovaný kurz Tipsportu −6,9 % (95% interval −9,9 až −4,2 %; 3 153 sázek). Podle plánu "
           "se střely hráčů v sezóně 2026-27 nesází; tipy jsou jen informativní.")
VERDICT_SHORT = ("Verdikt fáze 0 (10. 10. 2026): model neprošel. Na 330 zápasech sezóny 2025-26 "
                 "prodělal za odhadnutý kurz Tipsportu −6,9 % (95% interval −9,9 až −4,2 %).")

# (id, criterion, status text, state: ok / progress / wait / fail)
CRITERIA = [
    ("K1", "Tipsport vypisuje trh",
     "Střely hráče: 22 zkontrolovaných zápasů z 22 ve 4 dnech, vždy 6 hráčů; dvakrát ověřeno "
     "před 18:00 (dodatky D7, D8). Zásahy brankáře a zblokované střely Tipsport nevypisuje.", "ok"),
    ("K2", "Data zdarma a denně",
     "Splněno: 3 sezóny (3 936 zápasů) box score, čas na ledě i v přesilovce, "
     "střely za 60 min z play-by-play, vše ověřeno proti box score, 0 chyb.", "ok"),
    ("K3", "Historické kurzy ≥ 300 zápasů vzorku",
     "330 zápasů (42 herních dnů) s closingovou lajnou; nákup 10. 10. za 3 342 kreditů.", "ok"),
    ("K4a", "Brier modelu nejvýš o 0,010 horší než trh",
     "Model 0,2469, trh 0,2437; rozdíl 0,0032 (95% interval 0,0016 až 0,0048).", "ok"),
    ("K4b", "ROI filtru za kurz Tipsportu > 0 (D1, D3)",
     "−6,9 % (95% interval −9,9 až −4,2 %) na 3 153 sázkách; výhry 51,7 %, model čekal "
     "56,7 %, trh 51,0 %. Za nejlepší kurz amerických knih −3,5 %.", "fail"),
    ("K5", "≥ 3 sázky na herní den (přepočet na 6 hráčů, D2)",
     "30,0 sázky na herní den po přepočtu.", "ok"),
]

TIPSPORT_MARGIN = "8,74 % (medián 108 dvojic kurzů ze 4 dnů; zafixováno 10. 10.)"
