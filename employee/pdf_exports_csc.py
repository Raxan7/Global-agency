from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

try:
    from PIL import Image as PillowImage
except Exception:  # pragma: no cover
    PillowImage = None

from student_portal.models import WorkExperience

PAGE_W, PAGE_H = A4
TOTAL_PAGES = 6
MISSING = "-"

INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#475569")
BORDER = colors.HexColor("#cbd5e1")
HEADER_FILL = colors.HexColor("#eff6ff")
LABEL_FILL = colors.HexColor("#f8fafc")
BRAND_BLUE = colors.HexColor("#1d4ed8")
BRAND_ORANGE = colors.HexColor("#c2410c")

LEFT = 12 * mm
RIGHT = PAGE_W - 12 * mm
TOP = PAGE_H - 10 * mm
CONTENT_W = RIGHT - LEFT

HEADER_ADDRESS_LINES = [
    "Plot 8, Block 46",
    "Kijitonyama, Mpakani Centre",
    "3rd Floor, Suite F1.01",
    "P.O. Box 34402",
    "Dar es Salaam, Tanzania",
]

DECLARATION_LINES = [
    "Accuracy of Information: I confirm that all information provided in this application form and all supporting documents submitted are true, complete, and accurate to the best of my knowledge.",
    "Authorization to Process Information: I authorize Africa Western Education and its partner institutions, universities, embassies, and relevant authorities to collect, verify, process, and share my personal data and academic documents for admission, visa processing, and related services.",
    "Responsibility for Application Process: I understand that Africa Western Education acts as an education consultancy and recruitment agency and does not guarantee admission, scholarship, or visa approval.",
    "Compliance with Institutional and National Regulations: I agree to abide by all rules, regulations, policies, and laws of the country and institution where I will study.",
    "Admission and Program Placement: I acknowledge that the final decision regarding my admission, course, and institution will be determined by the receiving university.",
    "Financial Responsibility: I confirm that I am responsible for meeting the financial obligations attached to my application and study plans unless official sponsorship is confirmed.",
]

TERMS_AND_CONDITIONS = [
    "Application Process: The agency acts only as an intermediary. Admission and visa decisions are made by institutions and immigration authorities.",
    "Document Authenticity: Submission of false documents leads to immediate termination without refund.",
    "Fees and Payments: All service and administrative fees are non-refundable unless stated otherwise.",
    "Visa Responsibility: Visa approval is not guaranteed by the agency.",
    "Refund Policy: Refunds follow written policy. Government and third-party fees are non-refundable.",
    "Student Responsibilities: The student must provide accurate information, meet requirements, and obey the laws of the host country.",
    "Changes to Application: Changes after submission may incur additional charges.",
    "Liability Limitation: The agency is not liable for visa refusal, admission denial, policy changes, or travel disruptions.",
    "Accommodation And Travel: These are subject to availability and third-party terms.",
    "Data Privacy: Student data may be shared with institutions and embassies for processing.",
    "Cancellation: The agency may cancel services if the student violates policies.",
    "Governing Law: This agreement is governed by the laws of the agency registration country.",
]


def _styles():
    sample = getSampleStyleSheet()
    no_wrap = dict(splitLongWords=False, breakLongWords=False)
    return {
        "tiny_center": ParagraphStyle("tiny_center", parent=sample["Normal"], fontName="Helvetica", fontSize=9.2, leading=11.4, alignment=TA_CENTER, textColor=MUTED, **no_wrap),
        "office": ParagraphStyle("office", parent=sample["Normal"], fontName="Helvetica", fontSize=9.8, leading=12.8, alignment=TA_LEFT, textColor=INK, **no_wrap),
        "title": ParagraphStyle("title", parent=sample["Normal"], fontName="Helvetica-Bold", fontSize=18.6, leading=20.6, alignment=TA_CENTER, spaceAfter=4, textColor=INK, **no_wrap),
        "subtitle": ParagraphStyle("subtitle", parent=sample["Normal"], fontName="Helvetica", fontSize=10.5, leading=12.9, alignment=TA_CENTER, textColor=MUTED, **no_wrap),
        "section": ParagraphStyle("section", parent=sample["Normal"], fontName="Helvetica-Bold", fontSize=12.9, leading=15.2, alignment=TA_LEFT, spaceAfter=5, textColor=BRAND_BLUE, **no_wrap),
        "body": ParagraphStyle("body", parent=sample["Normal"], fontName="Helvetica", fontSize=10.4, leading=13.4, alignment=TA_LEFT, textColor=INK, **no_wrap),
        "field": ParagraphStyle("field", parent=sample["Normal"], fontName="Helvetica", fontSize=10.2, leading=12.9, alignment=TA_LEFT, textColor=INK, **no_wrap),
        "small": ParagraphStyle("small", parent=sample["Normal"], fontName="Helvetica", fontSize=9.6, leading=12, alignment=TA_LEFT, textColor=MUTED, **no_wrap),
    }


