from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import requests
import re

app = Flask(__name__)
CORS(app)

CSV_PATH = r"C:\Users\abdoe\Downloads\Rag_data.csv"
OLLAMA_URL = "http://localhost:11434/api/generate"

print("Loading CSV...")
df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", low_memory=False)
df.columns = df.columns.str.strip()
print(f"Loaded {len(df)} rows")


def ask_ollama(prompt):
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": "llama3.2",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "stop": ["\n\n\n", "###", "---"]},
            },
            timeout=180,
        )
        result = resp.json().get("response", "")
        # منع التكرار - خد أول فقرتين بس
        lines = result.strip().split("\n")
        seen = []
        final = []
        for line in lines:
            stripped = line.strip()
            if stripped and stripped not in seen:
                seen.append(stripped)
                final.append(line)
        return "\n".join(final[:30])  # أقصى 30 سطر
    except Exception as e:
        print("Ollama error:", str(e))
        return ""


def get_embedding(text):
    resp = requests.post(
        "http://localhost:11434/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=30,
    )
    return resp.json()["embedding"]


def search_qdrant(query_vector, limit=5):
    resp = requests.post(
        "http://localhost:6333/collections/rag_data/points/search",
        json={"vector": query_vector, "limit": limit, "with_payload": True},
    )
    return resp.json().get("result", [])


def is_individual_request(question):
    individual_keywords = [
        "اعطيني",
        "أعطيني",
        "مثال",
        "نموذج",
        "سجل",
        "شخص",
        "اعرفني",
        "أخبرني",
        "صف",
        "وصف",
    ]
    return any(kw in question for kw in individual_keywords)


def is_analytical_request(question):
    analytical_keywords = [
        "حلل",
        "تحليل",
        "دلالة",
        "دلاله",
        "علاقة",
        "علاقه",
        "قارن",
        "مقارنة",
        "مقارنه",
        "فجوة",
        "فجوه",
        "ما مدى",
        "ما دلالة",
        "ما العلاقة",
        "تأثير جائحة",
        "تأثير كوفيد",
        "تأثير كورونا على",
    ]
    return any(kw in question for kw in analytical_keywords)


def is_statistical(question):
    if is_individual_request(question) or is_analytical_request(question):
        return False
    statistical_keywords = [
        "كم",
        "عدد",
        "نسبة",
        "مجموع",
        "متوسط",
        "معدل",
        "توزيع",
        "إجمالي",
        "أكثر",
        "أقل",
        "وسيط",
        "إناث",
        "ذكور",
        "جنس",
        "عاطل",
        "بطالة",
        "تشغيل",
        "راتب",
        "دخل",
        "أجر",
        "قطاع",
        "محافظة",
        "محافظات",
        "معاق",
        "إعاقة",
        "اعاقة",
        "ذوي الهمم",
        "أصحاب الهمم",
        "اصحاب الهمم",
        "ذوى الهمم",
        "أنواع الإعاقة",
        "تعليم",
        "مؤهل",
        "تدريب",
        "عمر",
        "سن",
        "فئة عمرية",
        "متزوج",
        "أعزب",
        "مطلق",
        "أرمل",
        "حالة اجتماعية",
        "تأمين اجتماعي",
        "تأمين صحي",
        "تأمين",
        "عقد",
        "ساعات",
        "ريف",
        "حضر",
        "منطقة",
        "مناطق",
        "كورونا",
        "كوفيد",
        "رسمي",
        "إجازة",
        "مدفوعة",
        "أمي",
        "أمية",
        "قسم",
        "أقسام",
        "مركز",
        "مراكز",
        "وظيفة ثانية",
        "وظيفه ثانيه",
        "ثانوية",
        "ثانويه",
        "سنة العمل",
        "بداية العمل",
        "منذ عام",
    ]
    return any(kw in question for kw in statistical_keywords)


def get_disability_count(col):
    counts = df[col].value_counts()
    total = 0
    for k, v in counts.items():
        if k != "لا يوجد صعوبة":
            total += v
    return total


