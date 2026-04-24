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
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from student_portal.models import Document


TOTAL_PAGES = 6


def _as_text(value, default=''):
    if value in (None, ''):
        return default
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return str(value)


def _escaped_text(value, default=''):
    return escape(_as_text(value, default=default))


def _bool_tick(value):
    return '\u2713' if bool(value) else ''


def _bool_word(value):
    if value is None:
        return ''
    return 'Yes' if value else 'No'


def _date_range(start, end):
    left = _as_text(start, default='')
    right = _as_text(end, default='')
    if left or right:
        return f'{left} -- {right}'
    return ''


def _field_cell(label, value, styles, default=''):
    return Paragraph(
        (
            f'<font size="7.2" color="#555555">{escape(label)}</font><br/>'
            f'<font size="9"><b>{_escaped_text(value, default=default) or "&nbsp;"}</b></font>'
        ),
        styles['field'],
    )


def _single_line_cell(label, value, styles, default=''):
    return Paragraph(
        (
            f'<font size="7.2" color="#555555">{escape(label)}</font> '
            f'<font size="9"><b>{_escaped_text(value, default=default) or "&nbsp;"}</b></font>'
        ),
        styles['field'],
    )


def _boxed_table(rows, col_widths, row_heights=None, font_size=8.6, padding=4):
    table = Table(rows, colWidths=col_widths, rowHeights=row_heights)
    table.setStyle(
        TableStyle(
            [
                ('GRID', (0, 0), (-1, -1), 0.7, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), padding),
                ('RIGHTPADDING', (0, 0), (-1, -1), padding),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), font_size),
            ]
        )
    )
    return table


def _pairs_table(pairs, styles, col_widths=None):
    if col_widths is None:
        col_widths = [92 * mm, 92 * mm]

    rows = []
    working = list(pairs)
    if len(working) % 2:
        working.append(('', ''))

    for index in range(0, len(working), 2):
        left_label, left_value = working[index]
        right_label, right_value = working[index + 1]
        rows.append(
            [
                _field_cell(left_label, left_value, styles),
                _field_cell(right_label, right_value, styles),
            ]
        )

    return _boxed_table(rows, col_widths)


def _section_heading(text, styles):
    return Paragraph(text, styles['section'])


def _subsection_heading(text, styles):
    return Paragraph(text, styles['subsection'])


