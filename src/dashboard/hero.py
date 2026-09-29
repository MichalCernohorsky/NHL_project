"""Page headers (hero bands), the games ticker and team logos.

Same component as NBA_tool (src/dashboard/hero.py): a low dark band with a
hand-drawn SVG scene per page, title, subtitle and one key figure in a
glass capsule; gentle CSS/SMIL loops that honor prefers-reduced-motion.
Scenes are redrawn for hockey (rink, puck, net, goalie, ticket).
"""
from __future__ import annotations

import html

import streamlit as st

# NHL's public asset CDN, by team abbreviation (the schedule payload links
# the same files). Loaded by the browser, hidden on error.
TEAM_LOGO = "https://assets.nhle.com/logos/nhl/svg/{abbr}_dark.svg"

_CSS = """
<style>
.nb-wrap{border-radius:16px;overflow:hidden;margin:0 0 18px;
  border:1px solid #232B3D;box-shadow:0 8px 28px rgba(0,0,0,.35)}
.nb-hero{position:relative;height:150px;overflow:hidden;
  background:linear-gradient(105deg,#131824 0%,#1A2130 55%,#242B3F 100%)}
.nb-hero::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(ellipse at 78% 110%,rgba(76,195,255,.28),
  transparent 55%)}
.nb-hero svg.nb-scene{position:absolute;right:0;bottom:0;height:100%;z-index:1}
.nb-hero.has-kpi svg.nb-scene{right:190px}
@media(max-width:760px){.nb-hero.has-kpi svg.nb-scene{right:0}}
.nb-hero .nb-lines{position:absolute;left:-30px;top:-60px;width:320px;
  height:320px;opacity:.10}
.nb-tx{position:absolute;left:28px;top:50%;transform:translateY(-50%);z-index:3;
  display:flex;align-items:center;gap:16px}
.nb-tx img.nb-logo{height:64px;width:64px;object-fit:contain;
  filter:drop-shadow(0 2px 6px rgba(0,0,0,.5))}
.nb-ttl{margin:0;font-size:29px;font-weight:750;color:#EDF1F7;
  letter-spacing:-.01em;line-height:1.15}
.nb-ttl::before{content:"";display:inline-block;width:26px;height:4px;
  background:#4CC3FF;border-radius:2px;margin-right:12px;vertical-align:8px}
.nb-sub{color:#8B95A9;font-size:13px;margin-top:4px}
.nb-sub b{color:#EDF1F7;font-weight:600}
.nb-kpi{position:absolute;right:24px;top:50%;transform:translateY(-50%);
  text-align:right;z-index:3;background:rgba(11,14,20,.86);
  border:1px solid rgba(255,255,255,.12);border-radius:12px;
  padding:9px 15px;backdrop-filter:blur(4px)}
.nb-kpi .l{font-size:10px;text-transform:uppercase;letter-spacing:.08em;
  color:#8B95A9;font-weight:700}
.nb-kpi .v{font-size:21px;font-weight:800;color:#EDF1F7;
  font-variant-numeric:tabular-nums}
.nb-kpi .v.up{color:#2EE6A8}.nb-kpi .v.dn{color:#FF5C7A}.nb-kpi .v.acc{color:#4CC3FF}
@media(max-width:760px){.nb-kpi{display:none}.nb-tx img.nb-logo{display:none}
  .nb-ttl{font-size:22px}.nb-tx{left:18px;right:18px}.nb-sub{font-size:12px}
  .nb-hero svg.nb-scene{opacity:.28}.nb-hero .nb-lines{display:none}}

/* animations (one per motif) */
.nb-bounce{animation:nb-bounce 1.6s cubic-bezier(.3,0,.7,1) infinite alternate}
@keyframes nb-bounce{0%{transform:translateY(0) scaleY(1)}
  90%{transform:translateY(70px) scaleY(1)}100%{transform:translateY(76px) scaleY(.9)}}
.nb-shadow{transform-box:fill-box;transform-origin:center;
  animation:nb-shadow 1.6s cubic-bezier(.3,0,.7,1) infinite alternate}
@keyframes nb-shadow{0%{transform:scale(.5);opacity:.15}100%{transform:scale(1.2);opacity:.45}}
.nb-net{transform-box:fill-box;transform-origin:top center;
  animation:nb-net 2.8s ease-in-out infinite}
@keyframes nb-net{0%,60%,100%{transform:scaleY(1)}72%{transform:scaleY(1.12)}
  84%{transform:scaleY(.97)}}
.nb-pulse{transform-box:fill-box;transform-origin:center;
  animation:nb-pulse 2.2s ease-in-out infinite}
@keyframes nb-pulse{0%,100%{transform:scale(1);opacity:1}
  50%{transform:scale(1.6);opacity:.45}}
.nb-ring{transform-box:fill-box;transform-origin:center;
  animation:nb-ring 2.4s ease-out infinite}
@keyframes nb-ring{0%{transform:scale(.4);opacity:.7}100%{transform:scale(1.6);opacity:0}}
.nb-draw{stroke-dasharray:420;animation:nb-draw 7s ease-in-out infinite}
@keyframes nb-draw{0%{stroke-dashoffset:420}55%,100%{stroke-dashoffset:0}}
.nb-check{stroke-dasharray:60;animation:nb-check 3.6s ease-in-out infinite}
@keyframes nb-check{0%,15%{stroke-dashoffset:60}45%,85%{stroke-dashoffset:0}
  100%{stroke-dashoffset:60}}
.nb-blink{animation:nb-blink 1.1s steps(2,start) infinite}
@keyframes nb-blink{to{visibility:hidden}}
.nb-float{animation:nb-floaty 5s ease-in-out infinite}
@keyframes nb-floaty{0%,100%{transform:translateY(0) rotate(0deg)}
  50%{transform:translateY(-5px) rotate(1.2deg)}}
.nb-wobble{transform-box:fill-box;transform-origin:center;
  animation:nb-wobble 3s ease-in-out infinite}
@keyframes nb-wobble{0%,100%{transform:rotate(-4deg)}50%{transform:rotate(4deg)}}
@media(prefers-reduced-motion:reduce){
  .nb-bounce,.nb-shadow,.nb-net,.nb-pulse,.nb-ring,.nb-draw,.nb-check,
  .nb-blink,.nb-float,.nb-wobble,.nb-tick-track{animation:none}}

/* games ticker */
.nb-tick{background:#0B0E14;border-top:1px solid #232B3D;overflow:hidden;height:44px}
.nb-tick-track{display:flex;gap:10px;align-items:center;height:100%;
  width:max-content;padding:0 10px;animation:nb-roll 46s linear infinite}
.nb-tick:hover .nb-tick-track{animation-play-state:paused}
@keyframes nb-roll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
.nb-g{display:flex;align-items:center;gap:6px;background:#131824;
  border:1px solid #232B3D;border-radius:8px;padding:4px 10px;
  font-size:12px;color:#EDF1F7;white-space:nowrap;
  font-variant-numeric:tabular-nums}
.nb-g b{font-weight:700}
.nb-g .t{color:#8B95A9}
.nb-g .s{color:#4CC3FF;font-weight:700}
.nb-g img{height:18px;width:18px;object-fit:contain}
.nb-g .star{color:#FFC759;font-size:11px}
.nb-g .live{color:#2EE6A8;font-size:10px;font-weight:800;letter-spacing:.08em}
</style>
"""

