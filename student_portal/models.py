from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields import NOT_PROVIDED
from django.utils import timezone

from globalagency_project.storage import PdfFriendlyCloudinaryStorage


# -----------------------------------------------------------------------------
# Optional Tanzania location support through the `mtaa` python package.
# Install in your environment with: pip install mtaa
#
# Important: this file does NOT crash if mtaa is not installed. Your migrations,
# shell, and server will still run. When mtaa is installed, the helper functions
# below can be used by forms/views/API endpoints to populate dependent dropdowns
# and to validate Region -> District -> Ward -> Street/Mtaa values.
# -----------------------------------------------------------------------------
try:  # pragma: no cover - depends on installed package in runtime environment
    import mtaa as _mtaa
except Exception:  # pragma: no cover
    _mtaa = None


COUNTRY_DEFAULT = "Tanzania"


class LocationHelper:
    """Small wrapper around the mtaa package.

    The mtaa package exposes Tanzania locations from regions down to streets and
    neighbourhoods. It supports attribute access for valid Python identifiers and
    `.get()` for names like `Dar-es-salaam`.
    """

    @staticmethod
    def _mtaa_module():
        """Lazy accessor for the mtaa module.

        Re-attempts the import on every call so a server that started before
        mtaa was installed will pick it up without needing a restart.
        """
        global _mtaa
        if _mtaa is not None:
            return _mtaa
        try:
            import mtaa as _retry
        except Exception:
            return None
        _mtaa = _retry
        return _mtaa

    @classmethod
    def installed(cls) -> bool:
        return cls._mtaa_module() is not None

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def regions(cls) -> List[str]:
        mtaa_mod = cls._mtaa_module()
        if not mtaa_mod:
            return []
        try:
            return sorted(str(item).strip() for item in list(mtaa_mod.regions) if str(item).strip())
        except Exception:
            try:
                return sorted(str(item).strip() for item in list(mtaa_mod.tanzania) if str(item).strip())
            except Exception:
                return []

    @classmethod
    def get_region_obj(cls, region: str):
        mtaa_mod = cls._mtaa_module()
        if not mtaa_mod:
            return None
        region = cls._clean(region)
        if not region:
            return None
        try:
            return mtaa_mod.tanzania.get(region)
        except Exception:
            try:
                return getattr(mtaa_mod.tanzania, region)
            except Exception:
                return None

    @classmethod
    def get_district_obj(cls, region: str, district: str):
        mtaa_mod = cls._mtaa_module()
        if not mtaa_mod:
            return None
        region_obj = cls.get_region_obj(region)
        district = cls._clean(district)
        if region_obj is None or not district:
            return None
        districts_obj = getattr(region_obj, "districts", None)
        if districts_obj is None:
            return None
        try:
            return districts_obj.get(district)
        except Exception:
            try:
                return getattr(districts_obj, district)
            except Exception:
                return None

    @classmethod
    def get_ward_obj(cls, region: str, district: str, ward: str):
        mtaa_mod = cls._mtaa_module()
        if not mtaa_mod:
            return None
        district_obj = cls.get_district_obj(region, district)
        ward = cls._clean(ward)
        if district_obj is None or not ward:
            return None
        wards_obj = getattr(district_obj, "wards", None)
        if wards_obj is None:
            return None
        try:
            return wards_obj.get(ward)
        except Exception:
            try:
                return getattr(wards_obj, ward)
            except Exception:
                return None

    @classmethod
    def districts(cls, region: str = "") -> List[Dict[str, str]]:
        mtaa_mod = cls._mtaa_module()
        if not mtaa_mod:
            return []
        region_obj = cls.get_region_obj(region) if region else None
        source = getattr(region_obj, "districts", None) if region_obj is not None else getattr(mtaa_mod, "districts", [])
        return cls._normalise_named_postcode_items(source)

    @classmethod
    def wards(cls, region: str = "", district: str = "") -> List[Dict[str, str]]:
        mtaa_mod = cls._mtaa_module()
        if not mtaa_mod:
            return []
        if region and district:
            district_obj = cls.get_district_obj(region, district)
            source = getattr(district_obj, "wards", None) if district_obj is not None else []
        else:
            source = getattr(mtaa_mod, "wards", [])
        return cls._normalise_named_postcode_items(source)

    @classmethod
    def streets(cls, region: str = "", district: str = "", ward: str = "") -> List[str]:
        mtaa_mod = cls._mtaa_module()
        if not mtaa_mod:
            return []
        if region and district and ward:
            ward_obj = cls.get_ward_obj(region, district, ward)
            if ward_obj is not None:
                try:
                    tree = ward_obj.tree()
                    streets = list((tree.get("streets") or {}).keys())
                    return sorted(str(item).strip() for item in streets if str(item).strip())
                except Exception:
                    pass
        try:
            return sorted(str(item).strip() for item in list(mtaa_mod.streets) if str(item).strip())
        except Exception:
            return []

    @classmethod
    def neighbourhoods(cls, region: str = "", district: str = "", ward: str = "", street: str = "") -> List[str]:
        if not cls._mtaa_module() or not (region and district and ward and street):
            return []
        ward_obj = cls.get_ward_obj(region, district, ward)
        if ward_obj is None:
            return []
        try:
            tree = ward_obj.tree()
            streets = tree.get("streets") or {}
            values = streets.get(street) or streets.get(cls._clean(street)) or []
            return sorted(str(item).strip() for item in values if str(item).strip())
        except Exception:
            return []

    @classmethod
    def get_district_obj(cls, region: str, district: str):
        region_obj = cls.get_region_obj(region)
        district = cls._clean(district)
        if region_obj is None or not district:
            return None
        districts_obj = getattr(region_obj, "districts", None)
        if districts_obj is None:
            return None
        try:
            return districts_obj.get(district)
        except Exception:
            try:
                return getattr(districts_obj, district)
            except Exception:
                return None

    @classmethod
    def get_ward_obj(cls, region: str, district: str, ward: str):
        district_obj = cls.get_district_obj(region, district)
        ward = cls._clean(ward)
        if district_obj is None or not ward:
            return None
        wards_obj = getattr(district_obj, "wards", None)
        if wards_obj is None:
            return None
        try:
            return wards_obj.get(ward)
        except Exception:
            try:
                return getattr(wards_obj, ward)
            except Exception:
                return None

    @staticmethod
    def _normalise_named_postcode_items(source: Any) -> List[Dict[str, str]]:
        items = []
        try:
            iterable = list(source or [])
        except Exception:
            iterable = []
        for item in iterable:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                post_code = str(item.get("post_code") or item.get("postcode") or "").strip()
            else:
                name = str(item or "").strip()
                post_code = ""
            if name and name not in {"ward_post_code", "district_post_code"}:
                items.append({"name": name, "post_code": post_code})
        return sorted(items, key=lambda row: row["name"].lower())

    @classmethod
    def validate_location(cls, region: str = "", district: str = "", ward: str = "", street: str = "", neighbourhood: str = "") -> Dict[str, str]:
        """Return a dict of field errors. Empty dict means the location is OK.

        This is intentionally soft: when mtaa is not installed, validation is
        skipped so deployment does not break.
        """
        errors: Dict[str, str] = {}
        if not cls._mtaa_module():
            return errors

        region = cls._clean(region)
        district = cls._clean(district)
        ward = cls._clean(ward)
        street = cls._clean(street)
        neighbourhood = cls._clean(neighbourhood)

        if region and region not in cls.regions():
            errors["region"] = f"'{region}' is not a valid Tanzania region in mtaa."
            return errors

        if region and district:
            valid_districts = {item["name"] for item in cls.districts(region)}
            if district not in valid_districts:
                errors["district"] = f"'{district}' is not a valid district for {region}."
                return errors

        if region and district and ward:
            valid_wards = {item["name"] for item in cls.wards(region, district)}
            if ward not in valid_wards:
                errors["ward"] = f"'{ward}' is not a valid ward for {district}."
                return errors

        if region and district and ward and street:
            valid_streets = set(cls.streets(region, district, ward))
            if valid_streets and street not in valid_streets:
                errors["street"] = f"'{street}' is not a valid street/mtaa for {ward}."
                return errors

        if region and district and ward and street and neighbourhood:
            valid_neighbourhoods = set(cls.neighbourhoods(region, district, ward, street))
            if valid_neighbourhoods and neighbourhood not in valid_neighbourhoods:
                errors["neighbourhood"] = f"'{neighbourhood}' is not a valid neighbourhood for {street}."

        return errors


