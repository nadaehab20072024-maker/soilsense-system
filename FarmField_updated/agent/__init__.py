"""SoilSense agent. Two entry points:

    from agent import render_agent_chat
    render_agent_chat()                       # whole chat UI (Streamlit)

    from agent import ask_agent
    ask_agent(question, context, history)     # plain Python, no Streamlit
"""
from .agent import ask_agent


def render_agent_chat(context=None):
    from .ui import render_agent_chat as _render   # Streamlit is imported only when the UI is used
    return _render(context)


def render_farm_dashboard(context=None):
    """Weather with danger colours + alerts, watering chart, farm report (tabs)."""
    from .dashboard_ui import render_farm_dashboard as _render
    return _render(context)


def render_home_overview(context=None):
    """Main page block: danger meter first, KPI cards, why-this-level, coming days, alerts, charts."""
    from .dashboard_ui import render_home_overview as _render
    return _render(context)


def render_report_page(context=None):
    """Separate report page: farm info form, AI insights card, explanatory charts, download."""
    from .dashboard_ui import render_report_page as _render
    return _render(context)


def render_weather_panel(context=None):
    from .dashboard_ui import render_weather_panel as _render
    return _render(context)


def render_irrigation_panel(context=None):
    from .dashboard_ui import render_irrigation_panel as _render
    return _render(context)


def render_farm_report(context=None):
    from .dashboard_ui import render_farm_report as _render
    return _render(context)


__all__ = ["ask_agent", "render_agent_chat", "render_home_overview", "render_report_page", "render_farm_dashboard", "render_weather_panel",
           "render_irrigation_panel", "render_farm_report"]
