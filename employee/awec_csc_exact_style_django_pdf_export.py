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
from io import BytesIO
import json
import math
import logging
import textwrap
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

try:
    from PIL import Image as PILImage
except Exception:  # pragma: no cover
    PILImage = None

logger = logging.getLogger(__name__)

PAGE_W, PAGE_H = A4
TOTAL_PAGES = 7
MISSING = "-"

BLUE = colors.HexColor("#0066B3")
BLACK = colors.black
LIGHT_GRAY = colors.white

LEFT = 12 * mm
RIGHT = PAGE_W - 12 * mm
TOP = PAGE_H - 10 * mm
BOTTOM = 18 * mm
CONTENT_W = RIGHT - LEFT

def _register_professional_fonts() -> Tuple[str, str, str]:
    """Register a clean professional Unicode font when available.

    DejaVu Sans is used first because it renders check marks and international
    characters reliably. The code falls back to built-in Helvetica fonts when
    the DejaVu font files are not available on the server.
    """
    candidates = [
        (
            "DejaVuSans",
            "DejaVuSans-Bold",
            "DejaVuSans-BoldOblique",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
        ),
        (
            "Arial",
            "Arial-Bold",
            "Arial-BoldItalic",
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/arialbi.ttf"),
        ),
    ]
    for regular_name, bold_name, italic_name, regular_path, bold_path, italic_path in candidates:
        if regular_path.exists() and bold_path.exists() and italic_path.exists():
            try:
                pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
                pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
                pdfmetrics.registerFont(TTFont(italic_name, str(italic_path)))
                return regular_name, bold_name, italic_name
            except Exception:
                pass
    return "Helvetica", "Helvetica-Bold", "Helvetica-BoldOblique"


FONT, FONT_BOLD, FONT_ITALIC = _register_professional_fonts()

# Professional vertical spacing used before every new section heading.
# This prevents section titles from sitting too close to the previous block.
SECTION_TOP_GAP = 5.5 * mm
SECTION_AFTER_TITLE_GAP = 5.0 * mm

# MOFCOM/CSC-style field rhythm. Every answer field is drawn as its own
# bordered box with a small gutter around it, instead of one large block
# subdivided by internal lines.
# Tighter cell spacing. This removes the oversized empty look while keeping the form readable.
CELL_X_GAP = 0.75 * mm
CELL_Y_GAP = 0.55 * mm
CELL_BORDER_WIDTH = 0.85

def resolve_static_asset(relative_path: str) -> Path:
    """Resolve a Django static asset to a real filesystem path.

    Works in normal Django runs, management commands, and standalone script runs.
    The stamp file requested by the project is:
    static/global_agency/image/signature-removebg.png
    """
    normalized = relative_path.replace("\\", "/").lstrip("/")

    # Best option in Django: ask staticfiles where the file is.
    try:
        from django.contrib.staticfiles import finders  # type: ignore

        found = finders.find(normalized)
        if found:
            return Path(found)
    except Exception:
        pass

    candidates: List[Path] = []

    # Django settings.BASE_DIR / STATIC_ROOT support.
    try:
        from django.conf import settings  # type: ignore

        base_dir = getattr(settings, "BASE_DIR", None)
        if base_dir:
            candidates.append(Path(base_dir) / "static" / normalized)

        static_root = getattr(settings, "STATIC_ROOT", None)
        if static_root:
            candidates.append(Path(static_root) / normalized)
    except Exception:
        pass

    # Existing project-relative behavior.
    candidates.extend([
        Path(__file__).resolve().parent.parent / "static" / normalized,
        Path(__file__).resolve().parent / "static" / normalized,
        Path.cwd() / "static" / normalized,
        Path("C:/Users/WINDOWS 11/Documents/Projects/Global-agency/static") / normalized,
    ])

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Return the first Django-style location even if missing, so logs show the expected path.
    return candidates[0] if candidates else Path(normalized)


LOGO_PATH = resolve_static_asset("global_agency/img/logo.png")
STAMP_PATH = resolve_static_asset("global_agency/image/signature-removebg.png")
SIGNATURE_PATH = resolve_static_asset("global_agency/image/signature-pazza-removebg-preview.png")

# International passport-style student photo size used on the form.
# 35 mm x 45 mm is a widely accepted passport/ID portrait size.
PASSPORT_PHOTO_W = 35 * mm
PASSPORT_PHOTO_H = 45 * mm
PHOTO_INNER_PADDING = 2 * mm

DEFAULT_DATA: Dict[str, Any] = {
    "organization": {
        "name": "",
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
        "form_title": "LOCAL AND ABROAD UNIVERSITIES SEAT RESERVATION PORTFOLIO/ PROFILE FORM.",
        "application_id": "AWECO/INT/REG/TZ/DSM/20268001",
        "generated_date": date.today().strftime("%Y-%m-%d"),
        "application_date": date.today().strftime("%d/%m/%Y"),
    },
    "personal": {
        "Full Name (as in passport)": "Amina Grace Mwandu",
        "Gender": "Female",
        "Date of Birth": "14/03/2003",
        "Place of Birth": "Mwanza, Tanzania",
        "Nationality": "Tanzanian",
        "Native Language": "Swahili",
        "Marital Status": "Single",
        "City": "Dar es Salaam",
        "Region": "Dar es Salaam",
        "Ward": "Mbezi Beach",
        "Village": "Mbezi Beach",
        "Street": "Mbezi Beach Street",
        "House Number": "House 18",
        "Email": "amina.mwandu@example.com",
        "Phone Number": "+255 712 345 678",
        "Passport Number": "TZA123456",
        "Passport Issued Date": "01/01/2024",
        "Passport Expired Date": "01/01/2034",
        "Application ID / Serial Number": "AWECO/INT/REG/TZ/DSM/20268001",
        "Student Photo": "",
    },
    "parents": {
        "Father": {
            "Full Name": "Joseph Mwandu",
            "Occupation": "Accountant",
            "Phone": "+255 754 111 222",
            "Email": "joseph.mwandu@example.com",
            "Country": "Tanzania",
            "Region": "Dar es Salaam",
            "Region Post Code": "14100",
            "District": "Kinondoni",
            "District Post Code": "14128",
            "Ward": "Mbezi Beach",
            "Ward Post Code": "14128",
            "Street": "Mbezi Beach Street",
            "Place / Neighbourhood": "Mbezi Beach",
            "House No.": "House 18",
        },
        "Mother": {
            "Full Name": "Neema Mwandu",
            "Occupation": "Teacher",
            "Phone": "+255 755 333 444",
            "Email": "neema.mwandu@example.com",
            "Country": "Tanzania",
            "Region": "Dar es Salaam",
            "Region Post Code": "14100",
            "District": "Kinondoni",
            "District Post Code": "14128",
            "Ward": "Mbezi Beach",
            "Ward Post Code": "14128",
            "Street": "Mbezi Beach Street",
            "Place / Neighbourhood": "Mbezi Beach",
            "House No.": "House 18",
        },
    },
    "emergency": {
        "Full Name": "Daniel Komba",
        "Relationship": "Uncle",
        "Occupation": "Medical Officer",
        "Phone Number": "+255 765 777 888",
        "Email Address": "daniel.komba@example.com",
        "Country": "Tanzania",
        "Region": "Dar es Salaam",
        "Region Post Code": "14100",
        "District": "Kinondoni",
        "District Post Code": "14128",
        "Ward": "Kinondoni",
        "Ward Post Code": "14128",
        "Street": "Kinondoni Street",
        "Place / Neighbourhood": "Kinondoni",
        "House No.": "House 22",
    },
    "education_background": [
        {
            "Level": "Ordinary Level (O-Level)",
            "School Name": "Mlimani Secondary School",
            "Index Number": "S0123/0456",
            "Start Year": "2017",
            "Completed Year": "2020",
            "Division": "Division I",
            "Country": "Tanzania",
            "Region": "Morogoro",
            "Region Post Code": "67000",
            "District": "Morogoro Urban",
            "District Post Code": "67100",
            "Ward": "Mlimani",
            "Ward Post Code": "67101",
            "Street": "Mlimani Road",
            "Place / Neighbourhood": "Mlimani",
        },
        {
            "Level": "Advanced Level (A-Level)",
            "School Name": "Jangwani Secondary School",
            "Index Number": "S0456/0789",
            "Start Year": "2021",
            "Completed Year": "2023",
            "Division": "Division II",
            "Country": "Tanzania",
            "Region": "Dar es Salaam",
            "Region Post Code": "11100",
            "District": "Ilala",
            "District Post Code": "11101",
            "Ward": "Jangwani",
            "Ward Post Code": "11102",
            "Street": "Jangwani Street",
            "Place / Neighbourhood": "Jangwani",
        },
    ],
    "higher_education": [
        {"Level": "Certificate", "Institution": "Dar Training Centre", "Field of Study": "Computer Applications", "Start Year": "2021", "Completed Year": "2021", "GPA": "A"},
        {"Level": "Diploma", "Institution": "-", "Field of Study": "-", "Start Year": "-", "Completed Year": "-", "GPA": "-"},
        {"Level": "Bachelor Degree", "Institution": "-", "Field of Study": "-", "Start Year": "-", "Completed Year": "-", "GPA": "-"},
        {"Level": "Master Degree", "Institution": "-", "Field of Study": "-", "Start Year": "-", "Completed Year": "-", "GPA": "-"},
        {"Level": "PhD", "Institution": "-", "Field of Study": "-", "Start Year": "-", "Completed Year": "-", "GPA": "-"},
    ],
    "professional_qualifications": [
        {
            "Qualification Title": "Academic Writing Short Course",
            "Institution": "Dar Training Centre",
            "Institution Address": "Mpakani Centre, Kijitonyama",
            "Country": "Tanzania",
            "Period": "2 Months",
            "Start Date": "01/03/2024",
            "Finished Date": "30/04/2024",
            "Award / Certificate?": "Yes",
        },
        {
            "Qualification Title": "-",
            "Institution": "-",
            "Institution Address": "-",
            "Country": "-",
            "Period": "-",
            "Start Date": "-",
            "Finished Date": "-",
            "Award / Certificate?": "-",
        },
        {
            "Qualification Title": "-",
            "Institution": "-",
            "Institution Address": "-",
            "Country": "-",
            "Period": "-",
            "Start Date": "-",
            "Finished Date": "-",
            "Award / Certificate?": "-",
        },
    ],
    "english_proficiency": {
        "Test Name": "IELTS",
        "Institution": "British Council",
        "Score": "6.5",
        "Year": "2024",
        "English is Primary Language?": "No",
    },
    "employment_history": [
        {
            "Employer / Company Name": "Bright Future Academy",
            "Position / Job Title": "Assistant Teacher",
            "Start Date": "01/01/2024",
            "End Date": "Present",
            "Country": "Tanzania",
            "Region": "Dar es Salaam",
            "Region Post Code": "14100",
            "District": "Kinondoni",
            "District Post Code": "14128",
            "Ward": "Mikocheni",
            "Ward Post Code": "14112",
            "Street": "Mikocheni Street",
            "Place / Neighbourhood": "Mikocheni",
            "House No.": "-",
        },
        {
            "Employer / Company Name": "Community Youth Centre",
            "Position / Job Title": "Volunteer Tutor",
            "Start Date": "01/06/2022",
            "End Date": "30/11/2022",
            "Country": "Tanzania",
            "Region": "Mwanza",
            "Region Post Code": "33100",
            "District": "Nyamagana",
            "District Post Code": "33101",
            "Ward": "Nyamagana",
            "Ward Post Code": "33102",
            "Street": "Nyamagana Street",
            "Place / Neighbourhood": "Nyamagana",
            "House No.": "-",
        },
    ],
    "study_preferences": {
        "Preferred Intake": "September 2026",
        "Preferred Country 1": "China", "Preferred Program 1": "Bachelor of Business Administration",
        "Preferred Country 2": "Malaysia", "Preferred Program 2": "Bachelor of International Business",
        "Preferred Country 3": "Turkey", "Preferred Program 3": "Bachelor of Economics",
    },
    "addresses": {
        "Current Country": "Tanzania",
        "Current Region": "Dar es Salaam",
        "Current Region Post Code": "14100",
        "Current District": "Kinondoni",
        "Current District Post Code": "14128",
        "Current Ward": "Mbezi Beach",
        "Current Ward Post Code": "14128",
        "Current Street": "Mbezi Beach Street",
        "Current Place / Neighbourhood": "Mbezi Beach",
        "Current House No.": "House 18",
        "Permanent Country": "Tanzania",
        "Permanent Region": "Mwanza",
        "Permanent Region Post Code": "33100",
        "Permanent District": "Nyamagana",
        "Permanent District Post Code": "33101",
        "Permanent Ward": "Nyamagana",
        "Permanent Ward Post Code": "33102",
        "Permanent Street": "Nyamagana Street",
        "Permanent Place / Neighbourhood": "Nyamagana District",
        "Permanent House No.": "-",
    },
    "other_details": {
        "Valid Visa?": "No",
        "Visa Details (if applicable)": "-",
        "Program Level": "Bachelor Degree",
        "Accommodation Preference": "University Dormitory",
        "Sponsor of Education": "Parents",
        "Estimated Budget (USD)": "8500.00",
        "Scholarship Applied?": "Yes",
        "Scholarship Details (if applicable)": "University merit scholarship under consideration",
        "Any Medical Condition?": "No",
        "Medical Condition Details (if applicable)": "-",
        "Special Assistance Required?": "No",
        "Special Assistance Details (if applicable)": "-",
    },
    "heard_about_us": {"Source": "Friend / Referral", "Other (please specify)": "-"},
    "declaration": {
        "Applicant Full Name": "Amina Grace Mwandu", "Date": date.today().strftime("%d/%m/%Y"), "Signature": "", "Declaration Agreed": "Yes",
    },
    "documents": [],
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


def display_value_upper(value: Any) -> str:
    """Render user-entered values in uppercase while preserving the missing dash."""
    text = val(value)
    if text == MISSING:
        return MISSING
    return text.upper()


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


def draw_label_value(c: canvas.Canvas, x: float, y_top: float, w: float, h: float, label: str, value: Any, label_size: float = 8.9, value_size: float = 10.2) -> None:
    """Draw one independent bordered field cell.

    This matches the MOFCOM/CSC visual style: each item has its own border
    and small spacing from neighbouring cells, instead of a single huge table
    with internal subdivisions.
    """
    y = y_top - h
    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    c.rect(x, y, w, h, stroke=1, fill=0)

    pad = 2.0
    c.setFont(FONT, label_size)
    c.setFillColor(BLACK)
    if label:
        c.drawString(x + pad, y + h - label_size - 2.0, label)
        value_area_h = h - label_size - 3.8
    else:
        value_area_h = h - 4.0

    draw_wrapped(c, display_value_upper(value), x + pad, y + 2.0, w - 2 * pad, value_area_h, FONT_BOLD, value_size)


def _scaled_cell_widths(widths: Sequence[float], gap: float) -> List[float]:
    """Shrink widths proportionally so column gaps stay inside the same row width."""
    if not widths:
        return []
    total = float(sum(widths))
    total_gap = gap * max(0, len(widths) - 1)
    if total <= 0 or total <= total_gap:
        return list(widths)
    usable = total - total_gap
    return [w * usable / total for w in widths]


def draw_row(c: canvas.Canvas, y_top: float, cells: Sequence[Tuple[str, Any, float]], h: float = 15 * mm) -> float:
    """Draw a row as separated, individually bordered cells."""
    if not cells:
        return y_top
    widths = _scaled_cell_widths([cell[2] for cell in cells], CELL_X_GAP)
    x = LEFT
    for (label, value, _original_width), width in zip(cells, widths):
        draw_label_value(c, x, y_top, width, h, label, value)
        x += width + CELL_X_GAP
    return y_top - h - CELL_Y_GAP


def draw_cells_at(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    total_w: float,
    cells: Sequence[Tuple[str, Any, float]],
    h: float,
    label_size: float = 7.6,
    value_size: float = 8.6,
) -> float:
    """Draw separated cells inside a custom-width area.

    The third value in each cell is treated as a relative width. The widths are
    scaled to the available area, leaving the same MOFCOM-style gutter between
    cells. This lets compact values such as post codes and house numbers use
    smaller cells while names and emails get wider cells.
    """
    if not cells:
        return y_top
    raw_widths = [cell[2] for cell in cells]
    total_raw = float(sum(raw_widths)) or 1.0
    usable_w = total_w - CELL_X_GAP * max(0, len(cells) - 1)
    widths = [usable_w * w / total_raw for w in raw_widths]
    cx = x
    for (label, value, _), width in zip(cells, widths):
        draw_label_value(c, cx, y_top, width, h, label, value, label_size=label_size, value_size=value_size)
        cx += width + CELL_X_GAP
    return y_top - h - CELL_Y_GAP


def draw_parent_side_panel(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    panel_w: float,
    title: str,
    parent_data: Dict[str, Any],
) -> float:
    """Draw one compact parent panel with reduced height and better split spaces."""
    y = y_top

    # Compact sizing: these are the values that remove the large blank spaces.
    title_h = 6.0 * mm
    row_h = 8.8 * mm
    compact_h = 7.9 * mm

    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    c.rect(x, y - title_h, panel_w, title_h, stroke=1, fill=0)
    c.setFont(FONT_BOLD, 8.8)
    c.setFillColor(BLACK)
    c.drawCentredString(x + panel_w / 2, y - title_h + 1.8 * mm, title.upper())
    y -= title_h + CELL_Y_GAP

    # The large empty areas are divided into smaller practical fields.
    rows = [
        ([
            ("Full Name", parent_data.get("Full Name"), 58),
            ("Occupation", parent_data.get("Occupation"), 42),
        ], row_h),
        ([
            ("Phone", parent_data.get("Phone"), 42),
            ("Email", parent_data.get("Email"), 58),
        ], row_h),
        ([
            ("Country", parent_data.get("Country"), 30),
            ("Region", parent_data.get("Region"), 36),
            ("Region Post Code", parent_data.get("Region Post Code"), 34),
        ], compact_h),
        ([
            ("District", parent_data.get("District"), 34),
            ("District Post Code", parent_data.get("District Post Code"), 34),
            ("Ward", parent_data.get("Ward"), 32),
        ], compact_h),
        ([
            ("Ward Post Code", parent_data.get("Ward Post Code"), 32),
            ("Street", parent_data.get("Street"), 38),
            ("House No.", parent_data.get("House No."), 30),
        ], compact_h),
        ([
            ("Place / Neighbourhood", parent_data.get("Place / Neighbourhood"), 45),
            ("Status", parent_data.get("Status") or parent_data.get("Parent Status"), 25),
            ("Relationship", parent_data.get("Relationship"), 30),
        ], compact_h),
    ]

    for row, height in rows:
        y = draw_cells_at(
            c,
            x,
            y,
            panel_w,
            row,
            height,
            label_size=6.55,
            value_size=7.55,
        )
    return y


def parents_side_by_side_height() -> float:
    """Exact height of the compact side-by-side parent panels."""
    return (
        6.0 * mm
        + CELL_Y_GAP
        + (2 * (8.8 * mm + CELL_Y_GAP))
        + (4 * (7.9 * mm + CELL_Y_GAP))
        + 2.5 * mm
    )


def draw_parents_side_by_side_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    father: Dict[str, Any],
    mother: Dict[str, Any],
) -> Tuple[int, float]:
    """Draw Mother on the left and Father on the right with compact spacing."""
    block_h = parents_side_by_side_height()
    page_no, y = ensure_flow_space(c, data, page_no, y, block_h)

    panel_gap = 2.4 * mm
    panel_w = (CONTENT_W - panel_gap) / 2
    left_x = LEFT
    right_x = LEFT + panel_w + panel_gap

    y_mother = draw_parent_side_panel(c, left_x, y, panel_w, "Mother's Details", mother)
    y_father = draw_parent_side_panel(c, right_x, y, panel_w, "Father's Details", father)
    return page_no, min(y_mother, y_father) - 2.8 * mm

