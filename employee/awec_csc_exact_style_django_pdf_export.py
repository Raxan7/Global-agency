#!/usr/bin/env python3
"""
Create an Africa Western Education student application form using a CSC/Chinese
Government Scholarship style layout, but with AWEC fields and AWEC header text.

Independent generator: it does NOT use the old AWEC PDF style and does NOT need
any source PDF template. Change the JSON data and the same form layout is reused.

Usage:
  pip install reportlab pillow
  python create_awec_csc_style_form.py --output dummy_awec_csc_style_form.pdf
  python create_awec_csc_style_form.py --write-sample-json sample_awec_data.json
  python create_awec_csc_style_form.py --data sample_awec_data.json --output applicant.pdf
"""
from __future__ import annotations

import argparse
import json
import math
import textwrap
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

try:
    from PIL import Image as PILImage
except Exception:  # pragma: no cover
    PILImage = None

PAGE_W, PAGE_H = A4
TOTAL_PAGES = 6
MISSING = "-"

BLUE = colors.HexColor("#0066B3")
BLACK = colors.black
LIGHT_GRAY = colors.white

LEFT = 12 * mm
RIGHT = PAGE_W - 12 * mm
TOP = PAGE_H - 10 * mm
BOTTOM = 18 * mm
CONTENT_W = RIGHT - LEFT

FONT = "Times-Roman"
FONT_BOLD = "Times-Bold"
FONT_ITALIC = "Times-BoldItalic"

DEFAULT_DATA: Dict[str, Any] = {
    "organization": {
        "name": "Africa Western Education (AWEC)",
        "legal_name": "Africa Western Education Company LIMITED",
        "logo_path": "",
        "website": "www.africawesterneducation.com",
        "email": "info@africawesterneducation.com",
        "telephone": "+255 767 688 766",
        "address_lines": [
            "Plot 8, Block 46",
            "Kijitonyama, Mpakani Centre",
            "3rd Floor, Suite F1.01",
            "P.O. Box 34402",
            "Dar es Salaam, Tanzania",
        ],
    },
    "meta": {
        "form_title": "STUDY ABROAD REGISTRATION FORM",
        "application_id": "AWECO/Tz/DSM/001",
        "generated_date": date.today().strftime("%Y-%m-%d"),
        "application_date": date.today().strftime("%d/%m/%Y"),
            },
    "personal": {
        "Full Name (as in passport)": "Amina Grace Mwandu",
        "Gender": "Female",
        "Date of Birth": "14/03/2003",
        "Place of Birth": "Mwanza, Tanzania",
        "Nationality": "Tanzanian",
        "Email": "amina.mwandu@example.com",
        "Phone Number": "+255 712 345 678",
        "Form Six School Name": "Jangwani Secondary School",
        "Form Six School Address": "P.O. Box 12345, Dar es Salaam",
        "Passport Number": "TZA123456",
        "Form Four School Name": "Mlimani Secondary School",
        "Form Four School Address": "Mlimani Road, Morogoro",
        "Form Four Division / GPA": "Division I",
        "Application ID / Serial Number": "AWECO/Tz/DSM/001",
        "Student Photo": "",
    },
    "parents": {
        "Father": {
            "Full Name": "Joseph Mwandu",
            "Address (Street/Village/House No.)": "House 18, Mbezi Beach",
            "Postal Code": "14128",
            "Region": "Dar es Salaam",
            "Occupation": "Accountant",
            "Phone": "+255 754 111 222",
            "Email": "joseph.mwandu@example.com",
        },
        "Mother": {
            "Full Name": "Neema Mwandu",
            "Address (Street/Village/House No.)": "House 18, Mbezi Beach",
            "Postal Code": "14128",
            "Region": "Dar es Salaam",
            "Occupation": "Teacher",
            "Phone": "+255 755 333 444",
            "Email": "neema.mwandu@example.com",
        },
    },
    "emergency": {
        "Full Name": "Daniel Komba",
        "Relationship": "Uncle",
        "Occupation": "Medical Officer",
        "Phone Number": "+255 765 777 888",
        "Email Address": "daniel.komba@example.com",
        "Address (Street/Village/House No.)": "Kinondoni, Dar es Salaam",
    },
    "education_background": [
        {"Level": "Form Four (O-Level)", "School Name": "Mlimani Secondary School", "Index Number": "S0123/0456", "Year Completed": "2020", "Division / GPA": "Division I"},
        {"Level": "Form Six (A-Level)", "School Name": "Jangwani Secondary School", "Index Number": "S0456/0789", "Year Completed": "2023", "Division / GPA": "Division II"},
    ],
    "higher_education": [
        {"Level": "Certificate", "Institution": "Dar Training Centre", "Field of Study": "Computer Applications", "Year Completed": "2021", "GPA": "A"},
        {"Level": "Diploma", "Institution": "-", "Field of Study": "-", "Year Completed": "-", "GPA": "-"},
        {"Level": "Bachelor Degree", "Institution": "-", "Field of Study": "-", "Year Completed": "-", "GPA": "-"},
        {"Level": "Master Degree", "Institution": "-", "Field of Study": "-", "Year Completed": "-", "GPA": "-"},
        {"Level": "PhD", "Institution": "-", "Field of Study": "-", "Year Completed": "-", "GPA": "-"},
    ],
    "professional_qualifications": "Short course in academic writing, leadership training, and basic computer applications.",
    "english_proficiency": {"Test Name": "IELTS", "Score": "6.5", "Year": "2024"},
    "employment_history": [
        {"Employer / Company Name": "Bright Future Academy", "Position / Job Title": "Assistant Teacher", "Location": "Dar es Salaam", "Period": "01/01/2024 - Present"},
        {"Employer / Company Name": "Community Youth Centre", "Position / Job Title": "Volunteer Tutor", "Location": "Mwanza", "Period": "01/06/2022 - 30/11/2022"},
    ],
    "study_preferences": {
        "Preferred Country 1": "China", "Preferred Program 1": "Bachelor of Business Administration",
        "Preferred Country 2": "Malaysia", "Preferred Program 2": "Bachelor of International Business",
        "Preferred Country 3": "Turkey", "Preferred Program 3": "Bachelor of Economics",
    },
    "addresses": {
        "Current Address (Street/Village/House No.)": "Mbezi Beach, House 18",
        "Current Region": "Dar es Salaam", "Current City": "Dar es Salaam", "Current Country": "Tanzania", "Current Postal Code": "14128",
        "Permanent Address (Street/Village/House No.)": "Nyamagana District",
        "Permanent Region": "Mwanza", "Permanent City": "Mwanza", "Permanent Country": "Tanzania", "Permanent Postal Code": "33100",
    },
    "other_details": {
        "Passport Number": "TZA123456", "Country of Issue": "Tanzania", "Date of Issue": "10/05/2024", "Expiry Date": "09/05/2034",
        "Valid Visa?": "No", "Visa Details (if applicable)": "-", "Program Level": "Bachelor Degree", "Preferred Intake": "September 2026",
        "Accommodation Preference": "University Dormitory", "Sponsor of Education": "Parents", "Estimated Budget (USD)": "8500.00",
        "Scholarship Applied?": "Yes", "Scholarship Details (if applicable)": "University merit scholarship under consideration",
        "Any Medical Condition?": "No", "Medical Condition Details (if applicable)": "-", "Special Assistance Required?": "No", "Special Assistance Details (if applicable)": "-",
    },
    "heard_about_us": {"Source": "Friend / Referral", "Other (please specify)": "-"},
    "declaration": {
        "Applicant Full Name": "Amina Grace Mwandu", "Date": date.today().strftime("%d/%m/%Y"), "Signature": "", "Declaration Agreed": "Yes",
    },
}

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


def deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_update(result[key], value)
        else:
            result[key] = value
    return result


def val(x: Any) -> str:
    if x is None or x == "":
        return MISSING
    return str(x)


def checkbox(label: str, selected: bool) -> str:
    return ("✓ " if selected else "  ") + label


def fit_text(c: canvas.Canvas, text: str, max_w: float, font: str, size: float) -> List[str]:
    text = val(text)
    if text == "":
        return [MISSING]
    words = text.split()
    if not words:
        return [MISSING]
    lines: List[str] = []
    cur = ""
    for w in words:
        attempt = w if not cur else cur + " " + w
        if stringWidth(attempt, font, size) <= max_w:
            cur = attempt
        else:
            if cur:
                lines.append(cur)
            # Break a single very long word if necessary.
            if stringWidth(w, font, size) > max_w:
                part = ""
                for ch in w:
                    if stringWidth(part + ch, font, size) <= max_w:
                        part += ch
                    else:
                        lines.append(part)
                        part = ch
                cur = part
            else:
                cur = w
    if cur:
        lines.append(cur)
    return lines or [MISSING]


def draw_wrapped(c: canvas.Canvas, text: str, x: float, y: float, w: float, h: float, font: str = FONT, size: float = 9.3, leading: Optional[float] = None, color=BLACK) -> None:
    leading = leading or size + 2
    c.setFillColor(color)
    c.setFont(font, size)
    lines = fit_text(c, text, w, font, size)
    max_lines = max(1, int((h - 4) // leading))
    lines = lines[:max_lines]
    if len(lines) == max_lines and len(fit_text(c, text, w, font, size)) > max_lines:
        last = lines[-1]
        while stringWidth(last + "...", font, size) > w and last:
            last = last[:-1]
        lines[-1] = last + "..."
    cy = y + h - size - 3
    for line in lines:
        c.drawString(x, cy, line)
        cy -= leading


def draw_label_value(c: canvas.Canvas, x: float, y_top: float, w: float, h: float, label: str, value: Any, label_size: float = 9.7, value_size: float = 9.6) -> None:
    y = y_top - h
    c.setStrokeColor(BLACK)
    c.setLineWidth(1.05)
    c.rect(x, y, w, h, stroke=1, fill=0)
    pad = 2.0
    c.setFont(FONT, label_size)
    c.setFillColor(BLACK)
    c.drawString(x + pad, y + h - label_size - 2.0, label)
    draw_wrapped(c, val(value), x + pad, y + 2.0, w - 2 * pad, h - label_size - 3.8, FONT, value_size)


def draw_row(c: canvas.Canvas, y_top: float, cells: Sequence[Tuple[str, Any, float]], h: float = 15 * mm) -> float:
    x = LEFT
    for label, value, width in cells:
        draw_label_value(c, x, y_top, width, h, label, value)
        x += width
    return y_top - h


def draw_section(c: canvas.Canvas, title: str, y: float) -> float:
    c.setFont(FONT_ITALIC, 13.2)
    c.setFillColor(BLUE)
    c.drawString(LEFT, y, title)
    tw = stringWidth(title, FONT_ITALIC, 13.2)
    c.setStrokeColor(BLUE)
    c.setLineWidth(0.7)
    c.line(LEFT, y - 1.2, LEFT + tw, y - 1.2)
    c.setFillColor(BLACK)
    return y - 5.5


def draw_table(c: canvas.Canvas, x: float, y_top: float, col_widths: Sequence[float], row_heights: Sequence[float], rows: Sequence[Sequence[Any]], header_rows: int = 1, font_size: float = 9.2) -> float:
    y = y_top
    c.setLineWidth(1.05)
    for r, row in enumerate(rows):
        h = row_heights[r] if r < len(row_heights) else row_heights[-1]
        y -= h
        cx = x
        for col, width in enumerate(col_widths):
            if r < header_rows:
                c.setFillColor(LIGHT_GRAY)
                c.rect(cx, y, width, h, stroke=0, fill=1)
            c.setStrokeColor(BLACK)
            c.rect(cx, y, width, h, stroke=1, fill=0)
            text = row[col] if col < len(row) else ""
            draw_wrapped(c, text, cx + 2.2, y + 2.2, width - 4.4, h - 4.4, FONT_BOLD if r < header_rows else FONT, font_size)
            cx += width
    return y


def draw_header(c: canvas.Canvas, data: Dict[str, Any], page_no: int) -> float:
    """Header built to match the CSC form rhythm: left seal, centered agency text, no top-right table."""
    org = data["organization"]
    y = TOP
    if page_no == 1:
        cx, cy = LEFT + 15.5 * mm, y - 23 * mm
        # Draw company logo when provided, otherwise draw a simple seal.
        logo_path = org.get("logo_path", "")
        if logo_path and Path(logo_path).exists() and PILImage:
            try:
                img = PILImage.open(logo_path)
                iw, ih = img.size
                img.close()
                size = 23 * mm
                # center the logo on the same seal position
                c.drawImage(logo_path, cx - size / 2, cy - size / 2, size, size, preserveAspectRatio=True, mask="auto")
            except Exception:
                c.setStrokeColor(BLUE)
                c.setLineWidth(1.0)
                c.circle(cx, cy, 11.5 * mm, stroke=1, fill=0)
                c.setFont(FONT_BOLD, 12.5)
                c.setFillColor(BLUE)
                c.drawCentredString(cx, cy - 3.2, "AWEC")
        else:
            c.setStrokeColor(BLUE)
            c.setLineWidth(1.0)
            c.circle(cx, cy, 11.5 * mm, stroke=1, fill=0)
            c.setFont(FONT_BOLD, 12.5)
            c.setFillColor(BLUE)
            c.drawCentredString(cx, cy - 3.2, "AWEC")

        c.setFillColor(BLACK)
        c.setFont(FONT_BOLD, 9.8)
        c.drawCentredString(PAGE_W / 2, y - 13 * mm, org["name"])
        c.setFont(FONT_BOLD, 12.0)
        c.drawCentredString(PAGE_W / 2, y - 17 * mm, org["legal_name"])
        c.setFont(FONT, 8.4)
        c.drawCentredString(PAGE_W / 2, y - 21 * mm, ", ".join(org["address_lines"][:3]))
        c.drawCentredString(PAGE_W / 2, y - 25 * mm, ", ".join(org["address_lines"][3:]))
        c.drawCentredString(PAGE_W / 2, y - 29 * mm, f"Tel: {org['telephone']}    E-mail: {org['email']}")
        c.drawCentredString(PAGE_W / 2, y - 33 * mm, f"Website: {org['website']}")
        return y - 49 * mm
    return TOP - 12 * mm

def draw_footer(c: canvas.Canvas, data: Dict[str, Any], page_no: int) -> None:
    meta = data["meta"]
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.8)
    c.line(LEFT, 16 * mm, RIGHT, 16 * mm)
    c.setFont(FONT, 9)
    c.setFillColor(BLACK)
    c.drawString(LEFT + 2 * mm, 8 * mm, f"Application ID: {meta.get('application_id', MISSING)}")
    c.drawCentredString(PAGE_W / 2, 8 * mm, f"Page {page_no} of {TOTAL_PAGES}")
    c.drawRightString(RIGHT - 2 * mm, 8 * mm, f"Generated: {meta.get('generated_date', MISSING)}")


def new_page(c: canvas.Canvas, data: Dict[str, Any], page_no: int) -> float:
    if page_no > 1:
        c.showPage()
    y = draw_header(c, data, page_no)
    return y


def end_page(c: canvas.Canvas, data: Dict[str, Any], page_no: int) -> None:
    draw_footer(c, data, page_no)


def draw_title(c: canvas.Canvas, data: Dict[str, Any], y: float) -> float:
    c.setFont(FONT_BOLD, 16)
    c.drawCentredString(PAGE_W / 2, y, data["meta"]["form_title"])
    c.setFont(FONT, 9.8)
    c.drawCentredString(PAGE_W / 2, y - 6 * mm, f"Registration Reference Number: {data['meta']['application_id']}    Application Date: {data['meta']['application_date']}")
    return y - 12 * mm


def draw_photo(c: canvas.Canvas, x: float, y_top: float, w: float, h: float, photo_path: str = "") -> None:
    y = y_top - h
    c.rect(x, y, w, h, stroke=1, fill=0)
    if photo_path and Path(photo_path).exists() and PILImage:
        try:
            img = PILImage.open(photo_path)
            iw, ih = img.size
            img.close()
            scale = min((w - 6) / iw, (h - 6) / ih)
            dw, dh = iw * scale, ih * scale
            c.drawImage(photo_path, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh, preserveAspectRatio=True, mask="auto")
            return
        except Exception:
            pass
    c.setFont(FONT_BOLD, 11)
    c.drawCentredString(x + w / 2, y + h / 2 + 4, "Student")
    c.drawCentredString(x + w / 2, y + h / 2 - 9, "Photo")


def generate_pdf(output: str, data: Dict[str, Any]) -> None:
    c = canvas.Canvas(output, pagesize=A4)

    # PAGE 1
    page = 1
    y = new_page(c, data, page)
    y = draw_title(c, data, y)
    y = draw_section(c, "SECTION 1: PERSONAL DETAILS", y)
    p = data["personal"]
    gender = val(p.get("Gender"))
    photo_gap = 4 * mm
    photo_w = 44 * mm
    personal_w = CONTENT_W - photo_w - photo_gap
    row_h = 12 * mm
    personal_cells = [
        [("Full Name (as in passport)", p.get("Full Name (as in passport)"), personal_w / 2), ("Gender", f"{checkbox('Male', gender.lower() == 'male')}   {checkbox('Female', gender.lower() == 'female')}", personal_w / 2)],
        [("Date of Birth", p.get("Date of Birth"), personal_w * 0.30), ("Place of Birth", p.get("Place of Birth"), personal_w * 0.40), ("Nationality", p.get("Nationality"), personal_w * 0.30)],
        [("Email", p.get("Email"), personal_w / 2), ("Phone Number", p.get("Phone Number"), personal_w / 2)],
        [("Form Six School Name", p.get("Form Six School Name"), personal_w / 2), ("Form Six School Address", p.get("Form Six School Address"), personal_w / 2)],
        [("Passport Number", p.get("Passport Number"), personal_w * 0.32), ("Form Four School Name", p.get("Form Four School Name"), personal_w * 0.34), ("Form Four School Address", p.get("Form Four School Address"), personal_w * 0.34)],
        [("Form Four Division / GPA", p.get("Form Four Division / GPA"), personal_w / 2), ("Application ID / Serial Number", p.get("Application ID / Serial Number"), personal_w / 2)],
    ]
    yy = y
    for row in personal_cells:
        yy = draw_row(c, yy, row, row_h)
    draw_photo(c, LEFT + personal_w + photo_gap, y, photo_w, row_h * len(personal_cells), p.get("Student Photo", ""))
    y = yy - 5 * mm

    y = draw_section(c, "SECTION 2: PARENTS DETAILS", y)
    parent_rows = [["Field", "Father", "Mother"]]
    father = data["parents"].get("Father", {})
    mother = data["parents"].get("Mother", {})
    for field in ["Full Name", "Address (Street/Village/House No.)", "Postal Code", "Region", "Occupation", "Phone", "Email"]:
        parent_rows.append([field, father.get(field, MISSING), mother.get(field, MISSING)])
    y = draw_table(c, LEFT, y, [CONTENT_W * 0.25, CONTENT_W * 0.375, CONTENT_W * 0.375], [9.5 * mm] + [12 * mm] * 7, parent_rows, header_rows=1, font_size=8.8)
    end_page(c, data, page)

    # PAGE 2
    page = 2
    y = new_page(c, data, page)
    y = draw_section(c, "SECTION 3: EMERGENCY CONTACT DETAILS", y)
    e = data["emergency"]
    for row in [
        [("Full Name", e.get("Full Name"), (CONTENT_W / 3)), ("Relationship", e.get("Relationship"), (CONTENT_W / 3)), ("Occupation", e.get("Occupation"), (CONTENT_W / 3))],
        [("Phone Number", e.get("Phone Number"), (CONTENT_W / 3)), ("Email Address", e.get("Email Address"), (CONTENT_W / 3)), ("Address (Street/Village/House No.)", e.get("Address (Street/Village/House No.)"), (CONTENT_W / 3))],
    ]:
        y = draw_row(c, y, row, 15 * mm)
    y -= 6 * mm

    y = draw_section(c, "SECTION 4: EDUCATION BACKGROUND DETAILS", y)
    rows = [["Level", "School Name", "Index Number", "Year Completed", "Division / GPA"]]
    for item in data["education_background"]:
        rows.append([item.get("Level"), item.get("School Name"), item.get("Index Number"), item.get("Year Completed"), item.get("Division / GPA")])
    y = draw_table(c, LEFT, y, [CONTENT_W * 0.185, CONTENT_W * 0.345, CONTENT_W * 0.165, CONTENT_W * 0.15, CONTENT_W * 0.155], [10 * mm] + [16 * mm] * max(2, len(rows)-1), rows, font_size=8.8)
    end_page(c, data, page)

    # PAGE 3
    page = 3
    y = new_page(c, data, page)
    y = draw_section(c, "POST-SECONDARY / HIGHER EDUCATION", y)
    rows = [["Level", "Institution", "Field of Study", "Year Completed", "GPA"]]
    for item in data["higher_education"]:
        rows.append([item.get("Level"), item.get("Institution"), item.get("Field of Study"), item.get("Year Completed"), item.get("GPA")])
    y = draw_table(c, LEFT, y, [CONTENT_W * 0.165, CONTENT_W * 0.315, CONTENT_W * 0.26, CONTENT_W * 0.14, CONTENT_W * 0.12], [10 * mm] + [13.5 * mm] * 5, rows, font_size=8.4)
    y -= 5 * mm
    y = draw_section(c, "PROFESSIONAL QUALIFICATIONS / TRAINING", y)
    draw_label_value(c, LEFT, y, CONTENT_W, 21 * mm, "Professional Qualifications", data.get("professional_qualifications", MISSING), value_size=8.8)
    y -= 26 * mm
    y = draw_section(c, "ENGLISH LANGUAGE PROFICIENCY", y)
    ep = data["english_proficiency"]
    y = draw_table(c, LEFT, y, [CONTENT_W * 0.46, CONTENT_W * 0.27, CONTENT_W * 0.27], [10 * mm, 13 * mm], [["Test", "Score", "Year"], [ep.get("Test Name"), ep.get("Score"), ep.get("Year")]], font_size=8.8)
    y -= 5 * mm
    y = draw_section(c, "SECTION 5: EMPLOYMENT HISTORY / WORK EXPERIENCE", y)
    rows = [["Employer / Company Name", "Position / Job Title", "Location", "Period"]]
    emp = data.get("employment_history") or []
    if not emp:
        emp = [{"Employer / Company Name": "No work experience provided", "Position / Job Title": MISSING, "Location": MISSING, "Period": MISSING}]
    for item in emp[:4]:
        rows.append([item.get("Employer / Company Name"), item.get("Position / Job Title"), item.get("Location"), item.get("Period")])
    y = draw_table(c, LEFT, y, [CONTENT_W * 0.35, CONTENT_W * 0.25, CONTENT_W * 0.22, CONTENT_W * 0.18], [10 * mm] + [14 * mm] * (len(rows) - 1), rows, font_size=8.4)
    end_page(c, data, page)

    # PAGE 4
    page = 4
    y = new_page(c, data, page)
    y = draw_section(c, "SECTION 6: STUDY PREFERENCES", y)
    sp = data["study_preferences"]
    for row in [
        [("Preferred Country 1", sp.get("Preferred Country 1"), (CONTENT_W / 3)), ("Preferred Program 1", sp.get("Preferred Program 1"), (CONTENT_W / 3)), ("Preferred Country 2", sp.get("Preferred Country 2"), (CONTENT_W / 3))],
        [("Preferred Program 2", sp.get("Preferred Program 2"), (CONTENT_W / 3)), ("Preferred Country 3", sp.get("Preferred Country 3"), (CONTENT_W / 3)), ("Preferred Program 3", sp.get("Preferred Program 3"), (CONTENT_W / 3))],
    ]:
        y = draw_row(c, y, row, 15 * mm)
    y -= 5 * mm
    y = draw_section(c, "SECTION 7: CURRENT AND PERMANENT ADDRESS", y)
    ad = data["addresses"]
    address_keys = list(ad.keys())
    for i in range(0, len(address_keys), 2):
        k1 = address_keys[i]
        k2 = address_keys[i+1] if i+1 < len(address_keys) else ""
        y = draw_row(c, y, [(k1, ad.get(k1), (CONTENT_W / 2)), (k2, ad.get(k2), (CONTENT_W / 2))], 14 * mm)
    y -= 5 * mm
    y = draw_section(c, "SECTION 8: OTHER DETAILS", y)
    od = data["other_details"]
    od_keys = list(od.keys())
    for i in range(0, len(od_keys), 2):
        k1 = od_keys[i]
        k2 = od_keys[i+1] if i+1 < len(od_keys) else ""
        h = 13.2 * mm if i < 12 else 14.5 * mm
        y = draw_row(c, y, [(k1, od.get(k1), (CONTENT_W / 2)), (k2, od.get(k2), (CONTENT_W / 2))], h)
    end_page(c, data, page)

    # PAGE 5
    page = 5
    y = new_page(c, data, page)
    y = draw_section(c, "SECTION 9: HOW DID YOU HEAR ABOUT US?", y)
    hau = data["heard_about_us"]
    y = draw_row(c, y, [("Source", hau.get("Source"), (CONTENT_W / 2)), ("Other (please specify)", hau.get("Other (please specify)"), (CONTENT_W / 2))], 15 * mm)
    y -= 7 * mm
    y = draw_section(c, "SECTION 10: DECLARATION BY APPLICANT", y)
    for i, line in enumerate(DECLARATION_LINES, start=1):
        text = f"{i}. {line}"
        draw_wrapped(c, text, LEFT, y - 13 * mm, CONTENT_W, 12 * mm, FONT, 9.2, leading=10.2)
        y -= 13 * mm
    y -= 5 * mm
    dec = data["declaration"]
    for row in [
        [("Applicant Full Name", dec.get("Applicant Full Name"), (CONTENT_W / 2)), ("Date", dec.get("Date"), (CONTENT_W / 2))],
        [("Signature", dec.get("Signature") or "", (CONTENT_W / 2)), ("Declaration Agreed", dec.get("Declaration Agreed"), (CONTENT_W / 2))],
    ]:
        y = draw_row(c, y, row, 17 * mm)
    end_page(c, data, page)

    # PAGE 6
    page = 6
    y = new_page(c, data, page)
    y = draw_section(c, "TERMS AND CONDITIONS", y)
    for i, line in enumerate(TERMS_AND_CONDITIONS, start=1):
        text = f"{i}. {line}"
        draw_wrapped(c, text, LEFT, y - 15 * mm, CONTENT_W, 14 * mm, FONT, 9.2, leading=10.4)
        y -= 15 * mm
    end_page(c, data, page)

    c.save()



# ---------------------------------------------------------------------------
# Django integration helpers
# ---------------------------------------------------------------------------

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


def _bool_text(value: Any, default: str = MISSING) -> str:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _choice_text(obj: Any, field_name: str, default: str = MISSING) -> str:
    """Use Django's get_FIELD_display() when it exists, otherwise raw value."""
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
    return val(getattr(obj, field_name, default))


def _student_full_name(application: Any, supplemental_profile: Any = None) -> str:
    supplied = _safe_get(supplemental_profile, "full_name_passport")
    if supplied:
        return str(supplied)
    student = _safe_get(application, "student")
    full = _call_or_value(getattr(student, "get_full_name", None), "") if student else ""
    if full:
        return str(full)
    username = _safe_get(student, "username")
    return str(username or MISSING)


def _photo_source(student_profile: Any) -> str:
    """Return a filesystem path usable by ReportLab, when Django ImageField has one."""
    pic = _safe_get(student_profile, "profile_picture")
    if not pic:
        return ""
    try:
        # Try common attributes for ImageField-like objects.
        if hasattr(pic, 'path'):
            return pic.path
        if hasattr(pic, 'file') and hasattr(pic.file, 'name'):
            return pic.file.name
        if hasattr(pic, 'name'):
            return pic.name
    except Exception:
        return ""


def _get_work_experiences(student_profile: Any) -> List[Any]:
    if student_profile is None:
        return []
    manager = getattr(student_profile, "workexperience_set", None)
    if manager is None:
        return []
    try:
        return list(manager.all().order_by("-start_date")[:4])
    except Exception:
        try:
            return list(manager.all()[:4])
        except Exception:
            return []


def application_to_awec_csc_style_data(application: Any, student_profile: Any = None, supplemental_profile: Any = None) -> Dict[str, Any]:
    """
    Convert your existing Django Application, StudentProfile, and
    ApplicationSupplementalProfile objects into the dictionary used by the
    CSC-style AWEC renderer.
    """
    data = deepcopy(DEFAULT_DATA)
    student = _safe_get(application, "student")
    app_id = _safe_get(application, "id", "001")
    if _safe_get(supplemental_profile, "serial_number"):
        serial = str(_safe_get(supplemental_profile, "serial_number"))
    elif str(app_id).isdigit():
        serial = f"AWECO/Tz/DSM/{int(app_id):03d}"
    else:
        serial = f"AWECO/Tz/DSM/{app_id}"
    today = date.today()
    generated = _safe_get(supplemental_profile, "generated_at") or today
    generated_date = generated.strftime("%Y-%m-%d") if hasattr(generated, "strftime") else str(generated)
    application_date = _date_text(generated, today.strftime("%d/%m/%Y"))
    student_name = _student_full_name(application, supplemental_profile)

    data["meta"].update({
        "application_id": serial,
        "generated_date": generated_date,
        "application_date": application_date,
    })

    gender = _choice_text(student_profile, "gender", "")
    data["personal"] = {
        "Full Name (as in passport)": student_name,
        "Gender": gender,
        "Date of Birth": _date_text(_safe_get(student_profile, "date_of_birth")),
        "Place of Birth": val(_safe_get(supplemental_profile, "place_of_birth")),
        "Nationality": val(_safe_get(student_profile, "nationality")),
        "Email": val(_safe_get(student, "email")),
        "Phone Number": val(_safe_get(student_profile, "phone_number")),
        "Form Six School Name": val(_safe_get(student_profile, "alevel_school")),
        "Form Six School Address": val(_safe_get(student_profile, "alevel_address")),
        "Passport Number": val(_safe_get(supplemental_profile, "passport_number")),
        "Form Four School Name": val(_safe_get(student_profile, "olevel_school")),
        "Form Four School Address": val(_safe_get(student_profile, "olevel_address")),
        "Form Four Division / GPA": val(_safe_get(student_profile, "olevel_gpa")),
        "Application ID / Serial Number": serial,
        "Student Photo": _photo_source(student_profile),
    }

    data["parents"] = {
        "Father": {
            "Full Name": val(_safe_get(student_profile, "father_name")),
            "Address (Street/Village/House No.)": val(_safe_get(student_profile, "father_address")),
            "Postal Code": val(_safe_get(student_profile, "father_postal_code")),
            "Region": val(_safe_get(student_profile, "father_region")),
            "Occupation": val(_safe_get(student_profile, "father_occupation")),
            "Phone": val(_safe_get(student_profile, "father_phone")),
            "Email": val(_safe_get(student_profile, "father_email")),
        },
        "Mother": {
            "Full Name": val(_safe_get(student_profile, "mother_name")),
            "Address (Street/Village/House No.)": val(_safe_get(student_profile, "mother_address")),
            "Postal Code": val(_safe_get(student_profile, "mother_postal_code")),
            "Region": val(_safe_get(student_profile, "mother_region")),
            "Occupation": val(_safe_get(student_profile, "mother_occupation")),
            "Phone": val(_safe_get(student_profile, "mother_phone")),
            "Email": val(_safe_get(student_profile, "mother_email")),
        },
    }

    data["emergency"] = {
        "Full Name": val(_safe_get(student_profile, "emergency_contact")),
        "Relationship": val(_safe_get(student_profile, "emergency_relation")),
        "Occupation": val(_safe_get(student_profile, "emergency_occupation")),
        "Phone Number": val(_safe_get(student_profile, "phone_number")),
        "Email Address": val(_safe_get(student, "email")),
        "Address (Street/Village/House No.)": val(_safe_get(student_profile, "emergency_address")),
    }

    data["education_background"] = [
        {
            "Level": "Form Four (O-Level)",
            "School Name": val(_safe_get(student_profile, "olevel_school")),
            "Index Number": val(_safe_get(student_profile, "olevel_candidate_no")),
            "Year Completed": _year_text(_safe_get(student_profile, "olevel_year")),
            "Division / GPA": val(_safe_get(student_profile, "olevel_gpa")),
        },
        {
            "Level": "Form Six (A-Level)",
            "School Name": val(_safe_get(student_profile, "alevel_school")),
            "Index Number": val(_safe_get(student_profile, "alevel_candidate_no")),
            "Year Completed": _year_text(_safe_get(student_profile, "alevel_year")),
            "Division / GPA": val(_safe_get(student_profile, "alevel_gpa")),
        },
    ]

    data["higher_education"] = []
    for label, prefix in [
        ("Certificate", "certificate"),
        ("Diploma", "diploma"),
        ("Bachelor Degree", "bachelor"),
        ("Master Degree", "master"),
        ("PhD", "phd"),
    ]:
        data["higher_education"].append({
            "Level": label,
            "Institution": val(_safe_get(supplemental_profile, f"{prefix}_institution")),
            "Field of Study": val(_safe_get(supplemental_profile, f"{prefix}_field_of_study")),
            "Year Completed": _year_text(_safe_get(supplemental_profile, f"{prefix}_year_completed")),
            "GPA": val(_safe_get(supplemental_profile, f"{prefix}_gpa")),
        })

    data["professional_qualifications"] = val(_safe_get(supplemental_profile, "professional_qualifications"))
    data["english_proficiency"] = {
        "Test Name": val(_safe_get(supplemental_profile, "english_test_name")),
        "Score": val(_safe_get(supplemental_profile, "english_test_score")),
        "Year": _year_text(_safe_get(supplemental_profile, "english_test_year")),
    }

    work_rows = []
    for exp in _get_work_experiences(student_profile):
        end = "Present" if _safe_get(exp, "currently_working") else _date_text(_safe_get(exp, "end_date"))
        period = f"{_date_text(_safe_get(exp, 'start_date'))} - {end}"
        work_rows.append({
            "Employer / Company Name": val(_safe_get(exp, "company_name")),
            "Position / Job Title": val(_safe_get(exp, "position")),
            "Location": val(_safe_get(exp, "location")),
            "Period": period,
        })
    data["employment_history"] = work_rows

    data["study_preferences"] = {
        "Preferred Country 1": val(_safe_get(student_profile, "preferred_country_1")),
        "Preferred Program 1": val(_safe_get(student_profile, "preferred_program_1")),
        "Preferred Country 2": val(_safe_get(student_profile, "preferred_country_2")),
        "Preferred Program 2": val(_safe_get(student_profile, "preferred_program_2")),
        "Preferred Country 3": val(_safe_get(student_profile, "preferred_country_3")),
        "Preferred Program 3": val(_safe_get(student_profile, "preferred_program_3")),
    }

    data["addresses"] = {
        "Current Address (Street/Village/House No.)": val(_safe_get(supplemental_profile, "current_address") or _safe_get(student_profile, "address")),
        "Current Region": val(_safe_get(supplemental_profile, "current_region")),
        "Current City": val(_safe_get(supplemental_profile, "current_city")),
        "Current Country": val(_safe_get(supplemental_profile, "current_country")),
        "Current Postal Code": val(_safe_get(supplemental_profile, "current_postal_code")),
        "Permanent Address (Street/Village/House No.)": val(_safe_get(student_profile, "address")),
        "Permanent Region": val(_safe_get(supplemental_profile, "permanent_region")),
        "Permanent City": val(_safe_get(supplemental_profile, "permanent_city")),
        "Permanent Country": val(_safe_get(student_profile, "nationality")),
        "Permanent Postal Code": val(_safe_get(supplemental_profile, "permanent_postal_code")),
    }

    data["other_details"] = {
        "Passport Number": val(_safe_get(supplemental_profile, "passport_number")),
        "Country of Issue": val(_safe_get(supplemental_profile, "passport_issue_country")),
        "Date of Issue": _date_text(_safe_get(supplemental_profile, "passport_issue_date")),
        "Expiry Date": _date_text(_safe_get(supplemental_profile, "passport_expiration_date")),
        "Valid Visa?": _bool_text(_safe_get(supplemental_profile, "has_valid_visa")),
        "Visa Details (if applicable)": val(_safe_get(supplemental_profile, "valid_visa_details")),
        "Program Level": _choice_text(supplemental_profile, "program_level"),
        "Preferred Intake": _choice_text(supplemental_profile, "preferred_intake"),
        "Accommodation Preference": _choice_text(supplemental_profile, "accommodation_preference"),
        "Sponsor of Education": val(_safe_get(supplemental_profile, "education_sponsor")),
        "Estimated Budget (USD)": _money_text(_safe_get(supplemental_profile, "estimated_budget_usd")),
        "Scholarship Applied?": _bool_text(_safe_get(supplemental_profile, "scholarship_applied")),
        "Scholarship Details (if applicable)": val(_safe_get(supplemental_profile, "scholarship_details")),
        "Any Medical Condition?": _bool_text(_safe_get(supplemental_profile, "has_medical_condition")),
        "Medical Condition Details (if applicable)": val(_safe_get(supplemental_profile, "medical_condition_details")),
        "Special Assistance Required?": _bool_text(_safe_get(supplemental_profile, "needs_special_assistance")),
        "Special Assistance Details (if applicable)": val(_safe_get(supplemental_profile, "special_assistance_details")),
    }

    data["heard_about_us"] = {
        "Source": _choice_text(student_profile, "heard_about_us"),
        "Other (please specify)": val(_safe_get(student_profile, "heard_about_other")),
    }
    data["declaration"] = {
        "Applicant Full Name": student_name,
        "Date": today.strftime("%d/%m/%Y"),
        "Signature": "",
        "Declaration Agreed": _bool_text(_safe_get(supplemental_profile, "declaration_agreed"), "Yes"),
    }
    return data


def build_awec_csc_style_application_pdf_response(application: Any, student_profile: Any = None, supplemental_profile: Any = None):
    """
    Django-ready PDF response. Put this file in your app, then call this function
    from a Django view after fetching the Application object.
    """
    from io import BytesIO
    from django.http import HttpResponse

    data = application_to_awec_csc_style_data(application, student_profile, supplemental_profile)
    buffer = BytesIO()
    generate_pdf(buffer, data)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    student_name = data["personal"].get("Full Name (as in passport)", "student").replace(" ", "_")
    filename = f"{student_name}_application_form.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# Example Django view usage:
#
# from django.shortcuts import get_object_or_404
# from .models import Application
# from .pdf_exports_csc_style import build_awec_csc_style_application_pdf_response
#
# def export_student_application_pdf(request, application_id):
#     application = get_object_or_404(Application, id=application_id)
#     student_profile = getattr(application, "student_profile", None) or getattr(application.student, "studentprofile", None)
#     supplemental_profile = getattr(application, "supplemental_profile", None) or getattr(application, "applicationsupplementalprofile", None)
#     return build_awec_csc_style_application_pdf_response(application, student_profile, supplemental_profile)
