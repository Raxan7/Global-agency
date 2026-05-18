from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image as PillowImage
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from student_portal.models import WorkExperience


TOTAL_PAGES = 6
INK = colors.HexColor('#0f172a')
MUTED = colors.HexColor('#475569')
BORDER = colors.HexColor('#cbd5e1')
HEADER_FILL = colors.HexColor('#eff6ff')
LABEL_FILL = colors.HexColor('#f8fafc')
BRAND_BLUE = colors.HexColor('#1d4ed8')
BRAND_ORANGE = colors.HexColor('#c2410c')
HEADER_ADDRESS_LINES = [
    'Plot 8, Block 46',
    'Kijitonyama, Mpakani Centre',
    '3rd Floor, Suite F1.01',
    'P.O. Box 34402',
    'Dar es Salaam, Tanzania',
]
TERMS_AND_CONDITIONS = [
    '1. Application Process: The agency acts only as an intermediary. Admission and visa decisions are made by institutions and immigration authorities.',
    '2. Document Authenticity: Submission of false documents leads to immediate termination without refund.',
    '3. Fees and Payments: All service and administrative fees are non-refundable unless stated otherwise.',
    '4. Visa Responsibility: Visa approval is not guaranteed by the agency.',
    '5. Refund Policy: Refunds follow written policy. Government and third-party fees are non-refundable.',
    '6. Student Responsibilities: The student must provide accurate information, meet requirements, and obey the laws of the host country.',
    '7. Changes to Application: Changes after submission may incur additional charges.',
    '8. Liability Limitation: The agency is not liable for visa refusal, admission denial, policy changes, or travel disruptions.',
    '9. Accommodation And Travel: These are subject to availability and third-party terms.',
    '10. Data Privacy: Student data may be shared with institutions and embassies for processing.',
    '11. Cancellation: The agency may cancel services if the student violates policies.',
    '12. Governing Law: This agreement is governed by the laws of the agency registration country.',
]
DECLARATION_LINES = [
    '1. Accuracy of Information: I confirm that all information provided in this application form and all supporting documents submitted are true, complete, and accurate to the best of my knowledge.',
    '2. Authorization to Process Information: I authorize Africa Western Education and its partner institutions, universities, embassies, and relevant authorities to collect, verify, process, and share my personal data and academic documents for admission, visa processing, and related services.',
    '3. Responsibility for Application Process: I understand that Africa Western Education acts as an education consultancy and recruitment agency and does not guarantee admission, scholarship, or visa approval.',
    '4. Compliance with Institutional and National Regulations: I agree to abide by all rules, regulations, policies, and laws of the country and institution where I will study.',
    '5. Admission and Program Placement: I acknowledge that the final decision regarding my admission, course, and institution will be determined by the receiving university.',
    '6. Financial Responsibility: I confirm that I am responsible for meeting the financial obligations attached to my application and study plans unless official sponsorship is confirmed.',
]


def _as_text(value, default=''):
    if value in (None, ''):
        return default
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    return str(value)


def _bool_box(value):
    return '[X]' if value else '[ ]'


def _escaped(value, default=''):
    return escape(_as_text(value, default))