ADDRESS_LABELS = [
    "Country",
    "Region",
    "Region Post Code",
    "District",
    "District Post Code",
    "Ward",
    "Ward Post Code",
    "Street",
    "Place / Neighbourhood",
    "House No.",
]


def draw_address_hierarchy_rows(
    c: canvas.Canvas,
    y: float,
    source: Dict[str, Any],
    h: float = 11.8 * mm,
    prefix: str = "",
) -> float:
    """Draw Tanzania address hierarchy as separate professional fields."""
    def g(name: str) -> Any:
        return source.get(f"{prefix}{name}") if prefix else source.get(name)

    rows = [
        [
            ("Country", g("Country"), CONTENT_W / 3),
            ("Region", g("Region"), CONTENT_W / 3),
            ("Region Post Code", g("Region Post Code"), CONTENT_W / 3),
        ],
        [
            ("District", g("District"), CONTENT_W / 3),
            ("District Post Code", g("District Post Code"), CONTENT_W / 3),
            ("Ward", g("Ward"), CONTENT_W / 3),
        ],
        [
            ("Ward Post Code", g("Ward Post Code"), CONTENT_W / 3),
            ("Street", g("Street"), CONTENT_W / 3),
            ("Place / Neighbourhood", g("Place / Neighbourhood"), CONTENT_W / 3),
        ],
        [
            ("House No.", g("House No."), CONTENT_W / 3),
            ("", "", CONTENT_W / 3),
            ("", "", CONTENT_W / 3),
        ],
    ]
    for row in rows:
        y = draw_row(c, y, row, h)
    return y


def draw_named_address_block(c: canvas.Canvas, y: float, title: str, source: Dict[str, Any], prefix: str = "") -> float:
    c.setFont(FONT_BOLD, 10.2)
    c.setFillColor(BLACK)
    c.drawString(LEFT, y, title)
    y -= 4.0 * mm
    y = draw_address_hierarchy_rows(c, y, source, 11.4 * mm, prefix=prefix)
    return y - 4.2 * mm


def draw_education_school_block(c: canvas.Canvas, y: float, school_data: Dict[str, Any]) -> float:
    c.setFont(FONT_BOLD, 10.6)
    c.setFillColor(BLACK)
    c.drawString(LEFT, y, val(school_data.get("Level")))
    y -= 4.5 * mm

    row_h = 11.8 * mm
    rows = [
        [
            ("School Name", school_data.get("School Name"), CONTENT_W * 0.58),
            ("Index Number", school_data.get("Index Number"), CONTENT_W * 0.42),
        ],
        [
            ("Starting Year", school_data.get("Start Year"), CONTENT_W / 3),
            ("Completed Year", school_data.get("Completed Year"), CONTENT_W / 3),
            ("Division", school_data.get("Division"), CONTENT_W / 3),
        ],
    ]
    for row in rows:
        y = draw_row(c, y, row, row_h)

    y = draw_address_hierarchy_rows(c, y, school_data, row_h)
    return y - 5 * mm




def draw_parent_details_block(
    c: canvas.Canvas,
    y: float,
    parent_title: str,
    parent_data: Dict[str, Any],
) -> float:
    """
    Draw one parent's information in its own separated segmented block,
    including the full Tanzania address hierarchy.
    """
    c.setFont(FONT_BOLD, 10.8)
    c.setFillColor(BLACK)
    c.drawString(LEFT, y, parent_title)
    y -= 4.8 * mm

    row_h = 12.2 * mm

    for row in [
        [
            ("Full Name", parent_data.get("Full Name"), CONTENT_W / 2),
            ("Occupation", parent_data.get("Occupation"), CONTENT_W / 2),
        ],
        [
            ("Phone", parent_data.get("Phone"), CONTENT_W / 2),
            ("Email", parent_data.get("Email"), CONTENT_W / 2),
        ],
    ]:
        y = draw_row(c, y, row, row_h)

    y = draw_address_hierarchy_rows(c, y, parent_data, 11.4 * mm)
    return y - 5.5 * mm


def draw_section(c: canvas.Canvas, title: str, y: float) -> float:
    """Draw a centered black bold section heading with no underline."""
    y -= SECTION_TOP_GAP
    c.setFont(FONT_BOLD, 12.4)
    c.setFillColor(BLACK)
    c.drawCentredString(PAGE_W / 2, y, title.upper())
    return y - SECTION_AFTER_TITLE_GAP


def draw_table(c: canvas.Canvas, x: float, y_top: float, col_widths: Sequence[float], row_heights: Sequence[float], rows: Sequence[Sequence[Any]], header_rows: int = 1, font_size: float = 9.6) -> float:
    """Draw a table using separated MOFCOM/CSC-style cells."""
    y = y_top
    c.setLineWidth(CELL_BORDER_WIDTH)
    scaled_widths = _scaled_cell_widths(col_widths, CELL_X_GAP)

    for r, row in enumerate(rows):
        h = row_heights[r] if r < len(row_heights) else row_heights[-1]
        y -= h
        cx = x
        for col, width in enumerate(scaled_widths):
            c.setStrokeColor(BLACK)
            if r < header_rows:
                c.setFillColor(LIGHT_GRAY)
                c.rect(cx, y, width, h, stroke=1, fill=1)
            else:
                c.rect(cx, y, width, h, stroke=1, fill=0)
            text = row[col] if col < len(row) else ""
            if r >= header_rows:
                text = display_value_upper(text)
            draw_wrapped(c, text, cx + 2.2, y + 2.2, width - 4.4, h - 4.4, FONT_BOLD, font_size)
            cx += width + CELL_X_GAP
        y -= CELL_Y_GAP
    return y


def draw_header(c: canvas.Canvas, data: Dict[str, Any], page_no: int) -> float:
    """Header built to match the CSC form rhythm: left seal, centered agency text, no top-right table."""
    org = data["organization"]
    y = TOP

    def draw_logo_at(center_x: float, center_y: float, size: float = 29 * mm) -> None:
        if LOGO_PATH.exists() and PILImage:
            try:
                img = PILImage.open(LOGO_PATH)
                img.close()
                c.drawImage(str(LOGO_PATH), center_x - size / 2, center_y - size / 2, size, size, preserveAspectRatio=True, mask="auto")
                return
            except Exception:
                pass
        c.setStrokeColor(BLUE)
        c.setLineWidth(1.0)
        c.circle(center_x, center_y, 14.5 * mm, stroke=1, fill=0)
        c.setFont(FONT_BOLD, 15.0)
        c.setFillColor(BLUE)
        c.drawCentredString(center_x, center_y - 3.8, "AWEC")

    if page_no == 1:
        cy = y - 23 * mm
        left_x = LEFT + 15.5 * mm
        right_x = RIGHT - 15.5 * mm
        # Put the same logo on both sides of the header for a balanced layout.
        draw_logo_at(left_x, cy)
        draw_logo_at(right_x, cy)

        c.setFillColor(BLACK)
        c.setFont(FONT_BOLD, 12.0)
        c.drawCentredString(PAGE_W / 2, y - 14 * mm, org["legal_name"])
        c.setFont(FONT, 8.4)
        c.drawCentredString(PAGE_W / 2, y - 19 * mm, ", ".join(org["address_lines"][:3]))
        c.drawCentredString(PAGE_W / 2, y - 23 * mm, ", ".join(org["address_lines"][3:]))
        c.drawCentredString(PAGE_W / 2, y - 27 * mm, f"Tel: {org['telephone']}    E-mail: {org['email']}")
        c.drawCentredString(PAGE_W / 2, y - 31 * mm, f"Website: {org['website']}")
        return y - 47 * mm
    return TOP - 12 * mm