# faint rink markings in the top-left corner (every page)
_LINES = ('<svg class="nb-lines" viewBox="0 0 100 100"><g fill="none" '
          'stroke="#fff" stroke-width="1.6"><circle cx="50" cy="50" r="18"/>'
          '<line x1="0" y1="50" x2="100" y2="50"/><circle cx="50" cy="50" r="2"/>'
          '<rect x="2" y="2" width="96" height="96" rx="22"/></g></svg>')

_PUCK = ('<ellipse cx="0" cy="3" rx="{r}" ry="{h}" fill="#0B0E14" stroke="#4CC3FF" '
         'stroke-width="1.5"/><ellipse cx="0" cy="0" rx="{r}" ry="{h}" fill="#1A2130" '
         'stroke="rgba(237,241,247,.7)" stroke-width="1.5"/>')


def _puck(r: float) -> str:
    return _PUCK.format(r=r, h=r * 0.38)


_NET = """
      <g fill="none" stroke="rgba(237,241,247,.6)" stroke-width="3">
        <path d="M{x} {y} v-46 h60 v46"/></g>
      <g class="nb-net"><path d="M{x} {y} l12 -38 h36 l12 38 M{x2} {y2} v30
            M{x3} {y2} v30 M{x4} {y2} v30" fill="none"
            stroke="rgba(237,241,247,.35)" stroke-width="1.5"/></g>
      <path d="M{x0} {y} h{w}" stroke="#FF5C7A" stroke-width="3"/>"""


