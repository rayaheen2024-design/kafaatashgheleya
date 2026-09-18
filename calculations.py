
# ─── الطاقة الاستيعابية الافتراضية (تُستخدم كاحتياطي) ───
GRADE_CAPACITY = {
    "KG1": 20, "KG2": 20, "KG3": 20,
    "أولى ابتدائي": 24, "ثاني ابتدائي": 24, "ثالث ابتدائي": 24,
    "رابع ابتدائي": 24, "خامس ابتدائي": 24, "سادس ابتدائي": 24,
    "أول متوسط": 24, "ثاني متوسط": 24, "ثالث متوسط": 24,
    "أول ثانوي": 30, "ثاني ثانوي": 30, "ثالث ثانوي": 30,
}

STANDARDS = {"CCR": 24, "STR": 14, "SAR": 50, "SSR": 90, "SER": 10, "density": 24}

# ─── الطاقة الافتراضية مقسّمة حسب نوع المدرسة والمرحلة ───
DEFAULT_CAPACITY_PRIVATE = {
    "kg":      20,   # التمهيدي أهلي
    "primary": 24,   # الابتدائي أهلي
    "high":    30,   # الثانوي أهلي
}
DEFAULT_CAPACITY_INTERNATIONAL = {
    "kg":      20,   # التمهيدي عالمي
    "primary": 24,   # الابتدائي عالمي
    "high":    24,   # الثانوي عالمي
}

# تصنيف الصفوف حسب المرحلة
STAGE_GROUPS = {
    "kg":      ["KG1", "KG2", "KG3"],
    "primary": ["أولى ابتدائي", "ثاني ابتدائي", "ثالث ابتدائي",
                "رابع ابتدائي", "خامس ابتدائي", "سادس ابتدائي"],
    "high":    ["أول متوسط", "ثاني متوسط", "ثالث متوسط",
                "أول ثانوي", "ثاني ثانوي", "ثالث ثانوي"],
}


def build_grade_capacity(cap_settings=None, school_type=None):
    """
    يبني قاموس GRADE_CAPACITY بناءً على:
    - cap_settings : dict مخزّن في CapacitySettings (مفاتيحه: private_kg, private_primary, private_high, intl_kg, ...)
    - school_type  : 'private' | 'international' | None
    يعيد قاموساً بنفس شكل GRADE_CAPACITY القديم.
    """
    if cap_settings is None:
        cap_settings = {}

    if school_type == "international":
        kg_cap  = int(cap_settings.get("intl_kg",      DEFAULT_CAPACITY_INTERNATIONAL["kg"]))
        pr_cap  = int(cap_settings.get("intl_primary",  DEFAULT_CAPACITY_INTERNATIONAL["primary"]))
        hi_cap  = int(cap_settings.get("intl_high",     DEFAULT_CAPACITY_INTERNATIONAL["high"]))
    else:  # private أو أي نوع آخر
        kg_cap  = int(cap_settings.get("private_kg",      DEFAULT_CAPACITY_PRIVATE["kg"]))
        pr_cap  = int(cap_settings.get("private_primary",  DEFAULT_CAPACITY_PRIVATE["primary"]))
        hi_cap  = int(cap_settings.get("private_high",     DEFAULT_CAPACITY_PRIVATE["high"]))

    result = {}
    for grade in STAGE_GROUPS["kg"]:
        result[grade] = kg_cap
    for grade in STAGE_GROUPS["primary"]:
        result[grade] = pr_cap
    for grade in STAGE_GROUPS["high"]:
        result[grade] = hi_cap
    return result