def draw_footer(c: canvas.Canvas, data: Dict[str, Any], page_no: int) -> None:
    meta = data["meta"]
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.8)
    c.line(LEFT, 16 * mm, RIGHT, 16 * mm)
    c.setFont(FONT, 9)
    c.setFillColor(BLACK)
    c.drawString(LEFT + 2 * mm, 8 * mm, f"Application ID: {meta.get('application_id', MISSING)}")
    c.drawCentredString(PAGE_W / 2, 8 * mm, f"Page {page_no}")
    c.drawRightString(RIGHT - 2 * mm, 8 * mm, f"Generated: {meta.get('generated_date', MISSING)}")


def new_page(c: canvas.Canvas, data: Dict[str, Any], page_no: int) -> float:
    if page_no > 1:
        c.showPage()
    y = draw_header(c, data, page_no)
    return y


def end_page(c: canvas.Canvas, data: Dict[str, Any], page_no: int) -> None:
    draw_footer(c, data, page_no)


def draw_title(c: canvas.Canvas, data: Dict[str, Any], y: float) -> float:
    """Draw the main form title with automatic fitting for long titles."""
    title = str(data["meta"].get("form_title", MISSING)).upper()
    max_w = CONTENT_W - 6 * mm

    # Start strong, then reduce just enough so the new long title stays on one clean line.
    title_size = 13.2
    while title_size > 8.6 and stringWidth(title, FONT_BOLD, title_size) > max_w:
        title_size -= 0.2

    c.setFont(FONT_BOLD, title_size)
    c.setFillColor(BLACK)
    c.drawCentredString(PAGE_W / 2, y, title)

    c.setFont(FONT, 8.8)
    c.drawCentredString(
        PAGE_W / 2,
        y - 5.2 * mm,
        f"Registration Reference Number: {data['meta']['application_id']}    Application Date: {data['meta']['application_date']}",
    )
    return y - 11.0 * mm


def draw_photo(c: canvas.Canvas, x: float, y_top: float, w: float = PASSPORT_PHOTO_W, h: float = PASSPORT_PHOTO_H, photo_data: Any = None) -> None:
    """
    Draw the student photo box using an international passport-style size.

    The visible box is 35 mm x 45 mm by default. The image is fitted inside
    the box while preserving aspect ratio, so the applicant's photo will not be
    stretched or distorted.
    """
    y = y_top - h
    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    c.rect(x, y, w, h, stroke=1, fill=0)

    logger.warning("PDF photo render start: photo_data_type=%s photo_data_repr=%r", type(photo_data).__name__, photo_data)

    if photo_data:
        try:
            image_source = None
            if isinstance(photo_data, (str, Path)) and Path(str(photo_data)).exists():
                image_source = str(photo_data)
                logger.warning("PDF photo source resolved from direct path: %s", image_source)
            elif hasattr(photo_data, "path") and Path(str(photo_data.path)).exists():
                image_source = str(photo_data.path)
                logger.warning("PDF photo source resolved from .path: %s", image_source)
            elif hasattr(photo_data, "file"):
                file_obj = photo_data.file
                if hasattr(file_obj, "name") and file_obj.name and Path(str(file_obj.name)).exists():
                    image_source = str(file_obj.name)
                    logger.warning("PDF photo source resolved from file.name: %s", image_source)
                else:
                    image_source = file_obj
                    logger.warning("PDF photo source using file-like object: %s", type(file_obj).__name__)
            elif hasattr(photo_data, "read"):
                image_source = photo_data
                logger.warning("PDF photo source using readable object: %s", type(photo_data).__name__)

            if image_source:
                logger.warning("PDF photo attempting ImageReader load")
                reader = ImageReader(image_source)
                iw, ih = reader.getSize()
                logger.warning("PDF photo ImageReader success: width=%s height=%s", iw, ih)

                pad = PHOTO_INNER_PADDING
                available_w = max(1, w - (2 * pad))
                available_h = max(1, h - (2 * pad))
                scale = min(available_w / iw, available_h / ih)
                dw, dh = iw * scale, ih * scale
                c.drawImage(
                    reader,
                    x + (w - dw) / 2,
                    y + (h - dh) / 2,
                    dw,
                    dh,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                logger.warning("PDF photo drawn successfully")
                return
        except Exception:
            logger.exception("PDF photo rendering failed; falling back to placeholder")

    logger.warning("PDF photo placeholder used because no drawable image source was available")
    c.setFont(FONT_BOLD, 8.8)
    c.setFillColor(BLACK)
    c.drawCentredString(x + w / 2, y + h / 2 + 7, "Student")
    c.drawCentredString(x + w / 2, y + h / 2 - 3, "Photo")
    c.setFont(FONT, 6.5)
    c.drawCentredString(x + w / 2, y + 3.0 * mm, "35 mm x 45 mm")

def draw_tick_choice(c: canvas.Canvas, y: float, label: str, value: Any) -> float:
    """Draw a compact Yes/No tick choice field with independent bordered cells."""
    selected = str(val(value)).strip().lower()
    yes_tick = "✓" if selected in {"yes", "true", "1", "y"} else ""
    no_tick = "✓" if selected in {"no", "false", "0", "n"} else ""

    h = 7.2 * mm
    y_bottom = y - h
    widths = _scaled_cell_widths([CONTENT_W * 0.50, CONTENT_W * 0.25, CONTENT_W * 0.25], CELL_X_GAP)
    texts = [label, f"Yes  {yes_tick}".rstrip(), f"No  {no_tick}".rstrip()]

    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    x = LEFT
    for width, text in zip(widths, texts):
        c.rect(x, y_bottom, width, h, stroke=1, fill=0)
        c.setFont(FONT_BOLD, 8.9)
        c.setFillColor(BLACK)
        c.drawString(x + 2.0, y_bottom + 2.25 * mm, text)
        x += width + CELL_X_GAP
    return y_bottom - CELL_Y_GAP



def _normalise_professional_qualifications(qualifications: Any) -> List[Dict[str, Any]]:
    """Return exactly three professional qualification records."""
    if isinstance(qualifications, str):
        qualifications = [{"Qualification Title": qualifications}]

    if not isinstance(qualifications, list):
        qualifications = []

    cleaned: List[Dict[str, Any]] = []
    for item in qualifications[:3]:
        if not isinstance(item, dict):
            item = {}

        cleaned.append({
            "Qualification Title": (
                item.get("Qualification Title")
                or item.get("Qualification / Training")
                or item.get("Title")
                or MISSING
            ),
            "Institution": item.get("Institution") or MISSING,
            "Institution Address": (
                item.get("Institution Address")
                or item.get("Address")
                or item.get("Street")
                or MISSING
            ),
            "Country": item.get("Country") or MISSING,
            "Period": item.get("Period") or MISSING,
            "Start Date": item.get("Start Date") or item.get("From") or MISSING,
            "Finished Date": (
                item.get("Finished Date")
                or item.get("Completed Date")
                or item.get("To")
                or MISSING
            ),
            "Award / Certificate?": (
                item.get("Award / Certificate?")
                or item.get("Certificate?")
                or item.get("Awards / Certificate?")
                or item.get("Award Certificate")
                or MISSING
            ),
        })

    while len(cleaned) < 3:
        cleaned.append({
            "Qualification Title": MISSING,
            "Institution": MISSING,
            "Institution Address": MISSING,
            "Country": MISSING,
            "Period": MISSING,
            "Start Date": MISSING,
            "Finished Date": MISSING,
            "Award / Certificate?": MISSING,
        })

    return cleaned


def _draw_yes_no_certificate_cell(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    w: float,
    h: float,
    label: str,
    value: Any,
    label_size: float = 6.2,
    value_size: float = 7.2,
) -> None:
    """Draw the Award / Certificate Yes/No field."""
    y = y_top - h
    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    c.rect(x, y, w, h, stroke=1, fill=0)

    selected = str(val(value)).strip().lower()
    yes_tick = "✓" if selected in {"yes", "y", "true", "1"} else ""
    no_tick = "✓" if selected in {"no", "n", "false", "0"} else ""

    c.setFillColor(BLACK)
    c.setFont(FONT, label_size)
    c.drawString(x + 2.0, y + h - label_size - 1.8, label)

    c.setFont(FONT_BOLD, value_size)
    c.drawString(x + 2.0, y + 2.0 * mm, f"YES {yes_tick}".rstrip())
    c.drawRightString(x + w - 2.0, y + 2.0 * mm, f"NO {no_tick}".rstrip())


def draw_professional_qualification_card(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    card_w: float,
    title: str,
    item: Dict[str, Any],
) -> float:
    """Draw one compact professional qualification card."""
    y = y_top

    title_h = 6.2 * mm
    row_h = 9.5 * mm
    small_row_h = 8.8 * mm

    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    c.rect(x, y - title_h, card_w, title_h, stroke=1, fill=0)

    c.setFillColor(BLACK)
    c.setFont(FONT_BOLD, 8.4)
    c.drawCentredString(x + card_w / 2, y - title_h + 2.0 * mm, title.upper())

    y -= title_h + CELL_Y_GAP

    rows = [
        ([("Qualification Title", item.get("Qualification Title"), 100)], row_h),
        ([("Institution", item.get("Institution"), 100)], row_h),
        ([("Institution Address", item.get("Institution Address"), 100)], row_h),
        ([("Country", item.get("Country"), 45), ("Period", item.get("Period"), 55)], small_row_h),
        ([("Start Date", item.get("Start Date"), 50), ("Finished Date", item.get("Finished Date"), 50)], small_row_h),
    ]

    for row, height in rows:
        y = draw_cells_at(c, x, y, card_w, row, height, label_size=6.15, value_size=7.15)

    certificate_h = 8.8 * mm
    _draw_yes_no_certificate_cell(
        c,
        x,
        y,
        card_w,
        certificate_h,
        "Award / Certificate?",
        item.get("Award / Certificate?"),
        label_size=6.15,
        value_size=7.15,
    )

    y -= certificate_h + CELL_Y_GAP
    return y


def professional_qualifications_three_cards_height() -> float:
    """Height needed for the three-card professional qualifications layout."""
    return (
        6.2 * mm
        + CELL_Y_GAP
        + 3 * (9.5 * mm + CELL_Y_GAP)
        + 2 * (8.8 * mm + CELL_Y_GAP)
        + 8.8 * mm
        + CELL_Y_GAP
        + 4.0 * mm
    )


def draw_professional_qualifications_block(c: canvas.Canvas, y: float, qualifications: Any) -> float:
    """
    Draw exactly three professional qualifications.

    Requested order:
    Qualification 1 = right
    Qualification 2 = centre
    Qualification 3 = left
    """
    qualifications = _normalise_professional_qualifications(qualifications)

    card_gap = 2.2 * mm
    card_w = (CONTENT_W - (2 * card_gap)) / 3

    left_x = LEFT
    centre_x = LEFT + card_w + card_gap
    right_x = LEFT + (2 * (card_w + card_gap))

    positions = [
        ("Qualification 1", right_x, qualifications[0]),
        ("Qualification 2", centre_x, qualifications[1]),
        ("Qualification 3", left_x, qualifications[2]),
    ]

    y_values = [draw_professional_qualification_card(c, x, y, card_w, title, item) for title, x, item in positions]
    return min(y_values) - 4.0 * mm


def draw_english_proficiency_block(c: canvas.Canvas, y: float, ep: Dict[str, Any]) -> float:
    rows = [
        ["Test Name", "Institution", "Score", "Year"],
        [ep.get("Test Name"), ep.get("Institution"), ep.get("Score"), ep.get("Year")],
    ]
    y = draw_table(
        c,
        LEFT,
        y,
        [CONTENT_W * 0.25, CONTENT_W * 0.35, CONTENT_W * 0.20, CONTENT_W * 0.20],
        [10 * mm, 13 * mm],
        rows,
        font_size=9.0,
    )
    y -= 4.0 * mm
    y = draw_tick_choice(c, y, "Is English your primary language?", ep.get("English is Primary Language?"))
    return y


def employment_history_compact_height() -> float:
    """Height for one compact employment-history card.

    The employment section is now one clean table per work experience.
    Removed fields: Place / Neighbourhood and House No.
    Removed separate label: Workplace Location.
    """
    title_h = 5.8 * mm
    main_h = 9.8 * mm
    compact_h = 8.7 * mm
    bottom_gap = 3.2 * mm
    return title_h + CELL_Y_GAP + (2 * (main_h + CELL_Y_GAP)) + (3 * (compact_h + CELL_Y_GAP)) + bottom_gap


def draw_employment_experience_card(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    total_w: float,
    title: str,
    item: Dict[str, Any],
) -> float:
    """Draw one employment record as a single compact table.

    Everything is inside this table, including location details.
    There is no separate Workplace Location heading, and no
    Place / Neighbourhood or House No. fields.
    """
    y = y_top
    title_h = 5.8 * mm
    main_h = 9.8 * mm
    compact_h = 8.7 * mm

    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    c.rect(x, y - title_h, total_w, title_h, stroke=1, fill=0)
    c.setFont(FONT_BOLD, 8.9)
    c.setFillColor(BLACK)
    c.drawString(x + 2.0, y - title_h + 1.75 * mm, title.upper())
    y -= title_h + CELL_Y_GAP

    rows = [
        ([
            ("Employer / Company Name", item.get("Employer / Company Name"), 58),
            ("Position / Job Title", item.get("Position / Job Title"), 42),
        ], main_h),
        ([
            ("Worked From", item.get("Start Date") or item.get("From"), 28),
            ("Worked To", item.get("End Date") or item.get("To"), 28),
            ("Country", item.get("Country"), 22),
            ("Region", item.get("Region"), 22),
        ], main_h),
        ([
            ("Region Post Code", item.get("Region Post Code"), 25),
            ("District", item.get("District"), 25),
            ("District Post Code", item.get("District Post Code"), 25),
            ("Ward", item.get("Ward"), 25),
        ], compact_h),
        ([
            ("Ward Post Code", item.get("Ward Post Code"), 28),
            ("Street", item.get("Street"), 42),
            ("Employment Type", item.get("Employment Type") or item.get("Type"), 30),
        ], compact_h),
        ([
            ("Duties / Responsibilities", item.get("Duties / Responsibilities") or item.get("Responsibilities"), 55),
            ("Supervisor / Contact", item.get("Supervisor / Contact") or item.get("Supervisor") or item.get("Contact Person"), 25),
            ("Remarks", item.get("Remarks"), 20),
        ], compact_h),
    ]

    for row, height in rows:
        y = draw_cells_at(
            c,
            x,
            y,
            total_w,
            row,
            height,
            label_size=6.45,
            value_size=7.45,
        )

    return y - 3.2 * mm


def draw_employment_history_block(c: canvas.Canvas, y: float, employment_rows: Any) -> float:
    """Compatibility version for non-flow drawing."""
    if not employment_rows:
        employment_rows = [{
            "Employer / Company Name": "No work experience provided",
            "Position / Job Title": MISSING,
            "Start Date": MISSING,
            "End Date": MISSING,
        }]

    for idx, item in enumerate(employment_rows[:2], start=1):
        y = draw_employment_experience_card(
            c,
            LEFT,
            y,
            CONTENT_W,
            f"Work Experience {idx}",
            item,
        )
    return y


def draw_study_preferences_block(c: canvas.Canvas, y: float, sp: Dict[str, Any]) -> float:
    y = draw_row(c, y, [("Preferred Intake", sp.get("Preferred Intake"), CONTENT_W)], 13.2 * mm)
    for row in [
        [("Preferred Country 1", sp.get("Preferred Country 1"), CONTENT_W / 3), ("Preferred Program 1", sp.get("Preferred Program 1"), CONTENT_W / 3), ("Preferred Country 2", sp.get("Preferred Country 2"), CONTENT_W / 3)],
        [("Preferred Program 2", sp.get("Preferred Program 2"), CONTENT_W / 3), ("Preferred Country 3", sp.get("Preferred Country 3"), CONTENT_W / 3), ("Preferred Program 3", sp.get("Preferred Program 3"), CONTENT_W / 3)],
    ]:
        y = draw_row(c, y, row, 14.5 * mm)
    return y


def other_details_compact_height() -> float:
    """Compact height for Section 8: Other Details.

    The section is divided into many smaller cells like the Student Address
    section, so it uses less vertical space and avoids a long two-column table.
    """
    row_h = 10.2 * mm
    rows = 4
    return rows * (row_h + CELL_Y_GAP) + 2.5 * mm


def draw_other_details_block_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    od: Dict[str, Any],
) -> Tuple[int, float]:
    """Draw Other Details as a compact multi-cell table.

    This replaces the tall two-column layout with four compact rows.
    The information is split into smaller fields to save space while keeping
    every original item visible.
    """
    row_h = 10.2 * mm
    rows = [
        [
            ("Valid Visa?", od.get("Valid Visa?"), 24),
            ("Visa Details", od.get("Visa Details (if applicable)"), 46),
            ("Program Level", od.get("Program Level"), 30),
        ],
        [
            ("Accommodation Preference", od.get("Accommodation Preference"), 38),
            ("Sponsor of Education", od.get("Sponsor of Education"), 32),
            ("Estimated Budget (USD)", od.get("Estimated Budget (USD)"), 30),
        ],
        [
            ("Scholarship Applied?", od.get("Scholarship Applied?"), 28),
            ("Scholarship Details", od.get("Scholarship Details (if applicable)"), 47),
            ("Any Medical Condition?", od.get("Any Medical Condition?"), 25),
        ],
        [
            ("Medical Condition Details", od.get("Medical Condition Details (if applicable)"), 40),
            ("Special Assistance Required?", od.get("Special Assistance Required?"), 28),
            ("Special Assistance Details", od.get("Special Assistance Details (if applicable)"), 32),
        ],
    ]

    for row in rows:
        page_no, y = ensure_flow_space(c, data, page_no, y, row_h)
        y = draw_cells_at(
            c,
            LEFT,
            y,
            CONTENT_W,
            row,
            row_h,
            label_size=7.1,
            value_size=8.1,
        )

    return page_no, y - 2.5 * mm



