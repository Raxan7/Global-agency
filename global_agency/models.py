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
    nationality = models.CharField(max_length=100, default="Tanzanian")
    email = models.EmailField()
    phone = models.CharField(max_length=50)
    address = models.TextField()

    # Step 2: Parents Details
    father_name = models.CharField(max_length=150, blank=True, null=True)
    father_phone = models.CharField(max_length=50, blank=True, null=True)
    father_email = models.EmailField(blank=True, null=True)
    father_occupation = models.CharField(max_length=150, blank=True, null=True)

    mother_name = models.CharField(max_length=150, blank=True, null=True)
    mother_phone = models.CharField(max_length=50, blank=True, null=True)
    mother_email = models.EmailField(blank=True, null=True)
    mother_occupation = models.CharField(max_length=150, blank=True, null=True)

    # Step 3: Education Background - O-Level
    olevel_school = models.CharField(max_length=150, blank=True, null=True)
    olevel_country = models.CharField(max_length=100, default="Tanzania")
    olevel_address = models.CharField(max_length=255, blank=True, null=True)
    olevel_region = models.CharField(max_length=100, blank=True, null=True)
    olevel_year = models.CharField(max_length=10, blank=True, null=True)
    olevel_candidate_no = models.CharField(max_length=50, blank=True, null=True)
    olevel_gpa = models.CharField(max_length=20, blank=True, null=True)

    # Step 3: Education Background - A-Level
    alevel_school = models.CharField(max_length=150, blank=True, null=True)
    alevel_country = models.CharField(max_length=100, default="Tanzania")
    alevel_address = models.CharField(max_length=255, blank=True, null=True)
    alevel_region = models.CharField(max_length=100, blank=True, null=True)
    alevel_year = models.CharField(max_length=10, blank=True, null=True)
    alevel_candidate_no = models.CharField(max_length=50, blank=True, null=True)
    alevel_gpa = models.CharField(max_length=20, blank=True, null=True)

    # Step 4: Study Preferences
    preferred_country_1 = models.CharField(max_length=100, blank=True, null=True)
    preferred_country_2 = models.CharField(max_length=100, blank=True, null=True)
    preferred_country_3 = models.CharField(max_length=100, blank=True, null=True)
    preferred_country_4 = models.CharField(max_length=100, blank=True, null=True)
    preferred_program_1 = models.CharField(max_length=100, blank=True, null=True)
    preferred_program_2 = models.CharField(max_length=100, blank=True, null=True)
    preferred_program_3 = models.CharField(max_length=100, blank=True, null=True)
    preferred_program_4 = models.CharField(max_length=100, blank=True, null=True)

    # Step 5: Emergency Contact
    emergency_name = models.CharField(max_length=150)
    emergency_address = models.TextField()
    emergency_occupation = models.CharField(max_length=100, blank=True, null=True)
    emergency_gender = models.CharField(max_length=20, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
    ])
    emergency_relation = models.CharField(max_length=100)
    heard_about_us = models.CharField(max_length=100, blank=True, null=True)
    heard_about_other = models.CharField(max_length=255, blank=True, null=True)

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
                        'phone': self.phone,
                        'emergency_contact': self.emergency_name,
                        'emergency_phone': self.phone
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
