from flask import (Flask, render_template, request,
                   redirect, url_for, flash, jsonify)
from datetime import datetime, date
import openpyxl
import os
from database import (db, Complex, School, GradeData, StaffRecord,
                      TableSettings, DEFAULT_COLUMN_LABELS,
                      CapacitySettings, DEFAULT_CAPACITY_SETTINGS)
from calculations import (calculate_school_metrics, calculate_complex_metrics,
                          GRADE_CAPACITY, STANDARDS,
                          DEFAULT_CAPACITY_PRIVATE, DEFAULT_CAPACITY_INTERNATIONAL,
                          build_grade_capacity)

BASEDIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "school-efficiency-2024")

# ─── قاعدة البيانات ───
# على Render: يُضبط DATABASE_URL تلقائياً عند ربط PostgreSQL
# محلياً: يتراجع إلى SQLite
raw_db_url = os.environ.get("DATABASE_URL", "")
if raw_db_url.startswith("postgres://"):
    # SQLAlchemy يحتاج postgresql:// وليس postgres://
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    raw_db_url or "sqlite:///" + os.path.join(BASEDIR, "instance", "school_efficiency.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(BASEDIR, "uploads")

db.init_app(app)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(os.path.join(BASEDIR, "instance"), exist_ok=True)

with app.app_context():
    db.create_all()

def get_cap_settings():
    try:
        return CapacitySettings.get_all()
    except Exception:
        return dict(DEFAULT_CAPACITY_SETTINGS)

@app.context_processor
def inject_col_labels():
    """يحقن تسميات الأعمدة تلقائياً في جميع القوالب"""
    with app.app_context():
        try:
            labels = TableSettings.get_labels()
        except Exception:
            labels = dict(DEFAULT_COLUMN_LABELS)
    return dict(col=labels)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        # ── تسميات الأعمدة ──
        for key in DEFAULT_COLUMN_LABELS:
            val = request.form.get(key, "").strip()
            if val:
                TableSettings.set_label(key, val)
        # ── الطاقة الاستيعابية ──
        for key in DEFAULT_CAPACITY_SETTINGS:
            raw = request.form.get(key, "").strip()
            if raw.isdigit() and int(raw) > 0:
                CapacitySettings.set_value(key, int(raw))
        db.session.commit()
        flash("تم حفظ الإعدادات بنجاح ✅", "success")
        return redirect(url_for("settings"))
    labels   = TableSettings.get_labels()
    cap_vals = get_cap_settings()
    return render_template("settings.html", labels=labels, defaults=DEFAULT_COLUMN_LABELS,
                           cap_vals=cap_vals, cap_defaults=DEFAULT_CAPACITY_SETTINGS)


@app.route("/settings/reset-labels", methods=["POST"])
def reset_labels():
    """مسح جميع تسميات الأعمدة المخصصة والعودة للقيم الافتراضية"""
    TableSettings.query.delete()
    db.session.commit()
    flash("تم إعادة تسميات الأعمدة إلى القيم الافتراضية ✅", "success")
    return redirect(url_for("settings"))


def latest_grade(sid):
    return GradeData.query.filter_by(school_id=sid).order_by(GradeData.record_date.desc(), GradeData.id.desc()).first()

def latest_staff(sid):
    return StaffRecord.query.filter_by(school_id=sid).order_by(StaffRecord.record_date.desc(), StaffRecord.id.desc()).first()

def _int(f, k):
    try: return int(f.get(k, 0) or 0)
    except: return 0

@app.route("/")
def dashboard():
    complexes = Complex.query.filter_by(is_active=True).all()
    schools   = School.query.filter_by(is_active=True).all()
    stats = {"total_complexes": len(complexes), "total_schools": len(schools),
             "total_students": 0, "total_teachers": 0}
    for s in schools:
        g = latest_grade(s.id); t = latest_staff(s.id)
        if g:
            for _, d in g.to_dict()["grades"].items():
                stats["total_students"] += d["students"]
        if t: stats["total_teachers"] += t.teachers
    return render_template("dashboard.html", stats=stats, complexes=complexes)

@app.route("/complexes")
def list_complexes():
    return render_template("complexes/list.html",
                           complexes=Complex.query.filter_by(is_active=True).all())

@app.route("/complexes/add", methods=["GET","POST"])
def add_complex():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        desc = request.form.get("description","").strip()
        if not name: flash("اسم المجمع مطلوب","error"); return redirect(url_for("add_complex"))
        if Complex.query.filter_by(name=name).first(): flash("يوجد مجمع بهذا الاسم","error"); return redirect(url_for("add_complex"))
        db.session.add(Complex(name=name, description=desc)); db.session.commit()
        flash(f'تم إضافة مجمع "{name}"', "success"); return redirect(url_for("list_complexes"))
    return render_template("complexes/add.html")

@app.route("/complexes/<int:cid>/edit", methods=["GET","POST"])
def edit_complex(cid):
    cx = Complex.query.get_or_404(cid)
    if request.method == "POST":
        cx.name = request.form.get("name","").strip()
        cx.description = request.form.get("description","").strip()
        db.session.commit(); flash("تم التحديث","success"); return redirect(url_for("list_complexes"))
    return render_template("complexes/edit.html", complex=cx)

@app.route("/complexes/<int:cid>/delete", methods=["POST"])
def delete_complex(cid):
    cx = Complex.query.get_or_404(cid); cx.is_active = False
    db.session.commit(); flash("تم الحذف","success"); return redirect(url_for("list_complexes"))

@app.route("/schools")
def list_schools():
    cid = request.args.get("complex_id", type=int)
    complexes = Complex.query.filter_by(is_active=True).all()
    schools = School.query.filter_by(complex_id=cid, is_active=True).all() if cid else School.query.filter_by(is_active=True).all()
    cx = Complex.query.get(cid) if cid else None
    return render_template("schools/list.html", schools=schools, complexes=complexes, current_complex=cx)

@app.route("/schools/add", methods=["GET","POST"])
def add_school():
    complexes = Complex.query.filter_by(is_active=True).all()
    if request.method == "POST":
        cid = request.form.get("complex_id", type=int); name = request.form.get("name","").strip()
        if not (cid and name): flash("الحقول المطلوبة ناقصة","error"); return redirect(url_for("add_school"))
        db.session.add(School(complex_id=cid, name=name,
            school_type=request.form.get("school_type",""),
            school_level=request.form.get("school_level","")))
        db.session.commit(); flash(f'تم إضافة مدرسة "{name}"', "success"); return redirect(url_for("list_schools"))
    return render_template("schools/add.html", complexes=complexes)

@app.route("/schools/<int:sid>/delete", methods=["POST"])
def delete_school(sid):
    s = School.query.get_or_404(sid); s.is_active = False
    db.session.commit(); flash("تم حذف المدرسة","success"); return redirect(url_for("list_schools"))

@app.route("/data-entry/<int:sid>", methods=["GET","POST"])
def data_entry(sid):
    school = School.query.get_or_404(sid)
    if request.method == "POST":
        rd = datetime.strptime(request.form.get("record_date"),"%Y-%m-%d").date()
        f  = request.form
        gd = GradeData.query.filter_by(school_id=sid, record_date=rd).first()
        grade_fields = dict(
            kg1_classes=_int(f,"kg1_classes"), kg1_students=_int(f,"kg1_students"),
            kg2_classes=_int(f,"kg2_classes"), kg2_students=_int(f,"kg2_students"),
            kg3_classes=_int(f,"kg3_classes"), kg3_students=_int(f,"kg3_students"),
            grade1_classes=_int(f,"grade1_classes"), grade1_students=_int(f,"grade1_students"),
            grade2_classes=_int(f,"grade2_classes"), grade2_students=_int(f,"grade2_students"),
            grade3_classes=_int(f,"grade3_classes"), grade3_students=_int(f,"grade3_students"),
            grade4_classes=_int(f,"grade4_classes"), grade4_students=_int(f,"grade4_students"),
            grade5_classes=_int(f,"grade5_classes"), grade5_students=_int(f,"grade5_students"),
            grade6_classes=_int(f,"grade6_classes"), grade6_students=_int(f,"grade6_students"),
            middle1_classes=_int(f,"middle1_classes"), middle1_students=_int(f,"middle1_students"),
            middle2_classes=_int(f,"middle2_classes"), middle2_students=_int(f,"middle2_students"),
            middle3_classes=_int(f,"middle3_classes"), middle3_students=_int(f,"middle3_students"),
            high1_classes=_int(f,"high1_classes"), high1_students=_int(f,"high1_students"),
            high2_classes=_int(f,"high2_classes"), high2_students=_int(f,"high2_students"),
            high3_classes=_int(f,"high3_classes"), high3_students=_int(f,"high3_students"))
        if gd:
            for k, v in grade_fields.items(): setattr(gd, k, v)
        else:
            gd = GradeData(school_id=sid, record_date=rd, **grade_fields)
            db.session.add(gd)
        sr = StaffRecord.query.filter_by(school_id=sid, record_date=rd).first()
        staff_fields = dict(
            teachers=_int(f,"teachers"), admins=_int(f,"admins"),
            support_staff=_int(f,"support_staff"),
            general_admin=_int(f,"general_admin"),
            notes=f.get("notes",""))
        if sr:
            for k, v in staff_fields.items(): setattr(sr, k, v)
        else:
            sr = StaffRecord(school_id=sid, record_date=rd, **staff_fields)
            db.session.add(sr)
        db.session.commit()
        flash("تم حفظ البيانات بنجاح ✅","success")
        return redirect(url_for("school_report", sid=sid))
    lg = latest_grade(sid); ls = latest_staff(sid)
    return render_template("data_entry.html", school=school,
        latest_grade=lg.to_dict() if lg else None,
        latest_staff=ls.to_dict() if ls else None,
        today=date.today().isoformat(), GRADE_CAPACITY=GRADE_CAPACITY)

@app.route("/api/vacancies", methods=["POST"])
def api_vacancies():
    data = request.json
    stype = data.get("school_type", "private")
    cap_settings = get_cap_settings()
    grade_cap = build_grade_capacity(cap_settings, stype)
    cap  = grade_cap.get(data.get("grade",""), 24)
    cl   = int(data.get("classes",0))
    st   = int(data.get("students",0))
    return jsonify({"capacity": cl*cap, "vacancies": cl*cap - st})

@app.route("/import-excel", methods=["GET","POST"])
def import_excel():
    complexes = Complex.query.filter_by(is_active=True).all()
    if request.method == "POST":
        f   = request.files.get("excel_file")
        cid = request.form.get("complex_id", type=int)
        rd  = datetime.strptime(request.form.get("record_date"),"%Y-%m-%d").date()
        if not f or not f.filename:
            flash("اختر ملف","error")
            return redirect(url_for("import_excel"))
        path = os.path.join(app.config["UPLOAD_FOLDER"], f.filename)
        f.save(path)
        try:
            wb = openpyxl.load_workbook(path)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            header_row_idx = None
            for i, r in enumerate(rows):
                if any(str(c).strip() == "اسم المدرسة" for c in r if c):
                    header_row_idx = i
                    break
            if header_row_idx is None:
                flash("تعذّر إيجاد صف العناوين — تأكد من استخدام القالب الرسمي", "error")
                return redirect(url_for("import_excel"))
            headers = [str(h).strip() if h else "" for h in rows[header_row_idx]]
            count = 0
            created_complexes = {}
            auto_created_names = []
            for row_vals in rows[header_row_idx + 1:]:
                row = {headers[i]: row_vals[i] if i < len(row_vals) else 0 for i in range(len(headers))}
                sname = str(row.get("اسم المدرسة","")).strip()
                if not sname or sname in ("None", "اسم المدرسة"): continue
                row_cid = cid
                if not row_cid:
                    row_complex_name = str(row.get("اسم المجمع", "")).strip()
                    if row_complex_name and row_complex_name not in ("None", "اسم المجمع هنا"):
                        # أولاً: هل أنشأناه في نفس جلسة الاستيراد الحالية؟
                        if row_complex_name in created_complexes:
                            row_cid = created_complexes[row_complex_name].id
                        else:
                            # ثانياً: ابحث في قاعدة البيانات (نشط أو محذوف) — مع تجاهل المسافات
                            all_complexes = Complex.query.all()
                            matched = next((c for c in all_complexes if c.name.strip() == row_complex_name.strip()), None)
                            if matched:
                                if not matched.is_active:
                                    matched.is_active = True  # أعد تفعيله لو كان محذوفاً
                                row_cid = matched.id
                            else:
                                # ثالثاً: أنشئه جديداً
                                new_cx = Complex(name=row_complex_name)
                                db.session.add(new_cx)
                                db.session.flush()
                                created_complexes[row_complex_name] = new_cx
                                auto_created_names.append(row_complex_name)
                                row_cid = new_cx.id
                all_schools = School.query.filter_by(complex_id=row_cid).all()
                school = next((s for s in all_schools if s.name.strip() == sname), None)
                if not school:
                    school = School(name=sname, complex_id=row_cid,
                                    school_type=str(row.get("النوع","بنين")),
                                    school_level=str(row.get("مستوى المدرسة","") or ""))
                    db.session.add(school)
                    db.session.flush()
                def rv(c):
                    try: return int(row.get(c,0) or 0)
                    except: return 0
                gd_existing = GradeData.query.filter_by(school_id=school.id, record_date=rd).first()
                grade_vals = dict(
                    kg1_classes=rv("KG1_فصول"), kg1_students=rv("KG1_طلاب"),
                    kg2_classes=rv("KG2_فصول"), kg2_students=rv("KG2_طلاب"),
                    kg3_classes=rv("KG3_فصول"), kg3_students=rv("KG3_طلاب"),
                    grade1_classes=rv("أولى_ابتدائي_فصول"), grade1_students=rv("أولى_ابتدائي_طلاب"),
                    grade2_classes=rv("ثاني_ابتدائي_فصول"), grade2_students=rv("ثاني_ابتدائي_طلاب"),
                    grade3_classes=rv("ثالث_ابتدائي_فصول"), grade3_students=rv("ثالث_ابتدائي_طلاب"),
                    grade4_classes=rv("رابع_ابتدائي_فصول"), grade4_students=rv("رابع_ابتدائي_طلاب"),
                    grade5_classes=rv("خامس_ابتدائي_فصول"), grade5_students=rv("خامس_ابتدائي_طلاب"),
                    grade6_classes=rv("سادس_ابتدائي_فصول"), grade6_students=rv("سادس_ابتدائي_طلاب"),
                    middle1_classes=rv("أول_متوسط_فصول"), middle1_students=rv("أول_متوسط_طلاب"),
                    middle2_classes=rv("ثاني_متوسط_فصول"), middle2_students=rv("ثاني_متوسط_طلاب"),
                    middle3_classes=rv("ثالث_متوسط_فصول"), middle3_students=rv("ثالث_متوسط_طلاب"),
                    high1_classes=rv("أول_ثانوي_فصول"), high1_students=rv("أول_ثانوي_طلاب"),
                    high2_classes=rv("ثاني_ثانوي_فصول"), high2_students=rv("ثاني_ثانوي_طلاب"),
                    high3_classes=rv("ثالث_ثانوي_فصول"), high3_students=rv("ثالث_ثانوي_طلاب"))
                if gd_existing:
                    for k, v in grade_vals.items(): setattr(gd_existing, k, v)
                else:
                    db.session.add(GradeData(school_id=school.id, record_date=rd, **grade_vals))
                sr_existing = StaffRecord.query.filter_by(school_id=school.id, record_date=rd).first()
                staff_vals = dict(
                    teachers=rv("المعلمين"), admins=rv("الإداريين"),
                    support_staff=rv("الخدمات_المساندة"),
                    general_admin=rv("الإدارة_العامة"),
                    notes=str(row.get("ملاحظات","") or ""))
                if sr_existing:
                    for k, v in staff_vals.items(): setattr(sr_existing, k, v)
                else:
                    db.session.add(StaffRecord(school_id=school.id, record_date=rd, **staff_vals))
                count += 1
            db.session.commit()
            flash(f"تم استيراد {count} مدرسة بنجاح ✅","success")
            if auto_created_names:
                names_str = "، ".join(auto_created_names)
                flash(f"تم إنشاء {len(auto_created_names)} مجمع جديد تلقائياً: {names_str}", "info")
        except Exception as e:
            db.session.rollback()
            flash(f"خطأ: {e}","error")
        finally:
            if os.path.exists(path): os.remove(path)
        return redirect(url_for("import_excel"))
    orphan_count = School.query.filter_by(complex_id=None, is_active=True).count()
    return render_template("import_excel.html", complexes=complexes,
                           orphan_schools_count=orphan_count, today=date.today().isoformat())

@app.route("/fix-orphan-schools", methods=["POST"])
def fix_orphan_schools():
    orphans = School.query.filter_by(complex_id=None, is_active=True).all()
    if not orphans:
        flash("لا توجد مدارس بدون مجمع ✅", "info")
        return redirect(url_for("import_excel"))
    default_cx = Complex.query.filter_by(name="مجمع افتراضي").first()
    if not default_cx:
        default_cx = Complex(name="مجمع افتراضي", description="مجمع تلقائي للمدارس غير المصنّفة")
        db.session.add(default_cx)
        db.session.flush()
    for s in orphans:
        s.complex_id = default_cx.id
    db.session.commit()
    flash(f"تم نقل {len(orphans)} مدرسة إلى «مجمع افتراضي» — يمكنك تعديل المجمع لاحقاً", "success")
    return redirect(url_for("import_excel"))

@app.route("/reports/school/<int:sid>")
def school_report(sid):
    school = School.query.get_or_404(sid)
    gd = latest_grade(sid); sr = latest_staff(sid)
    if not gd or not sr:
        flash("لا توجد بيانات، أدخل البيانات أولاً","warning")
        return redirect(url_for("data_entry", sid=sid))
    cap_settings = get_cap_settings()
    metrics = calculate_school_metrics(gd.to_dict(), sr.to_dict(), cap_settings, school.school_type)
    return render_template("reports/school.html",
        school=school, metrics=metrics, grade_data=gd, staff_record=sr, STANDARDS=STANDARDS)

@app.route("/reports/complex/<int:cid>")
def complex_report(cid):
    cx = Complex.query.get_or_404(cid)
    data = []
    for s in School.query.filter_by(complex_id=cid, is_active=True).all():
        gd = latest_grade(s.id); sr = latest_staff(s.id)
        if gd and sr: data.append((s, gd.to_dict(), sr.to_dict()))
    cap_settings = get_cap_settings()
    return render_template("reports/complex.html",
        complex=cx, metrics=calculate_complex_metrics(data, cap_settings), STANDARDS=STANDARDS)

@app.route("/reports/company")
def company_report():
    all_data = []
    for cx in Complex.query.filter_by(is_active=True).all():
        data = []
        cap_settings = get_cap_settings()
        for s in School.query.filter_by(complex_id=cx.id, is_active=True).all():
            gd = latest_grade(s.id); sr = latest_staff(s.id)
            if gd and sr: data.append((s, gd.to_dict(), sr.to_dict()))
        if data: all_data.append({"complex": cx, "metrics": calculate_complex_metrics(data, cap_settings)})
    return render_template("reports/company.html", complexes_data=all_data, STANDARDS=STANDARDS)


@app.route("/download-template")
def download_template():
    import io, openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from flask import send_file

    complex_id  = request.args.get("complex_id", type=int)
    complex_obj = Complex.query.get(complex_id) if complex_id else None

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "قالب_البيانات"
    ws.sheet_view.rightToLeft = True

    header_fill   = PatternFill("solid", fgColor="1F4E79")
    required_fill = PatternFill("solid", fgColor="FCE4D6")
    example_fill  = PatternFill("solid", fgColor="D9E1F2")
    white_fill    = PatternFill("solid", fgColor="FFFFFF")
    thin = Border(left=Side(style="thin"), right=Side(style="thin"),
                  top=Side(style="thin"),  bottom=Side(style="thin"))

    ws.merge_cells("A1:AJ1")
    ws["A1"] = "📋 قالب استيراد بيانات المدارس — أدخل بيانات كل مدرسة في صف منفصل | الخلايا البرتقالية إلزامية | الصف الثاني مثال فقط (احذفه)"
    ws["A1"].font      = Font(name="Arial", bold=True, color="7B2D00", size=11)
    ws["A1"].fill      = PatternFill("solid", fgColor="FCE4D6")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30

    for cell_range, label in [
        ("A2:B2",  "معلومات المدرسة"),
        ("C2:H2",  "رياض الأطفال"),
        ("I2:R2",  "المرحلة الابتدائية"),
        ("S2:X2",  "المرحلة المتوسطة"),
        ("Y2:AD2", "المرحلة الثانوية"),
        ("AE2:AG2","الكوادر البشرية"),
        ("AH2:AJ2","معلومات إضافية"),
    ]:
        ws.merge_cells(cell_range)
        c = ws[cell_range.split(":")[0]]
        c.value = label
        c.font  = Font(name="Arial", bold=True, color="FFFFFF", size=11)
        c.fill  = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin
    ws.row_dimensions[2].height = 22

    columns = [
        ("اسم المدرسة", True), ("النوع", True),
        ("KG1_فصول", False), ("KG1_طلاب", False),
        ("KG2_فصول", False), ("KG2_طلاب", False),
        ("KG3_فصول", False), ("KG3_طلاب", False),
        ("أولى_ابتدائي_فصول", False), ("أولى_ابتدائي_طلاب", False),
        ("ثاني_ابتدائي_فصول", False), ("ثاني_ابتدائي_طلاب", False),
        ("ثالث_ابتدائي_فصول", False), ("ثالث_ابتدائي_طلاب", False),
        ("رابع_ابتدائي_فصول", False), ("رابع_ابتدائي_طلاب", False),
        ("خامس_ابتدائي_فصول", False), ("خامس_ابتدائي_طلاب", False),
        ("سادس_ابتدائي_فصول", False), ("سادس_ابتدائي_طلاب", False),
        ("أول_متوسط_فصول", False), ("أول_متوسط_طلاب", False),
        ("ثاني_متوسط_فصول", False), ("ثاني_متوسط_طلاب", False),
        ("ثالث_متوسط_فصول", False), ("ثالث_متوسط_طلاب", False),
        ("أول_ثانوي_فصول", False), ("أول_ثانوي_طلاب", False),
        ("ثاني_ثانوي_فصول", False), ("ثاني_ثانوي_طلاب", False),
        ("ثالث_ثانوي_فصول", False), ("ثالث_ثانوي_طلاب", False),
        ("المعلمين", True), ("الإداريين", True), ("الخدمات_المساندة", True),
        ("مستوى المدرسة", False), ("ملاحظات", False), ("اسم المجمع", False),
    ]
    for col_idx, (col_name, required) in enumerate(columns, start=1):
        cell = ws.cell(row=3, column=col_idx, value=col_name)
        cell.font      = Font(name="Arial", bold=True,
                              color="7B2D00" if required else "1F4E79", size=10)
        cell.fill      = required_fill if required else PatternFill("solid", fgColor="BDD7EE")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = thin
    ws.row_dimensions[3].height = 35

    example = [
        "مدرسة النموذج الابتدائية", "بنين",
        2,38, 2,35, 0,0,
        3,70, 3,68, 3,65, 2,48, 2,45, 2,44,
        0,0, 0,0, 0,0,
        0,0, 0,0, 0,0,
        18, 3, 5,
        "ابتدائي", "مدرسة حكومية", complex_obj.name if complex_obj else "اسم المجمع هنا",
    ]
    for col_idx, val in enumerate(example, start=1):
        cell = ws.cell(row=4, column=col_idx, value=val)
        cell.font      = Font(name="Arial", size=10, color="595959", italic=True)
        cell.fill      = example_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border    = thin
    ws.row_dimensions[4].height = 18

    complex_col_idx = len(columns)
    for row in range(5, 55):
        for col in range(1, len(columns) + 1):
            cell = ws.cell(row=row, column=col)
            cell.fill      = white_fill
            cell.border    = thin
            cell.font      = Font(name="Arial", size=10)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if col == complex_col_idx and complex_obj:
                cell.value = complex_obj.name
        ws.row_dimensions[row].height = 18

    for i, w in enumerate([30,12]+[12,10]*15+[12,12,16]+[18,20,18], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A4"

    wi = wb.create_sheet("تعليمات")
    wi.sheet_view.rightToLeft = True
    for r, (text, bold) in enumerate([
        ("📌 تعليمات الاستخدام", True),
        ("", False),
        ("1. احتفظ بأسماء الأعمدة كما هي في الصف الثالث تماماً", False),
        ("2. احذف صف المثال (الصف الرابع) قبل الرفع", False),
        ("3. اكتب بيانات كل مدرسة في صف منفصل بدءاً من الصف الخامس", False),
        ("4. الحقول الإلزامية: اسم المدرسة، النوع، المعلمين، الإداريين، الخدمات المساندة", False),
        ("5. اترك الخلية فارغة أو صفراً إذا لم يكن للمدرسة فصول في تلك المرحلة", False),
        ("6. اختر المجمع وتاريخ السجل من صفحة الاستيراد قبل رفع الملف", False),
    ], start=1):
        c = wi.cell(row=r, column=1, value=text)
        c.font = Font(name="Arial", bold=bold, size=11,
                      color="1F4E79" if bold else "000000")
        if bold: c.fill = PatternFill("solid", fgColor="D9E1F2")
    wi.column_dimensions["A"].width = 70

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name="قالب_استيراد_المدارس.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
