from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
        return all([
            self.personal_details_complete,
            self.academic_qualifications_complete,
            self.emergency_contact_complete
        ])
    
    def get_completion_percentage(self):
        """Calculate profile completion percentage"""
        sections = [
            self.personal_details_complete,
            self.parents_details_complete,
            self.academic_qualifications_complete,
            self.study_preferences_complete,
            self.emergency_contact_complete,
        ]
        completed = sum(1 for section in sections if section)
        return int((completed / len(sections)) * 100)
    
    def save(self, *args, **kwargs):
        # Auto-check completion status for each section
        
        # Personal details: phone, address, date_of_birth, nationality, gender
        if all([self.phone_number, self.address, self.date_of_birth, self.nationality, self.gender]):
            self.personal_details_complete = True
        
        # Parents details: at least one parent's info
        if self.father_name or self.mother_name:
            self.parents_details_complete = True
        
        # Academic qualifications: at least O-Level completed
        if all([self.olevel_school, self.olevel_year, self.olevel_gpa]):
            self.academic_qualifications_complete = True
        
        # Study preferences: at least one preference
        if self.preferred_country_1 and self.preferred_program_1:
            self.study_preferences_complete = True
        
        # Emergency contact: name, address, relation
        if all([self.emergency_contact, self.emergency_address, self.emergency_relation]):
            self.emergency_contact_complete = True
        
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


class Document(models.Model):
    DOCUMENT_TYPES = [
        ('passport', 'Passport'),
        ('ordinary_level', 'Ordinary Level Certificate'),
        ('advanced_level', 'Advanced Level Certificate'),
        ('academic_transcript', 'Academic Transcript'),
        ('degree_certificate', 'Degree Certificate'),
        ('recommendation_letter', 'Recommendation Letter'),
        ('sop', 'Statement of Purpose'),
        ('cv', 'CV'),
        ('language_test', 'Language Test Results'),
        ('financial_documents', 'Financial Documents'),
    ]
    
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='documents/')
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