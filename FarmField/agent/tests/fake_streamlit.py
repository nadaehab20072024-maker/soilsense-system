"""A minimal recording stand-in for the Streamlit API used by ui.py and dummy_host_app.py.
Lets us check key prefixes, CSS scoping and 'no set_page_config' where Streamlit is not installed.
It is NOT Streamlit: real rendering is checked by test_streamlit_apptest.py (needs streamlit)."""
import contextlib
import types


class Rerun(Exception):
    pass


def make():
    st = types.ModuleType("streamlit")
    st.session_state = {}
    st.secrets = {}
    rec = dict(keys=[], calls=[], styles=[], texts=[], inputs=[], clicks=set())
    st._rec = rec

    def log(name, key=None, text=None):
        rec["calls"].append(name)
        if key is not None:
            rec["keys"].append(key)
        if text is not None:
            rec["texts"].append(str(text))

    @contextlib.contextmanager
    def _ctx(*a, **k):
        yield st

    def container(key=None, border=None, **_):
        log("container", key)
        return _ctx()

    def markdown(body, unsafe_allow_html=False, **_):
        log("markdown", text=body)
        if "<style" in str(body):
            rec["styles"].append(body)

    def radio(label, options, index=0, horizontal=False, key=None, format_func=str, **_):
        log("radio", key, label)
        return st.session_state.setdefault(key, options[index])

    def number_input(label, min_value=None, max_value=None, value=0, step=None, key=None, help=None, **_):
        log("number_input", key, label)
        return st.session_state.setdefault(key, value)

    def button(label, key=None, on_click=None, kwargs=None, args=None, type=None, **_):
        log("button", key, label)
        if key in rec["clicks"]:
            rec["clicks"].discard(key)
            if on_click:
                on_click(*(args or ()), **(kwargs or {}))
            return True
        return False

    def chat_input(placeholder=None, key=None, **_):
        log("chat_input", key)
        return rec["inputs"].pop(0) if rec["inputs"] else None

    def text_input(label, key=None, **_):
        log("text_input", key)
        return st.session_state.setdefault(key, "")

    def selectbox(label, options, key=None, **_):
        log("selectbox", key)
        return st.session_state.setdefault(key, options[0])

    def columns(n, **_):
        n = n if isinstance(n, int) else len(n)
        return [st for _ in range(n)]

    def rerun():
        raise Rerun()

    def set_page_config(*a, **k):
        log("set_page_config")

    def simple(name):
        return lambda body="", *a, **k: log(name, text=body)

    for name in ("subheader", "caption", "warning", "info", "write", "title", "error"):
        setattr(st, name, simple(name))
    st.container, st.markdown, st.radio, st.number_input, st.button = container, markdown, radio, number_input, button
    st.chat_input, st.text_input, st.selectbox, st.columns, st.rerun = chat_input, text_input, selectbox, columns, rerun
    st.set_page_config = set_page_config
    st.chat_message = st.expander = st.spinner = _ctx
    return st


def run(st, script_path, max_reruns=5):
    code = compile(open(script_path, encoding="utf-8").read(), script_path, "exec")
    for _ in range(max_reruns):
        try:
            exec(code, {"__name__": "__main__"})
            return
        except Rerun:
            continue