def _styles():
    sample = getSampleStyleSheet()
    return {
        'tiny_center': ParagraphStyle(
            'tiny_center',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=9.2,
            leading=11.4,
            alignment=TA_CENTER,
            textColor=MUTED,
        ),
        'office': ParagraphStyle(
            'office',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=9.8,
            leading=12.8,
            alignment=TA_LEFT,
            textColor=INK,
        ),
        'title': ParagraphStyle(
            'title',
            parent=sample['Normal'],
            fontName='Helvetica-Bold',
            fontSize=18.6,
            leading=20.6,
            alignment=TA_CENTER,
            spaceAfter=4,
            textColor=INK,
        ),
        'subtitle': ParagraphStyle(
            'subtitle',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=10.5,
            leading=12.9,
            alignment=TA_CENTER,
            textColor=MUTED,
        ),
        'section': ParagraphStyle(
            'section',
            parent=sample['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12.9,
            leading=15.2,
            alignment=TA_LEFT,
            spaceAfter=5,
            textColor=BRAND_BLUE,
        ),
        'body': ParagraphStyle(
            'body',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=10.4,
            leading=13.4,
            alignment=TA_LEFT,
            textColor=INK,
        ),
        'field': ParagraphStyle(
            'field',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=10.2,
            leading=12.9,
            alignment=TA_LEFT,
            textColor=INK,
        ),
        'small': ParagraphStyle(
            'small',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=9.6,
            leading=12,
            alignment=TA_LEFT,
            textColor=MUTED,
        ),
    }


def _boxed_table(rows, widths, row_heights=None, font_size=9.9, padding=4.0, header_rows=0):
    table = Table(rows, colWidths=widths, rowHeights=row_heights)
    table_styles = [
        ('BOX', (0, 0), (-1, -1), 0.8, BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.55, BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), padding),
        ('RIGHTPADDING', (0, 0), (-1, -1), padding),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LABEL_FILL]),
    ]
    if header_rows:
        table_styles.extend(
            [
                ('BACKGROUND', (0, 0), (-1, header_rows - 1), HEADER_FILL),
                ('TEXTCOLOR', (0, 0), (-1, header_rows - 1), INK),
            ]
        )
    table.setStyle(TableStyle(table_styles))
    return table


def _field_paragraph(label, value, styles):
    text = (
        f'<font size="9.6" color="#1d4ed8"><b>{escape(label)}</b></font><br/>'
        f'<font size="10.7" color="#0f172a">{_escaped(value) or "&nbsp;"}</font>'
    )
    return Paragraph(text, styles['field'])


def _single_row_table(pairs, styles):
    rows = []
    if len(pairs) % 2:
        pairs = list(pairs) + [('', '')]
    for index in range(0, len(pairs), 2):
        left = _field_paragraph(pairs[index][0], pairs[index][1], styles)
        right = _field_paragraph(pairs[index + 1][0], pairs[index + 1][1], styles)
        rows.append([left, right])
    return _boxed_table(rows, [92 * mm, 92 * mm])


def _header(story, styles):
    story.append(
        Paragraph(
            'Website: www.africawesterneducation.com    Email: info@africawesterneducation.com    Tel: +255767688766',
            styles['tiny_center'],
        )
    )
    story.append(Paragraph('Address: Plot 8, Block 46, Kijitonyama, Mpakani Centre, 3rd Floor, Suite F1.01, Dar es Salaam', styles['tiny_center']))
    story.append(Spacer(1, 2 * mm))

    logo_path = Path(settings.BASE_DIR) / 'static' / 'global_agency' / 'img' / 'logo.png'
    logo = Image(str(logo_path), width=30 * mm, height=22 * mm) if logo_path.exists() else ''
    office_text = '<b>HEADQUARTERS OFFICE</b><br/><b>Africa Western Education Company LIMITED</b><br/>' + '<br/>'.join(HEADER_ADDRESS_LINES)
    office_text += '<br/>Website: www.africawesterneducation.com<br/>Email: info@africawesterneducation.com<br/>Tel: +255767688766'
    table = Table([[Paragraph(office_text, styles['office']), logo]], colWidths=[150 * mm, 34 * mm])
    table.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width='100%', thickness=1.2, color=BRAND_ORANGE, spaceBefore=0, spaceAfter=0))
    story.append(Spacer(1, 1.6 * mm))


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.drawString(14 * mm, 10 * mm, f'Application ID: {getattr(doc, "serial_number", "")}')
    canvas.drawCentredString(105 * mm, 10 * mm, f'Page {canvas.getPageNumber()} of {TOTAL_PAGES}')
    canvas.drawRightString(196 * mm, 10 * mm, f'Generated: {getattr(doc, "generated_date", "")}')
    canvas.restoreState()