def _build_styles():
    sample = getSampleStyleSheet()
    return {
        'topline': ParagraphStyle(
            'Topline',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=7.8,
            leading=9.4,
            alignment=TA_CENTER,
            textColor=colors.black,
        ),
        'office_label': ParagraphStyle(
            'OfficeLabel',
            parent=sample['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.4,
            leading=10.4,
            alignment=TA_LEFT,
            textColor=colors.black,
        ),
        'office_body': ParagraphStyle(
            'OfficeBody',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=8.1,
            leading=10,
            alignment=TA_LEFT,
            textColor=colors.black,
        ),
        'header_title': ParagraphStyle(
            'HeaderTitle',
            parent=sample['Normal'],
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=2,
        ),
        'header_meta': ParagraphStyle(
            'HeaderMeta',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=8.2,
            leading=10.2,
            alignment=TA_LEFT,
            textColor=colors.black,
        ),
        'header_subtitle': ParagraphStyle(
            'HeaderSubtitle',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=8.6,
            leading=10.5,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=3,
        ),
        'form_title': ParagraphStyle(
            'FormTitle',
            parent=sample['Normal'],
            fontName='Helvetica-Bold',
            fontSize=15.4,
            leading=17,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=4,
        ),
        'section': ParagraphStyle(
            'Section',
            parent=sample['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11.2,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceAfter=3,
        ),
        'subsection': ParagraphStyle(
            'Subsection',
            parent=sample['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9.3,
            leading=11,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceAfter=2,
            spaceBefore=4,
        ),
        'field': ParagraphStyle(
            'Field',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=8.7,
            leading=10.1,
            alignment=TA_LEFT,
            textColor=colors.black,
        ),
        'body': ParagraphStyle(
            'Body',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=10.5,
            alignment=TA_LEFT,
            textColor=colors.black,
        ),
        'small': ParagraphStyle(
            'Small',
            parent=sample['Normal'],
            fontName='Helvetica',
            fontSize=7.4,
            leading=9.2,
            alignment=TA_LEFT,
            textColor=colors.black,
        ),
        'agree': ParagraphStyle(
            'Agree',
            parent=sample['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9.4,
            leading=11.5,
            alignment=TA_LEFT,
            textColor=colors.black,
        ),
    }


def _build_header(story, styles):
    story.append(
        Paragraph(
            'Website: www.africawesterneducation.com    Email: info@africawesterneducation.com    Tel: +255767688766    Address: Victoria, Noble Centre, Kinondoni, Dar es Salaam',
            styles['topline'],
        )
    )
    story.append(Spacer(1, 2 * mm))

    logo_path = Path(settings.BASE_DIR) / 'static' / 'global_agency' / 'img' / 'logo.png'
    if logo_path.exists():
        logo_flowable = Image(str(logo_path), width=34 * mm, height=24 * mm)
    else:
        logo_flowable = ''

    office_text = (
        '<b>HEADQUARTERS OFFICE</b><br/>'
        '<b>Africa Western Education Company LIMITED</b><br/>'
        'P.O. BOX 36098 Dar es Salaam<br/>'
        'Website: www.africawesterneducation.com<br/>'
        'Email: info@africawesterneducation.com<br/>'
        'Tel: +255767688766<br/>'
        'Office Address: Victoria, NOBLE CENTRE, Kinondoni'
    )
    header_table = Table(
        [[Paragraph(office_text, styles['office_body']), logo_flowable]],
        colWidths=[148 * mm, 36 * mm],
    )
    header_table.setStyle(
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
    story.append(header_table)
    story.append(Spacer(1, 1.8 * mm))
    story.append(
        Paragraph(
            '<font color="#1c7c41">________________________________________________________________________________</font>',
            styles['header_subtitle'],
        )
    )
    story.append(Spacer(1, 1.4 * mm))


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    serial = getattr(doc, 'serial_number', '')
    generated = getattr(doc, 'generated_date', '')

    canvas.drawString(15 * mm, 10 * mm, f'Serial Number: {serial}')
    canvas.drawCentredString(105 * mm, 10 * mm, f'Page {canvas.getPageNumber()} of {TOTAL_PAGES}')
    canvas.drawRightString(195 * mm, 10 * mm, f'Generated: {generated}')
    canvas.restoreState()


def _photo_flowable(student_profile, styles):
    profile_picture = getattr(student_profile, 'profile_picture', None) if student_profile else None
    if profile_picture:
        try:
            profile_picture.open('rb')
            image_bytes = profile_picture.read()
            profile_picture.close()
            if image_bytes:
                preview = PillowImage.open(BytesIO(image_bytes))
                width_px, height_px = preview.size
                preview.close()

                max_width = 34 * mm
                max_height = 42 * mm
                scale = min(max_width / max(width_px, 1), max_height / max(height_px, 1))
                render_width = width_px * scale
                render_height = height_px * scale
                image = Image(BytesIO(image_bytes), width=render_width, height=render_height)
                image.hAlign = 'CENTER'

                frame = Table([[image]], colWidths=[34 * mm], rowHeights=[42 * mm])
                frame.setStyle(
                    TableStyle(
                        [
                            ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 2),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                            ('TOPPADDING', (0, 0), (-1, -1), 2),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                        ]
                    )
                )
                return frame
        except Exception:
            pass

    placeholder = Table(
        [[Paragraph('<font size="8">Student Photo</font>', styles['body'])]],
        colWidths=[34 * mm],
        rowHeights=[42 * mm],
    )
    placeholder.setStyle(
        TableStyle(
            [
                ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]
        )
    )
    return placeholder


def _document_type_names(documents):
    return {document.document_type for document in documents}


def _has_document(documents_by_type, *doc_types):
    return any(doc_type in documents_by_type for doc_type in doc_types)


def build_csc_style_application_pdf(application, student_profile=None, supplemental_profile=None):
    styles = _build_styles()
    documents = list(Document.objects.filter(student=application.student).order_by('-uploaded_at'))
    documents_by_type = _document_type_names(documents)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="application_{application.id}_{application.student.username}.pdf"'
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=16 * mm,
    )

    serial = (
        getattr(supplemental_profile, 'serial_number', None)
        or f'AWECO/Tz/DSM/{application.id:03d}'
    )
    generated_source = getattr(supplemental_profile, 'generated_at', None) or timezone.now()
    if timezone.is_aware(generated_source):
        generated_date = timezone.localtime(generated_source).strftime('%Y-%m-%d')
    else:
        generated_date = generated_source.strftime('%Y-%m-%d')
    doc.serial_number = serial
    doc.generated_date = generated_date

    student_name = application.student.get_full_name() or application.student.username
    first_name = application.student.first_name or ''
    last_name = application.student.last_name or ''
    gender_value = ''
    if student_profile and getattr(student_profile, 'gender', None):
        gender_value = student_profile.get_gender_display()

    agency_name = getattr(supplemental_profile, 'agency_name', None) or 'Africa Western Education Company Ltd'

    story = []

    # Page 1
    _build_header(story, styles)
    story.append(Paragraph('STUDY ABROAD REGISTRATION FORM', styles['form_title']))
    story.append(
        Paragraph(
            f'Registration Reference Number: {serial}    Application Date: {generated_date}',
            styles['header_subtitle'],
        )
    )
    story.append(_section_heading('Personal Information', styles))

    top_row = Table(
        [[
            _field_cell('Agency No.', getattr(supplemental_profile, 'agency_no', None), styles),
            _field_cell('Agency Name', agency_name, styles),
            _photo_flowable(student_profile, styles),
        ]],
        colWidths=[28 * mm, 108 * mm, 38 * mm],
        rowHeights=[46 * mm],
    )
    top_row.setStyle(
        TableStyle(
            [
                ('GRID', (0, 0), (-1, -1), 0.7, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('ALIGN', (2, 0), (2, 0), 'CENTER'),
            ]
        )
    )
    story.append(top_row)
    story.append(Spacer(1, 2.2 * mm))

    page1_pairs = [
        ('Surname', getattr(supplemental_profile, 'surname', None) or last_name),
        ('Given Name', getattr(supplemental_profile, 'given_name', None) or first_name),
        ('Chinese Name', getattr(supplemental_profile, 'chinese_name', None)),
        ('Gender', gender_value),
        ('Date of Birth', getattr(student_profile, 'date_of_birth', None) if student_profile else None),
        ('Marital Status', getattr(supplemental_profile, 'marital_status', None)),
        ('Nationality', getattr(student_profile, 'nationality', None) if student_profile else None),
        ('Native Language', getattr(supplemental_profile, 'native_language', None)),
        ('Passport No.', getattr(supplemental_profile, 'passport_no', None)),
        ('Date of Expiration', getattr(supplemental_profile, 'passport_expiration_date', None)),
        ('Country of Birth', getattr(supplemental_profile, 'country_of_birth', None)),
        ('City of Birth', getattr(supplemental_profile, 'city_of_birth', None)),
        ('Religion', getattr(supplemental_profile, 'religion', None)),
        ('Personal Contact Phone No.', getattr(supplemental_profile, 'personal_phone', None) or (student_profile.phone_number if student_profile else '')),
        ('Personal Contact Email', getattr(supplemental_profile, 'personal_email', None) or application.student.email),
        ('Personal Contact Alternate Email', getattr(supplemental_profile, 'alternate_email', None)),
        ('Personal Contact WeChat ID', getattr(supplemental_profile, 'wechat_id', None)),
        ('Personal Contact SKYPE No.', getattr(supplemental_profile, 'skype_no', None)),
        ('Personal Contact Correspondence Address', getattr(supplemental_profile, 'correspondence_address', None) or (student_profile.address if student_profile else '')),
        ('Emergency Contact Name', getattr(supplemental_profile, 'emergency_contact_name', None) or (student_profile.emergency_contact if student_profile else '')),
        ('Emergency Contact Gender', getattr(supplemental_profile, 'emergency_contact_gender', None)),
        ('Relation to the Applicant', getattr(supplemental_profile, 'emergency_contact_relation', None) or (student_profile.emergency_relation if student_profile else '')),
        ('Emergency Contact Phone No.', getattr(supplemental_profile, 'emergency_contact_phone', None)),
        ('Emergency Contact Email', getattr(supplemental_profile, 'emergency_contact_email', None)),
        ('Emergency Contact Correspondence Address', getattr(supplemental_profile, 'emergency_contact_address', None)),
        ('Application ID', serial),
    ]
    story.append(_pairs_table(page1_pairs, styles))
    story.append(Spacer(1, 1.8 * mm))

    story.append(
        _boxed_table(
            [[
                _single_line_cell('CSC NO.', '', styles),
                _single_line_cell('Dispatch Category', '', styles),
                _single_line_cell('Student Category', '', styles),
                _single_line_cell('Funding Method', '', styles),
            ]],
            [46 * mm, 46 * mm, 46 * mm, 46 * mm],
            row_heights=[11 * mm],
        )
    )
    story.append(Spacer(1, 1.4 * mm))
    story.append(Paragraph('(The above table is only for CSC)', styles['small']))
    story.append(PageBreak())

    # Page 2
    _build_header(story, styles)
    story.append(_section_heading('Education and Employment History', styles))

    story.append(_subsection_heading('Highest/Current Education', styles))
    story.append(
        _pairs_table(
            [
                ('Education Level', getattr(supplemental_profile, 'highest_education_level', None)),
                ('Country of the Institute', getattr(supplemental_profile, 'highest_education_country', None)),
                ('Institute Name', getattr(supplemental_profile, 'highest_education_institute', None)),
                ('Years Attended', _date_range(
                    getattr(supplemental_profile, 'highest_education_start_date', None),
                    getattr(supplemental_profile, 'highest_education_end_date', None),
                )),
                ('Field of Study', getattr(supplemental_profile, 'highest_education_field_of_study', None)),
                ('Qualification (eg. BA. BSc)', getattr(supplemental_profile, 'highest_education_qualification', None)),
            ],
            styles,
        )
    )

    story.append(_subsection_heading('Other Education Certificates I', styles))
    story.append(
        _pairs_table(
            [
                ('Education Level', getattr(supplemental_profile, 'other_education_1_level', None) or 'Advanced Level'),
                ('Country of the Institute', getattr(supplemental_profile, 'other_education_1_country', None) or (student_profile.alevel_country if student_profile else '')),
                ('Institute Name', getattr(supplemental_profile, 'other_education_1_institute', None) or (student_profile.alevel_school if student_profile else '')),
                ('Years Attended', _date_range(
                    getattr(supplemental_profile, 'other_education_1_start_date', None),
                    getattr(supplemental_profile, 'other_education_1_end_date', None),
                )),
                ('Field of Study', getattr(supplemental_profile, 'other_education_1_field_of_study', None)),
                ('Qualification (eg. BA. BSc)', getattr(supplemental_profile, 'other_education_1_qualification', None) or 'Advanced Level'),
            ],
            styles,
        )
    )

    story.append(_subsection_heading('Other Education Certificates II', styles))
    story.append(
        _pairs_table(
            [
                ('Education Level', getattr(supplemental_profile, 'other_education_2_level', None) or 'Ordinary Level'),
                ('Country of the Institute', getattr(supplemental_profile, 'other_education_2_country', None) or (student_profile.olevel_country if student_profile else '')),
                ('Institute Name', getattr(supplemental_profile, 'other_education_2_institute', None) or (student_profile.olevel_school if student_profile else '')),
                ('Years Attended', _date_range(
                    getattr(supplemental_profile, 'other_education_2_start_date', None),
                    getattr(supplemental_profile, 'other_education_2_end_date', None),
                )),
                ('Field of Study', getattr(supplemental_profile, 'other_education_2_field_of_study', None)),
                ('Qualification (eg. BA. BSc)', getattr(supplemental_profile, 'other_education_2_qualification', None) or 'Ordinary Level'),
            ],
            styles,
        )
    )

    story.append(_subsection_heading('Employment History', styles))
    story.append(
        _pairs_table(
            [
                ('Employer', getattr(supplemental_profile, 'employer', None)),
                ('Employment Duration', _date_range(
                    getattr(supplemental_profile, 'employment_start_date', None),
                    getattr(supplemental_profile, 'employment_end_date', None),
                )),
                ('Work Engaged', getattr(supplemental_profile, 'work_engaged', None)),
                ('Title & Position', getattr(supplemental_profile, 'title_position', None)),
            ],
            styles,
        )
    )
    story.append(PageBreak())

    # Page 3
    _build_header(story, styles)
    story.append(_section_heading('Language Proficiency and Study Plan', styles))

    story.append(
        _pairs_table(
            [
                ('Chinese Proficiency', getattr(supplemental_profile, 'chinese_proficiency', None)),
                ('Whether holding a HSK certificate or not?', _bool_word(getattr(supplemental_profile, 'has_hsk_certificate', None))),
                ('Level of Obtained HSK Certificate', getattr(supplemental_profile, 'hsk_level', None)),
                ('Score Obtained', getattr(supplemental_profile, 'hsk_score', None)),
                ('Test Date', getattr(supplemental_profile, 'hsk_test_date', None)),
                ('English Proficiency', getattr(supplemental_profile, 'english_proficiency', None)),
                ('Whether holding a certificate of English proficiency?', _bool_word(getattr(supplemental_profile, 'has_english_certificate', None))),
                ('Name of the Test', getattr(supplemental_profile, 'english_test_name', None)),
                ('Score Obtained', getattr(supplemental_profile, 'english_test_score', None)),
                ('Test Date', getattr(supplemental_profile, 'english_test_date', None)),
                ('Apply as', getattr(supplemental_profile, 'apply_as', None) or application.get_application_type_display()),
                ('Preferred Teaching Language', getattr(supplemental_profile, 'preferred_teaching_language', None)),
                ('Whether holding a pre-admission letter?', _bool_word(getattr(supplemental_profile, 'has_pre_admission_letter', None))),
                ('Preferences of Institute I', getattr(supplemental_profile, 'institute_preference_1', None) or application.university_name),
                ('Disciplines', getattr(supplemental_profile, 'discipline_1', None)),
                ('Majors', getattr(supplemental_profile, 'major_1', None) or application.course),
                ('Preferences of Institute II', getattr(supplemental_profile, 'institute_preference_2', None)),
                ('Disciplines', getattr(supplemental_profile, 'discipline_2', None)),
                ('Majors', getattr(supplemental_profile, 'major_2', None)),
                ('Preferences of Institute III', getattr(supplemental_profile, 'institute_preference_3', None)),
                ('Disciplines', getattr(supplemental_profile, 'discipline_3', None)),
                ('Majors', getattr(supplemental_profile, 'major_3', None)),
                ('Duration of Major Study', _date_range(
                    getattr(supplemental_profile, 'major_study_start_date', None),
                    getattr(supplemental_profile, 'major_study_end_date', None),
                )),
                ('Ever studied or worked in China?', _bool_word(getattr(supplemental_profile, 'ever_studied_or_worked_in_china', None))),
                ('Institute or Employer', getattr(supplemental_profile, 'china_institute_or_employer', None)),
                ('Employment Duration', _date_range(
                    getattr(supplemental_profile, 'china_employment_start_date', None),
                    getattr(supplemental_profile, 'china_employment_end_date', None),
                )),
                ('Ever studied in China under a Chinese Government Scholarship?', _bool_word(getattr(supplemental_profile, 'ever_had_chinese_government_scholarship', None))),
                ('Institute Name', getattr(supplemental_profile, 'previous_csc_institute_name', None)),
                ('Employment Duration', _date_range(
                    getattr(supplemental_profile, 'previous_csc_start_date', None),
                    getattr(supplemental_profile, 'previous_csc_end_date', None),
                )),
            ],
            styles,
        )
    )
    story.append(PageBreak())

    # Page 4
    _build_header(story, styles)
    story.append(_section_heading('Other Contacts', styles))

    story.append(
        _pairs_table(
            [
                ('Name of Contact Person or Organization in China', getattr(supplemental_profile, 'contact_person_china_name', None)),
                ('Tel', getattr(supplemental_profile, 'contact_person_china_tel', None)),
                ('E-mail', getattr(supplemental_profile, 'contact_person_china_email', None)),
                ('Fax', getattr(supplemental_profile, 'contact_person_china_fax', None)),
                ('Address', getattr(supplemental_profile, 'contact_person_china_address', None)),
                ("Spouse's Name", getattr(supplemental_profile, 'spouse_name', None)),
                ("Spouse's Age", getattr(supplemental_profile, 'spouse_age', None)),
                ("Spouse's Occupation", getattr(supplemental_profile, 'spouse_occupation', None)),
                ("Father's Name", getattr(supplemental_profile, 'father_name', None) or (student_profile.father_name if student_profile else '')),
                ("Father's Age", getattr(supplemental_profile, 'father_age', None)),
                ("Father's Occupation", getattr(supplemental_profile, 'father_occupation', None) or (student_profile.father_occupation if student_profile else '')),
                ("Mother's Name", getattr(supplemental_profile, 'mother_name', None) or (student_profile.mother_name if student_profile else '')),
                ("Mother's Age", getattr(supplemental_profile, 'mother_age', None)),
                ("Mother's Occupation", getattr(supplemental_profile, 'mother_occupation', None) or (student_profile.mother_occupation if student_profile else '')),
            ],
            styles,
        )
    )
    story.append(PageBreak())

    # Page 5
    _build_header(story, styles)
    story.append(_section_heading('Supporting Documents', styles))

    other_attachment_names = []
    if _has_document(documents_by_type, 'application_form'):
        other_attachment_names.append('Application Form')
    if _has_document(documents_by_type, 'proof_of_funds', 'financial_documents'):
        other_attachment_names.append('Proof of Funds')
    if _has_document(documents_by_type, 'health_insurance'):
        other_attachment_names.append('Health Insurance')
    if getattr(supplemental_profile, 'other_attachments_description', None):
        other_attachment_names.append(getattr(supplemental_profile, 'other_attachments_description'))

    support_lines = [
        f'{_bool_tick(getattr(supplemental_profile, "has_passport_photo", None) or _has_document(documents_by_type, "passport_photo") or bool(getattr(student_profile, "profile_picture", None)))} Passport/Visa Style Photo',
        f'{_bool_tick(getattr(supplemental_profile, "has_highest_education_certificate", None) or _has_document(documents_by_type, "degree_certificate", "ordinary_level", "advanced_level"))} Certificates of Highest Education (Notarized Copy)',
        f'{_bool_tick(getattr(supplemental_profile, "has_highest_education_transcript", None) or _has_document(documents_by_type, "academic_transcript"))} Transcripts of Highest Education (Notarized Copy)',
        f'{_bool_tick(getattr(supplemental_profile, "has_study_plan", None) or _has_document(documents_by_type, "sop"))} Study Plan',
        f'{_bool_tick(getattr(supplemental_profile, "has_reference_1", None) or _has_document(documents_by_type, "recommendation_letter"))} Reference I',
        f'{_bool_tick(getattr(supplemental_profile, "has_reference_2", None) or _has_document(documents_by_type, "recommendation_letter"))} Reference II',
        f'{_bool_tick(getattr(supplemental_profile, "has_passport_home_page", None) or _has_document(documents_by_type, "passport"))} Passport Home Page',
        f'{_bool_tick(getattr(supplemental_profile, "has_physical_exam_record", None))} Physical Examination Record for Foreigner',
        f'{_bool_tick(getattr(supplemental_profile, "has_articles_or_papers", None))} Articles or Papers Written or Published',
        f'{_bool_tick(getattr(supplemental_profile, "has_art_music_examples", None))} Examples of Art and Music Work',
        f'{_bool_tick(getattr(supplemental_profile, "has_chinese_language_certificate", None))} Chinese Language Proficiency Certificate',
        f'{_bool_tick(getattr(supplemental_profile, "has_english_language_certificate", None) or _has_document(documents_by_type, "language_test"))} English Language Proficiency Certificate',
        f'{_bool_tick(getattr(supplemental_profile, "has_csca_score_report", None))} CSCA Score Report (Applicants for bachelor\'s degree)',
        f'{_bool_tick(getattr(supplemental_profile, "has_pre_admission_letter_document", None))} Pre-admission Letter',
        f'{_bool_tick(getattr(supplemental_profile, "has_non_criminal_record", None))} Non-Criminal Record Report',
        f'{_bool_tick(getattr(supplemental_profile, "has_other_attachments", None) or bool(other_attachment_names))} Other Attachments: {"; ".join(other_attachment_names)}',
    ]

    support_rows = [[Paragraph(escape(line), styles['body'])] for line in support_lines]
    story.append(_boxed_table(support_rows, [184 * mm], font_size=8.2, padding=5))
    story.append(Spacer(1, 2.2 * mm))
    story.append(
        Paragraph(
            'Note: All supporting documents uploaded must be clear scanning copies of the original documents. Each set of complete materials should not exceed 20 pages. Please use DIN A4.',
            styles['small'],
        )
    )
    story.append(Spacer(1, 2.2 * mm))
    story.append(_section_heading('I Hereby Declare That', styles))

    declaration_lines = [
        'All information and supporting documentation provided for this application are complete, true and correct.',
        'During my stay in China, I shall abide by the laws and decrees of the Chinese government and will not participate in activities deemed adverse to the social order of China or inappropriate to my capacity as a student.',
        'I agree to the arrangements of my institution and specialty of study in China made by CSC and will not request changes in these two fields without valid reasons.',
        'During my study in China, I shall abide by the rules and regulations of the host university, concentrate on my studies and researches, and follow the teaching programs arranged by the university.',
        'I shall complete the procedures of the Annual Review of Chinese Government Scholarship Status as required.',
        'I shall return to my home country as soon as I complete my scheduled program in China and will not extend my stay without valid reasons.',
        'If I violate any of the above, I will not lodge an appeal against the decision of CSC on suspending or withdrawing my scholarship, or other penalties.',
    ]
    for entry in declaration_lines:
        story.append(Paragraph(f'• {escape(entry)}', styles['body']))
        story.append(Spacer(1, 0.8 * mm))
    story.append(PageBreak())

    # Page 6
    _build_header(story, styles)
    story.append(_section_heading('Applicant Declaration of Government Scholarship Information System', styles))
    story.append(Paragraph('China Scholarship Council (CSC)', styles['subsection']))
    story.append(
        Paragraph(
            'Welcome to the Chinese Government Scholarship Information System. Before proceeding, please carefully review the following terms. By agreeing and submitting your application through this system, you consent to these provisions, comply with relevant policies, and authorize the use of your personal information and application materials for scholarship processing.',
            styles['body'],
        )
    )
    story.append(Spacer(1, 2 * mm))

    declaration_items = [
        'Upon registration, you will be assigned a user account. Please safeguard your account and password. You bear responsibility for activities under your account.',
        'You are fully responsible for the authenticity, legality, validity, and accuracy of all submitted information and materials. False or misleading submissions may lead to disqualification.',
        'During studies in China, holding multiple scholarships from Chinese governments or institutions is prohibited. CSC reserves the right to revoke scholarships if violations are confirmed.',
        'Within each enrollment year, each applicant may submit no more than 3 applications, including a maximum of 2 Type A and 1 Type B applications, subject to CSC policy.',
        'Admission results will be notified by the designated application agency. CSC does not relay review progress or admission decisions directly to applicants.',
        'CSC safeguards users\' personal information and uses physical, technical, and administrative security measures to prevent unauthorized access, disclosure, alteration, damage, or loss.',
    ]
    for index, entry in enumerate(declaration_items, start=1):
        story.append(Paragraph(f'{index}. {escape(entry)}', styles['body']))
        story.append(Spacer(1, 1.2 * mm))

    agreed = getattr(supplemental_profile, 'declaration_agreed', None)
    if agreed is None:
        agreed = True
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            f'{_bool_tick(agreed)} I confirm that I have read and AGREE to all terms in the Applicant Declaration.',
            styles['agree'],
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(_boxed_table(
        [
            [
                _single_line_cell('Application ID', serial, styles),
                _single_line_cell('Applicant', student_name, styles),
            ]
        ],
        [92 * mm, 92 * mm],
        row_heights=[12 * mm],
    ))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)

    response.write(buffer.getvalue())
    buffer.close()
    return response