def terms_and_conditions_compact_height() -> float:
    """Compact height for the Terms and Conditions list."""
    title_space = SECTION_TOP_GAP + SECTION_AFTER_TITLE_GAP + 2.0 * mm
    line_h = 8.8 * mm
    bottom_gap = 3.0 * mm
    return title_space + (len(TERMS_AND_CONDITIONS) * line_h) + bottom_gap


def office_use_only_height() -> float:
    """Height for the Office Use Only approval box."""
    return 39 * mm


def draw_auto_signature(c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
    """Draw the director signature image inside the signature field."""
    c.saveState()
    if SIGNATURE_PATH.exists():
        try:
            img_w = w * 0.98
            img_h = h * 0.98
            c.drawImage(
                str(SIGNATURE_PATH),
                x + (w - img_w) / 2,
                y + (h - img_h) / 2,
                img_w,
                img_h,
                preserveAspectRatio=True,
                mask="auto",
            )
            c.restoreState()
            return
        except Exception:
            logger.warning("Failed to render signature image, falling back to auto-signature", exc_info=True)

    c.setStrokeColor(BLACK)
    c.setLineWidth(1.0)

    base_y = y + h * 0.46
    start_x = x + w * 0.08
    points = [
        (start_x, base_y),
        (x + w * 0.18, y + h * 0.70),
        (x + w * 0.28, y + h * 0.33),
        (x + w * 0.39, y + h * 0.62),
        (x + w * 0.52, y + h * 0.38),
        (x + w * 0.65, y + h * 0.58),
        (x + w * 0.82, y + h * 0.42),
    ]
    path = c.beginPath()
    path.moveTo(*points[0])
    for px, py in points[1:]:
        path.lineTo(px, py)
    c.drawPath(path, stroke=1, fill=0)

    c.setFont(FONT_ITALIC, 6.6)
    c.drawCentredString(x + w / 2, y + 1.2 * mm, "Auto-signed")
    c.restoreState()


def draw_auto_stamp(c: canvas.Canvas, center_x: float, center_y: float, radius: float = 11 * mm) -> None:
    """Draw the Africa Western Education company approval stamp.

    Uses the official scanned stamp image at ``STAMP_PATH`` when it exists,
    and falls back to a vector-drawn stamp otherwise so the form still
    renders cleanly on machines where the image has not been deployed yet.
    """
    c.saveState()
    if STAMP_PATH.exists():
        try:
            size = radius * 2
            c.drawImage(
                str(STAMP_PATH),
                center_x - radius,
                center_y - radius,
                size,
                size,
                preserveAspectRatio=True,
                mask="auto",
            )
            c.restoreState()
            return
        except Exception:
            logger.warning("Failed to render stamp image, falling back to vector stamp", exc_info=True)

    stamp_color = colors.HexColor("#B00020")
    c.setStrokeColor(stamp_color)
    c.setFillColor(stamp_color)
    c.setLineWidth(1.1)
    c.circle(center_x, center_y, radius, stroke=1, fill=0)
    c.circle(center_x, center_y, radius * 0.72, stroke=1, fill=0)

    c.setFont(FONT_BOLD, 5.8)
    c.drawCentredString(center_x, center_y + radius * 0.23, "AFRICA WESTERN")
    c.drawCentredString(center_x, center_y - radius * 0.02, "EDUCATION")
    c.setFont(FONT_BOLD, 5.2)
    c.drawCentredString(center_x, center_y - radius * 0.32, "APPROVED")
    c.restoreState()


def draw_office_use_only_box(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
) -> Tuple[int, float]:
    """Draw Office Use Only section with automatic signature and stamp."""
    needed = office_use_only_height()
    page_no, y = ensure_flow_space(c, data, page_no, y, needed)

    box_h = 34 * mm
    y_bottom = y - box_h

    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    c.rect(LEFT, y_bottom, CONTENT_W, box_h, stroke=1, fill=0)

    # Header strip
    header_h = 7 * mm
    c.setFont(FONT_BOLD, 10.3)
    c.setFillColor(BLACK)
    c.drawCentredString(LEFT + CONTENT_W / 2, y - 4.8 * mm, "OFFICE USE ONLY")
    c.line(LEFT, y - header_h, RIGHT, y - header_h)

    inner_top = y - header_h
    pad = 3 * mm
    left_x = LEFT + pad
    right_x = RIGHT - pad

    # Director name and signature line
    c.setFont(FONT, 8.4)
    c.drawString(left_x, inner_top - 5.2 * mm, "Director Name: ................................................")
    c.drawString(LEFT + CONTENT_W * 0.52, inner_top - 5.2 * mm, "Signature:")
    c.line(LEFT + CONTENT_W * 0.64, inner_top - 4.3 * mm, RIGHT - 14 * mm, inner_top - 4.3 * mm)

    signature_x = LEFT + CONTENT_W * 0.63
    signature_y = inner_top - 10.5 * mm
    signature_w = CONTENT_W * 0.28
    signature_h = 10.0 * mm
    draw_auto_signature(c, signature_x, signature_y, signature_w, signature_h)

    # Approval checkboxes
    check_y = inner_top - 13.4 * mm
    box = 4.2 * mm
    approved_x = left_x
    rejected_x = left_x + 33 * mm
    c.rect(approved_x, check_y, box, box, stroke=1, fill=0)
    c.rect(rejected_x, check_y, box, box, stroke=1, fill=0)
    c.setFont(FONT_BOLD, 8.5)
    c.drawString(approved_x + box + 2 * mm, check_y + 1.1 * mm, "Approved")
    c.drawString(rejected_x + box + 2 * mm, check_y + 1.1 * mm, "Rejected")

    # Reason area
    reason_x = LEFT + CONTENT_W * 0.47
    reason_y = inner_top - 22.5 * mm
    reason_w = CONTENT_W * 0.31
    reason_h = 13.2 * mm
    c.setFillColor(colors.HexColor("#F7E9E9"))
    c.roundRect(reason_x, reason_y, reason_w, reason_h, 3 * mm, stroke=0, fill=1)
    c.setFillColor(BLACK)
    c.setFont(FONT_BOLD, 8.0)
    c.drawString(reason_x + 3 * mm, reason_y + reason_h - 4.2 * mm, "Reason")

    # Automatic stamp
    stamp_center_x = RIGHT - 19 * mm
    stamp_center_y = inner_top - 11.7 * mm
    draw_auto_stamp(c, stamp_center_x, stamp_center_y, 21 * mm)
    c.setFont(FONT, 7.2)
    c.setFillColor(BLACK)
    c.drawCentredString(stamp_center_x, y_bottom + 2.7 * mm, "Stamp")

    return page_no, y_bottom - 4.0 * mm


def draw_documents_section(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    documents: List[Dict[str, Any]],
) -> Tuple[int, float]:
    """Draw the attached documents section as the final page of the form."""
    page_no, y = next_flow_page(c, data, page_no)

    page_no, y = draw_section_flow(c, data, page_no, y, "ATTACHED DOCUMENTS", 20 * mm)

    if not documents:
        page_no, y = ensure_flow_space(c, data, page_no, y, 15 * mm)
        c.setFont(FONT, 10.0)
        c.setFillColor(BLACK)
        c.drawString(LEFT + 4 * mm, y - 5 * mm, "No documents attached to this application.")
        y -= 15 * mm
        return page_no, y

    headers = ["#", "Document Type", "File Name", "Uploaded Date", "Description", "Verified"]
    col_widths = [
        CONTENT_W * 0.05,
        CONTENT_W * 0.20,
        CONTENT_W * 0.25,
        CONTENT_W * 0.14,
        CONTENT_W * 0.26,
        CONTENT_W * 0.10,
    ]

    rows = [headers]
    for idx, doc in enumerate(documents, start=1):
        rows.append([
            str(idx),
            doc.get("Document Type", "-"),
            doc.get("File Name", "-"),
            doc.get("Uploaded Date", "-"),
            doc.get("Description", "-"),
            doc.get("Verified", "No"),
        ])

    row_heights = [10 * mm] + [12 * mm] * (len(rows) - 1)
    total_table_height = sum(row_heights) + CELL_Y_GAP * len(row_heights)

    page_no, y = ensure_flow_space(c, data, page_no, y, total_table_height + 5 * mm)

    y = draw_table(
        c,
        LEFT,
        y,
        col_widths,
        row_heights,
        rows,
        font_size=7.8,
    )
    y -= 4 * mm

    return page_no, y



# ---------------------------------------------------------------------------
# Dynamic page-flow helpers
# ---------------------------------------------------------------------------

PAGE_SAFE_BOTTOM = BOTTOM + 8 * mm


def block_fits(y: float, needed_height: float) -> bool:
    """Return True when the next block can safely fit above the footer."""
    return (y - needed_height) >= PAGE_SAFE_BOTTOM


def next_flow_page(c: canvas.Canvas, data: Dict[str, Any], page_no: int) -> Tuple[int, float]:
    """Close the current page and continue on a fresh page."""
    end_page(c, data, page_no)
    page_no += 1
    y = new_page(c, data, page_no)
    return page_no, y


def ensure_flow_space(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    needed_height: float,
) -> Tuple[int, float]:
    """Move to a new page only when the next block cannot fit cleanly."""
    if not block_fits(y, needed_height):
        page_no, y = next_flow_page(c, data, page_no)
    return page_no, y


def draw_section_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    title: str,
    min_content_height: float = 18 * mm,
) -> Tuple[int, float]:
    """Draw a section title, but never leave it stranded at the bottom.

    The check uses the real height consumed by draw_section(), plus a small
    safety buffer. This keeps Section 2 on page 1 when there is enough space
    instead of pushing it to page 2 unnecessarily.
    """
    needed = SECTION_TOP_GAP + SECTION_AFTER_TITLE_GAP + (1.5 * mm) + min_content_height
    page_no, y = ensure_flow_space(c, data, page_no, y, needed)
    y = draw_section(c, title, y)
    return page_no, y