def get_analytical_stats(question):
    """تجمع إحصاءات حقيقية بناءً على نوع السؤال التحليلي"""
    q = question
    stats = {}

    # توظيف الرجال والنساء
    if any(x in q for x in ["رجال", "نساء", "جنس", "ذكور", "إناث", "فجوة"]):
        gender_employ = (
            df.groupby(["Gender", "Employment_Status"]).size().unstack(fill_value=0)
        )
        stats["توزيع التوظيف حسب الجنس"] = gender_employ.to_string()

        # فجوة الرواتب
        if "Monthly_Salary" in df.columns:
            salary_gender = (
                df[df["Monthly_Salary"] > 0]
                .groupby("Gender")["Monthly_Salary"]
                .apply(lambda x: pd.to_numeric(x, errors="coerce").mean())
            )
            stats["متوسط الراتب حسب الجنس"] = salary_gender.to_string()

    # العمالة غير الرسمية
    if any(x in q for x in ["غير رسمية", "غير الرسمية", "رسمي"]):
        informal = df["Is_Informal_Worker"].value_counts()
        total = informal.sum()
        stats["توزيع العمالة الرسمية وغير الرسمية"] = "\n".join(
            [f"{k}: {v:,} ({v/total*100:.1f}%)" for k, v in informal.items()]
        )
        # توزيع غير الرسميين حسب القطاع
        if "Sector" in df.columns:
            informal_sector = df[df["Is_Informal_Worker"] == "غير رسمي"][
                "Sector"
            ].value_counts()
            stats["قطاعات العمالة غير الرسمية"] = informal_sector.to_string()

    # التعليم والراتب
    if any(x in q for x in ["تعليم", "مؤهل"]) and any(
        x in q for x in ["راتب", "دخل", "أجر"]
    ):
        edu_salary = (
            df[pd.to_numeric(df["Monthly_Salary"], errors="coerce") > 0]
            .groupby("Education_Level")["Monthly_Salary"]
            .apply(lambda x: pd.to_numeric(x, errors="coerce").mean())
            .sort_values(ascending=False)
        )
        stats["متوسط الراتب حسب المستوى التعليمي"] = edu_salary.to_string()

    # الرواتب حسب القطاع
    if any(x in q for x in ["قطاع", "حكومي", "خاص"]) and any(
        x in q for x in ["راتب", "دخل", "توزيع"]
    ):
        sector_salary = (
            df[pd.to_numeric(df["Monthly_Salary"], errors="coerce") > 0]
            .groupby("Sector")["Monthly_Salary"]
            .apply(
                lambda x: pd.to_numeric(x, errors="coerce").agg(
                    ["mean", "median", "count"]
                )
            )
        )
        stats["إحصاءات الراتب حسب القطاع"] = sector_salary.to_string()

    # كوفيد وساعات العمل والرواتب
    if any(x in q for x in ["كوفيد", "كورونا", "جائحة"]):
        covid = df["COVID_Salary_Reduction"].value_counts()
        total_covid = covid.sum()
        stats["تأثير كوفيد على الرواتب"] = "\n".join(
            [f"{k}: {v:,} ({v/total_covid*100:.1f}%)" for k, v in covid.items()]
        )
        # ساعات العمل
        hours_change = df["Working_Hours_Change_Reason"].value_counts().head(5)
        stats["أسباب تغيير ساعات العمل"] = hours_change.to_string()

    # العمالة حضر وريف
    if any(x in q for x in ["حضر", "ريف", "مناطق"]):
        region = df["Region_Type"].value_counts()
        total_r = region.sum()
        stats["توزيع الحضر والريف"] = "\n".join(
            [f"{k}: {v:,} ({v/total_r*100:.1f}%)" for k, v in region.items()]
        )
        # التوظيف حسب المنطقة
        region_employ = (
            df.groupby(["Region_Type", "Employment_Status"])
            .size()
            .unstack(fill_value=0)
        )
        stats["التوظيف حسب المنطقة"] = region_employ.to_string()

    return stats


def handle_analytical(question):
    """يجمع إحصاءات حقيقية ويطلب من llama3.2 يحللها"""
    stats = get_analytical_stats(question)

    if stats:
        stats_text = "\n\n".join([f"**{k}:**\n{v}" for k, v in stats.items()])
        prompt = f"""أنت محلل بيانات متخصص في سوق العمل المصري.
البيانات الإحصائية الحقيقية:
{stats_text}

السؤال: {question}

اكتب تحليلاً موجزاً وواضحاً بالعربي في 5-7 أسطر فقط.
استخدم الأرقام الحقيقية من البيانات.
لا تكرر نفس المعلومة.
لا تزيد عن 7 أسطر."""
    else:
        prompt = f"""أنت محلل بيانات متخصص في سوق العمل المصري.
إجمالي الأفراد في البيانات: {len(df):,}
المحافظات: {df['Governorate_Name'].nunique()} محافظة
الفترة الزمنية: {df['Quarter_ID'].unique().tolist() if 'Quarter_ID' in df.columns else 'غير متاح'}

السؤال: {question}

اكتب تحليلاً موجزاً في 5-7 أسطر فقط بالعربي. لا تكرر نفس المعلومة."""

    return ask_ollama(prompt)


