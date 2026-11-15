import pandas as pd
import streamlit as st
from backend import CROPS, get_recommendations
from climate import climate_summary

st.set_page_config(page_title="SoilSense", page_icon="🌱", layout="wide")

st.markdown("""
<style>
.hero {background: linear-gradient(90deg, #E8F5E9, #F9FBE7); border-radius: 16px;
       padding: 22px 28px; margin-bottom: 18px; border: 1px solid #DCE8D2;}
.hero h1 {margin: 0; color: #1B5E20;}
.hero p {margin: 4px 0 0 0; color: #3E5B3E; font-size: 1.05rem;}
.chip {background: #E8F5E9; color: #1B5E20; border: 1px solid #C5E1C5;
       border-radius: 999px; padding: 3px 12px; font-weight: 600; margin-right: 2px;}
.badge {border-radius: 999px; padding: 2px 10px; font-size: 0.8rem; font-weight: 700;}
.low {background: #E8F5E9; color: #1B5E20;}
.medium {background: #FFF8E1; color: #8D6E00;}
.high {background: #FDECEA; color: #B71C1C;}
.small {color: #5F7A5F; font-size: 0.85rem;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>🌱 SoilSense</h1>
  <p>Smarter crop rotations from NASA Earth observation data.</p>
</div>
""", unsafe_allow_html=True)

@st.cache_data
def load_climate():
    return climate_summary("climate.csv")  

climate = load_climate()

# ---------- sidebar: farmer inputs ----------
with st.sidebar:
    st.header("Your farm")
    existing = st.multiselect("Current rotation (pick 3 crops, in order)",
                              list(CROPS), max_selections=3)
    irrigation = st.number_input("Irrigation water (mm per year)", 0, 2000, 250, step=50)
    st.subheader("What matters most?")
    water = st.slider("Saving water", 0.5, 3.0, 1.0, 0.5)
    soil_w = st.slider("Soil health", 0.5, 3.0, 1.0, 0.5)
    income = st.slider("Income", 0.5, 3.0, 1.0, 0.5)
    go = st.button("Get recommendations", type="primary", use_container_width=True)
    st.caption("SoilSense supports, and does not replace, farmer and local expert judgment.")

if go:
    if len(existing) != 3:
        st.sidebar.warning("Please pick exactly 3 crops.")
    else:
        st.session_state["out"] = get_recommendations(
            climate, {"irrigation_mm": irrigation},
            {"water": water, "soil": soil_w, "income": income}, existing)

# ---------- climate snapshot ----------
st.subheader("Climate snapshot")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Typical rainfall", f"{climate['annual_rain_mm']} mm/yr")
c2.metric("Average temperature", f"{climate['avg_temp_c']} °C")
c3.metric("Warming trend", f"{climate['temp_trend_c']:+.3f} °C/yr")
c4.metric("Driest year", f"{climate['worst_year']}", f"{climate['worst_year_rain_mm']} mm", delta_color="off")
st.caption(f"NASA POWER daily data, {climate['years_used']}. Satellite and model estimates, "
           "please verify locally.")

# ---------- result cards ----------
def badge(level):
    return f"<span class='badge {level.lower()}'>{level} risk</span>"

def show(title, r):
    with st.container(border=True):
        left, right = st.columns([4, 1])
        chips = " ➜ ".join(f"<span class='chip'>{c.replace('_', ' ')}</span>" for c in r["rotation"])
        left.markdown(f"**{title}**")
        left.markdown(chips, unsafe_allow_html=True)
        right.metric("Score", f"{r['total_score']}/100")
        cols = st.columns(4)
        for col, key in zip(cols, ["soil", "water", "climate", "income"]):
            col.markdown(f"{key.title()} {badge(r['risk_meters'][key])}", unsafe_allow_html=True)
            col.progress(int(max(0, min(100, r["factor_scores"][key]))))
        with st.expander("Why this score?"):
            for reason in r["reasons"]:
                st.write("✅ " + reason)
            for gap in r["data_gaps"]:
                st.markdown(f"<span class='small'>⚠️ Data gap: {gap}</span>", unsafe_allow_html=True)

def score_chart(items):
    df = pd.DataFrame({"Score": [r["total_score"] for _, r in items]},
                      index=[label for label, _ in items])
    st.bar_chart(df, color="#2E7D32")

out = st.session_state.get("out")
if out is None:
    st.info("👈 Choose your current rotation and priorities in the sidebar, "
            "then click **Get recommendations**.")
else:
    tab1, tab2 = st.tabs(["Recommendations", f"Replay worst year ({climate['worst_year']})"])
    with tab1:
        items = [("Current", out["existing"])] + \
                [(f"Suggestion {i}", a) for i, a in enumerate(out["alternatives"], 1)]
        score_chart(items)
        for label, r in items:
            show(label if label != "Current" else "Your current rotation", r)
    with tab2:
        st.write(f"How each rotation would have scored in {climate['worst_year']}, "
                 f"the driest year on record ({climate['worst_year_rain_mm']} mm).")
        wy = out["worst_year"]
        items = [("Current", wy["existing"])] + \
                [(f"Suggestion {i}", a) for i, a in enumerate(wy["alternatives"], 1)]
        score_chart(items)
        for label, r in items:
            show(label if label != "Current" else "Your current rotation", r)