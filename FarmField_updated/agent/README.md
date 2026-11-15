# SoilSense agent — what it adds to the app

| Page | File | What it shows |
|---|---|---|
| Main | `app.py` (3 lines added after the hero) | `render_home_overview()`: danger meter first, KPI cards, "why this level", coming days, alerts, charts, watering plan — then the team's rotation tool |
| Assistant | `pages/2_assistant.py` | `render_agent_chat()`: chat, voice, 📷 plant photo analysis |
| Farm report | `pages/3_farm_report.py` | `render_report_page()`: farm info form, AI insight card (why / meaning / action), explanatory charts, download |

Other blocks: `render_weather_panel()`, `render_irrigation_panel()`, `render_farm_dashboard()` (tabs).
Optional `context={"lat": .., "lon": .., "crop": "tomato", "lang": "ar"}` — then the farmer is not asked again.

## Secrets (Streamlit Cloud → Settings → Secrets). Never commit them.
`GROQ_API_KEY` (text + photos), `GEMINI_API_KEY` (text + photos), `OPENROUTER_API_KEY` (text; photos only if
`OPENROUTER_VISION_MODEL` is set). Weather needs no key (Open-Meteo). Put `.streamlit/secrets.toml` in `.gitignore`.

## Danger levels (0 green → 5 red) — thresholds in `config.py`
| Level | Colour | Examples |
|---|---|---|
| 5 Extreme | red | gusts ≥ 118 km/h (Beaufort 12, cyclone strength), rain ≥ 100 mm/day, dust > 1000 µg/m³ |
| 4 Very dangerous | dark orange | thunderstorm with hail, gusts ≥ 89 (storm), rain ≥ 50, dust storm ≥ 450, heat ≥ 48 °C |
| 3 Dangerous | orange | thunderstorm, gusts ≥ 62 (gale), heavy rain ≥ 25, thick dust ≥ 160, heat ≥ 45 °C |
| 2 Changeable | yellow | rain/showers/fog, gusts ≥ 39, dust ≥ 80, heat ≥ 42 °C |
| 1 Good | light green | partly cloudy, light dust ≥ 40 |
| 0 Ideal | green | sunny, calm |

Wind = Beaufort scale; dust = meteoblue desert-dust classes; **rain and heat limits are first guesses
(needs expert review)**. Forecasts are model output, not official warnings — the UI says so.

## Watering
Need before rain = Kc (FAO-56) × ET0 (Open-Meteo, FAO-56 Penman-Monteith). After rain = what is left after a
simple soil bucket (80 % of rain ≥ 2 mm counts, soil keeps up to 25 mm — needs expert review).
Charts: recent + coming days (red line = today) and a typical year by month (NASA POWER), each with a dashed
average line. 1 mm = 1 litre per m²; litres appear when the field area is given.

## Tests
```bash
python -m pytest agent/tests -q            # no key, no network
python -m agent.tests.run_eval             # 30 questions, Mock mode
SS_AGENT_WEATHER_DEMO=true streamlit run app.py   # offline demo weather (labelled DEMO)
```