def calculate_school_metrics(grade_data_dict, staff_dict, cap_settings=None, school_type=None):
    grades = grade_data_dict.get("grades", {})
    grade_capacity = build_grade_capacity(cap_settings, school_type)

    total_classes = total_students = total_capacity = 0
    grade_details = []
    for grade_name, cap in grade_capacity.items():
        info = grades.get(grade_name, {"classes": 0, "students": 0})
        cl = info["classes"]; st = info["students"]
        cp = cl * cap; vac = cp - st
        avg = round(st / cl, 2) if cl > 0 else 0
        total_classes += cl; total_students += st; total_capacity += cp
        grade_details.append({"grade": grade_name, "classes": cl, "students": st,
                               "capacity": cp, "vacancies": vac,
                               "avg_per_class": avg, "capacity_per_class": cap})
    total_vacancies = sum(g["vacancies"] for g in grade_details if g["vacancies"] > 0)
    total_overflow  = sum(-g["vacancies"] for g in grade_details if g["vacancies"] < 0)
    avg_density = round(total_students / total_classes, 2) if total_classes > 0 else 0
    teachers      = staff_dict.get("teachers", 0)
    admins        = staff_dict.get("admins",   0)
    support       = staff_dict.get("support_staff", 0)
    general_admin = staff_dict.get("general_admin", 0)
    total_staff   = teachers + admins + support + general_admin
    CCR = round(total_students / teachers,    2) if teachers    > 0 else 0
    STR = round(total_students / admins,      2) if admins      > 0 else 0
    SAR = round(total_students / support,     2) if support     > 0 else 0
    SER = round(total_students / total_staff, 2) if total_staff > 0 else 0
    return {
        "total_classes": total_classes, "total_students": total_students,
        "total_capacity": total_capacity, "total_vacancies": total_vacancies,
        "total_overflow": total_overflow,
        "avg_density": avg_density, "teachers": teachers, "admins": admins,
        "support_staff": support, "general_admin": general_admin,
        "total_staff": total_staff,
        "CCR": CCR, "STR": STR, "SAR": SAR, "SER": SER,
        "CCR_status":     "good" if CCR >= STANDARDS["CCR"]     else "bad",
        "STR_status":     "good" if STR >= STANDARDS["STR"]     else "bad",
        "SAR_status":     "good" if SAR >= STANDARDS["SAR"]     else "bad",
        "SER_status":     "good" if SER >= STANDARDS["SER"]     else "bad",
        "density_status": "good" if avg_density >= STANDARDS["density"] else "bad",
        "grade_details": grade_details,
        "weak_points": get_weak_points(CCR, STR, SAR, SER, avg_density)
    }


def calculate_complex_metrics(schools_data, cap_settings=None):
    totals = {"total_classes": 0, "total_students": 0, "total_capacity": 0,
              "total_vacancies": 0, "total_overflow": 0, "teachers": 0, "admins": 0,
              "support_staff": 0, "general_admin": 0, "total_staff": 0, "schools": []}
    for school_info, grade_data, staff_record in schools_data:
        stype = getattr(school_info, "school_type", None)
        m = calculate_school_metrics(grade_data, staff_record, cap_settings, stype)
        for k in ["total_classes","total_students","total_capacity","total_vacancies",
                  "total_overflow","teachers","admins","support_staff","general_admin","total_staff"]:
            totals[k] += m[k]
        totals["schools"].append({"school": school_info, "metrics": m})
    ts = totals["total_students"]
    totals["CCR"] = round(ts / totals["teachers"],      2) if totals["teachers"]      > 0 else 0
    totals["STR"] = round(ts / totals["admins"],        2) if totals["admins"]        > 0 else 0
    totals["SAR"] = round(ts / totals["support_staff"], 2) if totals["support_staff"] > 0 else 0
    totals["SER"] = round(ts / totals["total_staff"],   2) if totals["total_staff"]   > 0 else 0
    totals["avg_density"] = round(ts / totals["total_classes"], 2) if totals["total_classes"] > 0 else 0
    for k in ["CCR","STR","SAR","SER"]:
        totals[f"{k}_status"] = "good" if totals[k] >= STANDARDS[k] else "bad"
    totals["density_status"] = "good" if totals["avg_density"] >= STANDARDS["density"] else "bad"
    return totals


def get_weak_points(CCR, STR, SAR, SER, density):
    weak = []
    checks = [
        ("CCR", CCR, STANDARDS["CCR"], "زيادة كادر المعلمين",
         f"نسبة الطلاب للمعلمين {CCR} أقل من المعيار {STANDARDS['CCR']}"),
        ("STR", STR, STANDARDS["STR"], "تضخم الكادر الإداري",
         f"نسبة الطلاب للإداريين {STR} أقل من المعيار {STANDARDS['STR']}"),
        ("SAR", SAR, STANDARDS["SAR"], "ارتفاع الخدمات المساندة",
         f"نسبة الطلاب للخدمات {SAR} أقل من المعيار {STANDARDS['SAR']}"),
        ("SER", SER, STANDARDS["SER"], "انخفاض كفاءة المجمع",
         f"نسبة الطلاب لإجمالي الموظفين {SER} أقل من المعيار {STANDARDS['SER']}"),
        ("density", density, STANDARDS["density"], "انخفاض كثافة الفصول",
         f"متوسط كثافة الفصل {density} أقل من المعيار {STANDARDS['density']}"),
    ]
    for key, val, std, title, desc in checks:
        if val < std:
            weak.append({"type": key, "title": title,
                         "value": val, "standard": std, "description": desc})
    return weak