def _as_text(value, default=MISSING):
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _bool_box(value):
    return "[X]" if value else "[ ]"


def _escaped(value, default=MISSING):
    return escape(_as_text(value, default))


def _boxed_table(rows, widths, row_heights=None, font_size=9.9, padding=4.0, header_rows=0):
    table = Table(rows, colWidths=widths, rowHeights=row_heights)
    table_style = [
        ("BOX", (0, 0), (-1, -1), 0.8, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.55, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LABEL_FILL]),
    ]
    if header_rows:
        table_style.extend([
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), HEADER_FILL),
            ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), INK),
        ])
    table.setStyle(TableStyle(table_style))
    return table


def _field_paragraph(label, value, styles):
    text = f'<font size="9.6" color="#1d4ed8"><b>{escape(label)}</b></font><br/><font size="10.7" color="#0f172a">{_escaped(value)}</font>'
    return Paragraph(text, styles["field"])


def _single_row_table(pairs, styles):
    entries = list(pairs)
    if len(entries) % 2:
        entries.append(("", ""))
    rows = []
    for idx in range(0, len(entries), 2):
        rows.append([
            _field_paragraph(entries[idx][0], entries[idx][1], styles),
            _field_paragraph(entries[idx + 1][0], entries[idx + 1][1], styles),
        ])
    return _boxed_table(rows, [92 * mm, 92 * mm])


def _header(story, styles):
    story.append(Paragraph("Website: www.africawesterneducation.com    Email: info@africawesterneducation.com    Tel: +255767688766", styles["tiny_center"]))
    story.append(Paragraph("Address: Plot 8, Block 46, Kijitonyama, Mpakani Centre, 3rd Floor, Suite F1.01, Dar es Salaam", styles["tiny_center"]))
    story.append(Spacer(1, 2 * mm))

    logo_path = Path(settings.BASE_DIR) / "static" / "global_agency" / "img" / "logo.png"
    logo = Image(str(logo_path), width=30 * mm, height=22 * mm) if logo_path.exists() else ""
    office_text = (
        "<b>HEADQUARTERS OFFICE</b><br/>"
        "<b>Africa Western Education Company LIMITED</b><br/>"
        + "<br/>".join(HEADER_ADDRESS_LINES)
        + "<br/>Website: www.africawesterneducation.com<br/>"
        "Email: info@africawesterneducation.com<br/>"
        "Tel: +255767688766"
    )
    header_table = Table([[Paragraph(office_text, styles["office"]), logo]], colWidths=[150 * mm, 34 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width="100%", thickness=1.2, color=BRAND_ORANGE, spaceBefore=0, spaceAfter=0))
    story.append(Spacer(1, 1.6 * mm))


