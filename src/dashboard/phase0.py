"""Phase 0 checklist shown on the overview page.

Hand-maintained on purpose: each status is a decision written after the
evidence (docs/tipsport_k1_log.md, reports), never computed from odds on
the fly. Update together with the plan and the log, in the same commit.
"""

UPDATED = "2. 10. 2026"

# (id, criterion, status text, state: ok / progress / wait / fail)
CRITERIA = [
    ("K1", "Tipsport vypisuje trh",
     "Střely hráče: 10/10 zápasů ve 2 dnech, vždy 6 hráčů; podmínka „do 18:00“ "
     "zatím neověřena (kontroly ve 20:00 a 21:30) - potřeba 3 dny s kontrolou "
     "17:30–18:00. Zásahy brankáře v Tipsportu nevidět; zblokované střely "
     "nevypsal nikdo.", "progress"),
    ("K2", "Data zdarma a denně",
     "Splněno: 3 sezóny (3 936 zápasů) box score, čas na ledě i v přesilovce, "
     "střely za 60 min z play-by-play, vše ověřeno proti box score, 0 chyb.", "ok"),
    ("K3", "Historické kurzy ≥ 300 zápasů vzorku",
     "Čeká na K1 a na „jeď“ (etapa A, strop 9 942 kreditů).", "wait"),
    ("K4a", "Brier modelu nejvýš o 0,010 horší než trh", "Po etapě A.", "wait"),
    ("K4b", "ROI filtru za kurz Tipsportu > 0 (D1, D3)", "Po etapě A.", "wait"),
    ("K5", "≥ 3 sázky na herní den (přepočet na 6 hráčů, D2)", "Po etapě A.", "wait"),
]

TIPSPORT_MARGIN = "8,75 % (medián 36 dvojic, 29. 9. a 2. 10.)"
