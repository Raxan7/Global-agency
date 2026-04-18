from django.db import IntegrityError, models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from urllib.parse import parse_qs, urlparse
from student_portal.models import Application, Document

class UserProfile(models.Model):
    USER_ROLES = [
        ('student', 'Student'),
        ('employee', 'Employee'),
        ('admin', 'Administrator'),
    ]
    
    REGISTRATION_METHODS = [
        ('self', 'Self Registration'),
        ('admin', 'Admin Created'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=USER_ROLES, default='student')
    registration_method = models.CharField(max_length=20, choices=REGISTRATION_METHODS, default='self')
    department = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    employee_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role}"

    def is_employee(self):
        """Check if user is employee OR admin"""
        return self.role in ['employee', 'admin']
    
    def is_student(self):
        """Check if user is student"""
        return self.role == 'student'
    
    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin'
    
    def is_admin_created_employee(self):
        """Check if user is admin-created employee (employee role + admin registration)"""
        return self.role in ['employee', 'admin'] and self.registration_method == 'admin'
    
    def can_access_employee_portal(self):
        """Employee portal access: must be employee/admin AND created by admin"""
        return self.is_employee() and self.registration_method == 'admin'
    
    def can_access_student_portal(self):
        """Student portal access: allow all student accounts, including offline entries."""
        return self.is_student()
    
    def is_regular_employee(self):
        """Check if user is employee (not admin)"""
        return self.role == 'employee'
    
    def get_role_display_name(self):
        """Get human-readable role name"""
        return dict(self.USER_ROLES).get(self.role, self.role)
    
    def get_registration_method_display_name(self):
        """Get human-readable registration method"""
        return dict(self.REGISTRATION_METHODS).get(self.registration_method, self.registration_method)

class EmployeeProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    employee_id = models.CharField(max_length=20, unique=True)
    position = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.position}"

class ApplicationAssignment(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    employee = models.ForeignKey(User, on_delete=models.CASCADE)
    assigned_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], default='assigned')

    def __str__(self):
        return f"{self.application} - {self.employee.username}"
    
    def get_status_display_name(self):
        """Get human-readable status name"""
        status_dict = {
            'assigned': 'Assigned',
            'in_progress': 'In Progress',
            'completed': 'Completed'
        }
        return status_dict.get(self.status, self.status)


class PortalUpdate(models.Model):
    CONTENT_TYPES = [
        ('blog', 'Blog'),
        ('image', 'Image Story'),
        ('event', 'Event'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
    ]

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES, default='blog')
    excerpt = models.CharField(max_length=280)
    content = models.TextField(
        help_text="Main body content shown on the public detail page."
    )
    youtube_url = models.URLField(
        blank=True,
        help_text="Optional YouTube link to embed on the public update page.",
    )
    cover_image = models.ImageField(
        upload_to='updates/',
        blank=True,
        null=True,
        help_text="Recommended for homepage previews and image-based updates.",
    )
    image_alt_text = models.CharField(max_length=160, blank=True)
    location = models.CharField(max_length=160, blank=True)
    event_start = models.DateTimeField(blank=True, null=True)
    event_end = models.DateTimeField(blank=True, null=True)
    featured_on_homepage = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(blank=True, null=True)
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='portal_updates',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == 'published' and self.published_at is None:
            self.published_at = timezone.now()

        # Retry a few times to protect against concurrent inserts using the same title slug.
        max_attempts = 5
        for attempt in range(max_attempts):
            if not self.slug:
                self.slug = self._generate_unique_slug()

            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as exc:
                is_slug_conflict = 'employee_portalupdate.slug' in str(exc)
                if not is_slug_conflict or attempt == max_attempts - 1:
                    raise

                self.slug = ''

    def _generate_unique_slug(self):
        base_slug = slugify(self.title)[:200] or 'update'
        slug = base_slug
        counter = 2

        while PortalUpdate.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            slug = f'{base_slug[:190]}-{counter}'
            counter += 1

        return slug

    def get_absolute_url(self):
        return reverse('global_agency:update_detail', args=[self.slug])

    @property
    def is_published(self):
        return self.status == 'published'

    @property
    def has_event_schedule(self):
        return self.content_type == 'event' and self.event_start is not None

    @property
    def is_upcoming(self):
        return self.has_event_schedule and self.event_start >= timezone.now()

    @property
    def public_author_name(self):
        return "Marketing Team"

    @property
    def hero_image(self):
        if self.cover_image:
            return self.cover_image

        first_gallery_image = self.gallery_images.order_by('created_at').first()
        if first_gallery_image:
            return first_gallery_image.image

        return None

    @property
    def youtube_embed_url(self):
        if not self.youtube_url:
            return ''

        parsed_url = urlparse(self.youtube_url)
        host = (parsed_url.netloc or '').lower()

        video_id = ''
        if 'youtu.be' in host:
            video_id = parsed_url.path.strip('/').split('/')[0]
        elif 'youtube.com' in host:
            if parsed_url.path == '/watch':
                video_id = parse_qs(parsed_url.query).get('v', [''])[0]
            elif parsed_url.path.startswith('/embed/'):
                video_id = parsed_url.path.split('/embed/', 1)[1].split('/')[0]
            elif parsed_url.path.startswith('/shorts/'):
                video_id = parsed_url.path.split('/shorts/', 1)[1].split('/')[0]

        if not video_id:
            return ''

        return f'https://www.youtube.com/embed/{video_id}'


class PortalUpdateImage(models.Model):
    update = models.ForeignKey(
        PortalUpdate,
        on_delete=models.CASCADE,
        related_name='gallery_images',
    )
    image = models.ImageField(upload_to='updates/gallery/')
    alt_text = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f"Gallery image for {self.update.title}"


class PortalUpdateAttachment(models.Model):
    update = models.ForeignKey(
        PortalUpdate,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to='updates/attachments/')
    title = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return self.title or self.filename

    @property
    def filename(self):
        return self.file.name.rsplit('/', 1)[-1]