def draw_address_hierarchy_rows_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    source: Dict[str, Any],
    h: float = 11.8 * mm,
    prefix: str = "",
) -> Tuple[int, float]:
    """Draw address hierarchy row-by-row and continue on the next page when needed."""
    def g(name: str) -> Any:
        return source.get(f"{prefix}{name}") if prefix else source.get(name)

    rows = [
        [
            ("Country", g("Country"), CONTENT_W / 3),
            ("Region", g("Region"), CONTENT_W / 3),
            ("Region Post Code", g("Region Post Code"), CONTENT_W / 3),
        ],
        [
            ("District", g("District"), CONTENT_W / 3),
            ("District Post Code", g("District Post Code"), CONTENT_W / 3),
            ("Ward", g("Ward"), CONTENT_W / 3),
        ],
        [
            ("Ward Post Code", g("Ward Post Code"), CONTENT_W / 3),
            ("Street", g("Street"), CONTENT_W / 3),
            ("Place / Neighbourhood", g("Place / Neighbourhood"), CONTENT_W / 3),
        ],
        [
            ("House No.", g("House No."), CONTENT_W / 3),
            ("", "", CONTENT_W / 3),
            ("", "", CONTENT_W / 3),
        ],
    ]
    for row in rows:
        page_no, y = ensure_flow_space(c, data, page_no, y, h)
        y = draw_row(c, y, row, h)
    return page_no, y


def draw_named_address_block_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    title: str,
    source: Dict[str, Any],
    prefix: str = "",
) -> Tuple[int, float]:
    block_height = 4.0 * mm + (4 * 11.4 * mm) + 4.2 * mm
    page_no, y = ensure_flow_space(c, data, page_no, y, block_height)
    c.setFont(FONT_BOLD, 10.2)
    c.setFillColor(BLACK)
    c.drawString(LEFT, y, title)
    y -= 4.0 * mm
    page_no, y = draw_address_hierarchy_rows_flow(c, data, page_no, y, source, 11.4 * mm, prefix=prefix)
    return page_no, y - 4.2 * mm


def draw_education_school_block_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    school_data: Dict[str, Any],
) -> Tuple[int, float]:
    row_h = 11.8 * mm
    block_height = 4.5 * mm + (6 * row_h) + 5 * mm
    page_no, y = ensure_flow_space(c, data, page_no, y, block_height)

    c.setFont(FONT_BOLD, 10.6)
    c.setFillColor(BLACK)
    c.drawString(LEFT, y, val(school_data.get("Level")))
    y -= 4.5 * mm

    for row in [
        [
            ("School Name", school_data.get("School Name"), CONTENT_W * 0.58),
            ("Index Number", school_data.get("Index Number"), CONTENT_W * 0.42),
        ],
        [
            ("Starting Year", school_data.get("Start Year"), CONTENT_W / 3),
            ("Completed Year", school_data.get("Completed Year"), CONTENT_W / 3),
            ("Division", school_data.get("Division"), CONTENT_W / 3),
        ],
    ]:
        page_no, y = ensure_flow_space(c, data, page_no, y, row_h)
        y = draw_row(c, y, row, row_h)

    page_no, y = draw_address_hierarchy_rows_flow(c, data, page_no, y, school_data, row_h)
    return page_no, y - 5 * mm




def education_side_by_side_height() -> float:
    """Height for Advanced Level left and Ordinary Level right compact panels."""
    return (
        6.0 * mm
        + CELL_Y_GAP
        + 2 * (8.6 * mm + CELL_Y_GAP)
        + 4 * (7.8 * mm + CELL_Y_GAP)
        + 2.8 * mm
    )


def _education_level_key(item: Dict[str, Any]) -> str:
    return val(item.get("Level")).lower().replace("-", " ")


def _find_education_item(education_rows: Sequence[Dict[str, Any]], target: str) -> Dict[str, Any]:
    target = target.lower()
    for item in education_rows:
        level = _education_level_key(item)
        if target == "ordinary level" and (
            "ordinary level" in level or "form four" in level or "o level" in level or "olevel" in level
        ):
            return item
        if target == "advanced level" and (
            "advanced level" in level or "form six" in level or "a level" in level or "alevel" in level
        ):
            return item
    return {}


def draw_education_side_panel(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    panel_w: float,
    title: str,
    school_data: Dict[str, Any],
) -> float:
    """Draw one compact education panel."""
    y = y_top
    title_h = 6.0 * mm
    main_h = 8.6 * mm
    compact_h = 7.8 * mm

    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    c.rect(x, y - title_h, panel_w, title_h, stroke=1, fill=0)
    c.setFont(FONT_BOLD, 8.8)
    c.setFillColor(BLACK)
    c.drawCentredString(x + panel_w / 2, y - title_h + 1.8 * mm, title.upper())
    y -= title_h + CELL_Y_GAP

    rows = [
        ([
            ("School Name", school_data.get("School Name"), 60),
            ("Index Number", school_data.get("Index Number"), 40),
        ], main_h),
        ([
            ("Start Year", school_data.get("Start Year"), 25),
            ("Completed Year", school_data.get("Completed Year"), 35),
            ("Division", school_data.get("Division"), 40),
        ], main_h),
        ([
            ("Country", school_data.get("Country"), 30),
            ("Region", school_data.get("Region"), 38),
            ("Region Post Code", school_data.get("Region Post Code"), 32),
        ], compact_h),
        ([
            ("District", school_data.get("District"), 36),
            ("District Post Code", school_data.get("District Post Code"), 34),
            ("Ward", school_data.get("Ward"), 30),
        ], compact_h),
        ([
            ("Ward Post Code", school_data.get("Ward Post Code"), 32),
            ("Street", school_data.get("Street"), 38),
            ("Place / Neighbourhood", school_data.get("Place / Neighbourhood"), 30),
        ], compact_h),
        ([
            ("School Type", school_data.get("School Type"), 25),
            ("Exam Board", school_data.get("Exam Board"), 25),
            ("Certificate No.", school_data.get("Certificate No."), 25),
            ("Remarks", school_data.get("Remarks"), 25),
        ], compact_h),
    ]

    for row, height in rows:
        y = draw_cells_at(c, x, y, panel_w, row, height, label_size=6.35, value_size=7.25)

    return y


def draw_education_background_side_by_side_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    education_rows: Sequence[Dict[str, Any]],
) -> Tuple[int, float]:
    """Draw Advanced Level on the left and Ordinary Level on the right to save pages."""
    page_no, y = draw_section_flow(
        c,
        data,
        page_no,
        y,
        "SECTION 4: EDUCATION BACKGROUND DETAILS",
        education_side_by_side_height(),
    )
    page_no, y = ensure_flow_space(c, data, page_no, y, education_side_by_side_height())

    advanced_level = _find_education_item(education_rows, "advanced level")
    ordinary_level = _find_education_item(education_rows, "ordinary level")

    # Fallbacks keep the layout stable even when the data list comes in a different order.
    if not advanced_level and len(education_rows) > 1:
        advanced_level = education_rows[1]
    if not ordinary_level and len(education_rows) > 0:
        ordinary_level = education_rows[0]

    panel_gap = 2.4 * mm
    panel_w = (CONTENT_W - panel_gap) / 2
    left_x = LEFT
    right_x = LEFT + panel_w + panel_gap

    y_advanced = draw_education_side_panel(c, left_x, y, panel_w, "Advanced Level Details", advanced_level)
    y_ordinary = draw_education_side_panel(c, right_x, y, panel_w, "Ordinary Level Details", ordinary_level)

    return page_no, min(y_advanced, y_ordinary) - 2.8 * mm


def draw_professional_qualifications_block_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    qualifications: Any,
) -> Tuple[int, float]:
    """
    Flow version of the three-card professional qualifications section.

    Requested order:
    Qualification 1 = right
    Qualification 2 = centre
    Qualification 3 = left
    """
    qualifications = _normalise_professional_qualifications(qualifications)

    needed_h = professional_qualifications_three_cards_height()
    page_no, y = ensure_flow_space(c, data, page_no, y, needed_h)

    card_gap = 2.2 * mm
    card_w = (CONTENT_W - (2 * card_gap)) / 3

    left_x = LEFT
    centre_x = LEFT + card_w + card_gap
    right_x = LEFT + (2 * (card_w + card_gap))

    positions = [
        ("Qualification 1", right_x, qualifications[0]),
        ("Qualification 2", centre_x, qualifications[1]),
        ("Qualification 3", left_x, qualifications[2]),
    ]

    y_values = [draw_professional_qualification_card(c, x, y, card_w, title, item) for title, x, item in positions]
    return page_no, min(y_values) - 4.0 * mm


def draw_english_proficiency_block_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    ep: Dict[str, Any],
) -> Tuple[int, float]:
    needed = 10 * mm + 13 * mm + 4 * mm + 7.2 * mm
    page_no, y = ensure_flow_space(c, data, page_no, y, needed)
    y = draw_english_proficiency_block(c, y, ep)
    return page_no, y


def draw_employment_history_block_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    employment_rows: Any,
) -> Tuple[int, float]:
    """Flow version of the compact employment section.

    Each work experience is one table only. Location fields are included
    inside that same table; Place / Neighbourhood and House No. are removed.
    """
    if not employment_rows:
        employment_rows = [{
            "Employer / Company Name": "No work experience provided",
            "Position / Job Title": MISSING,
            "Start Date": MISSING,
            "End Date": MISSING,
        }]

    block_height = employment_history_compact_height()
    for idx, item in enumerate(employment_rows[:4], start=1):
        page_no, y = ensure_flow_space(c, data, page_no, y, block_height)
        y = draw_employment_experience_card(
            c,
            LEFT,
            y,
            CONTENT_W,
            f"Work Experience {idx}",
            item,
        )
    return page_no, y


def draw_study_preferences_block_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    sp: Dict[str, Any],
) -> Tuple[int, float]:
    rows = [
        [("Preferred Intake", sp.get("Preferred Intake"), CONTENT_W)],
        [("Preferred Country 1", sp.get("Preferred Country 1"), CONTENT_W / 3), ("Preferred Program 1", sp.get("Preferred Program 1"), CONTENT_W / 3), ("Preferred Country 2", sp.get("Preferred Country 2"), CONTENT_W / 3)],
        [("Preferred Program 2", sp.get("Preferred Program 2"), CONTENT_W / 3), ("Preferred Country 3", sp.get("Preferred Country 3"), CONTENT_W / 3), ("Preferred Program 3", sp.get("Preferred Program 3"), CONTENT_W / 3)],
    ]
    heights = [13.2 * mm, 14.5 * mm, 14.5 * mm]
    for row, height in zip(rows, heights):
        page_no, y = ensure_flow_space(c, data, page_no, y, height)
        y = draw_row(c, y, row, height)
    return page_no, y


def emergency_contact_compact_height() -> float:
    """Professional emergency contact block height with readable cells."""
    return (
        2 * (11.8 * mm + CELL_Y_GAP)
        + 4 * (10.4 * mm + CELL_Y_GAP)
        + 3.5 * mm
    )