def _net(x: int, y: int) -> str:
    return _NET.format(x=x, y=y, x2=x + 18, x3=x + 30, x4=x + 42, y2=y - 36,
                       x0=x - 20, w=100)


SCENES = {
    # Přehled: rink from above, a puck gliding across the centre circle
    "rink": f"""
      <g fill="none" stroke="rgba(237,241,247,.45)" stroke-width="3">
        <rect x="230" y="14" width="290" height="176" rx="46"/>
        <circle cx="375" cy="102" r="30"/></g>
      <line x1="375" y1="14" x2="375" y2="190" stroke="#FF5C7A" stroke-width="3" opacity=".7"/>
      <line x1="300" y1="14" x2="300" y2="190" stroke="#4CC3FF" stroke-width="3" opacity=".7"/>
      <line x1="450" y1="14" x2="450" y2="190" stroke="#4CC3FF" stroke-width="3" opacity=".7"/>
      <g><g>{_puck(12)}<animateMotion dur="4.5s" repeatCount="indefinite"
            path="M260 60 Q 375 150 495 70" calcMode="spline" keyPoints="0;1"
            keyTimes="0;1" keySplines="0.4 0 0.6 1"/></g></g>""",
    # Hráč: a puck flies into the net, the net ripples
    "player": f"""{_net(430, 118)}
      <path d="M270 128 q 90 -40 186 -30" stroke="rgba(76,195,255,.35)"
            stroke-width="2" stroke-dasharray="2 7" fill="none"/>
      <g><g>{_puck(9)}<animateMotion dur="2.4s" repeatCount="indefinite"
            path="M270 128 q 90 -40 186 -30" calcMode="spline" keyPoints="0;1"
            keyTimes="0;1" keySplines="0.3 0 0.7 1"/></g></g>
      <ellipse cx="380" cy="150" rx="200" ry="24" fill="rgba(76,195,255,.10)"/>""",
    # Brankáři: the net and a glove catching a bouncing puck
    "goalie": f"""{_net(410, 120)}
      <g transform="translate(470 58)"><g class="nb-wobble">
        <rect x="-22" y="-18" width="44" height="36" rx="14" fill="#EDF1F7"/>
        <path d="M-14 -6 h28 M-14 4 h28" stroke="#8B95A9" stroke-width="2"/></g></g>
      <g transform="translate(330 40)"><g class="nb-bounce">{_puck(10)}</g></g>""",
    # Týmy: two faceoff circles, the dots pulse
    "teams": """
      <g fill="none" stroke="rgba(237,241,247,.45)" stroke-width="3">
        <circle cx="330" cy="80" r="44"/><circle cx="460" cy="80" r="44"/></g>
      <g stroke="#FF5C7A" stroke-width="3">
        <path d="M312 72 h-10 M348 72 h10 M312 88 h-10 M348 88 h10"/>
        <path d="M442 72 h-10 M478 72 h10 M442 88 h-10 M478 88 h10"/></g>
      <circle class="nb-pulse" cx="330" cy="80" r="6" fill="#FF5C7A"/>
      <circle class="nb-pulse" style="animation-delay:1.1s" cx="460" cy="80" r="6"
              fill="#FF5C7A"/>""",
    # Kurzy: radar rings around a betting ticket with a puck
    "odds": f"""
      <g fill="none" stroke="#2EE6A8" stroke-width="2">
        <circle class="nb-ring" cx="420" cy="80" r="48"/>
        <circle class="nb-ring" style="animation-delay:.8s" cx="420" cy="80" r="48"/>
        <circle class="nb-ring" style="animation-delay:1.6s" cx="420" cy="80" r="48"/></g>
      <g transform="rotate(-8 420 80)"><g class="nb-float">
        <rect x="350" y="48" width="140" height="64" rx="9" fill="#EDF1F7"/>
        <line x1="452" y1="48" x2="452" y2="112" stroke="#8B95A9" stroke-dasharray="4 5"/>
        <rect x="362" y="60" width="70" height="8" rx="4" fill="#0B0E14"/>
        <rect x="362" y="74" width="80" height="6" rx="3" fill="#8B95A9"/>
        <rect x="362" y="86" width="50" height="6" rx="3" fill="#8B95A9"/>
        <rect x="362" y="98" width="34" height="8" rx="4" fill="#2EE6A8"/>
        <g transform="translate(471 80)">{_puck(12)}</g></g></g>""",
}