class TanzaniaLocationMixin(models.Model):
    """Reusable Tanzania location fields for addresses.

    These are plain CharFields so they work nicely with the mtaa package, with
    AJAX dropdowns, and with existing PDF export code. Do not use DB-level
    choices here because Tanzania location datasets are large and can change.
    """

    country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    region = models.CharField(max_length=120, blank=True)
    region_post_code = models.CharField(max_length=30, blank=True)
    district = models.CharField(max_length=120, blank=True)
    district_post_code = models.CharField(max_length=30, blank=True)
    ward = models.CharField(max_length=120, blank=True)
    ward_post_code = models.CharField(max_length=30, blank=True)
    street = models.CharField(max_length=180, blank=True, help_text="Street / Mtaa from the mtaa package")
    mtaa = models.CharField(max_length=180, blank=True, help_text="Optional explicit mtaa/local street name")
    place_neighbourhood = models.CharField(max_length=180, blank=True)
    house_no = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    address_line = models.TextField(blank=True)
    nearest_landmark = models.CharField(max_length=255, blank=True)

    class Meta:
        abstract = True

    def location_parts(self) -> Dict[str, str]:
        return {
            "country": self.country,
            "region": self.region or "",
            "region_post_code": self.region_post_code or "",
            "district": self.district or "",
            "district_post_code": self.district_post_code or "",
            "ward": self.ward or "",
            "ward_post_code": self.ward_post_code or "",
            "street": self.street or self.mtaa or "",
            "mtaa": self.mtaa or self.street or "",
            "place_neighbourhood": self.place_neighbourhood or "",
            "house_no": self.house_no or "",
            "postal_code": self.postal_code or "",
            "address_line": self.address_line or "",
            "nearest_landmark": self.nearest_landmark or "",
        }

    def formatted_location(self) -> str:
        parts = [
            self.house_no,
            self.place_neighbourhood,
            self.street or self.mtaa,
            self.ward,
            self.district,
            self.region,
            self.country,
        ]
        return ", ".join(str(part).strip() for part in parts if str(part or "").strip())