def draw_emergency_contact_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
) -> Tuple[int, float]:
    """
    Draw emergency contact with full-width readable cells.

    Important fix:
    The previous version passed small numeric weights into draw_row(), but
    draw_row() treats the third value as real width. That made the table tiny.
    This version uses draw_cells_at() across CONTENT_W, so the numbers are
    treated correctly as relative weights and each cell fills the full page width.
    """
    page_no, y = draw_section_flow(
        c,
        data,
        page_no,
        y,
        "SECTION 3: EMERGENCY CONTACT DETAILS",
        emergency_contact_compact_height(),
    )
    e = data["emergency"]

    main_h = 11.8 * mm
    address_h = 10.4 * mm

    rows = [
        ([
            ("Full Name", e.get("Full Name"), 42),
            ("Relationship", e.get("Relationship"), 24),
            ("Occupation", e.get("Occupation"), 34),
        ], main_h),
        ([
            ("Phone Number", e.get("Phone Number"), 32),
            ("Email Address", e.get("Email Address"), 48),
            ("House No.", e.get("House No."), 20),
        ], main_h),
        ([
            ("Country", e.get("Country"), 27),
            ("Region", e.get("Region"), 28),
            ("Region Post Code", e.get("Region Post Code"), 23),
            ("District", e.get("District"), 22),
        ], address_h),
        ([
            ("District Post Code", e.get("District Post Code"), 26),
            ("Ward", e.get("Ward"), 24),
            ("Ward Post Code", e.get("Ward Post Code"), 25),
            ("Street", e.get("Street"), 25),
        ], address_h),
        ([
            ("Place / Neighbourhood", e.get("Place / Neighbourhood"), 38),
            ("Alternative Phone", e.get("Alternative Phone") or e.get("Alt Phone"), 24),
            ("Relationship Status", e.get("Relationship Status") or e.get("Status"), 20),
            ("Remarks", e.get("Remarks"), 18),
        ], address_h),
    ]

    for row, height in rows:
        page_no, y = ensure_flow_space(c, data, page_no, y, height)
        y = draw_cells_at(
            c,
            LEFT,
            y,
            CONTENT_W,
            row,
            height,
            label_size=7.6,
            value_size=8.6,
        )

    return page_no, y - 3.5 * mm



def student_address_side_by_side_height() -> float:
    """Height for compact permanent/current student address panels."""
    return (
        6.2 * mm
        + CELL_Y_GAP
        + 5 * (9.8 * mm + CELL_Y_GAP)
        + 3.0 * mm
    )


def _prefixed_address_value(source: Dict[str, Any], prefix: str, name: str) -> Any:
    return source.get(f"{prefix}{name}")


def draw_student_address_side_panel(
    c: canvas.Canvas,
    x: float,
    y_top: float,
    panel_w: float,
    title: str,
    source: Dict[str, Any],
    prefix: str,
) -> float:
    """Draw one student address panel with fewer rows and more useful boxes."""
    y = y_top
    title_h = 6.2 * mm
    row_h = 9.8 * mm

    c.setStrokeColor(BLACK)
    c.setLineWidth(CELL_BORDER_WIDTH)
    c.rect(x, y - title_h, panel_w, title_h, stroke=1, fill=0)
    c.setFont(FONT_BOLD, 8.9)
    c.setFillColor(BLACK)
    c.drawCentredString(x + panel_w / 2, y - title_h + 1.9 * mm, title.upper())
    y -= title_h + CELL_Y_GAP

    def g(name: str) -> Any:
        return _prefixed_address_value(source, prefix, name)

    rows = [
        ([
            ("Country", g("Country"), 32),
            ("Region", g("Region"), 36),
            ("Region Post Code", g("Region Post Code"), 32),
        ], row_h),
        ([
            ("District", g("District"), 34),
            ("District Post Code", g("District Post Code"), 34),
            ("Ward", g("Ward"), 32),
        ], row_h),
        ([
            ("Ward Post Code", g("Ward Post Code"), 30),
            ("Street", g("Street"), 38),
            ("House No.", g("House No."), 32),
        ], row_h),
        ([
            ("Place / Neighbourhood", g("Place / Neighbourhood"), 52),
            ("Postal Code", g("Postal Code") or g("Post Code"), 24),
            ("Address Status", g("Address Status") or g("Status"), 24),
        ], row_h),
        ([
            ("Nearest Landmark", g("Nearest Landmark") or g("Landmark"), 42),
            ("Duration at Address", g("Duration at Address"), 28),
            ("Remarks", g("Remarks"), 30),
        ], row_h),
    ]

    for row, height in rows:
        y = draw_cells_at(c, x, y, panel_w, row, height, label_size=6.75, value_size=7.75)

    return y


def draw_student_address_side_by_side_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    addresses: Dict[str, Any],
) -> Tuple[int, float]:
    """Draw Permanent Address on the left and Current Address on the right."""
    page_no, y = draw_section_flow(
        c,
        data,
        page_no,
        y,
        "SECTION 7: STUDENT ADDRESS",
        student_address_side_by_side_height(),
    )
    page_no, y = ensure_flow_space(c, data, page_no, y, student_address_side_by_side_height())

    panel_gap = 2.4 * mm
    panel_w = (CONTENT_W - panel_gap) / 2
    left_x = LEFT
    right_x = LEFT + panel_w + panel_gap

    y_permanent = draw_student_address_side_panel(c, left_x, y, panel_w, "Permanent Address", addresses, "Permanent ")
    y_current = draw_student_address_side_panel(c, right_x, y, panel_w, "Current Address", addresses, "Current ")

    return page_no, min(y_permanent, y_current) - 3.0 * mm


def draw_parent_details_block_flow(
    c: canvas.Canvas,
    data: Dict[str, Any],
    page_no: int,
    y: float,
    parent_title: str,
    parent_data: Dict[str, Any],
    continuation_section_title: str = "SECTION 2: PARENTS DETAILS CONTINUED",
) -> Tuple[int, float]:
    """
    Draw a parent details block row-by-row with true page flow.

    This allows the mother's details to begin in the remaining space on page 1
    and continue cleanly on page 2 instead of forcing the entire mother block
    to start on a fresh page.
    """
    title_h = 4.8 * mm
    row_h = 12.2 * mm
    address_h = 11.4 * mm

    rows = [
        [
            ("Full Name", parent_data.get("Full Name"), CONTENT_W / 2),
            ("Occupation", parent_data.get("Occupation"), CONTENT_W / 2),
        ],
        [
            ("Phone", parent_data.get("Phone"), CONTENT_W / 2),
            ("Email", parent_data.get("Email"), CONTENT_W / 2),
        ],
        [
            ("Country", parent_data.get("Country"), CONTENT_W / 3),
            ("Region", parent_data.get("Region"), CONTENT_W / 3),
            ("Region Post Code", parent_data.get("Region Post Code"), CONTENT_W / 3),
        ],
        [
            ("District", parent_data.get("District"), CONTENT_W / 3),
            ("District Post Code", parent_data.get("District Post Code"), CONTENT_W / 3),
            ("Ward", parent_data.get("Ward"), CONTENT_W / 3),
        ],
        [
            ("Ward Post Code", parent_data.get("Ward Post Code"), CONTENT_W / 3),
            ("Street", parent_data.get("Street"), CONTENT_W / 3),
            ("Place / Neighbourhood", parent_data.get("Place / Neighbourhood"), CONTENT_W / 3),
        ],
        [
            ("House No.", parent_data.get("House No."), CONTENT_W / 3),
            ("", "", CONTENT_W / 3),
            ("", "", CONTENT_W / 3),
        ],
    ]
    heights = [row_h, row_h, address_h, address_h, address_h, address_h]

    def draw_parent_title(title: str, title_y: float) -> float:
        c.setFont(FONT_BOLD, 10.8)
        c.setFillColor(BLACK)
        c.drawString(LEFT, title_y, title)
        return title_y - title_h

    # Keep the parent title with at least the first row.
    page_no, y = ensure_flow_space(c, data, page_no, y, title_h + heights[0])
    y = draw_parent_title(parent_title, y)

    for idx, (row, height) in enumerate(zip(rows, heights)):
        if not block_fits(y, height):
            page_no, y = next_flow_page(c, data, page_no)
            page_no, y = draw_section_flow(c, data, page_no, y, continuation_section_title, height + title_h)
            y -= 3.0 * mm
            continued = f"{parent_title} Continued"
            y = draw_parent_title(continued, y)
        y = draw_row(c, y, row, height)

    return page_no, y - 5.5 * mm

def generate_pdf(output: str, data: Dict[str, Any]) -> None:
    c = canvas.Canvas(output, pagesize=A4)

    # PAGE 1 begins normally, then the form flows dynamically after the personal section.
    # Parent details now split row-by-row, so Mother's Details can start in the remaining
    # space on page 1 and continue on page 2 instead of wasting the blank area.
    page = 1
    y = new_page(c, data, page)
    y = draw_title(c, data, y)

    y = draw_section(c, "SECTION 1: PERSONAL DETAILS", y)
    p = data["personal"]
    gender = val(p.get("Gender"))
    photo_gap = 4 * mm
    photo_w = PASSPORT_PHOTO_W
    photo_h = PASSPORT_PHOTO_H
    personal_w = CONTENT_W - photo_w - photo_gap
    row_h = 12 * mm

    # Main student information stays beside the photo. Additional residence
    # fields continue below using the full page width, so no student details are missing.
    personal_cells = [
        [
            ("Full Name (as in passport)", p.get("Full Name (as in passport)"), personal_w * 0.64),
            ("Gender", gender, personal_w * 0.36),
        ],
        [
            ("Date of Birth", p.get("Date of Birth"), personal_w * 0.30),
            ("Place of Birth", p.get("Place of Birth"), personal_w * 0.40),
            ("Nationality", p.get("Nationality"), personal_w * 0.30),
        ],
        [
            ("Native Language", p.get("Native Language"), personal_w / 2),
            ("Marital Status", p.get("Marital Status"), personal_w / 2),
        ],
        [
            ("Email", p.get("Email"), personal_w / 2),
            ("Phone Number", p.get("Phone Number"), personal_w / 2),
        ],
        [
            ("Passport Number", p.get("Passport Number"), personal_w / 3),
            ("Passport Issued Date", p.get("Passport Issued Date"), personal_w / 3),
            ("Passport Expired Date", p.get("Passport Expired Date"), personal_w / 3),
        ],
        [
            ("Application ID / Serial Number", p.get("Application ID / Serial Number"), personal_w),
        ],
    ]
    yy = y
    for row in personal_cells:
        yy = draw_row(c, yy, row, row_h)
    draw_photo(c, LEFT + personal_w + photo_gap, y, photo_w, photo_h, p.get("Student Photo", ""))

    # Student residence/address details requested for the personal details section.
    y = yy - 2.2 * mm
    for row in [
        [
            ("City", p.get("City"), CONTENT_W / 3),
            ("Region", p.get("Region"), CONTENT_W / 3),
            ("Ward", p.get("Ward"), CONTENT_W / 3),
        ],
        [
            ("Village", p.get("Village"), CONTENT_W / 3),
            ("Street", p.get("Street"), CONTENT_W / 3),
            ("House Number", p.get("House Number"), CONTENT_W / 3),
        ],
    ]:
        y = draw_row(c, y, row, row_h)
    y -= 2.8 * mm

    # Section 2: one professional parent section with Mother on the left
    # and Father on the right, using content-sized independent cells.
    father = data["parents"].get("Father", {})
    mother = data["parents"].get("Mother", {})
    page, y = draw_section_flow(c, data, page, y, "SECTION 2: PARENTS DETAILS", parents_side_by_side_height())
    page, y = draw_parents_side_by_side_flow(c, data, page, y, father, mother)

    # From here onward, every section continues dynamically. Blocks are split between
    # pages when needed, so blank space is used better and footer overlap is avoided.
    page, y = draw_emergency_contact_flow(c, data, page, y)

    page, y = draw_education_background_side_by_side_flow(c, data, page, y, data["education_background"])

    page, y = draw_section_flow(c, data, page, y, "POST-SECONDARY / HIGHER EDUCATION", 70 * mm)
    rows = [["Level", "Institution", "Field of Study", "Start Year", "Completed Year", "GPA"]]
    for item in data["higher_education"]:
        rows.append([item.get("Level"), item.get("Institution"), item.get("Field of Study"), item.get("Start Year"), item.get("Completed Year"), item.get("GPA")])
    higher_table_height = 10 * mm + 12.2 * mm * len(data["higher_education"])
    page, y = ensure_flow_space(c, data, page, y, higher_table_height)
    y = draw_table(c, LEFT, y, [CONTENT_W * 0.14, CONTENT_W * 0.27, CONTENT_W * 0.24, CONTENT_W * 0.115, CONTENT_W * 0.14, CONTENT_W * 0.095], [10 * mm] + [12.2 * mm] * len(data["higher_education"]), rows, font_size=7.8)
    y -= 4 * mm

    page, y = draw_section_flow(
        c,
        data,
        page,
        y,
        "SECTION 5: PROFESSIONAL QUALIFICATIONS / TRAINING",
        professional_qualifications_three_cards_height(),
    )
    page, y = draw_professional_qualifications_block_flow(c, data, page, y, data.get("professional_qualifications", []))

    page, y = draw_section_flow(c, data, page, y, "ENGLISH LANGUAGE PROFICIENCY", 40 * mm)
    page, y = draw_english_proficiency_block_flow(c, data, page, y, data["english_proficiency"])
    y -= 4 * mm

    page, y = draw_section_flow(
        c,
        data,
        page,
        y,
        "SECTION 5: EMPLOYMENT HISTORY / WORK EXPERIENCE",
        employment_history_compact_height(),
    )
    page, y = draw_employment_history_block_flow(c, data, page, y, data.get("employment_history") or [])

    page, y = draw_section_flow(c, data, page, y, "SECTION 6: STUDY PREFERENCES", 45 * mm)
    page, y = draw_study_preferences_block_flow(c, data, page, y, data["study_preferences"])

    ad = data["addresses"]
    page, y = draw_student_address_side_by_side_flow(c, data, page, y, ad)

    page, y = draw_section_flow(c, data, page, y, "SECTION 8: OTHER DETAILS", other_details_compact_height())
    page, y = draw_other_details_block_flow(c, data, page, y, data["other_details"])

    page, y = draw_section_flow(c, data, page, y, "SECTION 9: HOW DID YOU HEAR ABOUT US?", 17 * mm)
    hau = data["heard_about_us"]
    page, y = ensure_flow_space(c, data, page, y, 15 * mm)
    y = draw_row(c, y, [("Source", hau.get("Source"), CONTENT_W / 2), ("Other (please specify)", hau.get("Other (please specify)"), CONTENT_W / 2)], 15 * mm)
    y -= 7 * mm

    page, y = draw_section_flow(c, data, page, y, "SECTION 10: DECLARATION BY APPLICANT", 30 * mm)
    for i, line in enumerate(DECLARATION_LINES, start=1):
        page, y = ensure_flow_space(c, data, page, y, 13 * mm)
        text = f"{i}. {line}"
        draw_wrapped(c, text, LEFT, y - 13 * mm, CONTENT_W, 12 * mm, FONT, 9.2, leading=10.2)
        y -= 13 * mm
    y -= 5 * mm
    dec = data["declaration"]
    for row in [
        [("Applicant Full Name", dec.get("Applicant Full Name"), CONTENT_W / 2), ("Date", dec.get("Date"), CONTENT_W / 2)],
        [("Signature", dec.get("Signature") or "", CONTENT_W / 2), ("Declaration Agreed", dec.get("Declaration Agreed"), CONTENT_W / 2)],
    ]:
        page, y = ensure_flow_space(c, data, page, y, 17 * mm)
        y = draw_row(c, y, row, 17 * mm)

    page, y = draw_section_flow(c, data, page, y, "TERMS AND CONDITIONS", terms_and_conditions_compact_height())
    terms_line_h = 8.8 * mm
    for i, line in enumerate(TERMS_AND_CONDITIONS, start=1):
        page, y = ensure_flow_space(c, data, page, y, terms_line_h)
        text = f"{i}. {line}"
        draw_wrapped(c, text, LEFT, y - terms_line_h, CONTENT_W, terms_line_h - 1.0 * mm, FONT, 8.6, leading=8.0)
        y -= terms_line_h
    y -= 2.5 * mm

    page, y = draw_office_use_only_box(c, data, page, y)

    documents = data.get("documents", [])
    page, y = draw_documents_section(c, data, page, y, documents)

    end_page(c, data, page)
    c.save()


