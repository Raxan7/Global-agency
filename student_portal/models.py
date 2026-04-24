from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from globalagency_project.storage import PdfFriendlyCloudinaryStorage

class StudentProfile(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Basic Information
    phone_number = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True, default="Tanzanian")
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    
    # Parents Details
    father_name = models.CharField(max_length=150, blank=True)
    father_phone = models.CharField(max_length=50, blank=True)
    father_email = models.EmailField(blank=True)
    father_occupation = models.CharField(max_length=150, blank=True)
    
    mother_name = models.CharField(max_length=150, blank=True)
    mother_phone = models.CharField(max_length=50, blank=True)
    mother_email = models.EmailField(blank=True)
    mother_occupation = models.CharField(max_length=150, blank=True)
    
    # O-Level Education
    olevel_school = models.CharField(max_length=150, blank=True)
    olevel_country = models.CharField(max_length=100, blank=True, default="Tanzania")
    olevel_address = models.CharField(max_length=255, blank=True)
    olevel_region = models.CharField(max_length=100, blank=True)
    olevel_year = models.CharField(max_length=10, blank=True)
    olevel_candidate_no = models.CharField(max_length=50, blank=True)
    olevel_gpa = models.CharField(max_length=20, blank=True)
    
    # A-Level Education
    alevel_school = models.CharField(max_length=150, blank=True)
    alevel_country = models.CharField(max_length=100, blank=True, default="Tanzania")
    alevel_address = models.CharField(max_length=255, blank=True)
    alevel_region = models.CharField(max_length=100, blank=True)
    alevel_year = models.CharField(max_length=10, blank=True)
    alevel_candidate_no = models.CharField(max_length=50, blank=True)
    alevel_gpa = models.CharField(max_length=20, blank=True)
    
    # Study Preferences
    preferred_country_1 = models.CharField(max_length=100, blank=True)
    preferred_country_2 = models.CharField(max_length=100, blank=True)
    preferred_country_3 = models.CharField(max_length=100, blank=True)
    preferred_country_4 = models.CharField(max_length=100, blank=True)
    preferred_program_1 = models.CharField(max_length=100, blank=True)
    preferred_program_2 = models.CharField(max_length=100, blank=True)
    preferred_program_3 = models.CharField(max_length=100, blank=True)
    preferred_program_4 = models.CharField(max_length=100, blank=True)
    
    # Emergency Contact
    emergency_contact = models.CharField(max_length=150, blank=True)
    emergency_address = models.TextField(blank=True)
    emergency_occupation = models.CharField(max_length=100, blank=True)
    emergency_gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    emergency_relation = models.CharField(max_length=100, blank=True)
    heard_about_us = models.CharField(max_length=100, blank=True)
    heard_about_other = models.CharField(max_length=255, blank=True)
    
    # Profile Completion Tracking
    personal_details_complete = models.BooleanField(default=False)
    parents_details_complete = models.BooleanField(default=False)
    academic_qualifications_complete = models.BooleanField(default=False)
    study_preferences_complete = models.BooleanField(default=False)
    emergency_contact_complete = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"
    
    def is_complete(self):
        """Check if all required profile sections are complete"""
        section_flags = self.get_completion_flags()
        return all([
            section_flags['personal_details_complete'],
            section_flags['academic_qualifications_complete'],
            section_flags['emergency_contact_complete'],
        ])

    def get_completion_flags(self):
        """Compute section completion directly from profile field values."""
        personal_complete = all([
            self.phone_number,
            self.address,
            self.nationality,
            self.gender,
        ])

        has_parent_info = bool(self.father_name or self.mother_name)
        has_guardian_info = bool(self.emergency_contact and self.emergency_relation)
        parents_complete = has_parent_info or has_guardian_info

        # Accept either strong O-Level data or strong A-Level data.
        has_olevel = all([self.olevel_school, self.olevel_year, self.olevel_gpa])
        has_alevel = all([self.alevel_school, self.alevel_year, self.alevel_gpa])
        academic_complete = has_olevel or has_alevel

        study_complete = bool(self.preferred_country_1 and self.preferred_program_1)
        emergency_complete = all([
            self.emergency_contact,
            self.emergency_address,
            self.emergency_relation,
        ])

        return {
            'personal_details_complete': personal_complete,
            'parents_details_complete': parents_complete,
            'academic_qualifications_complete': academic_complete,
            'study_preferences_complete': study_complete,
            'emergency_contact_complete': emergency_complete,
        }

    def get_completion_status(self):
        """Return computed section flags and percentage for UI/PDF use."""
        flags = self.get_completion_flags()
        sections = [
            flags['personal_details_complete'],
            flags['parents_details_complete'],
            flags['academic_qualifications_complete'],
            flags['study_preferences_complete'],
            flags['emergency_contact_complete'],
        ]
        completed = sum(1 for section in sections if section)
        percentage = int((completed / len(sections)) * 100)
        return {
            **flags,
            'percentage': percentage,
        }
    
    def get_completion_percentage(self):
        """Calculate profile completion percentage"""
        return self.get_completion_status()['percentage']
    
    def save(self, *args, **kwargs):
        # Keep stored completion flags synchronized for legacy consumers.
        flags = self.get_completion_flags()
        self.personal_details_complete = flags['personal_details_complete']
        self.parents_details_complete = flags['parents_details_complete']
        self.academic_qualifications_complete = flags['academic_qualifications_complete']
        self.study_preferences_complete = flags['study_preferences_complete']
        self.emergency_contact_complete = flags['emergency_contact_complete']

        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            completion_fields = {
                'personal_details_complete',
                'parents_details_complete',
                'academic_qualifications_complete',
                'study_preferences_complete',
                'emergency_contact_complete',
            }
            kwargs['update_fields'] = set(update_fields).union(completion_fields)
        
        super().save(*args, **kwargs)