class StudentProfile(models.Model):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
    ]

    MARITAL_STATUS_CHOICES = [
        ("", "---------"),
        ("single", "Single"),
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Basic Information
    phone_number = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=150, blank=True)
    nationality = models.CharField(max_length=100, blank=True, default="Tanzanian")
    native_language = models.CharField(max_length=100, blank=True, default="Swahili")
    marital_status = models.CharField(max_length=30, choices=MARITAL_STATUS_CHOICES, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    profile_picture = models.ImageField(upload_to="profiles/", null=True, blank=True)

    # Student current/home location.
    city = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    region_post_code = models.CharField(max_length=30, blank=True)
    district_post_code = models.CharField(max_length=30, blank=True)
    ward = models.CharField(max_length=120, blank=True)
    ward_post_code = models.CharField(max_length=30, blank=True)
    street = models.CharField(max_length=180, blank=True)
    mtaa = models.CharField(max_length=180, blank=True)
    village = models.CharField(max_length=180, blank=True)
    neighbourhood = models.CharField(max_length=180, blank=True)
    place_neighbourhood = models.CharField(max_length=180, blank=True)
    house_no = models.CharField(max_length=80, blank=True)
    house_number = models.CharField(max_length=80, blank=True)

    # Passport fields
    passport_number = models.CharField(max_length=100, blank=True)
    passport_issue_country = models.CharField(max_length=100, blank=True)
    passport_issue_date = models.DateField(null=True, blank=True)
    passport_expiration_date = models.DateField(null=True, blank=True)

    # Father Details
    father_name = models.CharField(max_length=150, blank=True)
    father_phone = models.CharField(max_length=50, blank=True)
    father_email = models.EmailField(blank=True)
    father_occupation = models.CharField(max_length=150, blank=True)
    father_country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    father_region = models.CharField(max_length=120, blank=True)
    father_region_post_code = models.CharField(max_length=30, blank=True)
    father_district = models.CharField(max_length=120, blank=True)
    father_district_post_code = models.CharField(max_length=30, blank=True)
    father_ward = models.CharField(max_length=120, blank=True)
    father_ward_post_code = models.CharField(max_length=30, blank=True)
    father_street = models.CharField(max_length=180, blank=True)
    father_place_neighbourhood = models.CharField(max_length=180, blank=True)
    father_house_no = models.CharField(max_length=80, blank=True)
    father_status = models.CharField(max_length=100, blank=True)
    father_relationship = models.CharField(max_length=100, blank=True)

    # Mother Details
    mother_name = models.CharField(max_length=150, blank=True)
    mother_phone = models.CharField(max_length=50, blank=True)
    mother_email = models.EmailField(blank=True)
    mother_occupation = models.CharField(max_length=150, blank=True)
    mother_country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    mother_region = models.CharField(max_length=120, blank=True)
    mother_region_post_code = models.CharField(max_length=30, blank=True)
    mother_district = models.CharField(max_length=120, blank=True)
    mother_district_post_code = models.CharField(max_length=30, blank=True)
    mother_ward = models.CharField(max_length=120, blank=True)
    mother_ward_post_code = models.CharField(max_length=30, blank=True)
    mother_street = models.CharField(max_length=180, blank=True)
    mother_place_neighbourhood = models.CharField(max_length=180, blank=True)
    mother_house_no = models.CharField(max_length=80, blank=True)
    mother_status = models.CharField(max_length=100, blank=True)
    mother_relationship = models.CharField(max_length=100, blank=True)

    # O-Level Education
    olevel_school = models.CharField(max_length=150, blank=True)
    olevel_school_country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    olevel_school_region = models.CharField(max_length=120, blank=True)
    olevel_school_region_post_code = models.CharField(max_length=30, blank=True)
    olevel_school_district = models.CharField(max_length=120, blank=True)
    olevel_school_district_post_code = models.CharField(max_length=30, blank=True)
    olevel_school_ward = models.CharField(max_length=120, blank=True)
    olevel_school_ward_post_code = models.CharField(max_length=30, blank=True)
    olevel_school_street = models.CharField(max_length=180, blank=True)
    olevel_school_place_neighbourhood = models.CharField(max_length=180, blank=True)
    olevel_school_house_no = models.CharField(max_length=80, blank=True)
    olevel_start_year = models.CharField(max_length=10, blank=True)
    olevel_completed_year = models.CharField(max_length=10, blank=True)
    olevel_candidate_no = models.CharField(max_length=50, blank=True)
    olevel_gpa = models.CharField(max_length=20, blank=True)
    olevel_school_type = models.CharField(max_length=100, blank=True)
    olevel_exam_board = models.CharField(max_length=100, blank=True)
    olevel_certificate_no = models.CharField(max_length=100, blank=True)
    olevel_remarks = models.TextField(blank=True)

    # A-Level Education
    alevel_school = models.CharField(max_length=150, blank=True)
    alevel_school_country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    alevel_school_region = models.CharField(max_length=120, blank=True)
    alevel_school_region_post_code = models.CharField(max_length=30, blank=True)
    alevel_school_district = models.CharField(max_length=120, blank=True)
    alevel_school_district_post_code = models.CharField(max_length=30, blank=True)
    alevel_school_ward = models.CharField(max_length=120, blank=True)
    alevel_school_ward_post_code = models.CharField(max_length=30, blank=True)
    alevel_school_street = models.CharField(max_length=180, blank=True)
    alevel_school_place_neighbourhood = models.CharField(max_length=180, blank=True)
    alevel_school_house_no = models.CharField(max_length=80, blank=True)
    alevel_start_year = models.CharField(max_length=10, blank=True)
    alevel_completed_year = models.CharField(max_length=10, blank=True)
    alevel_candidate_no = models.CharField(max_length=50, blank=True)
    alevel_gpa = models.CharField(max_length=20, blank=True)
    alevel_school_type = models.CharField(max_length=100, blank=True)
    alevel_exam_board = models.CharField(max_length=100, blank=True)
    alevel_certificate_no = models.CharField(max_length=100, blank=True)
    alevel_remarks = models.TextField(blank=True)

    # Study Preferences
    preferred_intake = models.CharField(max_length=80, blank=True)
    preferred_country_1 = models.CharField(max_length=100, blank=True)
    preferred_country_2 = models.CharField(max_length=100, blank=True)
    preferred_country_3 = models.CharField(max_length=100, blank=True)
    preferred_program_1 = models.CharField(max_length=150, blank=True)
    preferred_program_2 = models.CharField(max_length=150, blank=True)
    preferred_program_3 = models.CharField(max_length=150, blank=True)

    # Emergency Contact
    emergency_contact = models.CharField(max_length=150, blank=True)
    emergency_relation = models.CharField(max_length=100, blank=True)
    emergency_occupation = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(max_length=50, blank=True)
    emergency_email = models.EmailField(blank=True)
    emergency_alternative_phone = models.CharField(max_length=50, blank=True)
    emergency_country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    emergency_region = models.CharField(max_length=120, blank=True)
    emergency_region_post_code = models.CharField(max_length=30, blank=True)
    emergency_district = models.CharField(max_length=120, blank=True)
    emergency_district_post_code = models.CharField(max_length=30, blank=True)
    emergency_ward = models.CharField(max_length=120, blank=True)
    emergency_ward_post_code = models.CharField(max_length=30, blank=True)
    emergency_street = models.CharField(max_length=180, blank=True)
    emergency_place_neighbourhood = models.CharField(max_length=180, blank=True)
    emergency_house_no = models.CharField(max_length=80, blank=True)
    emergency_relationship_status = models.CharField(max_length=100, blank=True)
    emergency_remarks = models.TextField(blank=True)

    heard_about_us = models.CharField(max_length=100, blank=True)
    heard_about_other = models.CharField(max_length=255, blank=True)

    # Profile Completion Tracking
    personal_details_complete = models.BooleanField(default=False)
    parents_details_complete = models.BooleanField(default=False)
    academic_qualifications_complete = models.BooleanField(default=False)
    study_preferences_complete = models.BooleanField(default=False)
    emergency_contact_complete = models.BooleanField(default=False)

    # Draft resumption tracking
    current_step = models.CharField(max_length=50, blank=True, null=True, help_text="Last completed step name for draft resumption")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        full_name = (self.user.get_full_name() or self.user.username or "Student").strip()
        return full_name

    def is_complete(self):
        section_flags = self.get_completion_flags()
        return all([
            section_flags["personal_details_complete"],
            section_flags["academic_qualifications_complete"],
            section_flags["emergency_contact_complete"],
        ])

    def get_completion_flags(self):
        user_full_name = (self.user.get_full_name() or "").strip()
        personal_complete = all([
            user_full_name,
            self.phone_number,
            self.nationality,
            self.gender,
        ])

        has_parent_info = bool(self.father_name or self.mother_name)
        has_guardian_info = bool(self.emergency_contact and self.emergency_relation)
        parents_complete = has_parent_info or has_guardian_info

        has_olevel = all([self.olevel_school, self.olevel_completed_year, self.olevel_gpa])
        has_alevel = all([self.alevel_school, self.alevel_completed_year, self.alevel_gpa])
        academic_complete = has_olevel or has_alevel

        study_complete = bool(self.preferred_country_1 and self.preferred_program_1)
        emergency_complete = all([
            self.emergency_contact,
            self.emergency_relation,
        ])

        return {
            "personal_details_complete": personal_complete,
            "parents_details_complete": parents_complete,
            "academic_qualifications_complete": academic_complete,
            "study_preferences_complete": study_complete,
            "emergency_contact_complete": emergency_complete,
        }

    def get_completion_status(self):
        flags = self.get_completion_flags()
        sections = [
            flags["personal_details_complete"],
            flags["parents_details_complete"],
            flags["academic_qualifications_complete"],
            flags["study_preferences_complete"],
            flags["emergency_contact_complete"],
        ]
        completed = sum(1 for section in sections if section)
        percentage = int((completed / len(sections)) * 100)
        return {**flags, "percentage": percentage}

    def get_completion_percentage(self):
        return self.get_completion_status()["percentage"]

    def save(self, *args, **kwargs):
        flags = self.get_completion_flags()
        self.personal_details_complete = flags["personal_details_complete"]
        self.parents_details_complete = flags["parents_details_complete"]
        self.academic_qualifications_complete = flags["academic_qualifications_complete"]
        self.study_preferences_complete = flags["study_preferences_complete"]
        self.emergency_contact_complete = flags["emergency_contact_complete"]

        if self.email and not self.user.email:
            self.user.email = self.email
            self.user.save(update_fields=["email"])

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            completion_fields = {
                "personal_details_complete",
                "parents_details_complete",
                "academic_qualifications_complete",
                "study_preferences_complete",
                "emergency_contact_complete",
            }
            kwargs["update_fields"] = set(update_fields).union(completion_fields)

        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # Normalized schema accessors (see StudentAddress, StudentPassport,
    # StudentFamilyContact, StudentSchoolHistory below). These return the
    # canonical normalized record when available so PDF exports, admin
    # screens and other read paths do not depend on the legacy wide
    # columns staying physically present in MySQL.
    # ------------------------------------------------------------------
    def get_address(self, address_type):
        """Return the StudentAddress row for ``address_type`` or ``None``."""
        try:
            return self.addresses.filter(address_type=address_type).first()
        except Exception:
            return None

    def get_passport(self):
        """Return the related StudentPassport row or ``None``."""
        try:
            return getattr(self, "passport_record", None)
        except StudentPassport.DoesNotExist:
            return None
        except Exception:
            return None

    def get_family_contact(self, contact_type):
        """Return the StudentFamilyContact row for ``contact_type`` or ``None``."""
        try:
            return self.family_contacts.filter(contact_type=contact_type).first()
        except Exception:
            return None

    def get_school_history(self, level):
        """Return the StudentSchoolHistory row for ``level`` or ``None``."""
        try:
            return self.school_history.filter(level=level).first()
        except Exception:
            return None

    def sync_normalized_fields(self):
        """Mirror the legacy wide columns into the normalized tables.

        The function is intentionally tolerant: it never raises on missing
        physical columns or on rows that have not been migrated yet. Call
        it from form ``save()`` overrides and from any view that updates a
        StudentProfile so the normalized tables always stay in step with
        the legacy columns during the transition window.

        The cleanup release that drops the legacy columns will also delete
        this method.
        """
        from django.db import DatabaseError

        try:
            _sync_student_profile_normalized(self)
        except DatabaseError:
            # The destination tables may not exist on the very first
            # migrate. Swallowing this keeps the public API safe during
            # the deploy window.
            pass


class WorkExperience(models.Model):
    """Work experience entries for students."""

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="work_experiences")
    company_name = models.CharField(max_length=200)
    position = models.CharField(max_length=200)
    location = models.CharField(max_length=200, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    currently_working = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    responsibilities = models.TextField(blank=True, null=True)
    achievements = models.TextField(blank=True, null=True)

    # New export-friendly workplace location fields.
    country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    region = models.CharField(max_length=120, blank=True)
    region_post_code = models.CharField(max_length=30, blank=True)
    district = models.CharField(max_length=120, blank=True)
    district_post_code = models.CharField(max_length=30, blank=True)
    ward = models.CharField(max_length=120, blank=True)
    ward_post_code = models.CharField(max_length=30, blank=True)
    street = models.CharField(max_length=180, blank=True)
    mtaa = models.CharField(max_length=180, blank=True)
    neighbourhood = models.CharField(max_length=180, blank=True)
    place_neighbourhood = models.CharField(max_length=180, blank=True)
    house_no = models.CharField(max_length=80, blank=True)
    employment_type = models.CharField(max_length=100, blank=True)
    supervisor = models.CharField(max_length=150, blank=True)
    supervisor_contact = models.CharField(max_length=150, blank=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Work Experience"
        verbose_name_plural = "Work Experiences"

    def __str__(self):
        return f"{self.position} at {self.company_name} - {self.student.user.get_full_name()}"

    @property
    def duration(self):
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
        if years > 0:
            return f"{years} year{'s' if years > 1 else ''}"
        if months > 0:
            return f"{months} month{'s' if months > 1 else ''}"
        return "Less than a month"


# ---------------------------------------------------------------------------
# Normalized student-scoped tables.
#
# These replace the dozens of address / family / school / passport columns
# that used to live directly on ``StudentProfile`` and caused MySQL row-size
# 1118 errors (max row 8126 bytes for the default 16K page size). They are
# small, related-row tables, so the parent table stays slim.
#
# Existing wide columns on ``StudentProfile`` are deliberately retained for
# now so the in-flight transition deployment does not break any forms,
# views, admin screens, or exports that still write to those columns. A
# later cleanup migration will drop the legacy columns once data has been
# verified in the normalized tables.
# ---------------------------------------------------------------------------


class StudentAddress(models.Model):
    """Generic address row attached to a StudentProfile.

    ``address_type`` partitions rows into the well-known groupings the rest
    of the application uses: personal/current, permanent, father, mother,
    emergency, olevel_school, alevel_school. The relation is many-to-one so
    new address types can be added later without further migrations.

    Long fields use ``TextField`` so MySQL keeps them off-page and the row
    stays well under the 8126-byte limit even for many such relations.
    """

    ADDRESS_TYPE_CHOICES = [
        ("personal", "Personal / Current"),
        ("permanent", "Permanent"),
        ("father", "Father"),
        ("mother", "Mother"),
        ("emergency", "Emergency Contact"),
        ("olevel_school", "O-Level School"),
        ("alevel_school", "A-Level School"),
        ("other", "Other"),
    ]

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(max_length=30, choices=ADDRESS_TYPE_CHOICES)

    country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    region = models.CharField(max_length=120, blank=True)
    region_post_code = models.CharField(max_length=30, blank=True)
    district = models.CharField(max_length=120, blank=True)
    district_post_code = models.CharField(max_length=30, blank=True)
    ward = models.CharField(max_length=120, blank=True)
    ward_post_code = models.CharField(max_length=30, blank=True)
    house_no = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)

    street = models.TextField(blank=True)
    mtaa = models.TextField(blank=True)
    village = models.TextField(blank=True)
    neighbourhood = models.TextField(blank=True)
    place_neighbourhood = models.TextField(blank=True)
    landmark = models.TextField(blank=True)
    nearest_landmark = models.TextField(blank=True)
    address_line = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("student", "address_type")]
        verbose_name = "Student Address"
        verbose_name_plural = "Student Addresses"
        ordering = ["student_id", "address_type"]

    def __str__(self):
        try:
            owner = self.student.user.get_full_name() or self.student.user.username
        except Exception:
            owner = f"Student #{self.student_id}"
        return f"{self.get_address_type_display()} address for {owner}"

    def formatted(self) -> str:
        parts = [
            self.house_no,
            self.place_neighbourhood or self.neighbourhood,
            self.street or self.mtaa,
            self.ward,
            self.district,
            self.region,
            self.country,
        ]
        return ", ".join(str(part).strip() for part in parts if str(part or "").strip())


