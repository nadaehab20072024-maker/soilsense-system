"""Interface texts. Arabic/English written by the developer; Bengali (bn) and ur/hi NEED NATIVE REVIEW.
Missing keys fall back to English."""
from __future__ import annotations

S = {
    "title": {"ar": "مستشار SoilSense الزراعي", "en": "SoilSense Farm Advisor", "bn": "SoilSense কৃষি সহকারী",
              "ur": "SoilSense زرعی مددگار", "hi": "SoilSense कृषि सहायक"},
    "choose_language": {"ar": "اختر اللغة", "en": "Choose your language", "bn": "ভাষা বেছে নিন"},
    "ask": {"ar": "اكتب سؤالك هنا", "en": "Type your question", "bn": "আপনার প্রশ্ন লিখুন",
            "ur": "اپنا سوال لکھیں", "hi": "अपना सवाल लिखें"},
    "why": {"ar": "اقرأ المزيد: ليش هذي التوصية؟", "en": "Read more: why this advice?", "bn": "আরও পড়ুন: এই পরামর্শ কেন?",
            "ur": "یہ مشورہ کیوں؟", "hi": "यह सलाह क्यों?"},
    "confidence": {"ar": "مستوى الثقة", "en": "Confidence", "bn": "নির্ভরযোগ্যতা", "ur": "اعتماد کی سطح",
                   "hi": "भरोसे का स्तर"},
    "high": {"ar": "عالي", "en": "High", "bn": "বেশি", "ur": "زیادہ", "hi": "उच्च"},
    "medium": {"ar": "متوسط", "en": "Medium", "bn": "মাঝারি", "ur": "درمیانی", "hi": "मध्यम"},
    "low": {"ar": "منخفض", "en": "Low", "bn": "কম", "ur": "کم", "hi": "कम"},
    "sources": {"ar": "المصادر", "en": "Sources", "bn": "উৎস", "ur": "ذرائع", "hi": "स्रोत"},
    "caveats": {"ar": "تنبيهات مهمة عن البيانات", "en": "Important notes about the data", "bn": "ডেটা নিয়ে জরুরি কথা"},
    "busy": {"ar": "الخدمة مشغولة الحين، حاول بعد شوي.", "en": "The service is busy right now, please try again shortly.",
             "bn": "সেবা এখন ব্যস্ত, একটু পরে চেষ্টা করুন।", "ur": "سروس ابھی مصروف ہے، تھوڑی دیر بعد کوشش کریں۔",
             "hi": "सेवा अभी व्यस्त है, कृपया थोड़ी देर बाद कोशिश करें।"},
    "thinking": {"ar": "أجهّز الرد...", "en": "Preparing the answer...", "bn": "উত্তর তৈরি হচ্ছে...",
                 "ur": "جواب تیار ہو رہا ہے...", "hi": "जवाब तैयार हो रहा है..."},
    "fake_warning": {"ar": "⚠️ وضع تجريبي: أداة الدورة الزراعية الحقيقية (agent_tools.py) غير محمّلة. الدرجات المعروضة وهمية (FAKE).",
                     "en": "⚠️ Test mode: the real rotation tool (agent_tools.py) is not loaded. Scores shown are FAKE.",
                     "bn": "⚠️ পরীক্ষা মোড: আসল ফসল-চক্র টুল (agent_tools.py) লোড হয়নি। দেখানো স্কোরগুলো নকল (FAKE)।"},
    "mock_badge": {"ar": "وضع Mock: بدون ذكاء اصطناعي، ردود من القواعد والأدوات فقط.",
                   "en": "Mock mode: no AI model, answers come from rules and tools only.",
                   "bn": "Mock মোড: কোনো AI নেই, উত্তর শুধু নিয়ম ও টুল থেকে।"},
    # ---- risk meters (Low risk = good)
    "risk_Low": {"ar": "🟢 خطر منخفض (جيد)", "en": "🟢 Low risk (good)", "bn": "🟢 কম ঝুঁকি (ভালো)"},
    "risk_Medium": {"ar": "🟠 خطر متوسط", "en": "🟠 Some risk", "bn": "🟠 মাঝারি ঝুঁকি"},
    "risk_High": {"ar": "🔴 خطر عالي (انتبه)", "en": "🔴 High risk (take care)", "bn": "🔴 বেশি ঝুঁকি (সাবধান)"},
    "risk_legend": {"ar": "الأخضر = خطر منخفض = جيد.", "en": "Green = low risk = good.", "bn": "সবুজ = কম ঝুঁকি = ভালো।"},
    "f_soil": {"ar": "صحة التربة", "en": "Soil health", "bn": "মাটির স্বাস্থ্য"},
    "f_water": {"ar": "الماء", "en": "Water", "bn": "পানি"},
    "f_climate": {"ar": "تحمّل الحر والجفاف", "en": "Heat & drought tolerance", "bn": "গরম ও খরা সহনশীলতা"},
    "f_income": {"ar": "الدخل", "en": "Income", "bn": "আয়"},
    "risk_title": {"ar": "مستوى الخطر للخيار الأفضل", "en": "Risk levels for the best option", "bn": "সেরা বিকল্পের ঝুঁকি"},
    # ---- compare / replay
    "compare": {"ar": "📊 قارن: دورتك الحالية مقابل الأفضل", "en": "📊 Compare: your rotation vs the best option",
                "bn": "📊 তুলনা: আপনার চক্র বনাম সেরা বিকল্প"},
    "col_factor": {"ar": "العامل", "en": "Factor", "bn": "বিষয়"},
    "col_now": {"ar": "الحالية", "en": "Now", "bn": "এখন"},
    "col_best": {"ar": "الأفضل", "en": "Best", "bn": "সেরা"},
    "col_total": {"ar": "المجموع (من 100)", "en": "Total (out of 100)", "bn": "মোট (১০০-এর মধ্যে)"},
    "replay": {"ar": "🌵 أعد عرض أجفّ سنة", "en": "🌵 Replay the driest year", "bn": "🌵 সবচেয়ে শুকনো বছর আবার দেখুন"},
    "replay_story": {
        "ar": "في سنة {year} نزل {rain} ملم مطر فقط (المتوسط {avg} ملم{med}). دورتك الحالية ({ex}) كانت درجتها {ex_n} وصارت {ex_d}. "
              "الخيار الأفضل ({best}) كانت درجته {b_n} وصارت {b_d}.",
        "en": "In {year} only {rain} mm of rain fell (average {avg} mm{med}). Your current rotation ({ex}) goes from {ex_n} to {ex_d}. "
              "The best option ({best}) goes from {b_n} to {b_d}.",
        "bn": "{year} সালে মাত্র {rain} মিমি বৃষ্টি হয়েছিল (গড় {avg} মিমি{med})। আপনার বর্তমান চক্র ({ex}) {ex_n} থেকে {ex_d} হয়। "
              "সেরা বিকল্প ({best}) {b_n} থেকে {b_d} হয়।"},
    "replay_median": {"ar": "، والوسيط {m} ملم", "en": ", median {m} mm", "bn": ", মধ্যমা {m} মিমি"},
    "replay_flip": {"ar": "انتبه: في السنة الجافة الأفضل يصير {best}.", "en": "Note: in the dry year the best becomes {best}.",
                    "bn": "লক্ষ্য করুন: শুকনো বছরে সেরা হয় {best}।"},
    # ---- profile questions (tappable)
    "prio_title": {"ar": "وش أهم شي عندك؟ (اختياري)", "en": "What matters most to you? (optional)",
                   "bn": "আপনার কাছে কোনটা বেশি জরুরি? (ঐচ্ছিক)"},
    "p_water": {"ar": "توفير الماء", "en": "Saving water", "bn": "পানি বাঁচানো"},
    "p_soil": {"ar": "صحة التربة", "en": "Soil health", "bn": "মাটির স্বাস্থ্য"},
    "p_income": {"ar": "الدخل", "en": "Income", "bn": "আয়"},
    "c_not_important": {"ar": "مو مهم", "en": "Not important", "bn": "জরুরি নয়"},
    "c_normal": {"ar": "عادي", "en": "Normal", "bn": "সাধারণ"},
    "c_very_important": {"ar": "مهم جداً", "en": "Very important", "bn": "খুব জরুরি"},
    "irr_q": {"ar": "كم ماي سقي تستخدم في السنة تقريباً؟ (ملم)", "en": "About how much irrigation water do you use per year? (mm)",
              "bn": "বছরে আনুমানিক কত সেচের পানি দেন? (মিমি)"},
    "irr_hint": {"ar": "تقدير فقط. لو ما تعرف خلّه {d}.", "en": "Just an estimate. If unsure, leave {d}.",
                 "bn": "শুধু আনুমানিক। নিশ্চিত না হলে {d} রাখুন।"},
    "apply": {"ar": "حدّث التوصية", "en": "Update the advice", "bn": "পরামর্শ হালনাগাদ করুন"},
    "skip": {"ar": "تخطّي", "en": "Skip", "bn": "বাদ দিন"},
    "defaults_used": {"ar": "استخدمت القيم الافتراضية لـ: {items}.", "en": "I used default values for: {items}.",
                      "bn": "এগুলোর জন্য ডিফল্ট মান ব্যবহার করেছি: {items}।"},
    "d_water": {"ar": "أهمية الماء (عادي)", "en": "water priority (normal)", "bn": "পানির গুরুত্ব (সাধারণ)"},
    "d_soil": {"ar": "أهمية التربة (عادي)", "en": "soil priority (normal)", "bn": "মাটির গুরুত্ব (সাধারণ)"},
    "d_income": {"ar": "أهمية الدخل (عادي)", "en": "income priority (normal)", "bn": "আয়ের গুরুত্ব (সাধারণ)"},
    "d_irrigation_mm": {"ar": "ماي السقي {v} ملم (تقدير)", "en": "irrigation {v} mm (estimate)",
                        "bn": "সেচ {v} মিমি (আনুমানিক)"},
    # ---- safety / coverage lines added by code
    "caveat_line": {"ar": "الدرجات تقديرية من قواعد أولية، راجعها مع مرشد زراعي.",
                    "en": "Scores are rough estimates from early rules; check with a local farm advisor.",
                    "bn": "স্কোরগুলো প্রাথমিক নিয়ম থেকে আনুমানিক; স্থানীয় কৃষি পরামর্শকের সাথে মিলিয়ে নিন।"},
    "region_far": {"ar": "أداة الدورة تغطي فقط {site}. مزرعتك تبعد {d} كم، فالدرجات مو خاصة بمزرعتك.",
                   "en": "The rotation tool covers only {site}. Your farm is {d} km away, so these scores are not for your farm.",
                   "bn": "ফসল-চক্র টুল শুধু {site} এলাকার জন্য। আপনার খামার {d} কিমি দূরে, তাই স্কোরগুলো আপনার খামারের নয়।"},
    "region_unknown": {"ar": "أداة الدورة تغطي فقط {site}.", "en": "The rotation tool covers only {site}.",
                       "bn": "ফসল-চক্র টুল শুধু {site} এলাকার জন্য।"},
    "unsupported": {"ar": "للأسف {bad} غير مدعوم في أداة الدورة. المحاصيل المدعومة: {ok}.",
                    "en": "Sorry, {bad} is not supported by the rotation tool. Supported crops: {ok}.",
                    "bn": "দুঃখিত, {bad} ফসল-চক্র টুলে নেই। যেসব ফসল আছে: {ok}।"},
    "ask_rotation": {"ar": "وش المحاصيل اللي تزرعها الحين بالترتيب؟ مثلاً: قمح ثم طماطم.",
                     "en": "Which crops do you grow now, in order? For example: wheat, then tomato.",
                     "bn": "এখন কোন ফসলগুলো পরপর চাষ করেন? যেমন: গম, তারপর টমেটো।"},
    "supported_list": {"ar": "المحاصيل المدعومة: {ok}.", "en": "Supported crops: {ok}.", "bn": "যেসব ফসল আছে: {ok}।"},
    "refuse_offtopic": {"ar": "أقدر أساعدك فقط في الزراعة: المحاصيل، الماء، التربة والطقس.",
                        "en": "I can only help with farming: crops, water, soil and weather.",
                        "bn": "আমি শুধু চাষাবাদে সাহায্য করতে পারি: ফসল, পানি, মাটি ও আবহাওয়া।"},
    "refuse_chemical": {"ar": "ما أعطي جرعات مبيدات أو كيماويات. اسأل مكتب الإرشاد الزراعي القريب منك.",
                        "en": "I don't give pesticide or chemical doses. Please ask your local agricultural extension office.",
                        "bn": "আমি কীটনাশক বা রাসায়নিকের মাত্রা বলি না। স্থানীয় কৃষি সম্প্রসারণ অফিসে জিজ্ঞেস করুন।"},
    "photo_hint": {"ar": "ملاحظة الصورة مجرد تلميح أولي، مو تشخيص.", "en": "Photo remarks are early hints, not a diagnosis.",
                   "bn": "ছবির মন্তব্য শুধু প্রাথমিক ইঙ্গিত, রোগনির্ণয় নয়।"},
    "removed_numbers": {"ar": "حذفت رقماً لم أجده في البيانات.", "en": "I removed a number I could not find in the data.",
                        "bn": "ডেটায় পাইনি এমন একটি সংখ্যা বাদ দিয়েছি।"},
    # ---- what-if suggestion buttons (scenario sizes are user choices, not data)
    "wi_hotter": {"ar": "ماذا لو صار الجو أحر بدرجتين؟", "en": "What if it gets 2°C hotter?", "bn": "যদি ২°C বেশি গরম হয়?"},
    "wi_less_rain": {"ar": "ماذا لو قلّ المطر 30%؟", "en": "What if rain drops by 30%?", "bn": "যদি বৃষ্টি ৩০% কমে?"},
    "wi_less_water": {"ar": "ماذا لو صار عندي نص ماي السقي؟", "en": "What if I have half the irrigation water?",
                      "bn": "যদি সেচের পানি অর্ধেক হয়?"},
    "wi_story": {"ar": "في هذا السيناريو: دورتك الحالية {a}→{b}، والخيار الأفضل {c}→{d} (من 100).",
                 "en": "In this scenario: your rotation {a}→{b}, best option {c}→{d} (out of 100).",
                 "bn": "এই পরিস্থিতিতে: আপনার চক্র {a}→{b}, সেরা বিকল্প {c}→{d} (১০০-এর মধ্যে)।"},
    "wi_temp_note": {"ar": "درجات الدورة ما تتغير مع الحرارة في القواعد الحالية؛ لكن أيام الحر تزيد من {h0} إلى {h1}.",
                     "en": "Rotation scores do not change with heat in the current rules; but heat days go from {h0} to {h1}.",
                     "bn": "বর্তমান নিয়মে গরমে চক্রের স্কোর বদলায় না; তবে গরম দিনের সংখ্যা {h0} থেকে {h1} হয়।"},
    "voice_text": {"ar": "نص للقراءة بصوت (إنجليزي)", "en": "Text for reading aloud", "bn": "জোরে পড়ার লেখা (ইংরেজি)"},
    "clear": {"ar": "محادثة جديدة", "en": "New chat", "bn": "নতুন আলাপ"},
}