# ADD THIS WORK EXPERIENCE MODEL
class WorkExperience(models.Model):
    """Work experience entries for students"""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='work_experiences')
    company_name = models.CharField(max_length=200)
    position = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    currently_working = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    responsibilities = models.TextField(blank=True, null=True)
    achievements = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Work Experience'
        verbose_name_plural = 'Work Experiences'
        
    def __str__(self):
        return f"{self.position} at {self.company_name} - {self.student.user.get_full_name()}"
    
    @property
    def duration(self):
        """Calculate duration in years and months"""
        if not self.start_date:
            return "Not specified"
        
        end = self.end_date
        if self.currently_working:
            end = timezone.now().date()
        
        if not end:
            return "Present"
        
        years = end.year - self.start_date.year
        months = end.month - self.start_date.month
        
        if months < 0:
            years -= 1
            months += 12
            
        if years > 0 and months > 0:
            return f"{years} year{'s' if years > 1 else ''} {months} month{'s' if months > 1 else ''}"
        elif years > 0:
            return f"{years} year{'s' if years > 1 else ''}"
        elif months > 0:
            return f"{months} month{'s' if months > 1 else ''}"
        else:
            return "Less than a month"


class Application(models.Model):
    APPLICATION_STATUS = [
        ('pending_payment', 'Pending Payment'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('selected', 'Selected'),
    ]
    
    APPLICATION_TYPES = [
        ('university', 'University Application'),
        ('visa', 'Visa Application'),
        ('scholarship', 'Scholarship'),
        ('loan', 'Student Loan'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('not_paid', 'Not Paid'),
        ('pending_verification', 'Pending Verification'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    application_type = models.CharField(max_length=20, choices=APPLICATION_TYPES)
    university_name = models.CharField(max_length=255, blank=True)
    course = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default='pending_payment')
    submission_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_paid = models.BooleanField(default=False)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    
    # M-PESA Payment Tracking
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default='not_paid')
    mpesa_account_name = models.CharField(max_length=150, blank=True, help_text="Name on M-PESA account used for payment")
    payment_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_payments')
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    payment_notes = models.TextField(blank=True, help_text="Employee notes about payment verification")

    def __str__(self):
        return f"{self.get_application_type_display()} - {self.student.username}"


class ApplicationSupplementalProfile(models.Model):
    """CSC-style supplemental application data; additive and migration-safe."""

    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name='supplemental_profile',
    )

    # Page 1: Personal Information
    agency_no = models.CharField(max_length=50, null=True, blank=True)
    agency_name = models.CharField(max_length=255, null=True, blank=True)
    surname = models.CharField(max_length=100, null=True, blank=True)
    given_name = models.CharField(max_length=150, null=True, blank=True)
    chinese_name = models.CharField(max_length=150, null=True, blank=True)
    marital_status = models.CharField(max_length=50, null=True, blank=True)
    native_language = models.CharField(max_length=100, null=True, blank=True)
    passport_no = models.CharField(max_length=100, null=True, blank=True)
    passport_expiration_date = models.DateField(null=True, blank=True)
    country_of_birth = models.CharField(max_length=100, null=True, blank=True)
    city_of_birth = models.CharField(max_length=100, null=True, blank=True)
    religion = models.CharField(max_length=100, null=True, blank=True)
    personal_phone = models.CharField(max_length=50, null=True, blank=True)
    personal_email = models.EmailField(null=True, blank=True)
    alternate_email = models.EmailField(null=True, blank=True)
    wechat_id = models.CharField(max_length=100, null=True, blank=True)
    skype_no = models.CharField(max_length=100, null=True, blank=True)
    correspondence_address = models.TextField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=150, null=True, blank=True)
    emergency_contact_gender = models.CharField(max_length=20, null=True, blank=True)
    emergency_contact_relation = models.CharField(max_length=100, null=True, blank=True)
    emergency_contact_phone = models.CharField(max_length=50, null=True, blank=True)
    emergency_contact_email = models.EmailField(null=True, blank=True)
    emergency_contact_address = models.TextField(null=True, blank=True)

    # Page 2: Education and Employment History
    highest_education_level = models.CharField(max_length=100, null=True, blank=True)
    highest_education_country = models.CharField(max_length=100, null=True, blank=True)
    highest_education_institute = models.CharField(max_length=255, null=True, blank=True)
    highest_education_start_date = models.DateField(null=True, blank=True)
    highest_education_end_date = models.DateField(null=True, blank=True)
    highest_education_field_of_study = models.CharField(max_length=255, null=True, blank=True)
    highest_education_qualification = models.CharField(max_length=255, null=True, blank=True)
    other_education_1_level = models.CharField(max_length=100, null=True, blank=True)
    other_education_1_country = models.CharField(max_length=100, null=True, blank=True)
    other_education_1_institute = models.CharField(max_length=255, null=True, blank=True)
    other_education_1_start_date = models.DateField(null=True, blank=True)
    other_education_1_end_date = models.DateField(null=True, blank=True)
    other_education_1_field_of_study = models.CharField(max_length=255, null=True, blank=True)
    other_education_1_qualification = models.CharField(max_length=255, null=True, blank=True)
    other_education_2_level = models.CharField(max_length=100, null=True, blank=True)
    other_education_2_country = models.CharField(max_length=100, null=True, blank=True)
    other_education_2_institute = models.CharField(max_length=255, null=True, blank=True)
    other_education_2_start_date = models.DateField(null=True, blank=True)
    other_education_2_end_date = models.DateField(null=True, blank=True)
    other_education_2_field_of_study = models.CharField(max_length=255, null=True, blank=True)
    other_education_2_qualification = models.CharField(max_length=255, null=True, blank=True)
    employer = models.CharField(max_length=255, null=True, blank=True)
    employment_start_date = models.DateField(null=True, blank=True)
    employment_end_date = models.DateField(null=True, blank=True)
    work_engaged = models.CharField(max_length=255, null=True, blank=True)
    title_position = models.CharField(max_length=255, null=True, blank=True)

    # Page 3: Language Proficiency and Study Plan
    chinese_proficiency = models.CharField(max_length=50, null=True, blank=True)
    has_hsk_certificate = models.BooleanField(null=True, blank=True)
    hsk_level = models.CharField(max_length=100, null=True, blank=True)
    hsk_score = models.CharField(max_length=50, null=True, blank=True)
    hsk_test_date = models.DateField(null=True, blank=True)
    english_proficiency = models.CharField(max_length=50, null=True, blank=True)
    has_english_certificate = models.BooleanField(null=True, blank=True)
    english_test_name = models.CharField(max_length=100, null=True, blank=True)
    english_test_score = models.CharField(max_length=50, null=True, blank=True)
    english_test_date = models.DateField(null=True, blank=True)
    apply_as = models.CharField(max_length=100, null=True, blank=True)
    preferred_teaching_language = models.CharField(max_length=50, null=True, blank=True)
    has_pre_admission_letter = models.BooleanField(null=True, blank=True)
    institute_preference_1 = models.CharField(max_length=255, null=True, blank=True)
    discipline_1 = models.CharField(max_length=255, null=True, blank=True)
    major_1 = models.CharField(max_length=255, null=True, blank=True)
    institute_preference_2 = models.CharField(max_length=255, null=True, blank=True)
    discipline_2 = models.CharField(max_length=255, null=True, blank=True)
    major_2 = models.CharField(max_length=255, null=True, blank=True)
    institute_preference_3 = models.CharField(max_length=255, null=True, blank=True)
    discipline_3 = models.CharField(max_length=255, null=True, blank=True)
    major_3 = models.CharField(max_length=255, null=True, blank=True)
    major_study_start_date = models.DateField(null=True, blank=True)
    major_study_end_date = models.DateField(null=True, blank=True)
    ever_studied_or_worked_in_china = models.BooleanField(null=True, blank=True)
    china_institute_or_employer = models.CharField(max_length=255, null=True, blank=True)
    china_employment_start_date = models.DateField(null=True, blank=True)
    china_employment_end_date = models.DateField(null=True, blank=True)
    ever_had_chinese_government_scholarship = models.BooleanField(null=True, blank=True)
    previous_csc_institute_name = models.CharField(max_length=255, null=True, blank=True)
    previous_csc_start_date = models.DateField(null=True, blank=True)
    previous_csc_end_date = models.DateField(null=True, blank=True)

    # Page 4: Other Contacts
    contact_person_china_name = models.CharField(max_length=150, null=True, blank=True)
    contact_person_china_tel = models.CharField(max_length=50, null=True, blank=True)
    contact_person_china_email = models.EmailField(null=True, blank=True)
    contact_person_china_fax = models.CharField(max_length=50, null=True, blank=True)
    contact_person_china_address = models.TextField(null=True, blank=True)
    spouse_name = models.CharField(max_length=150, null=True, blank=True)
    spouse_age = models.PositiveIntegerField(null=True, blank=True)
    spouse_occupation = models.CharField(max_length=150, null=True, blank=True)
    father_name = models.CharField(max_length=150, null=True, blank=True)
    father_age = models.PositiveIntegerField(null=True, blank=True)
    father_occupation = models.CharField(max_length=150, null=True, blank=True)
    mother_name = models.CharField(max_length=150, null=True, blank=True)
    mother_age = models.PositiveIntegerField(null=True, blank=True)
    mother_occupation = models.CharField(max_length=150, null=True, blank=True)

    # Page 5: Supporting Documents and Declaration
    has_passport_photo = models.BooleanField(null=True, blank=True)
    has_highest_education_certificate = models.BooleanField(null=True, blank=True)
    has_highest_education_transcript = models.BooleanField(null=True, blank=True)
    has_study_plan = models.BooleanField(null=True, blank=True)
    has_reference_1 = models.BooleanField(null=True, blank=True)
    has_reference_2 = models.BooleanField(null=True, blank=True)
    has_passport_home_page = models.BooleanField(null=True, blank=True)
    has_physical_exam_record = models.BooleanField(null=True, blank=True)
    has_articles_or_papers = models.BooleanField(null=True, blank=True)
    has_art_music_examples = models.BooleanField(null=True, blank=True)
    has_chinese_language_certificate = models.BooleanField(null=True, blank=True)
    has_english_language_certificate = models.BooleanField(null=True, blank=True)
    has_csca_score_report = models.BooleanField(null=True, blank=True)
    has_pre_admission_letter_document = models.BooleanField(null=True, blank=True)
    has_non_criminal_record = models.BooleanField(null=True, blank=True)
    has_other_attachments = models.BooleanField(null=True, blank=True)
    other_attachments_description = models.TextField(null=True, blank=True)
    declaration_agreed = models.BooleanField(null=True, blank=True)

    serial_number = models.CharField(max_length=100, null=True, blank=True)
    generated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Supplemental Profile - Application #{self.application_id}"