class StudentPassport(models.Model):
    """Single passport record per student, normalised out of StudentProfile."""

    student = models.OneToOneField(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="passport_record",
    )
    passport_number = models.CharField(max_length=100, blank=True)
    issue_country = models.CharField(max_length=100, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Student Passport"
        verbose_name_plural = "Student Passports"

    def __str__(self):
        return f"Passport {self.passport_number or '-'} for student #{self.student_id}"


class StudentFamilyContact(models.Model):
    """Father / mother / emergency contact rows normalised out of StudentProfile."""

    CONTACT_TYPE_CHOICES = [
        ("father", "Father"),
        ("mother", "Mother"),
        ("emergency", "Emergency Contact"),
        ("guardian", "Guardian"),
        ("other", "Other"),
    ]

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="family_contacts",
    )
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPE_CHOICES)
    name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    occupation = models.CharField(max_length=150, blank=True)
    relation = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("student", "contact_type")]
        verbose_name = "Student Family Contact"
        verbose_name_plural = "Student Family Contacts"
        ordering = ["student_id", "contact_type"]

    def __str__(self):
        return f"{self.get_contact_type_display()}: {self.name or '-'} (student #{self.student_id})"


class StudentSchoolHistory(models.Model):
    """O-Level / A-Level / other school history per student."""

    LEVEL_CHOICES = [
        ("olevel", "O-Level"),
        ("alevel", "A-Level"),
        ("primary", "Primary"),
        ("other", "Other"),
    ]

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="school_history",
    )
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    school_name = models.CharField(max_length=255, blank=True)
    candidate_no = models.CharField(max_length=50, blank=True)
    gpa = models.CharField(max_length=20, blank=True)
    start_year = models.CharField(max_length=10, blank=True)
    completed_year = models.CharField(max_length=10, blank=True)

    country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    region = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=120, blank=True)
    ward = models.CharField(max_length=120, blank=True)
    house_no = models.CharField(max_length=80, blank=True)
    street = models.TextField(blank=True)
    mtaa = models.TextField(blank=True)
    address = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("student", "level")]
        verbose_name = "Student School History"
        verbose_name_plural = "Student School Histories"
        ordering = ["student_id", "level"]

    def __str__(self):
        return f"{self.get_level_display()}: {self.school_name or '-'} (student #{self.student_id})"


# ---------------------------------------------------------------------------
# Sync helper used by StudentProfile.sync_normalized_fields() and by data
# migrations. It reads any data still living in the legacy wide columns and
# mirrors it into the normalized tables. Reads are tolerant: any missing
# attribute is treated as empty, so this is safe even when migrations have
# already dropped a column in a future release.
# ---------------------------------------------------------------------------


def _attr(obj: Any, name: str, default: str = "") -> str:
    """Read an attribute defensively, even when the column is missing.

    Returns the model's field default if the value is None or equal to the
    field's default.  This ensures that fields declared with
    ``default=COUNTRY_DEFAULT`` (i.e. "Tanzania") read as empty during
    normalization, so we don't create empty rows for every country field
    on every student.
    """
    if obj is None:
        return default
    try:
        value = getattr(obj, name, default)
    except Exception:
        return default
    if value is None:
        return default
    try:
        field = obj._meta.get_field(name)
        field_default = getattr(field, "default", None)
        if field_default is not None and field_default is not NOT_PROVIDED and value == field_default:
            return default
    except Exception:
        pass
    return value


def _row_has_content(values: Dict[str, Any]) -> bool:
    """Return True when at least one value in ``values`` is non-empty."""
    for value in values.values():
        if value in (None, ""):
            continue
        return True
    return False


