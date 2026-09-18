from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

# التسميات الافتراضية لأعمدة جدول مؤشرات الكفاءة
DEFAULT_COLUMN_LABELS = {
    "col_school":   "المدرسة",
    "col_students":  "الطلاب",
    "col_classes":   "الفصول",
    "col_teachers":  "المعلمين",
    "col_CCR":       "معدل استغلال الفصول (CCR) ≥24",
    "col_admins":    "الإداريين",
    "col_STR":       "نسبة الطلاب للمعلمين (STR) ≥14",
    "col_support":   "الخدمات",
    "col_SAR":       "نسبة الطلاب للإداريين (SAR) ≥50",
    "col_staff":     "الكوادر",
    "col_SSR":       "نسبة الخدمات المساندة (SSR) ≥90",
    "col_SER":       "نسبة الطلاب للخدمات التشغيلية (SER) ≥10",
}


class TableSettings(db.Model):
    __tablename__ = "table_settings"
    id     = db.Column(db.Integer, primary_key=True)
    key    = db.Column(db.String(100), nullable=False, unique=True)
    value  = db.Column(db.Text, nullable=False)

    @staticmethod
    def get_labels():
        labels = dict(DEFAULT_COLUMN_LABELS)
        for row in TableSettings.query.all():
            if row.key in labels:
                labels[row.key] = row.value
        return labels

    @staticmethod
    def set_label(key, value):
        row = TableSettings.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            db.session.add(TableSettings(key=key, value=value))


class Complex(db.Model):
    __tablename__ = "complexes"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    is_active   = db.Column(db.Boolean, default=True)
    schools     = db.relationship("School", backref="complex",
                                  lazy=True, cascade="all, delete-orphan")
    def to_dict(self):
        return {"id": self.id, "name": self.name,
                "description": self.description,
                "schools_count": len(self.schools),
                "created_at": self.created_at.strftime("%Y-%m-%d")}


class School(db.Model):
    __tablename__ = "schools"
    id           = db.Column(db.Integer, primary_key=True)
    complex_id   = db.Column(db.Integer, db.ForeignKey("complexes.id"), nullable=True)
    name         = db.Column(db.String(200), nullable=False)
    school_type  = db.Column(db.String(50))
    school_level = db.Column(db.String(100))
    created_at   = db.Column(db.DateTime, default=datetime.now)
    is_active    = db.Column(db.Boolean, default=True)
    grade_data   = db.relationship("GradeData", backref="school",
                                   lazy=True, cascade="all, delete-orphan")
    staff_records= db.relationship("StaffRecord", backref="school",
                                   lazy=True, cascade="all, delete-orphan")
    def to_dict(self):
        return {"id": self.id, "name": self.name,
                "complex_id": self.complex_id,
                "complex_name": self.complex.name if self.complex else "",
                "school_type": self.school_type,
                "school_level": self.school_level}