class Document(models.Model):
    DOCUMENT_TYPES = [
        ('passport', 'Passport Copy'),
        ('passport_photo', 'Passport Photo'),
        ('ordinary_level', 'Ordinary Level Certificate'),
        ('advanced_level', 'Advanced Level Certificate'),
        ('academic_transcript', 'Academic Transcript'),
        ('degree_certificate', 'Degree / Diploma Certificate'),
        ('application_form', 'Application Form'),
        ('recommendation_letter', 'Recommendation Letter'),
        ('sop', 'Statement of Purpose / Motivation Letter'),
        ('cv', 'CV / Resume'),
        ('language_test', 'English Proficiency Test (IELTS / TOEFL)'),
        ('proof_of_funds', 'Proof of Funds'),
        ('health_insurance', 'Health Insurance'),
        ('financial_documents', 'Financial Documents (Legacy)'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='documents/', storage=PdfFriendlyCloudinaryStorage())
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.student.username}"


class Message(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject} - {self.student.username}"


# Payment Model with ClickPesa Integration
class Payment(models.Model):
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('settled', 'Settled'),
    ]
    
    PAYMENT_METHODS = [
        ('mobile_money', 'Mobile Money'),
        ('card', 'Card Payment'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    PAYMENT_GATEWAYS = [
        ('clickpesa', 'ClickPesa'),
        ('azampay', 'AzamPay'),
        ('manual', 'Manual Payment'),
    ]
    
    # Core fields
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')
    payment_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Payment method and gateway
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS, default='mobile_money')
    payment_gateway = models.CharField(max_length=20, choices=PAYMENT_GATEWAYS, default='clickpesa')
    
    # Transaction tracking
    order_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    is_successful = models.BooleanField(default=False)
    
    # Customer details
    phone_number = models.CharField(max_length=20, blank=True)
    mobile_provider = models.CharField(max_length=50, blank=True)  # For mobile money
    card_last_four = models.CharField(max_length=4, blank=True)  # For card payments
    
    # Bank transfer details
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    account_name = models.CharField(max_length=100, blank=True)
    
    # Additional info
    channel = models.CharField(max_length=100, blank=True)  # e.g., "TIGO-PESA", "M-PESA"
    message = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    
    # ClickPesa specific response data (stored as JSON string if needed)
    clickpesa_response = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
    
    def __str__(self):
        return f"Payment {self.order_reference} - {self.student.username} - {self.status}"
    
    def is_pending(self):
        return self.status in ['pending', 'processing']
    
    def is_completed(self):
        return self.status in ['success', 'settled']


# Application Assignment Model
class ApplicationAssignment(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_applications')
    assigned_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['application', 'employee']
        verbose_name = 'Application Assignment'
        verbose_name_plural = 'Application Assignments'
        ordering = ['-assigned_date']
    
    def __str__(self):
        return f"{self.employee.username} - Application #{self.application.id} ({self.application.student.username})"