def _footer(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawString(14 * mm, 10 * mm, f"Application ID: {getattr(doc, 'serial_number', MISSING)}")
    canvas_obj.drawCentredString(105 * mm, 10 * mm, f"Page {canvas_obj.getPageNumber()} of {TOTAL_PAGES}")
    canvas_obj.drawRightString(196 * mm, 10 * mm, f"Generated: {getattr(doc, 'generated_date', MISSING)}")
    canvas_obj.restoreState()


def _photo_flowable(student_profile, styles):
    profile_picture = getattr(student_profile, "profile_picture", None) if student_profile else None
    if profile_picture:
        try:
            profile_picture.open("rb")
            image_bytes = profile_picture.read()
            profile_picture.close()
            preview = PillowImage.open(BytesIO(image_bytes)) if PillowImage else None
            if preview is not None:
                width_px, height_px = preview.size
                preview.close()
            else:
                width_px, height_px = (300, 400)
            max_width = 34 * mm
            max_height = 42 * mm
            scale = min(max_width / max(width_px, 1), max_height / max(height_px, 1))
            image = Image(BytesIO(image_bytes), width=width_px * scale, height=height_px * scale)
            frame = Table([[image]], colWidths=[36 * mm], rowHeights=[44 * mm])
            frame.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            return frame
        except Exception:
            pass

    placeholder = Table([[Paragraph("Student Photo", styles["body"])]], colWidths=[36 * mm], rowHeights=[44 * mm])
    placeholder.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return placeholder


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    if obj is None:
        return default
    return getattr(obj, attr, default)


def _call_or_value(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if callable(value):
        try:
            return value()
        except TypeError:
            return default
    return value


def _date_text(value: Any, default: str = MISSING) -> str:
    if value in (None, ""):
        return default
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _year_text(value: Any, default: str = MISSING) -> str:
    if value in (None, ""):
        return default
    if hasattr(value, "strftime"):
        return value.strftime("%Y")
    return str(value)


def _money_text(value: Any, default: str = MISSING) -> str:
    if value in (None, ""):
        return default
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return str(value)


def _choice_text(obj: Any, field_name: str, default: str = MISSING) -> str:
    if obj is None:
        return default
    display_method = getattr(obj, f"get_{field_name}_display", None)
    if callable(display_method):
        try:
            value = display_method()
            if value not in (None, ""):
                return str(value)
        except Exception:
            pass
    return _as_text(getattr(obj, field_name, default))


def _student_full_name(application: Any, supplemental_profile: Any = None) -> str:
    supplied = _safe_get(supplemental_profile, "full_name_passport")
    if supplied:
        return str(supplied)
    student = _safe_get(application, "student")
    full_name = _call_or_value(getattr(student, "get_full_name", None), "") if student else ""
    if full_name:
        return str(full_name)
    username = _safe_get(student, "username")
    return str(username or MISSING)


def _photo_source(student_profile: Any) -> str:
    profile_picture = _safe_get(student_profile, "profile_picture")
    if not profile_picture:
        return ""
    try:
        return profile_picture.path
    except Exception:
        return ""


def _get_work_experiences(student_profile: Any) -> List[Any]:
    if student_profile is None:
        return []
    manager = getattr(student_profile, "work_experiences", None)
    if manager is None:
        return []
    try:
        return list(manager.all()[:4])
    except Exception:
        try:
            return list(manager.all().order_by("-start_date")[:4])
        except Exception:
            return []


def application_to_awec_csc_style_data(application: Any, student_profile: Any = None, supplemental_profile: Any = None) -> Dict[str, Any]:
    student = _safe_get(application, "student")
    application_id = _safe_get(application, "id", "001")
    if _safe_get(supplemental_profile, "serial_number"):
        serial = str(_safe_get(supplemental_profile, "serial_number"))
    elif str(application_id).isdigit():
        serial = f"AWECO/Tz/DSM/{int(application_id):03d}"
    else:
        serial = f"AWECO/Tz/DSM/{application_id}"

    generated_source = _safe_get(supplemental_profile, "generated_at") or timezone.now()
    if timezone.is_aware(generated_source):
        generated_date = timezone.localtime(generated_source).strftime("%Y-%m-%d")
        application_date = timezone.localtime(generated_source).strftime("%d/%m/%Y")
    else:
        generated_date = generated_source.strftime("%Y-%m-%d") if hasattr(generated_source, "strftime") else str(generated_source)
        application_date = generated_source.strftime("%d/%m/%Y") if hasattr(generated_source, "strftime") else str(generated_source)

    student_name = _student_full_name(application, supplemental_profile)
    gender = _choice_text(student_profile, "gender", "")

    data: Dict[str, Any] = {
        "organization": {
            "name": "Africa Western Education (AWEC)",
            "legal_name": "Africa Western Education Company LIMITED",
            "website": "www.africawesterneducation.com",
            "email": "info@africawesterneducation.com",
            "telephone": "+255 767 688 766",
            "address_lines": HEADER_ADDRESS_LINES,
        },
        "meta": {
            "form_title": "STUDY ABROAD REGISTRATION FORM",
            "application_id": serial,
            "generated_date": generated_date,
            "application_date": application_date,
        },
        "personal": {
            "Full Name (as in passport)": student_name,
            "Gender": gender,
            "Date of Birth": _date_text(_safe_get(student_profile, "date_of_birth")),
            "Place of Birth": _as_text(_safe_get(supplemental_profile, "place_of_birth")),
            "Nationality": _as_text(_safe_get(student_profile, "nationality")),
            "Email": _as_text(_safe_get(student, "email")),
            "Phone Number": _as_text(_safe_get(student_profile, "phone_number")),
            "Form Six School Name": _as_text(_safe_get(student_profile, "alevel_school")),
            "Form Six School Address": _as_text(_safe_get(student_profile, "alevel_address")),
            "Passport Number": _as_text(_safe_get(supplemental_profile, "passport_number")),
            "Form Four School Name": _as_text(_safe_get(student_profile, "olevel_school")),
            "Form Four School Address": _as_text(_safe_get(student_profile, "olevel_address")),
            "Form Four Division / GPA": _as_text(_safe_get(student_profile, "olevel_gpa")),
            "Application ID / Serial Number": serial,
            "Student Photo": _photo_source(student_profile),
        },
        "parents": {
            "Father": {
                "Full Name": _as_text(_safe_get(student_profile, "father_name")),
                "Address (Street/Village/House No.)": MISSING,
                "Postal Code": MISSING,
                "Region": MISSING,
                "Occupation": _as_text(_safe_get(student_profile, "father_occupation")),
                "Phone": _as_text(_safe_get(student_profile, "father_phone")),
                "Email": _as_text(_safe_get(student_profile, "father_email")),
            },
            "Mother": {
                "Full Name": _as_text(_safe_get(student_profile, "mother_name")),
                "Address (Street/Village/House No.)": MISSING,
                "Postal Code": MISSING,
                "Region": MISSING,
                "Occupation": _as_text(_safe_get(student_profile, "mother_occupation")),
                "Phone": _as_text(_safe_get(student_profile, "mother_phone")),
                "Email": _as_text(_safe_get(student_profile, "mother_email")),
            },
        },
        "emergency": {
            "Full Name": _as_text(_safe_get(student_profile, "emergency_contact")),
            "Relationship": _as_text(_safe_get(student_profile, "emergency_relation")),
            "Occupation": _as_text(_safe_get(student_profile, "emergency_occupation")),
            "Phone Number": _as_text(_safe_get(student_profile, "phone_number")),
            "Email Address": _as_text(_safe_get(student, "email")),
            "Address (Street/Village/House No.)": _as_text(_safe_get(student_profile, "emergency_address")),
        },
        "education_background": [
            {
                "Level": "Form Four (O-Level)",
                "School Name": _as_text(_safe_get(student_profile, "olevel_school")),
                "Index Number": _as_text(_safe_get(student_profile, "olevel_candidate_no")),
                "Year Completed": _year_text(_safe_get(student_profile, "olevel_year")),
                "Division / GPA": _as_text(_safe_get(student_profile, "olevel_gpa")),
            },
            {
                "Level": "Form Six (A-Level)",
                "School Name": _as_text(_safe_get(student_profile, "alevel_school")),
                "Index Number": _as_text(_safe_get(student_profile, "alevel_candidate_no")),
                "Year Completed": _year_text(_safe_get(student_profile, "alevel_year")),
                "Division / GPA": _as_text(_safe_get(student_profile, "alevel_gpa")),
            },
        ],
        "higher_education": [],
        "professional_qualifications": _as_text(_safe_get(supplemental_profile, "professional_qualifications")),
        "english_proficiency": {
            "Test Name": _as_text(_safe_get(supplemental_profile, "english_test_name")),
            "Score": _as_text(_safe_get(supplemental_profile, "english_test_score")),
            "Year": _year_text(_safe_get(supplemental_profile, "english_test_year")),
        },
        "employment_history": [],
        "study_preferences": {
            "Preferred Country 1": _as_text(_safe_get(student_profile, "preferred_country_1")),
            "Preferred Program 1": _as_text(_safe_get(student_profile, "preferred_program_1")),
            "Preferred Country 2": _as_text(_safe_get(student_profile, "preferred_country_2")),
            "Preferred Program 2": _as_text(_safe_get(student_profile, "preferred_program_2")),
            "Preferred Country 3": _as_text(_safe_get(student_profile, "preferred_country_3")),
            "Preferred Program 3": _as_text(_safe_get(student_profile, "preferred_program_3")),
        },
        "addresses": {
            "Current Address (Street/Village/House No.)": _as_text(_safe_get(supplemental_profile, "current_address") or _safe_get(student_profile, "address")),
            "Current Region": _as_text(_safe_get(supplemental_profile, "current_region")),
            "Current City": _as_text(_safe_get(supplemental_profile, "current_city")),
            "Current Country": _as_text(_safe_get(supplemental_profile, "current_country")),
            "Current Postal Code": _as_text(_safe_get(supplemental_profile, "current_postal_code")),
            "Permanent Address (Street/Village/House No.)": _as_text(_safe_get(student_profile, "address")),
            "Permanent Region": MISSING,
            "Permanent City": MISSING,
            "Permanent Country": _as_text(_safe_get(student_profile, "nationality")),
            "Permanent Postal Code": MISSING,
        },
        "other_details": {
            "Passport Number": _as_text(_safe_get(supplemental_profile, "passport_number")),
            "Country of Issue": _as_text(_safe_get(supplemental_profile, "passport_issue_country")),
            "Date of Issue": _date_text(_safe_get(supplemental_profile, "passport_issue_date")),
            "Expiry Date": _date_text(_safe_get(supplemental_profile, "passport_expiration_date")),
            "Valid Visa?": _as_text(_safe_get(supplemental_profile, "has_valid_visa")),
            "Visa Details (if applicable)": _as_text(_safe_get(supplemental_profile, "valid_visa_details")),
            "Program Level": _choice_text(supplemental_profile, "program_level"),
            "Preferred Intake": _choice_text(supplemental_profile, "preferred_intake"),
            "Accommodation Preference": _choice_text(supplemental_profile, "accommodation_preference"),
            "Sponsor of Education": _as_text(_safe_get(supplemental_profile, "education_sponsor")),
            "Estimated Budget (USD)": _money_text(_safe_get(supplemental_profile, "estimated_budget_usd")),
            "Scholarship Applied?": _as_text(_safe_get(supplemental_profile, "scholarship_applied")),
            "Scholarship Details (if applicable)": _as_text(_safe_get(supplemental_profile, "scholarship_details")),
            "Any Medical Condition?": _as_text(_safe_get(supplemental_profile, "has_medical_condition")),
            "Medical Condition Details (if applicable)": _as_text(_safe_get(supplemental_profile, "medical_condition_details")),
            "Special Assistance Required?": _as_text(_safe_get(supplemental_profile, "needs_special_assistance")),
            "Special Assistance Details (if applicable)": _as_text(_safe_get(supplemental_profile, "special_assistance_details")),
        },
        "heard_about_us": {
            "Source": _choice_text(student_profile, "heard_about_us"),
            "Other (please specify)": _as_text(_safe_get(student_profile, "heard_about_other")),
        },
        "declaration": {
            "Applicant Full Name": student_name,
            "Date": application_date,
            "Signature": "",
            "Declaration Agreed": _as_text(_safe_get(supplemental_profile, "declaration_agreed"), "Yes"),
        },
    }

    for label, prefix in [
        ("Certificate", "certificate"),
        ("Diploma", "diploma"),
        ("Bachelor Degree", "bachelor"),
        ("Master Degree", "master"),
        ("PhD", "phd"),
    ]:
        data["higher_education"].append({
            "Level": label,
            "Institution": _as_text(_safe_get(supplemental_profile, f"{prefix}_institution")),
            "Field of Study": _as_text(_safe_get(supplemental_profile, f"{prefix}_field_of_study")),
            "Year Completed": _year_text(_safe_get(supplemental_profile, f"{prefix}_year_completed")),
            "GPA": _as_text(_safe_get(supplemental_profile, f"{prefix}_gpa")),
        })

    for experience in _get_work_experiences(student_profile):
        end_value = "Present" if _safe_get(experience, "currently_working") else _date_text(_safe_get(experience, "end_date"))
        data["employment_history"].append({
            "Employer / Company Name": _as_text(_safe_get(experience, "company_name")),
            "Position / Job Title": _as_text(_safe_get(experience, "position")),
            "Location": _as_text(_safe_get(experience, "location")),
            "Period": f"{_date_text(_safe_get(experience, 'start_date'))} - {end_value}",
        })

    return data


def _get_work_experiences(student_profile: Any) -> List[Any]:
    if student_profile is None:
        return []
    manager = getattr(student_profile, "work_experiences", None)
    if manager is None:
        return []
    try:
        return list(manager.all()[:4])
    except Exception:
        try:
            return list(manager.all().order_by("-start_date")[:4])
        except Exception:
            return []


def build_csc_style_application_pdf(application, student_profile=None, supplemental_profile=None):
    styles = _styles()
    data = application_to_awec_csc_style_data(application, student_profile, supplemental_profile)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=16 * mm,
    )
    doc.serial_number = data["meta"]["application_id"]
    doc.generated_date = data["meta"]["generated_date"]

    story = []
    _header(story, styles)
    story.append(Paragraph("STUDY ABROAD REGISTRATION FORM", styles["title"]))
    story.append(Paragraph(
        f"Registration Reference Number: {data['meta']['application_id']}    Application Date: {data['meta']['application_date']}",
        styles["subtitle"],
    ))
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph("SECTION 1: PERSONAL DETAILS", styles["section"]))
    personal = data["personal"]
    gender = _as_text(personal.get("Gender"), "")
    personal_table = _single_row_table([
        ("Full Name (as in passport)", personal.get("Full Name (as in passport)")),
        ("Gender", f"{_bool_box(gender.lower() == 'male')} Male   {_bool_box(gender.lower() == 'female')} Female"),
        ("Date of Birth", personal.get("Date of Birth")),
        ("Place of Birth", personal.get("Place of Birth")),
        ("Nationality", personal.get("Nationality")),
        ("Email", personal.get("Email")),
        ("Phone Number", personal.get("Phone Number")),
        ("Form Six School Name", personal.get("Form Six School Name")),
        ("Form Six School Address", personal.get("Form Six School Address")),
        ("Passport Number", personal.get("Passport Number")),
        ("Form Four School Name", personal.get("Form Four School Name")),
        ("Form Four School Address", personal.get("Form Four School Address")),
        ("Form Four Division / GPA", personal.get("Form Four Division / GPA")),
        ("Application ID / Serial Number", personal.get("Application ID / Serial Number")),
    ], styles)
    story.append(Table([[personal_table, _photo_flowable(student_profile, styles)]], colWidths=[148 * mm, 38 * mm], style=TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ])))
    story.append(Spacer(1, 1.8 * mm))

    story.append(Paragraph("SECTION 2: PARENTS DETAILS", styles["section"]))
    father = data["parents"].get("Father", {})
    mother = data["parents"].get("Mother", {})
    parent_rows = [
        [Paragraph("<b>Field</b>", styles["body"]), Paragraph("<b>Father</b>", styles["body"]), Paragraph("<b>Mother</b>", styles["body"])],
        [Paragraph("Full Name", styles["body"]), Paragraph(escape(father.get("Full Name", MISSING)), styles["body"]), Paragraph(escape(mother.get("Full Name", MISSING)), styles["body"])],
        [Paragraph("Address (Street/Village/House No.)", styles["body"]), Paragraph(MISSING, styles["body"]), Paragraph(MISSING, styles["body"])],
        [Paragraph("Postal Code", styles["body"]), Paragraph(MISSING, styles["body"]), Paragraph(MISSING, styles["body"])],
        [Paragraph("Region", styles["body"]), Paragraph(MISSING, styles["body"]), Paragraph(MISSING, styles["body"])],
        [Paragraph("Occupation", styles["body"]), Paragraph(escape(father.get("Occupation", MISSING)), styles["body"]), Paragraph(escape(mother.get("Occupation", MISSING)), styles["body"])],
        [Paragraph("Phone", styles["body"]), Paragraph(escape(father.get("Phone", MISSING)), styles["body"]), Paragraph(escape(mother.get("Phone", MISSING)), styles["body"])],
        [Paragraph("Email", styles["body"]), Paragraph(escape(father.get("Email", MISSING)), styles["body"]), Paragraph(escape(mother.get("Email", MISSING)), styles["body"])],
    ]
    story.append(_boxed_table(parent_rows, [48 * mm, 68 * mm, 68 * mm], header_rows=1))
    story.append(PageBreak())

    story.append(Paragraph("SECTION 3: EMERGENCY CONTACT DETAILS", styles["section"]))
    emergency = data["emergency"]
    story.append(_single_row_table([
        ("Full Name", emergency.get("Full Name")),
        ("Relationship", emergency.get("Relationship")),
        ("Occupation", emergency.get("Occupation")),
        ("Phone Number", emergency.get("Phone Number")),
        ("Email Address", emergency.get("Email Address")),
        ("Address (Street/Village/House No.)", emergency.get("Address (Street/Village/House No.)")),
    ], styles))
    story.append(Spacer(1, 1.6 * mm))

    story.append(Paragraph("SECTION 4: EDUCATION BACKGROUND DETAILS", styles["section"]))
    education_rows = [
        [Paragraph("<b>Level</b>", styles["body"]), Paragraph("<b>School Name</b>", styles["body"]), Paragraph("<b>Index Number</b>", styles["body"]), Paragraph("<b>Year Completed</b>", styles["body"]), Paragraph("<b>Division / GPA</b>", styles["body"])],
        [Paragraph("Form Four (O-Level)", styles["body"]), Paragraph(escape(data["education_background"][0]["School Name"]), styles["body"]), Paragraph(escape(data["education_background"][0]["Index Number"]), styles["body"]), Paragraph(escape(data["education_background"][0]["Year Completed"]), styles["body"]), Paragraph(escape(data["education_background"][0]["Division / GPA"]), styles["body"])],
        [Paragraph("Form Six (A-Level)", styles["body"]), Paragraph(escape(data["education_background"][1]["School Name"]), styles["body"]), Paragraph(escape(data["education_background"][1]["Index Number"]), styles["body"]), Paragraph(escape(data["education_background"][1]["Year Completed"]), styles["body"]), Paragraph(escape(data["education_background"][1]["Division / GPA"]), styles["body"])],
    ]
    story.append(_boxed_table(education_rows, [34 * mm, 64 * mm, 30 * mm, 28 * mm, 28 * mm], header_rows=1))
    story.append(PageBreak())

    story.append(Paragraph("POST-SECONDARY / HIGHER EDUCATION", styles["section"]))
    higher_rows = [[Paragraph("<b>Level</b>", styles["body"]), Paragraph("<b>Institution</b>", styles["body"]), Paragraph("<b>Field of Study</b>", styles["body"]), Paragraph("<b>Year Completed</b>", styles["body"]), Paragraph("<b>GPA</b>", styles["body"])]]
    for row in data["higher_education"]:
        higher_rows.append([
            Paragraph(escape(row["Level"]), styles["body"]),
            Paragraph(escape(row["Institution"]), styles["body"]),
            Paragraph(escape(row["Field of Study"]), styles["body"]),
            Paragraph(escape(row["Year Completed"]), styles["body"]),
            Paragraph(escape(row["GPA"]), styles["body"]),
        ])
    story.append(_boxed_table(higher_rows, [30 * mm, 58 * mm, 48 * mm, 26 * mm, 22 * mm], font_size=8.4, header_rows=1))
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph("PROFESSIONAL QUALIFICATIONS / TRAINING", styles["section"]))
    story.append(_boxed_table([[Paragraph(escape(data["professional_qualifications"]), styles["body"]) ]], [184 * mm], row_heights=[18 * mm]))
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph("ENGLISH LANGUAGE PROFICIENCY", styles["section"]))
    story.append(_boxed_table([
        [Paragraph("<b>Test</b>", styles["body"]), Paragraph("<b>Score</b>", styles["body"]), Paragraph("<b>Year</b>", styles["body"])],
        [Paragraph(escape(data["english_proficiency"]["Test Name"]), styles["body"]), Paragraph(escape(data["english_proficiency"]["Score"]), styles["body"]), Paragraph(escape(data["english_proficiency"]["Year"]), styles["body"])],
    ], [84 * mm, 50 * mm, 50 * mm], header_rows=1))
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph("SECTION 5: EMPLOYMENT HISTORY / WORK EXPERIENCE", styles["section"]))
    employment_rows = [[Paragraph("<b>Employer</b>", styles["body"]), Paragraph("<b>Position</b>", styles["body"]), Paragraph("<b>Location</b>", styles["body"]), Paragraph("<b>Period</b>", styles["body"])]]
    if data["employment_history"]:
        for item in data["employment_history"][:4]:
            employment_rows.append([
                Paragraph(escape(item["Employer / Company Name"]), styles["body"]),
                Paragraph(escape(item["Position / Job Title"]), styles["body"]),
                Paragraph(escape(item["Location"]), styles["body"]),
                Paragraph(escape(item["Period"]), styles["body"]),
            ])
    else:
        employment_rows.append([Paragraph("No work experience provided", styles["body"]), Paragraph(MISSING, styles["body"]), Paragraph(MISSING, styles["body"]), Paragraph(MISSING, styles["body"])])
    story.append(_boxed_table(employment_rows, [64 * mm, 46 * mm, 40 * mm, 34 * mm], header_rows=1, font_size=8.4))
    story.append(PageBreak())

    story.append(Paragraph("SECTION 6: STUDY PREFERENCES", styles["section"]))
    story.append(_single_row_table([
        ("Preferred Country 1", data["study_preferences"].get("Preferred Country 1")),
        ("Preferred Program 1", data["study_preferences"].get("Preferred Program 1")),
        ("Preferred Country 2", data["study_preferences"].get("Preferred Country 2")),
        ("Preferred Program 2", data["study_preferences"].get("Preferred Program 2")),
        ("Preferred Country 3", data["study_preferences"].get("Preferred Country 3")),
        ("Preferred Program 3", data["study_preferences"].get("Preferred Program 3")),
    ], styles))
    story.append(Spacer(1, 1.6 * mm))

    story.append(Paragraph("SECTION 7: CURRENT AND PERMANENT ADDRESS", styles["section"]))
    addresses = data["addresses"]
    story.append(_single_row_table([
        ("Current Address (Street/Village/House No.)", addresses.get("Current Address (Street/Village/House No.)")),
        ("Current Region", addresses.get("Current Region")),
        ("Current City", addresses.get("Current City")),
        ("Current Country", addresses.get("Current Country")),
        ("Current Postal Code", addresses.get("Current Postal Code")),
        ("Permanent Address (Street/Village/House No.)", addresses.get("Permanent Address (Street/Village/House No.)")),
        ("Permanent Region", addresses.get("Permanent Region")),
        ("Permanent City", addresses.get("Permanent City")),
        ("Permanent Country", addresses.get("Permanent Country")),
        ("Permanent Postal Code", addresses.get("Permanent Postal Code")),
    ], styles))
    story.append(Spacer(1, 1.6 * mm))

    story.append(Paragraph("SECTION 8: OTHER DETAILS", styles["section"]))
    other = data["other_details"]
    story.append(_single_row_table([
        ("Passport Number", other.get("Passport Number")),
        ("Country of Issue", other.get("Country of Issue")),
        ("Date of Issue", other.get("Date of Issue")),
        ("Expiry Date", other.get("Expiry Date")),
        ("Valid Visa?", other.get("Valid Visa?")),
        ("Visa Details", other.get("Visa Details (if applicable)")),
        ("Program Level", other.get("Program Level")),
        ("Preferred Intake", other.get("Preferred Intake")),
        ("Accommodation Preference", other.get("Accommodation Preference")),
        ("Sponsor of Education", other.get("Sponsor of Education")),
        ("Estimated Budget (USD)", other.get("Estimated Budget (USD)")),
        ("Scholarship Applied?", other.get("Scholarship Applied?")),
        ("If yes, specify", other.get("Scholarship Details (if applicable)")),
        ("Any medical condition?", other.get("Any Medical Condition?")),
        ("If yes, explain", other.get("Medical Condition Details (if applicable)")),
        ("Special assistance required?", other.get("Special Assistance Required?")),
        ("If yes, specify", other.get("Special Assistance Details (if applicable)")),
    ], styles))
    story.append(PageBreak())

    story.append(Paragraph("SECTION 9: HOW DID YOU HEAR ABOUT US?", styles["section"]))
    heard = data["heard_about_us"]
    story.append(_single_row_table([
        ("Source", heard.get("Source")),
        ("Other (please specify)", heard.get("Other (please specify)")),
    ], styles))
    story.append(Spacer(1, 1.6 * mm))

    story.append(Paragraph("SECTION 10: DECLARATION BY APPLICANT", styles["section"]))
    for item in DECLARATION_LINES:
        story.append(Paragraph(escape(item), styles["body"]))
        story.append(Spacer(1, 1.2 * mm))
    story.append(Spacer(1, 1.6 * mm))
    declaration = data["declaration"]
    story.append(_single_row_table([
        ("Applicant Full Name", declaration.get("Applicant Full Name")),
        ("Date", declaration.get("Date")),
        ("Signature", declaration.get("Signature") or ""),
        ("Declaration Agreed", declaration.get("Declaration Agreed")),
    ], styles))
    story.append(PageBreak())

    story.append(Paragraph("TERMS AND CONDITIONS", styles["section"]))
    for item in TERMS_AND_CONDITIONS:
        story.append(Paragraph(escape(item), styles["small"]))
        story.append(Spacer(1, 1.1 * mm))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    student_name = data["personal"].get("Full Name (as in passport)", "student").replace(" ", "_")
    response["Content-Disposition"] = f'attachment; filename="{student_name}_application_form.pdf"'
    return response


def build_awec_csc_style_application_pdf_response(application: Any, student_profile: Any = None, supplemental_profile: Any = None) -> HttpResponse:
    return build_csc_style_application_pdf(application, student_profile, supplemental_profile)
