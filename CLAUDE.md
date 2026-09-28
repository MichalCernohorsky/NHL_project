# Pokyny pro Claude Code v tomto repozitáři

- Uživatel (Michal) neprogramuje. Česky. Odborný pojem vysvětlit jednou větou
  při prvním použití. Kroky do Terminálu očíslované, jeden příkaz na blok.
- Rozhodnutí, ne přehled možností. Když bez něj nejde rozhodnout: jedna
  otázka s doporučením.
- Poctivost: každé ROI s bootstrap 95% CI (seed 17, 10 000, převzorkují se
  herní dny), každý test se silou, každý „vzor" se simulací nulového efektu.
  Metrika = ROI v jednotkách; CLV je diagnostika. Sází se v Tipsportu,
  vyhodnocuje se kurz z tiketu.
- Disciplína jako v NBA_tool: plán commitnutý před kódem a výsledkem,
  předregistrace před prvním pohledem, zamrazení na sezónu, dodatky jen
  datované a s otiskem SHA-256. Žádné hledání řezů podle atributů.
- Chybu proti plánu nebo předregistraci říct hned a nahlas.
- Bezpečnost: klíč The Odds API a token GitHubu jen v `.env`; nikdy v URL,
  logu, výjimce, názvu cache ani commitu. Databáze se necommituje.
- Kredity The Odds API jsou sdílené s NBA a MLB: před každým nákupem
  suchý běh a čekat na „jeď".
- Testy (`python -m pytest`) musí projít před každým commitem a pushem.