def _sync_student_profile_normalized(profile: "StudentProfile") -> None:
    """Mirror legacy columns from a StudentProfile into normalized tables."""
    address_specs = [
        (
            "personal",
            {
                "country": _attr(profile, "country"),
                "region": _attr(profile, "region"),
                "region_post_code": _attr(profile, "region_post_code"),
                "district": _attr(profile, "district"),
                "district_post_code": _attr(profile, "district_post_code"),
                "ward": _attr(profile, "ward"),
                "ward_post_code": _attr(profile, "ward_post_code"),
                "street": _attr(profile, "street"),
                "mtaa": _attr(profile, "mtaa"),
                "village": _attr(profile, "village"),
                "neighbourhood": _attr(profile, "neighbourhood"),
                "place_neighbourhood": _attr(profile, "place_neighbourhood"),
                "house_no": _attr(profile, "house_no") or _attr(profile, "house_number"),
                "address_line": _attr(profile, "address"),
            },
        ),
        (
            "father",
            {
                "country": _attr(profile, "father_country"),
                "region": _attr(profile, "father_region"),
                "region_post_code": _attr(profile, "father_region_post_code"),
                "district": _attr(profile, "father_district"),
                "district_post_code": _attr(profile, "father_district_post_code"),
                "ward": _attr(profile, "father_ward"),
                "ward_post_code": _attr(profile, "father_ward_post_code"),
                "street": _attr(profile, "father_street"),
                "mtaa": _attr(profile, "father_mtaa"),
                "neighbourhood": _attr(profile, "father_neighbourhood"),
                "place_neighbourhood": _attr(profile, "father_place_neighbourhood"),
                "house_no": _attr(profile, "father_house_no"),
            },
        ),
        (
            "mother",
            {
                "country": _attr(profile, "mother_country"),
                "region": _attr(profile, "mother_region"),
                "region_post_code": _attr(profile, "mother_region_post_code"),
                "district": _attr(profile, "mother_district"),
                "district_post_code": _attr(profile, "mother_district_post_code"),
                "ward": _attr(profile, "mother_ward"),
                "ward_post_code": _attr(profile, "mother_ward_post_code"),
                "street": _attr(profile, "mother_street"),
                "mtaa": _attr(profile, "mother_mtaa"),
                "neighbourhood": _attr(profile, "mother_neighbourhood"),
                "place_neighbourhood": _attr(profile, "mother_place_neighbourhood"),
                "house_no": _attr(profile, "mother_house_no"),
            },
        ),
        (
            "emergency",
            {
                "country": _attr(profile, "emergency_country"),
                "region": _attr(profile, "emergency_region"),
                "region_post_code": _attr(profile, "emergency_region_post_code"),
                "district": _attr(profile, "emergency_district"),
                "district_post_code": _attr(profile, "emergency_district_post_code"),
                "ward": _attr(profile, "emergency_ward"),
                "ward_post_code": _attr(profile, "emergency_ward_post_code"),
                "street": _attr(profile, "emergency_street"),
                "mtaa": _attr(profile, "emergency_mtaa"),
                "neighbourhood": _attr(profile, "emergency_neighbourhood"),
                "place_neighbourhood": _attr(profile, "emergency_place_neighbourhood"),
                "house_no": _attr(profile, "emergency_house_no"),
            },
        ),
        (
            "olevel_school",
            {
                "country": _attr(profile, "olevel_school_country") or _attr(profile, "olevel_country"),
                "region": _attr(profile, "olevel_school_region") or _attr(profile, "olevel_region"),
                "region_post_code": _attr(profile, "olevel_school_region_post_code"),
                "district": _attr(profile, "olevel_school_district"),
                "district_post_code": _attr(profile, "olevel_school_district_post_code"),
                "ward": _attr(profile, "olevel_school_ward"),
                "ward_post_code": _attr(profile, "olevel_school_ward_post_code"),
                "street": _attr(profile, "olevel_school_street"),
                "mtaa": _attr(profile, "olevel_school_mtaa"),
                "neighbourhood": _attr(profile, "olevel_school_neighbourhood"),
                "place_neighbourhood": _attr(profile, "olevel_school_place_neighbourhood"),
                "house_no": _attr(profile, "olevel_school_house_no"),
            },
        ),
        (
            "alevel_school",
            {
                "country": _attr(profile, "alevel_school_country") or _attr(profile, "alevel_country"),
                "region": _attr(profile, "alevel_school_region") or _attr(profile, "alevel_region"),
                "region_post_code": _attr(profile, "alevel_school_region_post_code"),
                "district": _attr(profile, "alevel_school_district"),
                "district_post_code": _attr(profile, "alevel_school_district_post_code"),
                "ward": _attr(profile, "alevel_school_ward"),
                "ward_post_code": _attr(profile, "alevel_school_ward_post_code"),
                "street": _attr(profile, "alevel_school_street"),
                "mtaa": _attr(profile, "alevel_school_mtaa"),
                "neighbourhood": _attr(profile, "alevel_school_neighbourhood"),
                "place_neighbourhood": _attr(profile, "alevel_school_place_neighbourhood"),
                "house_no": _attr(profile, "alevel_school_house_no"),
            },
        ),
    ]

    for address_type, defaults in address_specs:
        if _row_has_content(defaults):
            StudentAddress.objects.update_or_create(
                student=profile,
                address_type=address_type,
                defaults=defaults,
            )

    passport_values = {
        "passport_number": _attr(profile, "passport_number"),
        "issue_country": _attr(profile, "passport_issue_country"),
        "issue_date": (
            getattr(profile, "passport_issue_date", None)
            or getattr(profile, "passport_issued_date", None)
            or getattr(profile, "passport_date_of_issue", None)
        ),
        "expiry_date": (
            getattr(profile, "passport_expiry_date", None)
            or getattr(profile, "passport_expiration_date", None)
            or getattr(profile, "passport_expired_date", None)
            or getattr(profile, "passport_date_of_expiry", None)
        ),
    }
    if _row_has_content(passport_values):
        StudentPassport.objects.update_or_create(
            student=profile,
            defaults=passport_values,
        )

    family_specs = [
        (
            "father",
            {
                "name": _attr(profile, "father_name"),
                "phone": _attr(profile, "father_phone"),
                "email": _attr(profile, "father_email"),
                "occupation": _attr(profile, "father_occupation"),
            },
        ),
        (
            "mother",
            {
                "name": _attr(profile, "mother_name"),
                "phone": _attr(profile, "mother_phone"),
                "email": _attr(profile, "mother_email"),
                "occupation": _attr(profile, "mother_occupation"),
            },
        ),
        (
            "emergency",
            {
                "name": _attr(profile, "emergency_contact"),
                "occupation": _attr(profile, "emergency_occupation"),
                "gender": _attr(profile, "emergency_gender"),
                "relation": _attr(profile, "emergency_relation"),
            },
        ),
    ]
    for contact_type, defaults in family_specs:
        if _row_has_content(defaults):
            StudentFamilyContact.objects.update_or_create(
                student=profile,
                contact_type=contact_type,
                defaults=defaults,
            )

    school_specs = [
        (
            "olevel",
            {
                "school_name": _attr(profile, "olevel_school"),
                "candidate_no": _attr(profile, "olevel_candidate_no"),
                "gpa": _attr(profile, "olevel_gpa"),
                "start_year": _attr(profile, "olevel_start_year"),
                "completed_year": _attr(profile, "olevel_completed_year"),
                "country": _attr(profile, "olevel_school_country") or _attr(profile, "olevel_country"),
                "region": _attr(profile, "olevel_school_region") or _attr(profile, "olevel_region"),
                "district": _attr(profile, "olevel_school_district"),
                "ward": _attr(profile, "olevel_school_ward"),
                "house_no": _attr(profile, "olevel_school_house_no"),
                "street": _attr(profile, "olevel_school_street"),
                "mtaa": _attr(profile, "olevel_school_mtaa"),
            },
        ),
        (
            "alevel",
            {
                "school_name": _attr(profile, "alevel_school"),
                "candidate_no": _attr(profile, "alevel_candidate_no"),
                "gpa": _attr(profile, "alevel_gpa"),
                "start_year": _attr(profile, "alevel_start_year"),
                "completed_year": _attr(profile, "alevel_completed_year"),
                "country": _attr(profile, "alevel_school_country") or _attr(profile, "alevel_country"),
                "region": _attr(profile, "alevel_school_region") or _attr(profile, "alevel_region"),
                "district": _attr(profile, "alevel_school_district"),
                "ward": _attr(profile, "alevel_school_ward"),
                "house_no": _attr(profile, "alevel_school_house_no"),
                "street": _attr(profile, "alevel_school_street"),
                "mtaa": _attr(profile, "alevel_school_mtaa"),
            },
        ),
    ]
    for level, defaults in school_specs:
        if _row_has_content(defaults):
            StudentSchoolHistory.objects.update_or_create(
                student=profile,
                level=level,
                defaults=defaults,
            )


