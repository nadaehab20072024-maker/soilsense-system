"""All settings in one place. Anything you may want to tune lives here."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv  
    load_dotenv()
except ImportError:
    pass

PKG_DIR = Path(__file__).resolve().parent

REPO_ROOT = Path(os.getenv("SOILSENSE_REPO_ROOT", PKG_DIR.parent)).resolve()
TEAM_CLIMATE_CSV = REPO_ROOT / "climate.csv"

PROC_DIR = PKG_DIR / "data" / "processed"
CACHE_DIR = Path(os.getenv("SOILSENSE_CACHE_DIR", PKG_DIR / "data" / "cache"))
PROMPT_DIR = PKG_DIR / "prompts"
GLOSSARY_PATH = PKG_DIR / "data" / "glossary.json"
RAW_DIR = PKG_DIR / "data" / "raw"          


def get_secret(name: str):
   
    try:
        import streamlit as st
        try:
            if name in st.secrets:
                return str(st.secrets[name]) or None
        except Exception:      
            pass
    except ImportError:
        pass
    return os.getenv(name) or None


def _flag(name: str, default: str = "false") -> bool:
    v = get_secret(name)          
    return (v if v is not None else default).strip().lower() in ("1", "true", "yes", "on")


# --- switches ---------------------------------------------------------------
USE_MOCK = _flag("USE_MOCK")                             
USE_POWER_API = _flag("USE_POWER_API", "true")            
ENABLE_VOICE_TOOL = _flag("SS_AGENT_ENABLE_VOICE")        
FORCE_FAKE_TEAM = _flag("SS_AGENT_FORCE_FAKE")            

# --- languages ----------------------------------------------------------------
LANG_NAMES = {"ar": "العربية", "en": "English", "bn": "বাংলা", "ur": "اردو", "hi": "हिन्दी"}
ENABLED_LANGS = [c for c in os.getenv("ENABLED_LANGS", "ar,en,bn").split(",") if c in LANG_NAMES]
RTL_LANGS = {"ar", "ur"}
DEFAULT_LANG = ENABLED_LANGS[0] if ENABLED_LANGS else "en"


PROVIDERS = [
    dict(name="gemini", key_env="GEMINI_API_KEY",
         base_url="https://generativelanguage.googleapis.com/v1beta/openai",
         model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
    dict(name="groq", key_env="GROQ_API_KEY",
         base_url="https://api.groq.com/openai/v1",
         model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")),
    dict(name="openrouter", key_env="OPENROUTER_API_KEY",
         base_url="https://openrouter.ai/api/v1",
         model=os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")),
]
LLM_TIMEOUT = 30
MAX_TOKENS = 900
MAX_TOOL_ROUNDS = 4

ROTATION_SITE_LABEL = {   
    "ar": "موقع واحد في الداخلية (23.71 شمال، 57.91 شرق)",
    "en": "one site in Al Dakhiliyah (23.71N, 57.91E)",
    "bn": "আল দাখিলিয়ার একটি স্থান (23.71N, 57.91E)",
}
ROTATION_SITE_FALLBACK = (23.7067, 57.9065)   
ROTATION_MAX_KM = 50          


PRIORITY_CHOICES = {"not_important": 0.5, "normal": 1.0, "very_important": 2.0}
PRIORITY_KEYS = ("water", "soil", "income")
DEFAULT_PRIORITY = 1.0
DEFAULT_IRRIGATION_MM = 250   
IRRIGATION_MAX_MM = 3000      


HEAT_DAY_C = 40.0
COMPLETE_YEAR_DAYS = 360
RISK_BINS = (40, 70, 90)
LOCAL_SITE_MAX_KM = 50
DIST_MEDIUM_KM = 50
DIST_LOW_KM = 150

# --- weather forecast, alerts, irrigation schedule (Open-Meteo: free, no key) ----------------
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
FORECAST_PAST_DAYS = 7          # days of recent weather shown before today
FORECAST_DAYS = 7               # days ahead (Open-Meteo allows up to 16)
FORECAST_TTL_S = 1800           # re-download at most every 30 minutes
TIMEZONE = os.getenv("SS_AGENT_TIMEZONE", "Asia/Muscat")   # for the greeting
REPORT_PAGE = "pages/3_farm_report.py"        # the overview links here
WEATHER_DEMO = _flag("SS_AGENT_WEATHER_DEMO")   # offline demo data, clearly labelled DEMO in the UI

# Severity levels 0 (ideal, green) ... 5 (extreme, red). Lower bound of each level 2..5.
# Wind gusts follow the Beaufort scale (km/h): 39 = force 6 strong breeze, 62 = force 8 gale,
# 89 = force 10 storm, 118 = force 12 hurricane force.
WIND_GUST_KMH = (39, 62, 89, 118)
# Dust (ug/m3, CAMS via Open-Meteo) follows meteoblue's desert-dust colour classes:
# <40 green, <80 light green, <160 yellow, <450 light orange, <1000 dark orange, >1000 red.
DUST_UGM3 = (80, 160, 450, 1000)
DUST_LIGHT_UGM3 = 40
# NEEDS EXPERT REVIEW (first guesses for an arid farm region):
RAIN_MM_DAY = (10, 25, 50, 100)
HEAT_TMAX_C = (42, 45, 48, 50)

# Irrigation bucket (NEEDS EXPERT REVIEW): share of rain that reaches the roots, rain below this is lost,
# and how much rain the soil can keep for the next days.
EFFECTIVE_RAIN_FRACTION = 0.8
MIN_EFFECTIVE_RAIN_MM = 2.0
SOIL_STORE_MM = 25.0

# --- photo analysis (vision models, free tiers) -------------------------------------------
VISION_PROVIDERS = [
    dict(name="gemini", key_env="GEMINI_API_KEY",
         base_url="https://generativelanguage.googleapis.com/v1beta/openai",
         model=os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")),
    dict(name="groq", key_env="GROQ_API_KEY", base_url="https://api.groq.com/openai/v1",
         model=os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")),
    dict(name="openrouter", key_env="OPENROUTER_API_KEY", base_url="https://openrouter.ai/api/v1",
         model=os.getenv("OPENROUTER_VISION_MODEL", "")),       # empty = skipped
]
IMAGE_MAX_PX = 1024             # photos are shrunk before upload (smaller, faster, within API limits)
PHOTO_MAX_MB = 10


if not any(get_secret(p["key_env"]) for p in PROVIDERS):
    USE_MOCK = True