"""Page registry for click-through navigation (st.switch_page needs the
page object the router created). Pages run standalone (tests, direct run)
find it empty and simply do not navigate."""
import streamlit as st

PAGES: dict = {}


def goto(name: str, **state) -> None:
    for k, v in state.items():
        st.session_state[k] = v
    page = PAGES.get(name)
    if page is not None:
        st.switch_page(page)