def compute_stats(question):
    q = question

    if any(x in q for x in ["تأمين اجتماعي", "ضمان اجتماعي", "تامين اجتماعي"]):
        counts = df["Social_Security_Status"].value_counts()
        total_with_data = counts.sum()
        yes = counts.get("نعم", 0)
        no = counts.get("لا", 0)
        return (
            f"التأمين الاجتماعي للعاملين:\n"
            f"عندهم تأمين اجتماعي: {yes:,} ({yes/total_with_data*100:.1f}%)\n"
            f"مش عندهم تأمين اجتماعي: {no:,} ({no/total_with_data*100:.1f}%)\n"
            f"إجمالي العاملين في العينة: {total_with_data:,}"
        )

    if any(x in q for x in ["تأمين صحي", "تامين صحي", "تغطية صحية"]):
        counts = df["Health_Insurance_Status"].value_counts()
        total_with_data = counts.sum()
        yes = counts.get("نعم", 0)
        no = counts.get("لا", 0)
        return (
            f"التأمين الصحي للعاملين:\n"
            f"عندهم تأمين صحي: {yes:,} ({yes/total_with_data*100:.1f}%)\n"
            f"مش عندهم تأمين صحي: {no:,} ({no/total_with_data*100:.1f}%)\n"
            f"إجمالي العاملين في العينة: {total_with_data:,}"
        )

    if any(x in q for x in ["إجازة", "أجازة", "مدفوعة", "مدفوعه"]):
        counts = df["Paid_Leave_Benefit"].value_counts()
        total_with_data = counts.sum()
        yes = counts.get("نعم", 0)
        no = counts.get("لا", 0)
        return (
            f"الإجازة المدفوعة للعاملين:\n"
            f"عندهم إجازة مدفوعة: {yes:,} ({yes/total_with_data*100:.1f}%)\n"
            f"مش عندهم إجازة مدفوعة: {no:,} ({no/total_with_data*100:.1f}%)\n"
            f"إجمالي العاملين في العينة: {total_with_data:,}"
        )

    if any(
        x in q
        for x in [
            "زواج",
            "متزوج",
            "أعزب",
            "مطلق",
            "أرمل",
            "حالة اجتماعية",
            "الحالة الاجتماعية",
            "حالة اجتماعيه",
            "الحالة الاجتماعيه",
        ]
    ):
        counts = df["Marital_Status"].value_counts()
        total = len(df)
        result = ""
        for k, v in counts.items():
            result += f"{k}: {v:,} ({v/total*100:.1f}%)\n"
        return f"توزيع الحالة الاجتماعية:\n{result}"

    if any(
        x in q
        for x in [
            "وظيفة ثانية",
            "وظيفه ثانيه",
            "ثانوية",
            "ثانويه",
            "عمل ثانوي",
            "عمل تاني",
        ]
    ):
        if any(x in q for x in ["دخل", "راتب", "أجر", "مرتب"]):
            valid = pd.to_numeric(df["Secondary_Monthly_Income"], errors="coerce")
            valid = valid[valid > 0].dropna()
            return (
                f"إحصائيات دخل الوظيفة الثانوية:\n"
                f"عدد من لديهم دخل ثانوي: {len(valid):,}\n"
                f"متوسط الدخل الشهري: {valid.mean():.0f} جنيه\n"
                f"أعلى دخل: {valid.max():.0f} جنيه\n"
                f"أقل دخل: {valid.min():.0f} جنيه"
            )
        if any(x in q for x in ["ساعات", "وقت"]):
            valid = pd.to_numeric(df["Secondary_Weekly_Hours"], errors="coerce")
            valid = valid[valid > 0].dropna()
            return (
                f"ساعات العمل الأسبوعية في الوظيفة الثانوية:\n"
                f"متوسط: {valid.mean():.1f} ساعة\n"
                f"أعلى: {valid.max():.0f} ساعة\n"
                f"أقل: {valid.min():.0f} ساعة"
            )
        counts = df["Has_Secondary_Job"].value_counts()
        total_with_data = counts.sum()
        yes = counts.get("نعم", 0)
        no = counts.get("لا", 0)
        return (
            f"الوظيفة الثانوية:\n"
            f"لديهم وظيفة ثانوية: {yes:,} ({yes/total_with_data*100:.1f}%)\n"
            f"ليس لديهم وظيفة ثانوية: {no:,} ({no/total_with_data*100:.1f}%)"
        )

    if any(x in q for x in ["سنة العمل", "بداية العمل", "منذ عام", "بدأ العمل"]):
        valid = pd.to_numeric(df["Career_Start_Year"], errors="coerce").dropna()
        years = re.findall(r"\d{4}", q)
        if years:
            year = int(years[0])
            count_year = df["Career_Start_Year"].value_counts().get(year, 0)
            return f"عدد العاملين الذين بدأوا العمل عام {year}: {int(count_year):,}"
        return (
            f"إحصائيات سنة بداية العمل:\n"
            f"أقدم سنة: {int(valid.min())}\n"
            f"أحدث سنة: {int(valid.max())}\n"
            f"إجمالي العاملين اللي عندهم بيانات: {len(valid):,}"
        )

    if any(x in q for x in ["إناث", "انثى", "نساء", "ذكور", "جنس"]):
        counts = df["Gender"].value_counts()
        total = len(df)
        result = ""
        for k, v in counts.items():
            result += f"{k}: {v:,} ({v/total*100:.1f}%)\n"
        return f"توزيع الجنس:\n{result}"

    if any(x in q for x in ["عاطل", "بطالة", "تشغيل", "توظيف", "قوة العمل", "مشتغل"]):
        counts = df["Employment_Status"].value_counts()
        total = len(df)
        result = ""
        for k, v in counts.items():
            result += f"{k}: {v:,} ({v/total*100:.1f}%)\n"
        return f"توزيع حالة التوظيف:\n{result}"

    if any(x in q for x in ["راتب", "دخل", "أجر", "مرتب"]):
        valid = pd.to_numeric(df["Monthly_Salary"], errors="coerce")
        valid = valid[valid > 0].dropna()
        return (
            f"إحصائيات الراتب الشهري للعاملين:\n"
            f"عدد العاملين اللي عندهم راتب: {len(valid):,}\n"
            f"متوسط الراتب: {valid.mean():.0f} جنيه\n"
            f"وسيط الراتب: {valid.median():.0f} جنيه\n"
            f"أعلى راتب: {valid.max():.0f} جنيه\n"
            f"أقل راتب: {valid.min():.0f} جنيه"
        )

    if any(
        x in q
        for x in [
            "معاق",
            "إعاقة",
            "اعاقة",
            "ذوي الهمم",
            "ذوى الهمم",
            "أصحاب الهمم",
            "اصحاب الهمم",
            "أنواع الإعاقة",
        ]
    ):
        total = len(df)
        disabled = int(df["Has_Disability"].value_counts().get(1, 0))
        not_disabled = int(df["Has_Disability"].value_counts().get(0, 0))
        sight = get_disability_count("Sight_Difficulty")
        hearing = get_disability_count("Hearing_Difficulty")
        memory = get_disability_count("Memory_Difficulty")
        walking = get_disability_count("Walking_Difficulty")
        types = {
            "صعوبة المشي/الحركة": walking,
            "صعوبة الذاكرة/التركيز": memory,
            "صعوبة السمع": hearing,
            "صعوبة البصر": sight,
        }
        most_common = max(types, key=types.get)
        return (
            f"إحصائيات ذوي الإعاقة (أصحاب الهمم):\n"
            f"إجمالي ذوي الإعاقة: {disabled:,} ({disabled/total*100:.1f}%)\n"
            f"بدون إعاقة: {not_disabled:,} ({not_disabled/total*100:.1f}%)\n\n"
            f"أنواع الإعاقات:\n"
            f"صعوبة المشي/الحركة: {walking:,} ({walking/disabled*100:.1f}%)\n"
            f"صعوبة الذاكرة/التركيز: {memory:,} ({memory/disabled*100:.1f}%)\n"
            f"صعوبة السمع: {hearing:,} ({hearing/disabled*100:.1f}%)\n"
            f"صعوبة البصر: {sight:,} ({sight/disabled*100:.1f}%)\n\n"
            f"أكثر نوع إعاقة تكراراً: {most_common}"
        )

    if any(x in q for x in ["قطاع", "حكومي", "خاص"]):
        counts = df["Sector"].value_counts()
        total = len(df)
        result = ""
        for k, v in counts.items():
            result += f"{k}: {v:,} ({v/total*100:.1f}%)\n"
        return f"توزيع العمال حسب القطاع:\n{result}"

    if any(x in q for x in ["محافظة", "محافظات"]):
        counts = df["Governorate_Name"].value_counts()
        total = len(df)
        result = ""
        for k, v in counts.items():
            result += f"{k}: {v:,} ({v/total*100:.1f}%)\n"
        return f"التوزيع حسب المحافظة:\n{result}"

    if any(x in q for x in ["قسم", "أقسام", "مركز", "مراكز"]):
        counts = df["section_name"].value_counts()
        total = len(df)
        result = ""
        for k, v in counts.items():
            result += f"{k}: {v:,} ({v/total*100:.1f}%)\n"
        return f"التوزيع حسب الأقسام والمراكز:\n{result}"

    if any(x in q for x in ["ريف", "حضر", "حضري", "ريفي", "منطقة", "مناطق"]):
        counts = df["Region_Type"].value_counts()
        total = len(df)
        result = ""
        for k, v in counts.items():
            result += f"{k}: {v:,} ({v/total*100:.1f}%)\n"
        return f"توزيع المناطق (حضر/ريف):\n{result}"

    if any(x in q for x in ["تعليم", "مؤهل", "تعليمي", "أمي", "أمية"]):
        counts = df["Education_Level"].value_counts()
        return f"توزيع المستوى التعليمي:\n{counts.to_string()}"

    if any(x in q for x in ["تدريب", "مهني"]):
        counts = df["Professional_Training_Status"].value_counts()
        return f"حالة التدريب المهني:\n{counts.to_string()}"

    if any(x in q for x in ["عمر", "سن", "فئة عمرية", "أعمار", "شباب"]):
        counts = df["AGE_GROUP"].value_counts().sort_index()
        valid_age = pd.to_numeric(df["Age"], errors="coerce").dropna()
        avg = f"{valid_age.mean():.1f}" if len(valid_age) > 0 else "غير متاح"
        return (
            f"توزيع الفئات العمرية:\n{counts.to_string()}\n\n" f"متوسط السن: {avg} سنة"
        )

    if any(x in q for x in ["غير رسمي", "رسمية", "رسمي"]):
        counts = df["Is_Informal_Worker"].value_counts()
        total = len(df)
        result = ""
        for k, v in counts.items():
            result += f"{k}: {v:,} ({v/total*100:.1f}%)\n"
        return f"توزيع العمالة الرسمية وغير الرسمية:\n{result}"

    if any(x in q for x in ["كورونا", "كوفيد", "covid", "جائحة"]):
        counts = df["COVID_Salary_Reduction"].value_counts()
        return f"تأثير كورونا على الرواتب:\n{counts.to_string()}"

    if any(x in q for x in ["ساعات", "أسبوعي"]):
        valid = pd.to_numeric(df["Weekly_Hours"], errors="coerce").dropna()
        return (
            f"إحصائيات ساعات العمل الأسبوعية:\n"
            f"متوسط: {valid.mean():.1f} ساعة\n"
            f"أعلى: {valid.max():.0f} ساعة\n"
            f"أقل: {valid.min():.0f} ساعة"
        )

    if any(x in q for x in ["كم", "عدد", "إجمالي", "مجموع"]):
        return f"إجمالي عدد الأفراد في قاعدة البيانات: {len(df):,}"

    return None