def hero(title: str, sub: str = "", kpi_label: str | None = None,
         kpi_value: str | None = None, kpi_cls: str = "",
         scene: str = "rink", ticker_html: str = "",
         logo_url: str | None = None) -> None:
    """Render the page's band (and optionally a ticker under it).

    `sub` may carry <b> for emphasis; everything else is escaped."""
    kpi = (f'<div class="nb-kpi"><div class="l">{html.escape(str(kpi_label))}</div>'
           f'<div class="v {kpi_cls}">{html.escape(str(kpi_value))}</div></div>'
           if kpi_label and kpi_value is not None else "")
    logo = (f'<img class="nb-logo" alt="" src="{html.escape(logo_url, quote=True)}">'
            if logo_url else "")
    cls = "nb-hero has-kpi" if kpi else "nb-hero"
    st.markdown(
        _CSS + f'<div class="nb-wrap"><div class="{cls}">{_LINES}'
        f'<svg class="nb-scene" viewBox="0 0 520 150" '
        f'preserveAspectRatio="xMaxYMax meet">{SCENES[scene]}</svg>'
        f'<div class="nb-tx">{logo}<div><div class="nb-ttl">{html.escape(title)}'
        f'</div><div class="nb-sub">{sub}</div></div></div>{kpi}</div>'
        f'{ticker_html}</div>',
        unsafe_allow_html=True)


def logo_url(abbr: str | None) -> str | None:
    return TEAM_LOGO.format(abbr=abbr) if abbr else None


def team_logo(abbr: str | None, size: int = 22) -> str:
    if not abbr:
        return ""
    return (f'<img src="{html.escape(logo_url(abbr), quote=True)}" alt="" '
            f'style="height:{size}px;width:{size}px;object-fit:contain;'
            'vertical-align:middle" onerror="this.style.display=&quot;none&quot;">')


def ticker(rows: list[dict]) -> str:
    """Games strip: rows = [{cas, a_ab, h_ab, score (str|None)}]."""
    if not rows:
        return ""
    chips = ""
    for r in rows:
        mid = (f'<span class="s">{html.escape(str(r["score"]))}</span>'
               if r.get("score") else '<span class="t">@</span>')
        chips += (f'<span class="nb-g"><span class="t">{html.escape(str(r["cas"]))}</span>'
                  f'{team_logo(r.get("a_ab"), 18)}<b>{html.escape(str(r["a_ab"]))}</b>'
                  f'{mid}{team_logo(r.get("h_ab"), 18)}'
                  f'<b>{html.escape(str(r["h_ab"]))}</b></span>')
    return (f'<div class="nb-tick"><div class="nb-tick-track">{chips}{chips}'
            '</div></div>')