class Application(models.Model):
    APPLICATION_STATUS = [
        ("pending_payment", "Pending Payment"),
        ("submitted", "Submitted"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("selected", "Selected"),
    ]
    OFFICE_ELIGIBILITY_CHOICES = [
        ("", "---------"),
        ("eligible", "Eligible"),
        ("not_eligible", "Not Eligible"),
    ]
    OFFICE_ADMISSION_STATUS_CHOICES = [
        ("", "---------"),
        ("not_applied", "Not Applied"),
        ("applied", "Applied"),
        ("offer_received", "Offer Received"),
        ("accepted", "Accepted"),
    ]
    OFFICE_VISA_STATUS_CHOICES = [
        ("", "---------"),
        ("not_started", "Not Started"),
        ("processing", "Processing"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    OFFICE_FINAL_DECISION_CHOICES = [
        ("", "---------"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("conditional", "Conditional"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("not_paid", "Not Paid"),
        ("pending_verification", "Pending Verification"),
        ("paid", "Paid"),
        ("refunded", "Refunded"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=APPLICATION_STATUS, default="pending_payment")
    submission_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_paid = models.BooleanField(default=False)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)

    # M-PESA Payment Tracking
    payment_status = models.CharField(max_length=30, choices=PAYMENT_STATUS_CHOICES, default="not_paid")
    mpesa_account_name = models.CharField(max_length=150, blank=True, help_text="Name on M-PESA account used for payment")
    payment_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_payments")
    payment_verified_at = models.DateTimeField(null=True, blank=True)
    payment_notes = models.TextField(blank=True, help_text="Employee notes about payment verification")
    employee_status_note = models.TextField(blank=True, help_text="Status feedback visible to the student and partner.")
    status_updated_at = models.DateTimeField(null=True, blank=True)
    status_updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="application_status_updates",
    )
    reference_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    official_eligibility = models.CharField(max_length=20, choices=OFFICE_ELIGIBILITY_CHOICES, blank=True, default="")
    official_documents_verified = models.BooleanField(null=True, blank=True)
    official_admission_status = models.CharField(max_length=20, choices=OFFICE_ADMISSION_STATUS_CHOICES, blank=True, default="")
    official_visa_status = models.CharField(max_length=20, choices=OFFICE_VISA_STATUS_CHOICES, blank=True, default="")
    official_final_decision = models.CharField(max_length=20, choices=OFFICE_FINAL_DECISION_CHOICES, blank=True, default="")
    official_remarks = models.TextField(blank=True)

    def __str__(self):
        return f"Application - {self.student.username}"

    def get_registration_number(self):
        if self.reference_number:
            return self.reference_number
        year = self.created_at.year if self.created_at else timezone.now().year
        return f"AWECO/INT/REG/TZ/DSM/{year}8{self.id:03d}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.reference_number:
            year = self.created_at.year if self.created_at else timezone.now().year
            self.reference_number = f"AWECO/INT/REG/TZ/DSM/{year}8{self.id:03d}"
            super().save(update_fields=['reference_number'])


class ApplicationSupplementalProfile(models.Model):
    """Supplemental AWEC registration data used for intake and export."""

    PROGRAM_LEVEL_CHOICES = [
        ("", "---------"),
        ("certificate", "Certificate"),
        ("diploma", "Diploma"),
        ("bachelor", "Bachelor Degree"),
        ("master", "Master Degree"),
        ("phd", "PhD"),
        ("language", "Language Program"),
        ("foundation", "Foundation Program"),
        ("short_course", "Short Course"),
    ]

    INTAKE_CHOICES = [
        ("", "---------"),
        ("january", "January"),
        ("february", "February"),
        ("march", "March"),
        ("april", "April"),
        ("may", "May"),
        ("june", "June"),
        ("july", "July"),
        ("august", "August"),
        ("september", "September"),
        ("october", "October"),
        ("november", "November"),
        ("december", "December"),
    ]

    ACCOMMODATION_CHOICES = [
        ("", "---------"),
        ("university_dormitory", "University Dormitory"),
        ("private_apartment", "Private Apartment"),
        ("homestay", "Homestay"),
        ("not_required", "Not Required"),
    ]

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name="supplemental_profile")

    # Identity / Passport / Contact
    full_name_passport = models.TextField(null=True, blank=True)
    place_of_birth = models.TextField(null=True, blank=True)
    passport_number = models.TextField(null=True, blank=True)
    passport_issue_country = models.TextField(null=True, blank=True)
    passport_issue_date = models.DateField(null=True, blank=True)
    passport_expiration_date = models.DateField(null=True, blank=True)
    has_valid_visa = models.BooleanField(null=True, blank=True)
    valid_visa_details = models.TextField(null=True, blank=True)
    residential_email = models.EmailField(null=True, blank=True)

    # Current address, mtaa-ready.
    current_country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    current_region = models.CharField(max_length=120, null=True, blank=True)
    current_region_post_code = models.CharField(max_length=30, null=True, blank=True)
    current_city = models.CharField(max_length=120, null=True, blank=True)
    current_district = models.CharField(max_length=120, null=True, blank=True)
    current_district_post_code = models.CharField(max_length=30, null=True, blank=True)
    current_ward = models.CharField(max_length=120, null=True, blank=True)
    current_ward_post_code = models.CharField(max_length=30, null=True, blank=True)
    current_street = models.CharField(max_length=180, null=True, blank=True)
    current_mtaa = models.CharField(max_length=180, null=True, blank=True)
    current_village = models.CharField(max_length=180, null=True, blank=True)
    current_neighbourhood = models.CharField(max_length=180, null=True, blank=True)
    current_place_neighbourhood = models.CharField(max_length=180, null=True, blank=True)
    current_house_no = models.CharField(max_length=80, null=True, blank=True)
    current_postal_code = models.TextField(null=True, blank=True)
    current_address = models.TextField(null=True, blank=True)
    current_address_status = models.CharField(max_length=120, null=True, blank=True)
    current_nearest_landmark = models.CharField(max_length=255, null=True, blank=True)
    current_landmark = models.CharField(max_length=255, null=True, blank=True)
    current_duration_at_address = models.CharField(max_length=120, null=True, blank=True)
    current_address_remarks = models.TextField(null=True, blank=True)

    # Permanent address, mtaa-ready.
    permanent_country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    permanent_region = models.CharField(max_length=120, null=True, blank=True)
    permanent_region_post_code = models.CharField(max_length=30, null=True, blank=True)
    permanent_city = models.CharField(max_length=120, null=True, blank=True)
    permanent_district = models.CharField(max_length=120, null=True, blank=True)
    permanent_district_post_code = models.CharField(max_length=30, null=True, blank=True)
    permanent_ward = models.CharField(max_length=120, null=True, blank=True)
    permanent_ward_post_code = models.CharField(max_length=30, null=True, blank=True)
    permanent_street = models.CharField(max_length=180, null=True, blank=True)
    permanent_mtaa = models.CharField(max_length=180, null=True, blank=True)
    permanent_village = models.CharField(max_length=180, null=True, blank=True)
    permanent_neighbourhood = models.CharField(max_length=180, null=True, blank=True)
    permanent_place_neighbourhood = models.CharField(max_length=180, null=True, blank=True)
    permanent_house_no = models.CharField(max_length=80, null=True, blank=True)
    permanent_postal_code = models.CharField(max_length=30, null=True, blank=True)
    permanent_address = models.TextField(null=True, blank=True)
    permanent_address_status = models.CharField(max_length=120, null=True, blank=True)
    permanent_nearest_landmark = models.CharField(max_length=255, null=True, blank=True)
    permanent_landmark = models.CharField(max_length=255, null=True, blank=True)
    permanent_duration_at_address = models.CharField(max_length=120, null=True, blank=True)
    permanent_address_remarks = models.TextField(null=True, blank=True)

    # Higher education fields. Existing *_year_completed names are kept, and
    # new *_start_year / *_completed_year names are added for the new PDF exporter.
    certificate_institution = models.TextField(null=True, blank=True)
    certificate_field_of_study = models.TextField(null=True, blank=True)
    certificate_start_year = models.TextField(null=True, blank=True)
    certificate_started_year = models.TextField(null=True, blank=True)
    certificate_year_completed = models.TextField(null=True, blank=True)
    certificate_completed_year = models.TextField(null=True, blank=True)
    certificate_gpa = models.TextField(null=True, blank=True)

    diploma_institution = models.TextField(null=True, blank=True)
    diploma_field_of_study = models.TextField(null=True, blank=True)
    diploma_start_year = models.TextField(null=True, blank=True)
    diploma_started_year = models.TextField(null=True, blank=True)
    diploma_year_completed = models.TextField(null=True, blank=True)
    diploma_completed_year = models.TextField(null=True, blank=True)
    diploma_gpa = models.TextField(null=True, blank=True)

    bachelor_institution = models.TextField(null=True, blank=True)
    bachelor_field_of_study = models.TextField(null=True, blank=True)
    bachelor_start_year = models.TextField(null=True, blank=True)
    bachelor_started_year = models.TextField(null=True, blank=True)
    bachelor_year_completed = models.TextField(null=True, blank=True)
    bachelor_completed_year = models.TextField(null=True, blank=True)
    bachelor_gpa = models.TextField(null=True, blank=True)

    master_institution = models.TextField(null=True, blank=True)
    master_field_of_study = models.TextField(null=True, blank=True)
    master_start_year = models.TextField(null=True, blank=True)
    master_started_year = models.TextField(null=True, blank=True)
    master_year_completed = models.TextField(null=True, blank=True)
    master_completed_year = models.TextField(null=True, blank=True)
    master_gpa = models.TextField(null=True, blank=True)

    phd_institution = models.TextField(null=True, blank=True)
    phd_field_of_study = models.TextField(null=True, blank=True)
    phd_start_year = models.TextField(null=True, blank=True)
    phd_started_year = models.TextField(null=True, blank=True)
    phd_year_completed = models.TextField(null=True, blank=True)
    phd_completed_year = models.TextField(null=True, blank=True)
    phd_gpa = models.TextField(null=True, blank=True)

    # Legacy single professional qualification text field. Keep it for old forms.
    professional_qualifications = models.TextField(null=True, blank=True)

    # Legacy single professional qualification detail fields. Keep them for old export code.
    professional_qualification_institution = models.TextField(null=True, blank=True)
    professional_qualification_start_date = models.DateField(null=True, blank=True)
    professional_qualification_from = models.DateField(null=True, blank=True)
    professional_qualification_completed_date = models.DateField(null=True, blank=True)
    professional_qualification_to = models.DateField(null=True, blank=True)
    professional_qualification_country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    professional_qualification_region = models.CharField(max_length=120, null=True, blank=True)
    professional_qualification_region_post_code = models.CharField(max_length=30, null=True, blank=True)
    professional_qualification_district = models.CharField(max_length=120, null=True, blank=True)
    professional_qualification_district_post_code = models.CharField(max_length=30, null=True, blank=True)
    professional_qualification_ward = models.CharField(max_length=120, null=True, blank=True)
    professional_qualification_ward_post_code = models.CharField(max_length=30, null=True, blank=True)
    professional_qualification_street = models.CharField(max_length=180, null=True, blank=True)
    professional_qualification_mtaa = models.CharField(max_length=180, null=True, blank=True)
    professional_qualification_neighbourhood = models.CharField(max_length=180, null=True, blank=True)
    professional_qualification_place_neighbourhood = models.CharField(max_length=180, null=True, blank=True)
    professional_qualification_location = models.TextField(null=True, blank=True)
    professional_qualification_house_no = models.CharField(max_length=80, null=True, blank=True)
    professional_qualification_period = models.CharField(max_length=100, null=True, blank=True)
    professional_qualification_certificate_awarded = models.BooleanField(null=True, blank=True)

    # English proficiency
    english_test_name = models.TextField(null=True, blank=True)
    english_test_institution = models.TextField(null=True, blank=True)
    english_test_score = models.TextField(null=True, blank=True)
    english_test_year = models.TextField(null=True, blank=True)
    english_is_primary_language = models.BooleanField(null=True, blank=True)

    # Study, finance, medical, declaration
    program_level = models.CharField(max_length=80, choices=PROGRAM_LEVEL_CHOICES, null=True, blank=True)
    preferred_intake = models.CharField(max_length=80, choices=INTAKE_CHOICES, null=True, blank=True)
    accommodation_preference = models.CharField(max_length=100, choices=ACCOMMODATION_CHOICES, null=True, blank=True)
    education_sponsor = models.TextField(null=True, blank=True)
    estimated_budget_usd = models.TextField(null=True, blank=True)
    scholarship_applied = models.BooleanField(null=True, blank=True)
    scholarship_details = models.TextField(null=True, blank=True)
    has_medical_condition = models.BooleanField(null=True, blank=True)
    medical_condition_details = models.TextField(null=True, blank=True)
    needs_special_assistance = models.BooleanField(null=True, blank=True)
    special_assistance_details = models.TextField(null=True, blank=True)

    declaration_agreed = models.BooleanField(null=True, blank=True)

    serial_number = models.CharField(max_length=100, null=True, blank=True)
    generated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Supplemental Profile - Application #{self.application_id}"

    def clean(self):
        super().clean()
        errors = {}
        for prefix in ["current", "permanent", "professional_qualification"]:
            location_errors = LocationHelper.validate_location(
                region=getattr(self, f"{prefix}_region", ""),
                district=getattr(self, f"{prefix}_district", ""),
                ward=getattr(self, f"{prefix}_ward", ""),
                street=getattr(self, f"{prefix}_street", "") or getattr(self, f"{prefix}_mtaa", ""),
                neighbourhood=getattr(self, f"{prefix}_place_neighbourhood", "") or getattr(self, f"{prefix}_neighbourhood", ""),
            )
            for field, message in location_errors.items():
                field_name = f"{prefix}_{field}"
                if hasattr(self, field_name):
                    errors[field_name] = message
        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------
    # Normalized supplemental address accessors
    # (see ``ApplicationSupplementalAddress`` below).
    # ------------------------------------------------------------------
    def get_address(self, address_type):
        """Return the supplemental address row for ``address_type`` or ``None``."""
        try:
            return self.addresses.filter(address_type=address_type).first()
        except Exception:
            return None

    def sync_normalized_fields(self):
        """Mirror legacy supplemental columns into the normalized table."""
        from django.db import DatabaseError

        try:
            _sync_supplemental_profile_normalized(self)
        except DatabaseError:
            pass


class ApplicationSupplementalAddress(models.Model):
    """Normalised current / permanent / professional-qualification addresses
    for an ``ApplicationSupplementalProfile``.

    This is the supplemental-profile analogue of ``StudentAddress``. It
    drains the wide ``current_*``, ``permanent_*`` and
    ``professional_qualification_*`` location columns off the parent table
    so the row-size limit is no longer at risk.
    """

    ADDRESS_TYPE_CHOICES = [
        ("current", "Current Address"),
        ("permanent", "Permanent Address"),
        ("professional_qualification", "Professional Qualification"),
        ("other", "Other"),
    ]

    supplemental = models.ForeignKey(
        "ApplicationSupplementalProfile",
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(max_length=40, choices=ADDRESS_TYPE_CHOICES)

    country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    region = models.CharField(max_length=120, blank=True)
    region_post_code = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=120, blank=True)
    district_post_code = models.CharField(max_length=30, blank=True)
    ward = models.CharField(max_length=120, blank=True)
    ward_post_code = models.CharField(max_length=30, blank=True)
    house_no = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    duration_at_address = models.CharField(max_length=120, blank=True)
    address_status = models.CharField(max_length=120, blank=True)

    street = models.TextField(blank=True)
    mtaa = models.TextField(blank=True)
    village = models.TextField(blank=True)
    neighbourhood = models.TextField(blank=True)
    place_neighbourhood = models.TextField(blank=True)
    landmark = models.TextField(blank=True)
    nearest_landmark = models.TextField(blank=True)
    address_line = models.TextField(blank=True)
    location = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("supplemental", "address_type")]
        verbose_name = "Application Supplemental Address"
        verbose_name_plural = "Application Supplemental Addresses"
        ordering = ["supplemental_id", "address_type"]

    def __str__(self):
        return f"{self.get_address_type_display()} (supplemental #{self.supplemental_id})"


def _sync_supplemental_profile_normalized(supplemental: "ApplicationSupplementalProfile") -> None:
    """Mirror legacy supplemental columns into ApplicationSupplementalAddress."""
    address_specs = [
        (
            "current",
            {
                "country": _attr(supplemental, "current_country"),
                "region": _attr(supplemental, "current_region"),
                "region_post_code": _attr(supplemental, "current_region_post_code"),
                "city": _attr(supplemental, "current_city"),
                "district": _attr(supplemental, "current_district"),
                "district_post_code": _attr(supplemental, "current_district_post_code"),
                "ward": _attr(supplemental, "current_ward"),
                "ward_post_code": _attr(supplemental, "current_ward_post_code"),
                "house_no": _attr(supplemental, "current_house_no"),
                "postal_code": _attr(supplemental, "current_postal_code"),
                "duration_at_address": _attr(supplemental, "current_duration_at_address"),
                "address_status": _attr(supplemental, "current_address_status"),
                "street": _attr(supplemental, "current_street"),
                "mtaa": _attr(supplemental, "current_mtaa"),
                "village": _attr(supplemental, "current_village"),
                "neighbourhood": _attr(supplemental, "current_neighbourhood"),
                "place_neighbourhood": _attr(supplemental, "current_place_neighbourhood"),
                "landmark": _attr(supplemental, "current_landmark"),
                "nearest_landmark": _attr(supplemental, "current_nearest_landmark"),
                "address_line": _attr(supplemental, "current_address"),
                "remarks": _attr(supplemental, "current_address_remarks"),
            },
        ),
        (
            "permanent",
            {
                "country": _attr(supplemental, "permanent_country"),
                "region": _attr(supplemental, "permanent_region"),
                "region_post_code": _attr(supplemental, "permanent_region_post_code"),
                "city": _attr(supplemental, "permanent_city"),
                "district": _attr(supplemental, "permanent_district"),
                "district_post_code": _attr(supplemental, "permanent_district_post_code"),
                "ward": _attr(supplemental, "permanent_ward"),
                "ward_post_code": _attr(supplemental, "permanent_ward_post_code"),
                "house_no": _attr(supplemental, "permanent_house_no"),
                "postal_code": _attr(supplemental, "permanent_postal_code"),
                "duration_at_address": _attr(supplemental, "permanent_duration_at_address"),
                "address_status": _attr(supplemental, "permanent_address_status"),
                "street": _attr(supplemental, "permanent_street"),
                "mtaa": _attr(supplemental, "permanent_mtaa"),
                "village": _attr(supplemental, "permanent_village"),
                "neighbourhood": _attr(supplemental, "permanent_neighbourhood"),
                "place_neighbourhood": _attr(supplemental, "permanent_place_neighbourhood"),
                "landmark": _attr(supplemental, "permanent_landmark"),
                "nearest_landmark": _attr(supplemental, "permanent_nearest_landmark"),
                "address_line": _attr(supplemental, "permanent_address"),
                "remarks": _attr(supplemental, "permanent_address_remarks"),
            },
        ),
        (
            "professional_qualification",
            {
                "country": _attr(supplemental, "professional_qualification_country"),
                "region": _attr(supplemental, "professional_qualification_region"),
                "region_post_code": _attr(supplemental, "professional_qualification_region_post_code"),
                "district": _attr(supplemental, "professional_qualification_district"),
                "district_post_code": _attr(supplemental, "professional_qualification_district_post_code"),
                "ward": _attr(supplemental, "professional_qualification_ward"),
                "ward_post_code": _attr(supplemental, "professional_qualification_ward_post_code"),
                "house_no": _attr(supplemental, "professional_qualification_house_no"),
                "street": _attr(supplemental, "professional_qualification_street"),
                "mtaa": _attr(supplemental, "professional_qualification_mtaa"),
                "neighbourhood": _attr(supplemental, "professional_qualification_neighbourhood"),
                "place_neighbourhood": _attr(supplemental, "professional_qualification_place_neighbourhood"),
                "location": _attr(supplemental, "professional_qualification_location"),
            },
        ),
    ]
    for address_type, defaults in address_specs:
        if _row_has_content(defaults):
            ApplicationSupplementalAddress.objects.update_or_create(
                supplemental=supplemental,
                address_type=address_type,
                defaults=defaults,
            )


class ProfessionalQualification(models.Model):
    """Exactly three export-ready professional qualifications per application.

    Use order_number 1, 2 and 3. The PDF layout can render order 1 on the right,
    order 2 in the centre, and order 3 on the left.
    """

    YES_NO_CHOICES = [
        ("", "---------"),
        ("yes", "Yes"),
        ("no", "No"),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="professional_qualification_entries")
    order_number = models.PositiveSmallIntegerField(default=1, help_text="Use 1, 2 or 3 only")
    qualification_title = models.CharField(max_length=255, blank=True)
    institution = models.CharField(max_length=255, blank=True)
    institution_address = models.TextField(blank=True)
    country = models.CharField(max_length=100, blank=True, default=COUNTRY_DEFAULT)
    period = models.CharField(max_length=100, blank=True)
    start_date = models.DateField(null=True, blank=True)
    finished_date = models.DateField(null=True, blank=True)
    award_certificate = models.CharField(max_length=10, choices=YES_NO_CHOICES, blank=True)

    # Optional mtaa-backed institution location. No House No. and no Neighbourhood
    # are required by your latest Professional Qualifications layout, so those are
    # intentionally not used for export here.
    region = models.CharField(max_length=120, blank=True)
    district = models.CharField(max_length=120, blank=True)
    ward = models.CharField(max_length=120, blank=True)
    street = models.CharField(max_length=180, blank=True)
    mtaa = models.CharField(max_length=180, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order_number", "id"]
        unique_together = ["application", "order_number"]
        verbose_name = "Professional Qualification"
        verbose_name_plural = "Professional Qualifications"

    def __str__(self):
        title = self.qualification_title or "Professional Qualification"
        return f"{title} - Application #{self.application_id}"

    def clean(self):
        super().clean()
        errors = {}
        if self.order_number not in [1, 2, 3]:
            errors["order_number"] = "Only three professional qualifications are allowed: 1, 2 or 3."
        if self.start_date and self.finished_date and self.finished_date < self.start_date:
            errors["finished_date"] = "Finished date cannot be earlier than start date."
        location_errors = LocationHelper.validate_location(
            region=self.region,
            district=self.district,
            ward=self.ward,
            street=self.street or self.mtaa,
        )
        for field, message in location_errors.items():
            if hasattr(self, field):
                errors[field] = message
        if errors:
            raise ValidationError(errors)

    @property
    def award_certificate_boolean(self) -> Optional[bool]:
        if self.award_certificate == "yes":
            return True
        if self.award_certificate == "no":
            return False
        return None

    def to_pdf_dict(self) -> Dict[str, str]:
        return {
            "Qualification Title": self.qualification_title or "-",
            "Qualification / Training": self.qualification_title or "-",
            "Institution": self.institution or "-",
            "Institution Address": self.institution_address or self.street or self.mtaa or "-",
            "Country": self.country,
            "Period": self.period or "-",
            "Start Date": self.start_date.strftime("%d/%m/%Y") if self.start_date else "-",
            "Finished Date": self.finished_date.strftime("%d/%m/%Y") if self.finished_date else "-",
            "Completed Date": self.finished_date.strftime("%d/%m/%Y") if self.finished_date else "-",
            "Award / Certificate?": self.get_award_certificate_display() if self.award_certificate else "-",
            "Region": self.region or "-",
            "District": self.district or "-",
            "Ward": self.ward or "-",
            "Street": self.street or self.mtaa or "-",
        }


class Document(models.Model):
    DOCUMENT_TYPES = [
        ("passport", "Passport Copy"),
        ("passport_photo", "Passport Photo"),
        ("ordinary_level", "Ordinary Level Certificate"),
        ("advanced_level", "Advanced Level Certificate"),
        ("academic_transcript", "Academic Transcript"),
        ("degree_certificate", "Degree / Diploma Certificate"),
        ("application_form", "Application Form"),
        ("recommendation_letter", "Recommendation Letter"),
        ("sop", "Statement of Purpose / Motivation Letter"),
        ("cv", "CV / Resume"),
        ("language_test", "English Proficiency Test (IELTS / TOEFL)"),
        ("proof_of_funds", "Proof of Funds"),
        ("health_insurance", "Health Insurance"),
        ("financial_documents", "Financial Documents (Legacy)"),
        ("other", "Other Document"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to="documents/")
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


class Payment(models.Model):
    PAYMENT_STATUS = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("settled", "Settled"),
    ]

    PAYMENT_METHODS = [
        ("mobile_money", "Mobile Money"),
        ("card", "Card Payment"),
        ("bank_transfer", "Bank Transfer"),
    ]

    PAYMENT_GATEWAYS = [
        ("clickpesa", "ClickPesa"),
        ("azampay", "AzamPay"),
        ("manual", "Manual Payment"),
    ]

    student = models.ForeignKey(User, on_delete=models.CASCADE)
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="TZS")
    payment_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS, default="mobile_money")
    payment_gateway = models.CharField(max_length=20, choices=PAYMENT_GATEWAYS, default="clickpesa")

    order_reference = models.CharField(max_length=100, unique=True, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default="pending")
    is_successful = models.BooleanField(default=False)

    phone_number = models.CharField(max_length=20, blank=True)
    mobile_provider = models.CharField(max_length=50, blank=True)
    card_last_four = models.CharField(max_length=4, blank=True)

    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    account_name = models.CharField(max_length=100, blank=True)

    channel = models.CharField(max_length=100, blank=True)
    message = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    clickpesa_response = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-payment_date"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"Payment {self.order_reference} - {self.student.username} - {self.status}"

    def is_pending(self):
        return self.status in ["pending", "processing"]

    def is_completed(self):
        return self.status in ["success", "settled"]


class ApplicationAssignment(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="assignments")
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assigned_applications")
    assigned_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ["application", "employee"]
        verbose_name = "Application Assignment"
        verbose_name_plural = "Application Assignments"
        ordering = ["-assigned_date"]

    def __str__(self):
        return f"{self.employee.username} - Application #{self.application.id} ({self.application.student.username})"