def handle_statistical(question):
    stats = compute_stats(question)
    if stats:
        return stats
    return "يمكنك السؤال عن: العاطلين، الرواتب، الجنس، القطاع، المحافظة، الإعاقة، التعليم، التدريب، التأمين، الإجازات، الوظيفة الثانوية، ساعات العمل، كورونا، الحالة الاجتماعية، الفئة العمرية، المناطق، الأقسام."


def handle_individual(question):
    try:
        embedding = get_embedding(question)
        results = search_qdrant(embedding, limit=5)
        context = "\n".join([r["payload"]["text"] for r in results])
        prompt = f"""أنت مساعد بيانات متخصص في سوق العمل المصري.
بناءً على البيانات التالية:
{context}

السؤال: {question}
أجب بالعربي في 3-5 أسطر فقط. لا تكرر نفس المعلومة."""
        answer = ask_ollama(prompt)
        if not answer:
            return context
        return answer
    except Exception as e:
        return f"خطأ: {str(e)}"


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    question = data.get("question", "")
    if not question:
        return jsonify({"error": "No question provided"}), 400

    print(f"Question: {question}")

    if is_individual_request(question):
        answer = handle_individual(question)
        qtype = "individual"
    elif is_analytical_request(question):
        answer = handle_analytical(question)
        qtype = "analytical"
    elif is_statistical(question):
        answer = handle_statistical(question)
        qtype = "statistical"
    else:
        answer = handle_individual(question)
        qtype = "individual"

    print(f"Type: {qtype} | Answer: {answer[:100] if answer else 'EMPTY'}")
    return jsonify({"question": question, "answer": answer, "type": qtype})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "rows": len(df)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
