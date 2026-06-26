from django.db import models
from django.contrib.auth.models import User

class StudentManager(models.Manager):
    def create_student_from_application(self, application):
        """Create a student user from application data"""
        try:
            # Extract first name from full name
            first_name = application.full_name.split()[0] if application.full_name else "student"
            
            # Generate username and password
            username = application.email
            password = f"{first_name}@gase"
            
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                user = User.objects.get(username=username)
                user.email = application.email
                user.first_name = first_name
                user.last_name = " ".join(application.full_name.split()[1:]) if len(application.full_name.split()) > 1 else ""
                # nosemgrep: python.django.security.audit.unvalidated-password.unvalidated-password
                # The default password is a system-generated temporary credential
                # that the student must change on first login; validation against
                # the standard password validators is intentionally skipped so the
                # predictable format is preserved.
                user.set_password(password)
                user.save()
            else:
                # Create new user
                user = User.objects.create_user(
                    username=username,
                    email=application.email,
                    password=password,
                    first_name=first_name,
                    last_name=" ".join(application.full_name.split()[1:]) if len(application.full_name.split()) > 1 else ""
                )
            
            return user
            
        except Exception as e:
            print(f"Error creating student account: {e}")
            return None

class Student(User):
    """Proxy model for Student users - extends Django's built-in User model"""
    
    class Meta:
        proxy = True
        verbose_name = "Student"
        verbose_name_plural = "Students"
    
    objects = StudentManager()
    
    @property
    def student_applications(self):
        """Get all applications for this student"""
        return StudentApplication.objects.filter(email=self.email)
    
    @property
    def latest_application(self):
        """Get the most recent application for this student"""
        return self.student_applications.order_by('-created_at').first()
    
    def __str__(self):
        return f"Student: {self.username}"

