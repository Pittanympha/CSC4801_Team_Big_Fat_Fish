"""Documentation, traceability, and packaging checks (FP-PROC-1, FP-DOC-1/2, FP-TEST-1, FP-SUB-1)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = PROJECT_ROOT / "tests"

REQUIRED_IDS = [
    "FP-ARCH-1",
    "FP-AUTH-1",
    "FP-AUTH-2",
    "FP-AUTH-3",
    "FP-CAN-1",
    "FP-CAN-2",
    "FP-CAN-3",
    "FP-EMP-1",
    "FP-EMP-2",
    "FP-EMP-3",
    "FP-MATCH-1",
    "FP-MATCH-2",
    "FP-SCHED-1",
    "FP-SCHED-2",
    "FP-SCHED-3",
    "FP-SEC-1",
    "FP-SEC-2",
    "FP-SEC-3",
    "FP-SEC-4",
    "FP-PROC-1",
    "FP-DOC-1",
    "FP-DOC-2",
    "FP-DOC-3",
    "FP-TEST-1",
    "FP-SUB-1",
]

FUNCTIONAL_PREFIXES = [
    "fp_auth_1",
    "fp_auth_2",
    "fp_auth_3",
    "fp_can_1",
    "fp_can_2",
    "fp_can_3",
    "fp_emp_1",
    "fp_emp_2",
    "fp_emp_3",
    "fp_match_1",
    "fp_sched_1",
    "fp_sched_2",
    "fp_sched_3",
]


def test_sources() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(TESTS_ROOT.glob("test_*.py"))
    )


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.spec = (PROJECT_ROOT / "SPEC.md").read_text(encoding="utf-8")
        self.install = (PROJECT_ROOT / "INSTALL.md").read_text(encoding="utf-8")

    def test_fp_doc_2_readme_maps_every_requirement_id(self):
        for requirement_id in REQUIRED_IDS:
            with self.subTest(requirement_id=requirement_id):
                self.assertIn(requirement_id, self.readme)

    def test_fp_doc_2_every_mapped_test_name_exists(self):
        mapped = set(re.findall(r"test_fp_[a-z0-9_]+", self.readme))
        source = test_sources()
        self.assertGreater(len(mapped), 40)
        for name in sorted(mapped):
            with self.subTest(test=name):
                self.assertIn(f"def {name}(", source)

    def test_fp_doc_2_readme_has_demo_credentials_and_test_command(self):
        self.assertIn("DemoPass123!", self.readme)
        for email in (
            "alice@demo.test",
            "bob@demo.test",
            "carol@demo.test",
            "dave@demo.test",
            "erin@demo.test",
            "hr@acme.test",
            "hr@globex.test",
        ):
            self.assertIn(email, self.readme)
        self.assertIn("python -m unittest discover -s tests -v", self.readme)

    def test_fp_proc_1_spec_covers_architecture_data_auth_routes_matching_booking_security(self):
        spec = self.spec.lower()
        for topic in (
            "architecture",
            "data model",
            "authentication and authorization",
            "routes",
            "ui screens",
            "matching contract",
            "booking transaction",
            "security controls",
        ):
            with self.subTest(topic=topic):
                self.assertIn(topic, spec)

    def test_fp_doc_1_install_documents_build_run_seed_and_test(self):
        for token in (
            "docker build",
            "docker run",
            "init-db",
            "seed",
            "python -m unittest discover -s tests -v",
            "SECRET_KEY",
            "DATABASE_PATH",
            "requirements.txt",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.install)

    def test_fp_test_1_documented_test_command_runs_suite(self):
        self.assertIn("python -m unittest discover -s tests -v", self.install)
        definitions = re.findall(r"def (test_[a-z0-9_]+)\(", test_sources())
        self.assertGreaterEqual(len(definitions), 70)
        for prefix in FUNCTIONAL_PREFIXES:
            with self.subTest(prefix=prefix):
                self.assertTrue(
                    any(prefix in name for name in definitions),
                    f"no unit test covers {prefix}",
                )

    def test_fp_sub_1_dockerfile_and_submission_checklist_present(self):
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("FROM python:", dockerfile)
        self.assertIn("requirements.txt", dockerfile)
        self.assertIn("ENTRYPOINT", dockerfile)
        self.assertNotIn("ADD http", dockerfile)

        checklist = (PROJECT_ROOT / "SUBMISSION_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("40-character", checklist)
        self.assertIn("public", checklist.lower())
        self.assertIn("/commit/", checklist)

    def test_fp_arch_1_repository_contains_all_stack_layers(self):
        self.assertTrue((PROJECT_ROOT / "app" / "templates" / "base.html").exists())
        self.assertTrue((PROJECT_ROOT / "app" / "schema.sql").exists())
        self.assertTrue((PROJECT_ROOT / "app" / "static" / "style.css").exists())
        self.assertTrue((PROJECT_ROOT / "run.py").exists())
