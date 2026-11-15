"""Tiny stand-in for the teammate's existing Streamlit app: it has its OWN widgets and session keys with
similar names, then adds the agent with the two official lines. Used by the UI tests."""
import streamlit as st

st.session_state.setdefault("msgs", "HOST VALUE")          # host keys that look like the agent's
st.session_state.setdefault("lang", "host-lang")
st.text_input("Host farm name", key="input")
st.selectbox("Host language", ["en", "ar"], key="profile")

import importlib  # noqa: E402
import pathlib  # noqa: E402
import sys  # noqa: E402

_pkg_dir = pathlib.Path(__file__).resolve().parents[1]          # the agent folder, whatever it is called
sys.path.insert(0, str(_pkg_dir.parent))
render_agent_chat = importlib.import_module(_pkg_dir.name).render_agent_chat

render_agent_chat()