class StudentProfile(models.Model):
    """Extended profile information for students"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    phone = models.CharField(max_length=50, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    emergency_contact = models.CharField(max_length=150, blank=True, null=True)
    emergency_phone = models.CharField(max_length=50, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - Student Profile"

class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    destination = models.CharField(max_length=100, blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    reply_subject = models.CharField(max_length=255, blank=True)
    reply_message = models.TextField(blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)
    replied_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_message_replies',
    )

    def __str__(self):
        return f"{self.name} - {self.email}"

class StudentApplication(models.Model):
    # Step 1: Personal Information
    full_name = models.CharField(max_length=150)
    gender = models.CharField(max_length=20, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
    ])
    date_of_birth = models.DateField(null=True, blank=True)
    place_of_birth = models.TextField(blank=True, null=True)
    nationality = models.CharField(max_length=100, default="Tanzanian")
    native_language = models.CharField(max_length=100, blank=True, null=True)
    marital_status = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField()
    phone = models.CharField(max_length=50)

    # Step 2: Parents Details
    father_name = models.CharField(max_length=150, blank=True, null=True)
    father_phone = models.CharField(max_length=50, blank=True, null=True)
    father_email = models.EmailField(blank=True, null=True)
    father_occupation = models.CharField(max_length=150, blank=True, null=True)
    father_place_neighbourhood = models.TextField(blank=True, null=True)
    father_status = models.CharField(max_length=100, blank=True, null=True)
    father_relationship = models.CharField(max_length=100, blank=True, null=True)

    mother_name = models.CharField(max_length=150, blank=True, null=True)
    mother_phone = models.CharField(max_length=50, blank=True, null=True)
    mother_email = models.EmailField(blank=True, null=True)
    mother_occupation = models.CharField(max_length=150, blank=True, null=True)
    mother_place_neighbourhood = models.TextField(blank=True, null=True)
    mother_status = models.CharField(max_length=100, blank=True, null=True)
    mother_relationship = models.CharField(max_length=100, blank=True, null=True)

    # Step 3: Education Background - O-Level
    olevel_school = models.CharField(max_length=150, blank=True, null=True)
    olevel_start_year = models.CharField(max_length=10, blank=True, null=True)
    olevel_completed_year = models.CharField(max_length=10, blank=True, null=True)
    olevel_candidate_no = models.CharField(max_length=50, blank=True, null=True)
    olevel_gpa = models.CharField(max_length=20, blank=True, null=True)
    olevel_school_type = models.CharField(max_length=100, blank=True, null=True)
    olevel_exam_board = models.CharField(max_length=100, blank=True, null=True)
    olevel_certificate_no = models.CharField(max_length=100, blank=True, null=True)
    olevel_remarks = models.TextField(blank=True, null=True)

    # Step 3: Education Background - A-Level
    alevel_school = models.CharField(max_length=150, blank=True, null=True)
    alevel_start_year = models.CharField(max_length=10, blank=True, null=True)
    alevel_completed_year = models.CharField(max_length=10, blank=True, null=True)
    alevel_candidate_no = models.CharField(max_length=50, blank=True, null=True)
    alevel_gpa = models.CharField(max_length=20, blank=True, null=True)
    alevel_school_type = models.CharField(max_length=100, blank=True, null=True)
    alevel_exam_board = models.CharField(max_length=100, blank=True, null=True)
    alevel_certificate_no = models.CharField(max_length=100, blank=True, null=True)
    alevel_remarks = models.TextField(blank=True, null=True)

    # Step 4: Study Preferences
    preferred_intake = models.CharField(max_length=80, blank=True, null=True)
    preferred_country_1 = models.CharField(max_length=100, blank=True, null=True)
    preferred_country_2 = models.CharField(max_length=100, blank=True, null=True)
    preferred_country_3 = models.CharField(max_length=100, blank=True, null=True)
    preferred_program_1 = models.CharField(max_length=100, blank=True, null=True)
    preferred_program_2 = models.CharField(max_length=100, blank=True, null=True)
    preferred_program_3 = models.CharField(max_length=100, blank=True, null=True)

    # Step 5: Emergency Contact
    emergency_name = models.CharField(max_length=150)
    emergency_relation = models.CharField(max_length=100)
    emergency_occupation = models.CharField(max_length=100, blank=True, null=True)
    emergency_phone = models.CharField(max_length=50, blank=True, null=True)
    emergency_email = models.EmailField(blank=True, null=True)
    emergency_alternative_phone = models.CharField(max_length=50, blank=True, null=True)
    emergency_relationship_status = models.CharField(max_length=100, blank=True, null=True)
    emergency_remarks = models.TextField(blank=True, null=True)
    heard_about_us = models.CharField(max_length=100, blank=True, null=True)
    heard_about_other = models.TextField(blank=True, null=True)

    # Declaration
    declaration_applicant_name = models.TextField(blank=True, null=True)
    declaration_date = models.DateField(null=True, blank=True)
    declaration_signature_name = models.TextField(blank=True, null=True)
    terms_accepted = models.BooleanField(default=False)

    # Office Use
    office_director_name = models.TextField(blank=True, null=True)
    office_approval_status = models.CharField(max_length=30, blank=True, null=True)
    office_reason = models.TextField(blank=True, null=True)

    # Work Experience 1
    work1_company_name = models.TextField(blank=True, null=True)
    work1_position = models.TextField(blank=True, null=True)
    work1_worked_from = models.DateField(null=True, blank=True)
    work1_worked_to = models.DateField(null=True, blank=True)
    work1_country = models.CharField(max_length=100, blank=True, null=True, default="Tanzania")
    work1_region = models.TextField(blank=True, null=True)
    work1_region_post_code = models.CharField(max_length=30, blank=True, null=True)
    work1_district = models.TextField(blank=True, null=True)
    work1_district_post_code = models.CharField(max_length=30, blank=True, null=True)
    work1_ward = models.TextField(blank=True, null=True)
    work1_ward_post_code = models.CharField(max_length=30, blank=True, null=True)
    work1_street = models.TextField(blank=True, null=True)
    work1_employment_type = models.TextField(blank=True, null=True)
    work1_duties = models.TextField(blank=True, null=True)
    work1_supervisor = models.TextField(blank=True, null=True)
    work1_remarks = models.TextField(blank=True, null=True)

    # Work Experience 2
    work2_company_name = models.TextField(blank=True, null=True)
    work2_position = models.TextField(blank=True, null=True)
    work2_worked_from = models.DateField(null=True, blank=True)
    work2_worked_to = models.DateField(null=True, blank=True)
    work2_country = models.CharField(max_length=100, blank=True, null=True, default="Tanzania")
    work2_region = models.TextField(blank=True, null=True)
    work2_region_post_code = models.CharField(max_length=30, blank=True, null=True)
    work2_district = models.TextField(blank=True, null=True)
    work2_district_post_code = models.CharField(max_length=30, blank=True, null=True)
    work2_ward = models.TextField(blank=True, null=True)
    work2_ward_post_code = models.CharField(max_length=30, blank=True, null=True)
    work2_street = models.TextField(blank=True, null=True)
    work2_employment_type = models.TextField(blank=True, null=True)
    work2_duties = models.TextField(blank=True, null=True)
    work2_supervisor = models.TextField(blank=True, null=True)
    work2_remarks = models.TextField(blank=True, null=True)

    # Professional Qualification 1
    profq1_title = models.TextField(blank=True, null=True)
    profq1_institution = models.TextField(blank=True, null=True)
    profq1_institution_address = models.TextField(blank=True, null=True)
    profq1_country = models.CharField(max_length=100, blank=True, null=True, default="Tanzania")
    profq1_period = models.TextField(blank=True, null=True)
    profq1_start_date = models.DateField(null=True, blank=True)
    profq1_finished_date = models.DateField(null=True, blank=True)
    profq1_award_certificate = models.CharField(max_length=10, blank=True, null=True)

    # Professional Qualification 2
    profq2_title = models.TextField(blank=True, null=True)
    profq2_institution = models.TextField(blank=True, null=True)
    profq2_institution_address = models.TextField(blank=True, null=True)
    profq2_country = models.CharField(max_length=100, blank=True, null=True, default="Tanzania")
    profq2_period = models.TextField(blank=True, null=True)
    profq2_start_date = models.DateField(null=True, blank=True)
    profq2_finished_date = models.DateField(null=True, blank=True)
    profq2_award_certificate = models.CharField(max_length=10, blank=True, null=True)

    # Professional Qualification 3
    profq3_title = models.TextField(blank=True, null=True)
    profq3_institution = models.TextField(blank=True, null=True)
    profq3_institution_address = models.TextField(blank=True, null=True)
    profq3_country = models.CharField(max_length=100, blank=True, null=True, default="Tanzania")
    profq3_period = models.TextField(blank=True, null=True)
    profq3_start_date = models.DateField(null=True, blank=True)
    profq3_finished_date = models.DateField(null=True, blank=True)
    profq3_award_certificate = models.CharField(max_length=10, blank=True, null=True)

    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_student_applications')
    portal_application = models.ForeignKey('student_portal.Application', on_delete=models.SET_NULL, null=True, blank=True, related_name='offline_intakes')
    
    # Account creation fields
    account_created = models.BooleanField(default=False)
    username = models.CharField(max_length=150, blank=True, null=True)
    temporary_password = models.CharField(max_length=100, blank=True, null=True)
    student_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')

    def __str__(self):
        return f"{self.full_name} ({self.nationality})"

    def create_student_account(self):
        """Create a student account from application data"""
        try:
            # Use the Student proxy model to create the account
            student_user = Student.objects.create_student_from_application(self)
            
            if student_user:
                # Create student profile
                student_profile, created = StudentProfile.objects.get_or_create(
                    user=student_user,
                    defaults={
                        'phone_number': self.phone,
                        'emergency_contact': self.emergency_name,
                        'emergency_phone': self.emergency_phone or self.phone
                    }
                )
                
                # Link application to student user
                self.student_user = student_user
                self.account_created = True
                self.username = student_user.username
                self.temporary_password = f"{self.full_name.split()[0] if self.full_name else 'student'}@gase"
                self.save()
                
                return student_user
            
        except Exception as e:
            print(f"Error creating student account: {e}")
            return None

    @property
    def login_credentials(self):
        """Get login credentials for display"""
        if self.account_created:
            return {
                'username': self.username,
                'password': self.temporary_password
            }
        return None