CROP_NAMES = {   # display names (bn NEEDS NATIVE REVIEW)
    "wheat": {"ar": "قمح", "en": "wheat", "bn": "গম"},
    "barley": {"ar": "شعير", "en": "barley", "bn": "যব"},
    "sorghum": {"ar": "ذرة رفيعة", "en": "sorghum", "bn": "জোয়ার"},
    "pearl_millet": {"ar": "دخن", "en": "pearl millet", "bn": "বাজরা"},
    "cowpea": {"ar": "لوبيا", "en": "cowpea", "bn": "বরবটি"},
    "chickpea": {"ar": "حمص", "en": "chickpea", "bn": "ছোলা"},
    "tomato": {"ar": "طماطم", "en": "tomato", "bn": "টমেটো"},
    "onion": {"ar": "بصل", "en": "onion", "bn": "পেঁয়াজ"},
    "sesame": {"ar": "سمسم", "en": "sesame", "bn": "তিল"},
    "okra": {"ar": "بامية", "en": "okra", "bn": "ঢেঁড়স"},
}

# Standard caveats by code (numbers filled from rotation_tools.data_quality()).
CAVEATS = {
    "placeholder_scores": {
        "ar": "قيم المحاصيل في قواعد التقييم مبدئية (backend.py يقول إنها مؤقتة)، مو قياسات زراعية.",
        "en": "Crop values in the scoring rules are rough placeholders (backend.py says so), not agronomic measurements.",
        "bn": "স্কোরের নিয়মে ফসলের মানগুলো অস্থায়ী (backend.py নিজেই বলে), কৃষি পরিমাপ নয়।"},
    "no_soil_data": {
        "ar": "ما فيه قياس للتربة في البيانات؛ درجة التربة محسوبة من صفات المحاصيل فقط.",
        "en": "There is no soil measurement; the soil score comes only from crop traits.",
        "bn": "মাটির কোনো পরিমাপ নেই; মাটির স্কোর শুধু ফসলের বৈশিষ্ট্য থেকে।"},
    "irrigation_estimate": {
        "ar": "كمية السقي تقدير من المزارع.", "en": "The irrigation amount is a farmer estimate.",
        "bn": "সেচের পরিমাণ কৃষকের আনুমানিক হিসাব।"},
    "reanalysis_rain": {
        "ar": "المطر تقدير من NASA POWER (MERRA-2) مو من محطة. سنة {wettest_year} فيها {wettest_year_rain_mm:.0f} ملم وهذا غالباً مبالغ فيه. المتوسط {mean_rain_mm} ملم والوسيط {median_rain_mm} ملم.",
        "en": "Rainfall is a NASA POWER (MERRA-2) estimate, not a rain gauge. {wettest_year} shows {wettest_year_rain_mm:.0f} mm, likely overstated. Mean {mean_rain_mm} mm, median {median_rain_mm} mm.",
        "bn": "বৃষ্টি NASA POWER (MERRA-2)-এর আনুমানিক হিসাব, বৃষ্টিমাপক নয়। {wettest_year} সালে {wettest_year_rain_mm:.0f} মিমি দেখায়, সম্ভবত বাড়িয়ে। গড় {mean_rain_mm} মিমি, মধ্যমা {median_rain_mm} মিমি।"},
    "water_optimistic": {
        "ar": "درجة الماء غالباً متفائلة: اتجاه المطر المستخدم {rain_trend_used_pct}% (بدون {wettest_year} فقط {rain_trend_without_wettest_year_pct}%) ويزيد الماء المتاح {water_supply_boost_pct:.0f}%.",
        "en": "The water score is likely optimistic: the rain trend used is {rain_trend_used_pct}% (only {rain_trend_without_wettest_year_pct}% without {wettest_year}), which adds {water_supply_boost_pct:.0f}% to water supply.",
        "bn": "পানির স্কোর সম্ভবত বেশি আশাবাদী: ব্যবহৃত বৃষ্টির প্রবণতা {rain_trend_used_pct}% ({wettest_year} বাদে মাত্র {rain_trend_without_wettest_year_pct}%), যা পানির জোগান {water_supply_boost_pct:.0f}% বাড়ায়।"},
    "data_gaps": {
        "ar": "الأداة ما ذكرت نقص في البيانات، لكن هذا ما يعني إن البيانات كاملة.",
        "en": "The tool reported no data gaps, but that does not mean the data is complete.",
        "bn": "টুল কোনো ঘাটতি দেখায়নি, তবে এর মানে ডেটা সম্পূর্ণ নয়।"},
    "data_gaps_list": {"ar": "نقص في البيانات ذكرته الأداة: {gaps}", "en": "Data gaps reported by the tool: {gaps}",
                       "bn": "টুল যে ঘাটতি জানিয়েছে: {gaps}"},
}


def t(key: str, lang: str, **kw) -> str:
    row = S[key]
    text = row.get(lang) or row["en"]
    return text.format(**kw) if kw else text


def crop_name(crop: str, lang: str) -> str:
    return CROP_NAMES.get(crop, {}).get(lang) or CROP_NAMES.get(crop, {}).get("en") or crop


def crops_text(crops: list[str], lang: str) -> str:
    sep = "، " if lang in ("ar", "ur") else ", "
    return sep.join(crop_name(c, lang) for c in crops)


def caveat_text(cav: dict, lang: str, quality: dict) -> str:
    code = cav["code"]
    if code == "data_gaps" and cav["text"].startswith("Data gaps reported"):
        gaps = cav["text"].split(":", 1)[1].strip()
        row = CAVEATS["data_gaps_list"]
        return (row.get(lang) or row["en"]).format(gaps=gaps)
    row = CAVEATS.get(code)
    if not row:
        return cav["text"]
    try:
        return (row.get(lang) or row["en"]).format(**quality)
    except (KeyError, ValueError):       # data quality unavailable (FAKE stub) -> English text from the tool
        return cav["text"]