def _photo_flowable(student_profile, styles):
    profile_picture = getattr(student_profile, 'profile_picture', None) if student_profile else None
    if profile_picture:
        try:
            profile_picture.open('rb')
            image_bytes = profile_picture.read()
            profile_picture.close()
            preview = PillowImage.open(BytesIO(image_bytes))
            width_px, height_px = preview.size
            preview.close()
            max_width = 34 * mm
            max_height = 42 * mm
            scale = min(max_width / max(width_px, 1), max_height / max(height_px, 1))
            image = Image(BytesIO(image_bytes), width=width_px * scale, height=height_px * scale)
            frame = Table([[image]], colWidths=[36 * mm], rowHeights=[44 * mm])
            frame.setStyle(
                TableStyle(
                    [
                        ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]
                )
            )
            return frame
        except Exception:
            pass

    placeholder = Table([[Paragraph('Student Photo', styles['body'])]], colWidths=[36 * mm], rowHeights=[44 * mm])
    placeholder.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.8, colors.black), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    return placeholder


def _office_value(choice_value, display_value, fallback=''):
    if display_value and display_value != '---------':
        return display_value
    return choice_value or fallback


def build_csc_style_application_pdf(application, student_profile=None, supplemental_profile=None):
    styles = _styles()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="application_{application.id}_{application.student.username}.pdf"'

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm, topMargin=10 * mm, bottomMargin=16 * mm)
    serial = getattr(supplemental_profile, 'serial_number', None) or f'AWECO/Tz/DSM/{application.id:03d}'
    generated_source = getattr(supplemental_profile, 'generated_at', None) or timezone.now()
    generated_date = timezone.localtime(generated_source).strftime('%d/%m/%Y') if timezone.is_aware(generated_source) else generated_source.strftime('%d/%m/%Y')
    doc.serial_number = serial
    doc.generated_date = generated_date

    student_name = getattr(supplemental_profile, 'full_name_passport', None) or application.student.get_full_name() or application.student.username
    gender = student_profile.get_gender_display() if student_profile and getattr(student_profile, 'gender', None) else ''
    work_experiences = list(WorkExperience.objects.filter(student=student_profile).order_by('-start_date')) if student_profile else []

    story = []

    # Page 1
    _header(story, styles)
    story.append(Paragraph('STUDY ABROAD REGISTRATION FORM', styles['title']))
    story.append(Paragraph(f'Registration Reference Number: {serial}    Application Date: {generated_date}', styles['subtitle']))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph('SECTION 1: PERSONAL DETAILS', styles['section']))
    page_one = Table(
        [[
            _single_row_table([
                ('Full Name (as in passport)', student_name),
                ('Gender', f'{_bool_box(gender == "Male")} Male   {_bool_box(gender == "Female")} Female'),
                ('Date of Birth', getattr(student_profile, 'date_of_birth', None) if student_profile else None),
                ('Place of Birth', getattr(supplemental_profile, 'place_of_birth', None)),
                ('Nationality', getattr(student_profile, 'nationality', None) if student_profile else None),
                ('Email and Phone Number', f'{application.student.email} / {getattr(student_profile, "phone_number", "")}'),
                ('Form Six (school name / address)', f'{getattr(student_profile, "alevel_school", "")} / {getattr(student_profile, "alevel_address", "")}'),
                ('Passport Number', getattr(supplemental_profile, 'passport_number', None)),
                ('Form Four (school / address / division)', f'{getattr(student_profile, "olevel_school", "")} / {getattr(student_profile, "olevel_address", "")} / {getattr(student_profile, "olevel_gpa", "")}'),
                ('Application ID', serial),
            ], styles),
            _photo_flowable(student_profile, styles),
        ]],
        colWidths=[148 * mm, 38 * mm],
    )
    page_one.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
    story.append(page_one)
    story.append(Spacer(1, 1.8 * mm))
    story.append(Paragraph('SECTION 2: PARENTS DETAILS', styles['section']))
    parent_rows = [
        [
            Paragraph('<b>Field</b>', styles['body']),
            Paragraph('<b>Father</b>', styles['body']),
            Paragraph('<b>Mother</b>', styles['body']),
        ],
        [
            Paragraph('Full Name', styles['body']),
            Paragraph(_escaped(getattr(student_profile, 'father_name', None)), styles['body']),
            Paragraph(_escaped(getattr(student_profile, 'mother_name', None)), styles['body']),
        ],
        [
            Paragraph('Address (Street/Village/House No.)', styles['body']),
            Paragraph('&nbsp;', styles['body']),
            Paragraph('&nbsp;', styles['body']),
        ],
        [
            Paragraph('Postal Code', styles['body']),
            Paragraph('&nbsp;', styles['body']),
            Paragraph('&nbsp;', styles['body']),
        ],
        [
            Paragraph('Region', styles['body']),
            Paragraph('&nbsp;', styles['body']),
            Paragraph('&nbsp;', styles['body']),
        ],
        [
            Paragraph('Occupation', styles['body']),
            Paragraph(_escaped(getattr(student_profile, 'father_occupation', None)), styles['body']),
            Paragraph(_escaped(getattr(student_profile, 'mother_occupation', None)), styles['body']),
        ],
        [
            Paragraph('Phone', styles['body']),
            Paragraph(_escaped(getattr(student_profile, 'father_phone', None)), styles['body']),
            Paragraph(_escaped(getattr(student_profile, 'mother_phone', None)), styles['body']),
        ],
        [
            Paragraph('Email', styles['body']),
            Paragraph(_escaped(getattr(student_profile, 'father_email', None)), styles['body']),
            Paragraph(_escaped(getattr(student_profile, 'mother_email', None)), styles['body']),
        ],
    ]
    story.append(_boxed_table(parent_rows, [48 * mm, 68 * mm, 68 * mm], header_rows=1))
    story.append(PageBreak())

    # Page 2
    story.append(Paragraph('SECTION 3: EMERGENCY CONTACT DETAILS', styles['section']))
    story.append(
        _single_row_table([
            ('Full Name', getattr(student_profile, 'emergency_contact', None) if student_profile else None),
            ('Relationship', getattr(student_profile, 'emergency_relation', None) if student_profile else None),
            ('Occupation', getattr(student_profile, 'emergency_occupation', None) if student_profile else None),
            ('Phone Number', getattr(student_profile, 'phone_number', None) if student_profile else None),
            ('Email Address', application.student.email),
            ('Address (Street/Village/House No.)', getattr(student_profile, 'emergency_address', None) if student_profile else None),
        ], styles)
    )
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph('SECTION 4: EDUCATION BACKGROUND DETAILS', styles['section']))
    story.append(
        _boxed_table(
            [
                [Paragraph('<b>Level</b>', styles['body']), Paragraph('<b>School Name</b>', styles['body']), Paragraph('<b>Index Number</b>', styles['body']), Paragraph('<b>Year Completed</b>', styles['body']), Paragraph('<b>Division / GPA</b>', styles['body'])],
                [Paragraph('Form Four (O-Level)', styles['body']), Paragraph(_escaped(getattr(student_profile, 'olevel_school', None)), styles['body']), Paragraph(_escaped(getattr(student_profile, 'olevel_candidate_no', None)), styles['body']), Paragraph(_escaped(getattr(student_profile, 'olevel_year', None)), styles['body']), Paragraph(_escaped(getattr(student_profile, 'olevel_gpa', None)), styles['body'])],
                [Paragraph('Form Six (A-Level)', styles['body']), Paragraph(_escaped(getattr(student_profile, 'alevel_school', None)), styles['body']), Paragraph(_escaped(getattr(student_profile, 'alevel_candidate_no', None)), styles['body']), Paragraph(_escaped(getattr(student_profile, 'alevel_year', None)), styles['body']), Paragraph(_escaped(getattr(student_profile, 'alevel_gpa', None)), styles['body'])],
            ],
            [34 * mm, 64 * mm, 30 * mm, 28 * mm, 28 * mm],
            header_rows=1,
        )
    )
    story.append(PageBreak())

    # Page 3
    story.append(Paragraph('Post-Secondary / Higher Education', styles['section']))
    story.append(
        _boxed_table(
            [
                [Paragraph('<b>Level</b>', styles['body']), Paragraph('<b>Institution</b>', styles['body']), Paragraph('<b>Field of Study</b>', styles['body']), Paragraph('<b>Year Completed</b>', styles['body']), Paragraph('<b>GPA</b>', styles['body'])],
                [Paragraph('Certificate', styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'certificate_institution', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'certificate_field_of_study', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'certificate_year_completed', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'certificate_gpa', None)), styles['body'])],
                [Paragraph('Diploma', styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'diploma_institution', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'diploma_field_of_study', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'diploma_year_completed', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'diploma_gpa', None)), styles['body'])],
                [Paragraph('Bachelor Degree', styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'bachelor_institution', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'bachelor_field_of_study', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'bachelor_year_completed', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'bachelor_gpa', None)), styles['body'])],
                [Paragraph('Master Degree', styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'master_institution', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'master_field_of_study', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'master_year_completed', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'master_gpa', None)), styles['body'])],
                [Paragraph('PhD', styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'phd_institution', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'phd_field_of_study', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'phd_year_completed', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'phd_gpa', None)), styles['body'])],
            ],
            [30 * mm, 58 * mm, 48 * mm, 26 * mm, 22 * mm],
            font_size=9.3,
            header_rows=1,
        )
    )
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph('Professional Qualifications / Training', styles['section']))
    story.append(_boxed_table([[Paragraph(_escaped(getattr(supplemental_profile, 'professional_qualifications', None)), styles['body'])]], [184 * mm], row_heights=[18 * mm]))
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph('English Language Proficiency', styles['section']))
    story.append(
        _boxed_table(
            [
                [Paragraph('<b>Test</b>', styles['body']), Paragraph('<b>Score</b>', styles['body']), Paragraph('<b>Year</b>', styles['body'])],
                [Paragraph(_escaped(getattr(supplemental_profile, 'english_test_name', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'english_test_score', None)), styles['body']), Paragraph(_escaped(getattr(supplemental_profile, 'english_test_year', None)), styles['body'])],
            ],
            [84 * mm, 50 * mm, 50 * mm],
            header_rows=1,
        )
    )
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph('SECTION 5: EMPLOYMENT HISTORY / WORK EXPERIENCE', styles['section']))
    work_rows = [
        [
            Paragraph('<b>Employer</b>', styles['body']),
            Paragraph('<b>Position</b>', styles['body']),
            Paragraph('<b>Location</b>', styles['body']),
            Paragraph('<b>Period</b>', styles['body']),
        ]
    ]
    if work_experiences:
        for experience in work_experiences[:4]:
            end_value = 'Present' if experience.currently_working else _as_text(experience.end_date)
            period = f'{_as_text(experience.start_date)} - {end_value}'
            work_rows.append(
                [
                    Paragraph(_escaped(experience.company_name), styles['body']),
                    Paragraph(_escaped(experience.position), styles['body']),
                    Paragraph(_escaped(experience.location), styles['body']),
                    Paragraph(_escaped(period), styles['body']),
                ]
            )
    else:
        work_rows.append([
            Paragraph('No work experience provided', styles['body']),
            Paragraph('&nbsp;', styles['body']),
            Paragraph('&nbsp;', styles['body']),
            Paragraph('&nbsp;', styles['body']),
        ])
    story.append(_boxed_table(work_rows, [64 * mm, 46 * mm, 40 * mm, 34 * mm], header_rows=1))
    story.append(PageBreak())

    # Page 4
    story.append(Paragraph('SECTION 6: STUDY PREFERENCES', styles['section']))
    story.append(
        _single_row_table([
            ('Preferred Country 1', getattr(student_profile, 'preferred_country_1', None) if student_profile else None),
            ('Preferred Program 1', getattr(student_profile, 'preferred_program_1', None) if student_profile else None),
            ('Preferred Country 2', getattr(student_profile, 'preferred_country_2', None) if student_profile else None),
            ('Preferred Program 2', getattr(student_profile, 'preferred_program_2', None) if student_profile else None),
            ('Preferred Country 3', getattr(student_profile, 'preferred_country_3', None) if student_profile else None),
            ('Preferred Program 3', getattr(student_profile, 'preferred_program_3', None) if student_profile else None),
        ], styles)
    )
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph('SECTION 7: CURRENT AND PERMANENT ADDRESS', styles['section']))
    story.append(
        _single_row_table([
            ('Current Address (Street/Village/House No.)', getattr(supplemental_profile, 'current_address', None) or (student_profile.address if student_profile else '')),
            ('Current Region', getattr(supplemental_profile, 'current_region', None)),
            ('Current City', getattr(supplemental_profile, 'current_city', None)),
            ('Current Country', getattr(supplemental_profile, 'current_country', None)),
            ('Current Postal Code', getattr(supplemental_profile, 'current_postal_code', None)),
            ('Permanent Address (Street/Village/House No.)', student_profile.address if student_profile else ''),
            ('Permanent Region', ''),
            ('Permanent City', ''),
            ('Permanent Country', getattr(student_profile, 'nationality', None) if student_profile else ''),
            ('Permanent Postal Code', ''),
        ], styles)
    )
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph('SECTION 8: OTHER DETAILS', styles['section']))
    story.append(
        _single_row_table([
            ('Passport Number', getattr(supplemental_profile, 'passport_number', None)),
            ('Country of Issue', getattr(supplemental_profile, 'passport_issue_country', None)),
            ('Date of Issue', getattr(supplemental_profile, 'passport_issue_date', None)),
            ('Expiry Date', getattr(supplemental_profile, 'passport_expiration_date', None)),
            ('Valid Visa?', f'{_bool_box(getattr(supplemental_profile, "has_valid_visa", None) is True)} Yes   {_bool_box(getattr(supplemental_profile, "has_valid_visa", None) is False)} No'),
            ('Visa Details', getattr(supplemental_profile, 'valid_visa_details', None)),
            ('Program Level', getattr(supplemental_profile, 'program_level', None)),
            ('Preferred Intake', getattr(supplemental_profile, 'preferred_intake', None)),
            ('Accommodation Preference', getattr(supplemental_profile, 'accommodation_preference', None)),
            ('Sponsor of Education', getattr(supplemental_profile, 'education_sponsor', None)),
            ('Estimated Budget (USD)', getattr(supplemental_profile, 'estimated_budget_usd', None)),
            ('Scholarship Applied?', _as_text(getattr(supplemental_profile, 'scholarship_applied', None))),
            ('If yes, specify', getattr(supplemental_profile, 'scholarship_details', None)),
            ('Any medical condition?', _as_text(getattr(supplemental_profile, 'has_medical_condition', None))),
            ('If yes, explain', getattr(supplemental_profile, 'medical_condition_details', None)),
            ('Special assistance required?', _as_text(getattr(supplemental_profile, 'needs_special_assistance', None))),
            ('If yes, specify', getattr(supplemental_profile, 'special_assistance_details', None)),
        ], styles)
    )
    story.append(PageBreak())

    # Page 5
    story.append(Paragraph('SECTION 9: HOW DID YOU HEAR ABOUT US?', styles['section']))
    story.append(
        _single_row_table([
            ('Source', getattr(student_profile, 'heard_about_us', None) if student_profile else ''),
            ('Other (please specify)', getattr(student_profile, 'heard_about_other', None) if student_profile else ''),
        ], styles)
    )
    story.append(Spacer(1, 1.6 * mm))
    story.append(Paragraph('SECTION 10: DECLARATION BY APPLICANT', styles['section']))
    for item in DECLARATION_LINES:
        story.append(Paragraph(escape(item), styles['body']))
        story.append(Spacer(1, 1.2 * mm))
    story.append(Spacer(1, 1.6 * mm))
    story.append(
        _single_row_table([
            ('Applicant Full Name', student_name),
            ('Date', generated_date),
            ('Signature', ''),
            ('Declaration Agreed', _as_text(getattr(supplemental_profile, 'declaration_agreed', None), 'Yes')),
        ], styles)
    )
    story.append(PageBreak())

    # Page 6
    story.append(Paragraph('TERMS AND CONDITIONS', styles['section']))
    for item in TERMS_AND_CONDITIONS:
        story.append(Paragraph(escape(item), styles['small']))
        story.append(Spacer(1, 1.1 * mm))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    response.write(buffer.getvalue())
    buffer.close()
    return response
