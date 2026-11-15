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
        return st.session_state.setdefault(key, value) if key else value

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

    def text_input(label, value="", key=None, **_):
        log("text_input", key)
        return st.session_state.setdefault(key, value)

    def selectbox(label, options, key=None, **_):
        log("selectbox", key)
        return st.session_state.setdefault(key, options[0])

    class Col:
        def __getattr__(self, name):
            return getattr(st, name)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def columns(n, **_):
        n = n if isinstance(n, int) else len(n)
        return [Col() for _ in range(n)]

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
    rec.update(charts=[], uploads={}, submit=set(), downloads=[], images=0)

    def cache_data(func=None, **_):
        return func if callable(func) else (lambda f: f)

    def keyed(name, default_from=None):
        def w(label=None, *a, key=None, value=None, default=None, options=None, index=0, **k):
            log(name, key, label)
            if key is None:
                return value if value is not None else default
            if default_from == "options":
                opts = options if options is not None else (a[0] if a else [])
                return st.session_state.setdefault(key, opts[index] if opts else None)
            init = value if value is not None else (default if default is not None else (a[2] if len(a) > 2 else None))
            return st.session_state.setdefault(key, init)
        return w

    def form_submit_button(label, **_):
        log("form_submit_button", text=label)
        hit = label in rec["submit"]
        rec["submit"].discard(label)
        return hit

    def file_uploader(label, type=None, key=None, **_):
        log("file_uploader", key, label)
        return rec["uploads"].pop(key, None)

    def camera_input(label, key=None, **_):
        log("camera_input", key, label)
        return rec["uploads"].pop(key, None)

    def vega_lite_chart(data=None, spec=None, **_):
        log("vega_lite_chart")
        rec["charts"].append(spec or data)

    def download_button(label, data, file_name=None, mime=None, key=None, **_):
        log("download_button", key, label)
        rec["downloads"].append(dict(name=file_name, data=data))

    def image(*a, **k):
        log("image")
        rec["images"] += 1

    st.cache_data, st.form_submit_button, st.file_uploader, st.camera_input = cache_data, form_submit_button, file_uploader, camera_input
    st.vega_lite_chart, st.download_button, st.image = vega_lite_chart, download_button, image
    st.selectbox = keyed("selectbox", "options")
    st.multiselect = keyed("multiselect")
    st.text_area = keyed("text_area")
    st.date_input = keyed("date_input")
    st.metric = lambda label, value, *a, **k: log("metric", text=f"{label}={value}")
    for name in ("success",):
        setattr(st, name, simple(name))
    st.chat_message = st.expander = st.spinner = st.popover = st.form = _ctx
    st.tabs = lambda labels, **_: [_ctx() for _ in labels]
    comp = types.ModuleType("streamlit.components")
    v1 = types.ModuleType("streamlit.components.v1")
    v1.html = lambda *a, **k: log("components.html")
    comp.v1 = v1
    st.components = comp
    st.__path__ = []                    # behave like a package so "import streamlit.components.v1" works
    return st


def run(st, script_path, max_reruns=5):
    code = compile(open(script_path, encoding="utf-8").read(), script_path, "exec")
    for _ in range(max_reruns):
        try:
            exec(code, {"__name__": "__main__", "__file__": script_path})
            return
        except Rerun:
            continue
