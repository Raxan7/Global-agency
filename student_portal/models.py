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
    OFFICE_ELIGIBILITY_CHOICES = [
        ('', '---------'),
        ('eligible', 'Eligible'),
        ('not_eligible', 'Not Eligible'),
    ]
    OFFICE_ADMISSION_STATUS_CHOICES = [
        ('', '---------'),
        ('not_applied', 'Not Applied'),
        ('applied', 'Applied'),
        ('offer_received', 'Offer Received'),
        ('accepted', 'Accepted'),
    ]
    OFFICE_VISA_STATUS_CHOICES = [
        ('', '---------'),
        ('not_started', 'Not Started'),
        ('processing', 'Processing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    OFFICE_FINAL_DECISION_CHOICES = [
        ('', '---------'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('conditional', 'Conditional'),
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
    employee_status_note = models.TextField(blank=True, help_text="Status feedback visible to the student and partner.")
    status_updated_at = models.DateTimeField(null=True, blank=True)
    status_updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='application_status_updates',
    )
    official_eligibility = models.CharField(
        max_length=20,
        choices=OFFICE_ELIGIBILITY_CHOICES,
        blank=True,
        default='',
    )
    official_documents_verified = models.BooleanField(null=True, blank=True)
    official_admission_status = models.CharField(
        max_length=20,
        choices=OFFICE_ADMISSION_STATUS_CHOICES,
        blank=True,
        default='',
    )
    official_visa_status = models.CharField(
        max_length=20,
        choices=OFFICE_VISA_STATUS_CHOICES,
        blank=True,
        default='',
    )
    official_final_decision = models.CharField(
        max_length=20,
        choices=OFFICE_FINAL_DECISION_CHOICES,
        blank=True,
        default='',
    )
    official_remarks = models.TextField(blank=True)

    def __str__(self):
        return f"{self.get_application_type_display()} - {self.student.username}"


class ApplicationSupplementalProfile(models.Model):
    """Supplemental AWEC registration data used for intake and export."""

    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        related_name='supplemental_profile',
    )

    full_name_passport = models.TextField(null=True, blank=True)
    place_of_birth = models.TextField(null=True, blank=True)
    passport_number = models.TextField(null=True, blank=True)
    passport_issue_country = models.TextField(null=True, blank=True)
    passport_issue_date = models.DateField(null=True, blank=True)
    passport_expiration_date = models.DateField(null=True, blank=True)
    has_valid_visa = models.BooleanField(null=True, blank=True)
    valid_visa_details = models.TextField(null=True, blank=True)
    current_region = models.TextField(null=True, blank=True)
    current_city = models.TextField(null=True, blank=True)
    current_country = models.TextField(null=True, blank=True)
    current_postal_code = models.TextField(null=True, blank=True)
    whatsapp_number = models.TextField(null=True, blank=True)
    residential_email = models.EmailField(null=True, blank=True)
    current_address = models.TextField(null=True, blank=True)

    certificate_institution = models.TextField(null=True, blank=True)
    certificate_field_of_study = models.TextField(null=True, blank=True)
    certificate_year_completed = models.TextField(null=True, blank=True)
    certificate_gpa = models.TextField(null=True, blank=True)
    diploma_institution = models.TextField(null=True, blank=True)
    diploma_field_of_study = models.TextField(null=True, blank=True)
    diploma_year_completed = models.TextField(null=True, blank=True)
    diploma_gpa = models.TextField(null=True, blank=True)
    bachelor_institution = models.TextField(null=True, blank=True)
    bachelor_field_of_study = models.TextField(null=True, blank=True)
    bachelor_year_completed = models.TextField(null=True, blank=True)
    bachelor_gpa = models.TextField(null=True, blank=True)
    master_institution = models.TextField(null=True, blank=True)
    master_field_of_study = models.TextField(null=True, blank=True)
    master_year_completed = models.TextField(null=True, blank=True)
    master_gpa = models.TextField(null=True, blank=True)
    phd_institution = models.TextField(null=True, blank=True)
    phd_field_of_study = models.TextField(null=True, blank=True)
    phd_year_completed = models.TextField(null=True, blank=True)
    phd_gpa = models.TextField(null=True, blank=True)
    professional_qualifications = models.TextField(null=True, blank=True)
    english_test_name = models.TextField(null=True, blank=True)
    english_test_score = models.TextField(null=True, blank=True)
    english_test_year = models.TextField(null=True, blank=True)
    program_level = models.TextField(null=True, blank=True)
    preferred_intake = models.TextField(null=True, blank=True)
    accommodation_preference = models.TextField(null=True, blank=True)
    education_sponsor = models.TextField(null=True, blank=True)
    estimated_budget_usd = models.TextField(null=True, blank=True)
    scholarship_applied = models.BooleanField(null=True, blank=True)
    scholarship_details = models.TextField(null=True, blank=True)
    has_medical_condition = models.BooleanField(null=True, blank=True)
    medical_condition_details = models.TextField(null=True, blank=True)
    needs_special_assistance = models.BooleanField(null=True, blank=True)
    special_assistance_details = models.TextField(null=True, blank=True)

    has_passport_photo = models.BooleanField(null=True, blank=True)
    has_passport_copy = models.BooleanField(null=True, blank=True)
    has_academic_certificates = models.BooleanField(null=True, blank=True)
    has_academic_transcripts = models.BooleanField(null=True, blank=True)
    has_english_test_results = models.BooleanField(null=True, blank=True)
    has_cv_resume = models.BooleanField(null=True, blank=True)
    has_personal_statement = models.BooleanField(null=True, blank=True)
    has_recommendation_letters = models.BooleanField(null=True, blank=True)
    has_financial_proof = models.BooleanField(null=True, blank=True)
    has_health_insurance = models.BooleanField(null=True, blank=True)
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
