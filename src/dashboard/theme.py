"""Dashboard design system: colors, typography, Plotly template, CSS.

Light "Gameday" look of the MLB dashboard (user's choice, 2. 10. 2026):
navy accent, white cards on a cool gray ground, deep navy sidebar. The
component structure (setup_page, hero bands, router) comes from NBA_tool.
Semantic colors: navy = our numbers, steel = market, green = over / win,
red = under / loss, amber = warning.
"""
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ASSETS = Path(__file__).resolve().parents[2] / "assets"

COLORS = {
    "bg": "#eef1f4",
    "surface": "#ffffff",
    "surface2": "#f7f9fb",
    "border": "#e2e6ea",
    "text": "#0c1c33",
    "muted": "#5a6572",
    "accent": "#2E5FB7",       # MLB Gameday navy
    "accent_soft": "rgba(46, 95, 183, 0.14)",
    "model": "#2E5FB7",
    "baseline": "#8b95a9",
    "reality": "#0c1c33",
    "over": "#1e7a46",
    "under": "#b3403a",
    "warn": "#b7791f",
    "red": "#c8102e",
    "grid": "rgba(12, 28, 51, 0.08)",
}

FONT_STACK = ("Inter, -apple-system, BlinkMacSystemFont, 'SF Pro Text', "
              "'Segoe UI', Roboto, sans-serif")

PLOTLY_TEMPLATE = "nhl_light"
ROUTER_FLAG = "_nhl_router_active"


def register_plotly_template():
    pio.templates[PLOTLY_TEMPLATE] = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family=FONT_STACK, color=COLORS["text"], size=13),
            title=dict(font=dict(size=15, color=COLORS["text"])),
            xaxis=dict(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"],
                       linecolor=COLORS["border"]),
            yaxis=dict(gridcolor=COLORS["grid"], zerolinecolor=COLORS["grid"],
                       linecolor=COLORS["border"]),
            legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0,
                        orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(l=48, r=16, t=40, b=40),
            colorway=[COLORS["model"], COLORS["baseline"], COLORS["over"],
                      COLORS["under"], COLORS["warn"]],
            hoverlabel=dict(bgcolor=COLORS["surface2"], bordercolor=COLORS["border"],
                            font=dict(family=FONT_STACK, color=COLORS["text"])),
        )
    )
    pio.templates.default = PLOTLY_TEMPLATE


def inject_css():
    css = (ASSETS / "style.css").read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def setup_page(title: str, icon: str = "🏒", *, app: bool = False):
    """Call FIRST on every page. Under the router it already happened in
    this run (app=True is the router's own call and never skips); run
    standalone (AppTest, direct streamlit run) the page does it itself."""
    register_plotly_template()
    if st.session_state.get(ROUTER_FLAG) and not app:
        return
    tab_title = title if title.endswith("NHL Props") else f"{title} · NHL Props"
    st.set_page_config(page_title=tab_title, page_icon=icon,
                       layout="wide", initial_sidebar_state="auto")
    inject_css()


def metric_card(label: str, value: str, delta: str = "",
                delta_good: bool | None = None, footnote: str = "") -> str:
    delta_html = ""
    if delta:
        cls = ("delta-good" if delta_good else
               "delta-bad" if delta_good is not None else "delta-neutral")
        delta_html = f'<span class="metric-delta {cls}">{delta}</span>'
    foot = f'<div class="metric-footnote">{footnote}</div>' if footnote else ""
    return (f'<div class="metric-card"><div class="metric-label">{label}</div>'
            f'<div class="metric-value">{value}{delta_html}</div>{foot}</div>')


def badge(text: str, kind: str = "neutral") -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'


def stat_pill(label: str, value: str, sub: str = "", kind: str = "") -> str:
    sub_html = f'<div class="pill-sub">{sub}</div>' if sub else ""
    return (f'<div class="stat-pill {kind}"><div class="pill-label">{label}</div>'
            f'<div class="pill-value">{value}</div>{sub_html}</div>')


def pill_row(pills: list[str]) -> str:
    return f'<div class="pill-row">{"".join(pills)}</div>'


def section(title: str, hint: str = ""):
    h = f' <span class="hint">{hint}</span>' if hint else ""
    st.markdown(f'<div class="section-title">{title}{h}</div>', unsafe_allow_html=True)
