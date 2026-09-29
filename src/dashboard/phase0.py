"""Phase 0 checklist shown on the overview page.

Hand-maintained on purpose: each status is a decision written after the
evidence (docs/tipsport_k1_log.md, reports), never computed from odds on
the fly. Update together with the plan and the log, in the same commit.
"""

UPDATED = "29. 9. 2026"

# (id, criterion, status text, state: ok / progress / wait / fail)
CRITERIA = [
    ("K1", "Tipsport vypisuje trh",
     "Střely hráče: den 1 ze 3 splněn (5/5 zápasů, 6 hráčů). "
     "Zásahy brankáře a zblokované střely zatím nevidět.", "progress"),
    ("K2", "Data zdarma a denně",
     "Splněno: 3 sezóny box score, čas na ledě, 0 chyb; střely za 60 min "
     "se stahují.", "ok"),
    ("K3", "Historické kurzy ≥ 300 zápasů vzorku",
     "Čeká na K1 a na „jeď“ (etapa A, strop 9 942 kreditů).", "wait"),
    ("K4a", "Brier modelu nejvýš o 0,010 horší než trh", "Po etapě A.", "wait"),
    ("K4b", "ROI filtru za kurz Tipsportu > 0 (D1, D3)", "Po etapě A.", "wait"),
    ("K5", "≥ 3 sázky na herní den (přepočet na 6 hráčů, D2)", "Po etapě A.", "wait"),
]

TIPSPORT_MARGIN = "8,75 % (medián 30 dvojic, 29. 9.)"
