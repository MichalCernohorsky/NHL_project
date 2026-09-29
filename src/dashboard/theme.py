"""Dashboard design system: colors, typography, Plotly template, CSS.

Taken over from NBA_tool (src/dashboard/theme.py) so both dashboards read
as one family; only the accent changes - ice blue instead of basketball
orange. Semantic colors are fixed across the whole dashboard: accent =
our numbers, muted steel = market / baseline, over = green, under = red.
"""
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ASSETS = Path(__file__).resolve().parents[2] / "assets"

COLORS = {
    "bg": "#0B0E14",
    "surface": "#131824",
    "surface2": "#1A2130",
    "border": "#232B3D",
    "text": "#EDF1F7",
    "muted": "#8B95A9",
    "accent": "#4CC3FF",       # ice blue
    "accent_soft": "rgba(76, 195, 255, 0.16)",
    "model": "#4CC3FF",
    "baseline": "#7C89A6",
    "reality": "#EDF1F7",
    "over": "#2EE6A8",
    "under": "#FF5C7A",
    "warn": "#FFC759",
    "grid": "rgba(139, 149, 169, 0.14)",
}

FONT_STACK = ("Inter, -apple-system, BlinkMacSystemFont, 'SF Pro Text', "
              "'Segoe UI', Roboto, sans-serif")

PLOTLY_TEMPLATE = "nhl_dark"
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