# ---------------------------------------------------------------------------
# Django integration helpers
# ---------------------------------------------------------------------------

def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    if obj is None:
        return default
    return getattr(obj, attr, default)



def _first_attr(obj: Any, names: Sequence[str], default: Any = None) -> Any:
    """Return the first non-empty attribute value from a list of possible Django field names."""
    for name in names:
        value = _safe_get(obj, name, None)
        if value not in (None, ""):
            return value
    return default


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


def _photo_source(student_profile: Any) -> Any:
    """Return a file-like object or path usable by ReportLab from Django ImageField."""
    pic = _safe_get(student_profile, "profile_picture")
    if not pic:
        logger.warning("PDF photo source missing: student_profile has no profile_picture")
        return ""
    try:
        # Try common attributes for ImageField-like objects without triggering
        # storage backends that do not support absolute filesystem paths.
        path_value = None
        try:
            path_value = pic.path
        except Exception as exc:
            logger.warning("PDF photo helper .path unavailable: %s", exc)
        if path_value:
            if Path(str(path_value)).exists():
                logger.warning("PDF photo helper resolved local path: %s", path_value)
                return path_value
            logger.warning("PDF photo helper found .path but file does not exist: %s", path_value)

        file_obj = getattr(pic, 'file', None)
        file_name = getattr(file_obj, 'name', None)
        if file_name:
            if Path(str(file_name)).exists():
                logger.warning("PDF photo helper resolved file.name path: %s", file_name)
                return file_name
            logger.warning("PDF photo helper found file.name but it does not exist locally: %s", file_name)

        name_value = getattr(pic, 'name', None)
        if name_value:
            if Path(str(name_value)).exists():
                logger.warning("PDF photo helper resolved name path: %s", name_value)
                return name_value
            logger.warning("PDF photo helper found name but it does not exist locally: %s", name_value)

        # Handle remote storage and non-local file objects by reading the bytes.
        if hasattr(pic, 'open'):
            logger.warning("PDF photo helper opening stored file as bytes: %s", type(pic).__name__)
            pic.open('rb')
            img_data = BytesIO(pic.read())
            pic.close()
            img_data.seek(0)
            logger.warning("PDF photo helper read %s bytes from stored file", img_data.getbuffer().nbytes)
            return img_data
        if file_obj is not None and hasattr(file_obj, 'read'):
            try:
                file_obj.seek(0)
            except Exception:
                pass
            img_data = BytesIO(file_obj.read())
            img_data.seek(0)
            logger.warning("PDF photo helper read %s bytes from file object", img_data.getbuffer().nbytes)
            return img_data
    except Exception:
        logger.exception("PDF photo helper failed while resolving profile_picture")
        return ""
    logger.warning("PDF photo helper could not resolve a drawable source for profile_picture=%r", pic)
    return ""


def _get_work_experiences(student_profile: Any) -> List[Any]:
    if student_profile is None:
        return []
    manager = getattr(student_profile, "work_experiences", None) or getattr(student_profile, "workexperience_set", None)
    if manager is None:
        return []
    try:
        return list(manager.all().order_by("-start_date")[:4])
    except Exception:
        try:
            return list(manager.all()[:4])
        except Exception:
            return []


