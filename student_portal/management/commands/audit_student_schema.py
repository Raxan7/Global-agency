"""audit_student_schema — diagnose the student_portal tables after the 1118 fix.

Reports:
* which migrations are applied
* row counts and row format for the wide tables
* which legacy wide columns physically exist
* counts in the new normalized tables
* a sample of students who have no data in the new normalized tables

Run with::

    python manage.py audit_student_schema
    python manage.py audit_student_schema --json
"""
from __future__ import annotations

import json
from collections import OrderedDict

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


WIDE_TABLES = (
    "student_portal_studentprofile",
    "student_portal_applicationsupplementalprofile",
    "student_portal_workexperience",
)

NORMALIZED_TABLES = (
    "student_portal_studentaddress",
    "student_portal_studentpassport",
    "student_portal_studentfamilycontact",
    "student_portal_studentschoolhistory",
    "student_portal_applicationsupplementaladdress",
)

LEGACY_COLUMN_PREFIXES = (
    "father_",
    "mother_",
    "emergency_",
    "permanent_",
    "personal_",
    "school_olevel_",
    "school_alevel_",
    "primary_school_",
    "passport_",
    "current_",
    "professional_qualification_",
)


def _row_format_for(table: str) -> str:
    if connection.vendor != "mysql":
        return "n/a"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT CREATE_OPTIONS FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            [table],
        )
        row = cursor.fetchone()
        if not row:
            return "table missing"
        options = (row[0] or "").lower()
        if "row_format=dynamic" in options:
            return "DYNAMIC"
        if "row_format=compact" in options:
            return "COMPACT"
        return options or "default"


def _physical_columns(table: str) -> set[str]:
    if connection.vendor != "mysql":
        # Fall back to ORM introspection for SQLite tests.
        try:
            from django.db import connection as conn
            with conn.cursor() as cursor:
                return {col.name for col in conn.introspection.get_table_description(cursor, table)}
        except Exception:
            return set()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            [table],
        )
        return {row[0] for row in cursor.fetchall()}


def _row_count(table: str) -> int:
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            return int(cursor.fetchone()[0])
    except Exception as exc:  # pragma: no cover
        return -1


def _sample_students_without_normalized_rows(limit: int = 5) -> list[dict]:
    """Return up to ``limit`` StudentProfile rows that have no normalized
    address/passport/contact/school rows yet."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT sp.id, sp.user_id
                FROM student_portal_studentprofile sp
                LEFT JOIN student_portal_studentaddress sa ON sa.student_id = sp.id
                LEFT JOIN student_portal_studentpassport sps ON sps.student_id = sp.id
                WHERE sa.id IS NULL AND sps.id IS NULL
                LIMIT %s
                """,
                [limit],
            )
            return [{"student_id": r[0], "user_id": r[1]} for r in cursor.fetchall()]
    except Exception:
        return []


class Command(BaseCommand):
    help = "Audit the student_portal schema and the 1118 recovery state."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json", help="Emit machine-readable JSON.")

    def handle(self, *args, **options):
        report = OrderedDict()
        applied = MigrationRecorder(connection).applied_migrations()
        report["applied_migrations"] = [
            {"app": m.app, "name": m.name}
            for m in sorted(applied.values(), key=lambda m: (m.app, m.name))
            if m.app == "student_portal"
        ]
        report["wide_tables"] = OrderedDict()
        for table in WIDE_TABLES:
            report["wide_tables"][table] = {
                "row_format": _row_format_for(table),
                "row_count": _row_count(table),
                "physical_columns": sorted(_physical_columns(table)),
            }
        report["normalized_tables"] = OrderedDict()
        for table in NORMALIZED_TABLES:
            report["normalized_tables"][table] = {
                "row_count": _row_count(table),
                "physical_columns": sorted(_physical_columns(table)),
            }
        report["legacy_columns_missing"] = OrderedDict()
        for table in WIDE_TABLES:
            physical = _physical_columns(table)
            missing = sorted(
                {
                    f"{prefix}{col}"
                    for prefix in LEGACY_COLUMN_PREFIXES
                    for col in (
                        "country",
                        "region",
                        "district",
                        "ward",
                        "street",
                        "mtaa",
                        "house_no",
                        "address",
                        "name",
                        "phone",
                        "email",
                        "occupation",
                        "relation",
                    )
                }
                - physical
            )
            report["legacy_columns_missing"][table] = missing
        report["students_without_normalized_rows"] = _sample_students_without_normalized_rows()

        if options.get("as_json"):
            self.stdout.write(json.dumps(report, indent=2, default=str))
            return

        self.stdout.write(self.style.NOTICE("=== student_portal audit ==="))
        self.stdout.write(f"Applied migrations: {len(report['applied_migrations'])}")
        for m in report["applied_migrations"]:
            self.stdout.write(f"  - {m['app']}.{m['name']}")
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Wide tables (potential 1118 risk):"))
        for table, info in report["wide_tables"].items():
            self.stdout.write(
                f"  {table}: rows={info['row_count']}  format={info['row_format']}  "
                f"columns={len(info['physical_columns'])}"
            )
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Normalized tables:"))
        for table, info in report["normalized_tables"].items():
            self.stdout.write(f"  {table}: rows={info['row_count']}")
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Students with no normalized rows (sample):"))
        for row in report["students_without_normalized_rows"]:
            self.stdout.write(f"  student_id={row['student_id']} user_id={row['user_id']}")
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Legacy wide columns physically missing (top prefixes):"))
        for table, missing in report["legacy_columns_missing"].items():
            self.stdout.write(f"  {table}: {len(missing)} missing")
            for col in missing[:10]:
                self.stdout.write(f"    - {col}")
            if len(missing) > 10:
                self.stdout.write(f"    ... and {len(missing) - 10} more")
