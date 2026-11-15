"""SoilSense agent. Two entry points:

    from soilsense_agent import render_agent_chat
    render_agent_chat()                       # whole chat UI (Streamlit)

    from soilsense_agent import ask_agent
    ask_agent(question, context, history)     # plain Python, no Streamlit
"""
from .agent import ask_agent


def render_agent_chat(context=None):
    from .ui import render_agent_chat as _render   # Streamlit is imported only when the UI is used
    return _render(context)


__all__ = ["ask_agent", "render_agent_chat"]