def application_to_awec_csc_style_data(application: Any, student_profile: Any = None, supplemental_profile: Any = None, documents: Any = None) -> Dict[str, Any]:
    """
    Convert your existing Django Application, StudentProfile, and
    ApplicationSupplementalProfile objects into the dictionary used by the
    CSC-style AWEC renderer.
    """
    data = deepcopy(DEFAULT_DATA)
    student = _safe_get(application, "student")
    app_id = _safe_get(application, "id", "001")
    today_val = date.today()
    generated_at_source = _safe_get(supplemental_profile, "generated_at") or today_val

    serial = None
    if hasattr(application, 'reference_number') and application.reference_number:
        serial = str(application.reference_number)
    elif _safe_get(supplemental_profile, "serial_number"):
        serial = str(_safe_get(supplemental_profile, "serial_number"))
    elif hasattr(application, 'get_registration_number'):
        try:
            retrieved_serial = application.get_registration_number()
            if retrieved_serial:
                serial = str(retrieved_serial)
        except (AttributeError, TypeError):
            pass # Ignore errors and proceed to generate if serial is still None

    if not serial: # If serial is still None or empty after all attempts, generate one
        gen_year = getattr(generated_at_source, 'year', today_val.year)
        try:
            numeric_id = int(app_id)
            serial = f"AWECO/INT/REG/TZ/DSM/{gen_year}8{numeric_id:03d}"
        except (ValueError, TypeError):
            serial = f"AWECO/INT/REG/TZ/DSM/{gen_year}8{app_id}"

    generated_date = generated_at_source.strftime("%Y-%m-%d") if hasattr(generated_at_source, "strftime") else str(generated_at_source)
    application_date = _date_text(generated_at_source, today_val.strftime("%d/%m/%Y"))
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
        "Place of Birth": val(_safe_get(supplemental_profile, "place_of_birth") or _safe_get(student_profile, "place_of_birth")),
        "Nationality": val(_safe_get(student_profile, "nationality")),
        "Native Language": val(_safe_get(student_profile, "native_language")),
        "Marital Status": val(_safe_get(student_profile, "marital_status")),
        "City": val(_safe_get(student_profile, "city") or _safe_get(supplemental_profile, "current_city") or _safe_get(supplemental_profile, "permanent_city")),
        "Region": val(_safe_get(student_profile, "region") or _safe_get(supplemental_profile, "current_region") or _safe_get(supplemental_profile, "permanent_region")),
        "Ward": val(_safe_get(student_profile, "ward") or _safe_get(supplemental_profile, "current_ward") or _safe_get(supplemental_profile, "permanent_ward")),
        "Village": val(_safe_get(student_profile, "village") or _safe_get(supplemental_profile, "current_village") or _safe_get(supplemental_profile, "permanent_village")),
        "Street": val(_safe_get(student_profile, "street") or _safe_get(supplemental_profile, "current_street") or _safe_get(supplemental_profile, "permanent_street")),
        "House Number": val(_safe_get(student_profile, "house_no") or _safe_get(supplemental_profile, "current_house_no") or _safe_get(supplemental_profile, "permanent_house_no")),
        "Email": val(_safe_get(student, "email")),
        "Phone Number": val(_safe_get(student_profile, "phone_number")),
        "Passport Number": val(_safe_get(supplemental_profile, "passport_number") or _safe_get(student_profile, "passport_number")),
        "Passport Issued Date": _date_text(_safe_get(supplemental_profile, "passport_issue_date") or _safe_get(student_profile, "passport_issue_date")),
        "Passport Expired Date": _date_text(_safe_get(supplemental_profile, "passport_expiration_date") or _safe_get(student_profile, "passport_expiration_date")),
        "Application ID / Serial Number": serial,
        "Student Photo": _photo_source(student_profile),
    }

    data["parents"] = {
        "Father": {
            "Full Name": val(_safe_get(student_profile, "father_name")),
            "Occupation": val(_safe_get(student_profile, "father_occupation")),
            "Phone": val(_safe_get(student_profile, "father_phone")),
            "Email": val(_safe_get(student_profile, "father_email")),
            "Country": val(_safe_get(student_profile, "father_country") or "Tanzania"),
            "Region": val(_safe_get(student_profile, "father_region")),
            "Region Post Code": val(_safe_get(student_profile, "father_region_post_code")),
            "District": val(_safe_get(student_profile, "father_district")),
            "District Post Code": val(_safe_get(student_profile, "father_district_post_code")),
            "Ward": val(_safe_get(student_profile, "father_ward")),
            "Ward Post Code": val(_safe_get(student_profile, "father_ward_post_code")),
            "Street": val(_safe_get(student_profile, "father_street")),
            "Place / Neighbourhood": val(_safe_get(student_profile, "father_place_neighbourhood")),
            "House No.": val(_safe_get(student_profile, "father_house_no")),
            "Status": val(_safe_get(student_profile, "father_status")),
            "Relationship": val(_safe_get(student_profile, "father_relationship")),
        },
        "Mother": {
            "Full Name": val(_safe_get(student_profile, "mother_name")),
            "Occupation": val(_safe_get(student_profile, "mother_occupation")),
            "Phone": val(_safe_get(student_profile, "mother_phone")),
            "Email": val(_safe_get(student_profile, "mother_email")),
            "Country": val(_safe_get(student_profile, "mother_country") or "Tanzania"),
            "Region": val(_safe_get(student_profile, "mother_region")),
            "Region Post Code": val(_safe_get(student_profile, "mother_region_post_code")),
            "District": val(_safe_get(student_profile, "mother_district")),
            "District Post Code": val(_safe_get(student_profile, "mother_district_post_code")),
            "Ward": val(_safe_get(student_profile, "mother_ward")),
            "Ward Post Code": val(_safe_get(student_profile, "mother_ward_post_code")),
            "Street": val(_safe_get(student_profile, "mother_street")),
            "Place / Neighbourhood": val(_safe_get(student_profile, "mother_place_neighbourhood")),
            "House No.": val(_safe_get(student_profile, "mother_house_no")),
            "Status": val(_safe_get(student_profile, "mother_status")),
            "Relationship": val(_safe_get(student_profile, "mother_relationship")),
        },
    }

    data["emergency"] = {
        "Full Name": val(_safe_get(student_profile, "emergency_contact")),
        "Relationship": val(_safe_get(student_profile, "emergency_relation")),
        "Occupation": val(_safe_get(student_profile, "emergency_occupation")),
        "Phone Number": val(_safe_get(student_profile, "emergency_phone") or _safe_get(student_profile, "phone_number")),
        "Email Address": val(_safe_get(student_profile, "emergency_email") or _safe_get(student, "email")),
        "Alternative Phone": val(_safe_get(student_profile, "emergency_alternative_phone")),
        "Country": val(_safe_get(student_profile, "emergency_country") or "Tanzania"),
        "Region": val(_safe_get(student_profile, "emergency_region")),
        "Region Post Code": val(_safe_get(student_profile, "emergency_region_post_code")),
        "District": val(_safe_get(student_profile, "emergency_district")),
        "District Post Code": val(_safe_get(student_profile, "emergency_district_post_code")),
        "Ward": val(_safe_get(student_profile, "emergency_ward")),
        "Ward Post Code": val(_safe_get(student_profile, "emergency_ward_post_code")),
        "Street": val(_safe_get(student_profile, "emergency_street")),
        "Place / Neighbourhood": val(_safe_get(student_profile, "emergency_place_neighbourhood")),
        "House No.": val(_safe_get(student_profile, "emergency_house_no")),
        "Relationship Status": val(_safe_get(student_profile, "emergency_relationship_status")),
        "Remarks": val(_safe_get(student_profile, "emergency_remarks")),
    }

    data["education_background"] = [
        {
            "Level": "Ordinary Level (O-Level)",
            "School Name": val(_safe_get(student_profile, "olevel_school")),
            "Index Number": val(_safe_get(student_profile, "olevel_candidate_no")),
            "Start Year": _year_text(_safe_get(student_profile, "olevel_start_year")),
            "Completed Year": _year_text(_safe_get(student_profile, "olevel_completed_year")),
            "Division": val(_safe_get(student_profile, "olevel_gpa")),
            "Country": val(_safe_get(student_profile, "olevel_school_country") or "Tanzania"),
            "Region": val(_safe_get(student_profile, "olevel_school_region")),
            "Region Post Code": val(_safe_get(student_profile, "olevel_school_region_post_code")),
            "District": val(_safe_get(student_profile, "olevel_school_district")),
            "District Post Code": val(_safe_get(student_profile, "olevel_school_district_post_code")),
            "Ward": val(_safe_get(student_profile, "olevel_school_ward")),
            "Ward Post Code": val(_safe_get(student_profile, "olevel_school_ward_post_code")),
            "Street": val(_safe_get(student_profile, "olevel_school_street")),
            "Place / Neighbourhood": val(_safe_get(student_profile, "olevel_school_place_neighbourhood")),
            "House No.": val(_safe_get(student_profile, "olevel_school_house_no")),
            "School Type": val(_safe_get(student_profile, "olevel_school_type")),
            "Exam Board": val(_safe_get(student_profile, "olevel_exam_board")),
            "Certificate No.": val(_safe_get(student_profile, "olevel_certificate_no")),
            "Remarks": val(_safe_get(student_profile, "olevel_remarks")),
        },
        {
            "Level": "Advanced Level (A-Level)",
            "School Name": val(_safe_get(student_profile, "alevel_school")),
            "Index Number": val(_safe_get(student_profile, "alevel_candidate_no")),
            "Start Year": _year_text(_safe_get(student_profile, "alevel_start_year")),
            "Completed Year": _year_text(_safe_get(student_profile, "alevel_completed_year")),
            "Division": val(_safe_get(student_profile, "alevel_gpa")),
            "Country": val(_safe_get(student_profile, "alevel_school_country") or "Tanzania"),
            "Region": val(_safe_get(student_profile, "alevel_school_region")),
            "Region Post Code": val(_safe_get(student_profile, "alevel_school_region_post_code")),
            "District": val(_safe_get(student_profile, "alevel_school_district")),
            "District Post Code": val(_safe_get(student_profile, "alevel_school_district_post_code")),
            "Ward": val(_safe_get(student_profile, "alevel_school_ward")),
            "Ward Post Code": val(_safe_get(student_profile, "alevel_school_ward_post_code")),
            "Street": val(_safe_get(student_profile, "alevel_school_street")),
            "Place / Neighbourhood": val(_safe_get(student_profile, "alevel_school_place_neighbourhood")),
            "House No.": val(_safe_get(student_profile, "alevel_school_house_no")),
            "School Type": val(_safe_get(student_profile, "alevel_school_type")),
            "Exam Board": val(_safe_get(student_profile, "alevel_exam_board")),
            "Certificate No.": val(_safe_get(student_profile, "alevel_certificate_no")),
            "Remarks": val(_safe_get(student_profile, "alevel_remarks")),
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
            "Start Year": _year_text(_first_attr(supplemental_profile, [f"{prefix}_start_year", f"{prefix}_started_year"])),
            "Completed Year": _year_text(_first_attr(supplemental_profile, [f"{prefix}_completed_year", f"{prefix}_year_completed"])),
            "GPA": val(_safe_get(supplemental_profile, f"{prefix}_gpa")),
        })

    def _professional_qualification_from_profile(index: int) -> Dict[str, Any]:
        suffix = "" if index == 1 else f"_{index}"
        return {
            "Qualification Title": val(_first_attr(supplemental_profile, [
                f"professional_qualification_title{suffix}",
                f"professional_qualifications{suffix}",
                f"professional_qualification_training{suffix}",
            ])),
            "Institution": val(_safe_get(supplemental_profile, f"professional_qualification_institution{suffix}")),
            "Institution Address": val(_first_attr(supplemental_profile, [
                f"professional_qualification_address{suffix}",
                f"professional_qualification_institution_address{suffix}",
                f"professional_qualification_street{suffix}",
            ])),
            "Country": val(_first_attr(supplemental_profile, [f"professional_qualification_country{suffix}"], "Tanzania")),
            "Period": val(_safe_get(supplemental_profile, f"professional_qualification_period{suffix}")),
            "Start Date": _date_text(_first_attr(supplemental_profile, [
                f"professional_qualification_start_date{suffix}",
                f"professional_qualification_from{suffix}",
            ])),
            "Finished Date": _date_text(_first_attr(supplemental_profile, [
                f"professional_qualification_finished_date{suffix}",
                f"professional_qualification_completed_date{suffix}",
                f"professional_qualification_to{suffix}",
            ])),
            "Award / Certificate?": _bool_text(_first_attr(supplemental_profile, [
                f"professional_qualification_certificate{suffix}",
                f"professional_qualification_award_certificate{suffix}",
                f"professional_qualification_has_certificate{suffix}",
            ])),
        }

    data["professional_qualifications"] = [
        _professional_qualification_from_profile(1),
        _professional_qualification_from_profile(2),
        _professional_qualification_from_profile(3),
    ]
    data["english_proficiency"] = {
        "Test Name": val(_safe_get(supplemental_profile, "english_test_name")),
        "Institution": val(_safe_get(supplemental_profile, "english_test_institution")),
        "Score": val(_safe_get(supplemental_profile, "english_test_score")),
        "Year": _year_text(_safe_get(supplemental_profile, "english_test_year")),
        "English is Primary Language?": _bool_text(_safe_get(supplemental_profile, "english_is_primary_language")),
    }

    work_rows = []
    for exp in _get_work_experiences(student_profile):
        end = "Present" if _safe_get(exp, "currently_working") else _date_text(_safe_get(exp, "end_date"))
        work_rows.append({
            "Employer / Company Name": val(_safe_get(exp, "company_name")),
            "Position / Job Title": val(_safe_get(exp, "position")),
            "Start Date": _date_text(_safe_get(exp, "start_date")),
            "End Date": end,
            "Country": val(_first_attr(exp, ["country"], "Tanzania")),
            "Region": val(_safe_get(exp, "region")),
            "Region Post Code": val(_safe_get(exp, "region_post_code")),
            "District": val(_safe_get(exp, "district")),
            "District Post Code": val(_safe_get(exp, "district_post_code")),
            "Ward": val(_safe_get(exp, "ward")),
            "Ward Post Code": val(_safe_get(exp, "ward_post_code")),
            "Street": val(_safe_get(exp, "street")),
            "Place / Neighbourhood": val(_first_attr(exp, ["place_neighbourhood", "neighbourhood", "location"])),
            "House No.": val(_safe_get(exp, "house_no")),
        })
    data["employment_history"] = work_rows

    data["study_preferences"] = {
        "Preferred Intake": _choice_text(supplemental_profile, "preferred_intake") or _safe_get(student_profile, "preferred_intake"),
        "Preferred Country 1": val(_safe_get(student_profile, "preferred_country_1")),
        "Preferred Program 1": val(_safe_get(student_profile, "preferred_program_1")),
        "Preferred Country 2": val(_safe_get(student_profile, "preferred_country_2")),
        "Preferred Program 2": val(_safe_get(student_profile, "preferred_program_2")),
        "Preferred Country 3": val(_safe_get(student_profile, "preferred_country_3")),
        "Preferred Program 3": val(_safe_get(student_profile, "preferred_program_3")),
    }

    data["addresses"] = {
        "Current Country": val(_first_attr(supplemental_profile, ["current_country"], "Tanzania")),
        "Current Region": val(_safe_get(supplemental_profile, "current_region")),
        "Current Region Post Code": val(_first_attr(supplemental_profile, ["current_region_post_code", "current_postal_code"])),
        "Current District": val(_safe_get(supplemental_profile, "current_district")),
        "Current District Post Code": val(_safe_get(supplemental_profile, "current_district_post_code")),
        "Current Ward": val(_safe_get(supplemental_profile, "current_ward")),
        "Current Ward Post Code": val(_safe_get(supplemental_profile, "current_ward_post_code")),
        "Current Street": val(_safe_get(supplemental_profile, "current_street")),
        "Current Place / Neighbourhood": val(_first_attr(supplemental_profile, ["current_place_neighbourhood", "current_neighbourhood", "current_address"])),
        "Current House No.": val(_safe_get(supplemental_profile, "current_house_no")),
        "Current Postal Code": val(_safe_get(supplemental_profile, "current_postal_code")),
        "Current Address Status": val(_safe_get(supplemental_profile, "current_address_status")),
        "Current Nearest Landmark": val(_first_attr(supplemental_profile, ["current_nearest_landmark", "current_landmark"])),
        "Current Duration at Address": val(_safe_get(supplemental_profile, "current_duration_at_address")),
        "Current Remarks": val(_safe_get(supplemental_profile, "current_address_remarks")),
        "Permanent Country": val(_first_attr(supplemental_profile, ["permanent_country"], _safe_get(student_profile, "nationality"))),
        "Permanent Region": val(_safe_get(supplemental_profile, "permanent_region")),
        "Permanent Region Post Code": val(_first_attr(supplemental_profile, ["permanent_region_post_code", "permanent_postal_code"])),
        "Permanent District": val(_safe_get(supplemental_profile, "permanent_district")),
        "Permanent District Post Code": val(_safe_get(supplemental_profile, "permanent_district_post_code")),
        "Permanent Ward": val(_safe_get(supplemental_profile, "permanent_ward")),
        "Permanent Ward Post Code": val(_safe_get(supplemental_profile, "permanent_ward_post_code")),
        "Permanent Street": val(_safe_get(supplemental_profile, "permanent_street")),
        "Permanent Place / Neighbourhood": val(_first_attr(supplemental_profile, ["permanent_place_neighbourhood", "permanent_neighbourhood", "permanent_address"]) or _safe_get(student_profile, "address")),
        "Permanent House No.": val(_safe_get(supplemental_profile, "permanent_house_no")),
        "Permanent Postal Code": val(_safe_get(supplemental_profile, "permanent_postal_code")),
        "Permanent Address Status": val(_safe_get(supplemental_profile, "permanent_address_status")),
        "Permanent Nearest Landmark": val(_first_attr(supplemental_profile, ["permanent_nearest_landmark", "permanent_landmark"])),
        "Permanent Duration at Address": val(_safe_get(supplemental_profile, "permanent_duration_at_address")),
        "Permanent Remarks": val(_safe_get(supplemental_profile, "permanent_address_remarks")),
    }

    data["other_details"] = {
        "Valid Visa?": _bool_text(_safe_get(supplemental_profile, "has_valid_visa")),
        "Visa Details (if applicable)": val(_safe_get(supplemental_profile, "valid_visa_details")),
        "Program Level": _choice_text(supplemental_profile, "program_level"),
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
        "Date": today_val.strftime("%d/%m/%Y"),
        "Signature": "",
        "Declaration Agreed": _bool_text(_safe_get(supplemental_profile, "declaration_agreed"), "Yes"),
    }

    doc_list = []
    if documents is not None:
        for doc in documents:
            doc_name = _safe_get(doc, "file")
            if hasattr(doc_name, "name"):
                doc_name = doc_name.name
            elif doc_name:
                doc_name = str(doc_name)
            else:
                doc_name = "-"
            doc_list.append({
                "Document Type": val(_safe_get(doc, "document_type")),
                "File Name": val(doc_name.split("/")[-1] if doc_name else "-"),
                "Uploaded Date": _date_text(_safe_get(doc, "uploaded_at")),
                "Description": val(_safe_get(doc, "description")) or "-",
                "Verified": "Yes" if _safe_get(doc, "is_verified") else "No",
            })
    data["documents"] = doc_list

    return data


def build_awec_csc_style_application_pdf_response(application: Any, student_profile: Any = None, supplemental_profile: Any = None, documents: Any = None):
    """
    Django-ready PDF response. Put this file in your app, then call this function
    from a Django view after fetching the Application object.
    """
    from io import BytesIO
    from django.http import HttpResponse

    data = application_to_awec_csc_style_data(application, student_profile, supplemental_profile, documents=documents)
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


def build_empty_form_pdf_response():
    """Generate a blank application form PDF with no data for printing and manual filling."""
    from io import BytesIO
    from django.http import HttpResponse

    empty_data = deepcopy(DEFAULT_DATA)

    def _blank_all(d):
        if isinstance(d, dict):
            return {k: _blank_all(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [_blank_all(item) for item in d]
        elif isinstance(d, str):
            return ""
        return d

    # Blank all data fields but preserve organization/meta structure
    empty_data["personal"] = _blank_all(empty_data["personal"])
    empty_data["personal"]["Student Photo"] = ""
    empty_data["parents"] = _blank_all(empty_data["parents"])
    empty_data["emergency"] = _blank_all(empty_data["emergency"])
    empty_data["education_background"] = _blank_all(empty_data["education_background"])
    empty_data["higher_education"] = _blank_all(empty_data["higher_education"])
    empty_data["professional_qualifications"] = _blank_all(empty_data["professional_qualifications"])
    empty_data["english_proficiency"] = _blank_all(empty_data["english_proficiency"])
    empty_data["employment_history"] = _blank_all(empty_data["employment_history"])
    empty_data["study_preferences"] = _blank_all(empty_data["study_preferences"])
    empty_data["addresses"] = _blank_all(empty_data["addresses"])
    empty_data["other_details"] = _blank_all(empty_data["other_details"])
    empty_data["heard_about_us"] = _blank_all(empty_data["heard_about_us"])
    empty_data["declaration"] = _blank_all(empty_data["declaration"])
    empty_data["meta"]["application_id"] = "________________________"

    buffer = BytesIO()
    generate_pdf(buffer, empty_data)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = "blank_application_form.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
