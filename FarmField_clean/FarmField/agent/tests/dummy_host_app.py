"""Tiny stand-in for the teammate's existing Streamlit app: it has its OWN widgets and session keys with
similar names, then adds the agent with the two official lines. Used by the UI tests."""
import streamlit as st

st.session_state.setdefault("msgs", "HOST VALUE")          # host keys that look like the agent's
st.session_state.setdefault("lang", "host-lang")
st.text_input("Host farm name", key="input")
st.selectbox("Host language", ["en", "ar"], key="profile")

from soilsense_agent import render_agent_chat  # noqa: E402

render_agent_chat()