class GradeData(db.Model):
    __tablename__ = "grade_data"
    id          = db.Column(db.Integer, primary_key=True)
    school_id   = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    record_date = db.Column(db.Date, nullable=False)
    kg1_classes = db.Column(db.Integer, default=0)
    kg2_classes = db.Column(db.Integer, default=0)
    kg3_classes = db.Column(db.Integer, default=0)
    grade1_classes = db.Column(db.Integer, default=0)
    grade2_classes = db.Column(db.Integer, default=0)
    grade3_classes = db.Column(db.Integer, default=0)
    grade4_classes = db.Column(db.Integer, default=0)
    grade5_classes = db.Column(db.Integer, default=0)
    grade6_classes = db.Column(db.Integer, default=0)
    middle1_classes = db.Column(db.Integer, default=0)
    middle2_classes = db.Column(db.Integer, default=0)
    middle3_classes = db.Column(db.Integer, default=0)
    high1_classes = db.Column(db.Integer, default=0)
    high2_classes = db.Column(db.Integer, default=0)
    high3_classes = db.Column(db.Integer, default=0)
    kg1_students = db.Column(db.Integer, default=0)
    kg2_students = db.Column(db.Integer, default=0)
    kg3_students = db.Column(db.Integer, default=0)
    grade1_students = db.Column(db.Integer, default=0)
    grade2_students = db.Column(db.Integer, default=0)
    grade3_students = db.Column(db.Integer, default=0)
    grade4_students = db.Column(db.Integer, default=0)
    grade5_students = db.Column(db.Integer, default=0)
    grade6_students = db.Column(db.Integer, default=0)
    middle1_students = db.Column(db.Integer, default=0)
    middle2_students = db.Column(db.Integer, default=0)
    middle3_students = db.Column(db.Integer, default=0)
    high1_students = db.Column(db.Integer, default=0)
    high2_students = db.Column(db.Integer, default=0)
    high3_students = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id, "school_id": self.school_id,
            "record_date": self.record_date.strftime("%Y-%m-%d"),
            "grades": {
                "KG1":           {"classes": self.kg1_classes,      "students": self.kg1_students},
                "KG2":           {"classes": self.kg2_classes,      "students": self.kg2_students},
                "KG3":           {"classes": self.kg3_classes,      "students": self.kg3_students},
                "أولى ابتدائي": {"classes": self.grade1_classes,   "students": self.grade1_students},
                "ثاني ابتدائي": {"classes": self.grade2_classes,   "students": self.grade2_students},
                "ثالث ابتدائي": {"classes": self.grade3_classes,   "students": self.grade3_students},
                "رابع ابتدائي": {"classes": self.grade4_classes,   "students": self.grade4_students},
                "خامس ابتدائي": {"classes": self.grade5_classes,   "students": self.grade5_students},
                "سادس ابتدائي": {"classes": self.grade6_classes,   "students": self.grade6_students},
                "أول متوسط":    {"classes": self.middle1_classes,  "students": self.middle1_students},
                "ثاني متوسط":   {"classes": self.middle2_classes,  "students": self.middle2_students},
                "ثالث متوسط":   {"classes": self.middle3_classes,  "students": self.middle3_students},
                "أول ثانوي":    {"classes": self.high1_classes,    "students": self.high1_students},
                "ثاني ثانوي":   {"classes": self.high2_classes,    "students": self.high2_students},
                "ثالث ثانوي":   {"classes": self.high3_classes,    "students": self.high3_students},
            }
        }


class StaffRecord(db.Model):
    __tablename__ = "staff_records"
    id            = db.Column(db.Integer, primary_key=True)
    school_id     = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    record_date   = db.Column(db.Date, nullable=False)
    teachers      = db.Column(db.Integer, default=0)
    admins        = db.Column(db.Integer, default=0)
    support_staff = db.Column(db.Integer, default=0)
    general_admin = db.Column(db.Integer, default=0)  # الإدارة العامة (محسوب من المجمع)
    notes         = db.Column(db.Text, nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            "id": self.id, "school_id": self.school_id,
            "record_date": self.record_date.strftime("%Y-%m-%d"),
            "teachers": self.teachers, "admins": self.admins,
            "support_staff": self.support_staff,
            "general_admin": self.general_admin,
            "total_staff": self.teachers + self.admins + self.support_staff + self.general_admin,
            "notes": self.notes or ""
        }


# ─── إعدادات الطاقة الاستيعابية ───
DEFAULT_CAPACITY_SETTINGS = {
    # أهلي
    "private_kg":       20,
    "private_primary":  24,
    "private_high":     30,
    # عالمي
    "intl_kg":          20,
    "intl_primary":     24,
    "intl_high":        24,
}

class CapacitySettings(db.Model):
    __tablename__ = "capacity_settings"
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(60), nullable=False, unique=True)
    value = db.Column(db.Integer,  nullable=False)

    @staticmethod
    def get_all():
        result = dict(DEFAULT_CAPACITY_SETTINGS)
        for row in CapacitySettings.query.all():
            if row.key in result:
                result[row.key] = row.value
        return result

    @staticmethod
    def set_value(key, value):
        row = CapacitySettings.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            db.session.add(CapacitySettings(key=key, value=value))
