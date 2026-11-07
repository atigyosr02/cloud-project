import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app import create_app
from app.models.user import User


class RouteSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "SECRET_KEY": "unit-test-secret",
                "TESTING": True,
                "WTF_CSRF_ENABLED": False,
            }
        )
        cls.client = cls.app.test_client()

    def request_as(self, role: str, path: str, method: str = "get", data=None):
        user = User(
            {
                "id": 71,
                "email": "test@medicare.test",
                "name": "Utilisateur Fictif",
                "role": role,
                "is_active": True,
            }
        )
        with patch("app.get_user_by_id", return_value=user):
            with self.client.session_transaction() as session:
                session["_user_id"] = user.id
                session["_fresh"] = True
            return getattr(self.client, method)(path, data=data)

    def test_secretary_cannot_access_medical_routes(self):
        paths = (
            "/patients/1/consultations",
            "/patients/1/consultations/new",
            "/patients/1/prescriptions/new",
            "/patients/1/documents/1/download",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.request_as("secretaire", path).status_code, 403)

    def test_admin_cannot_access_medical_routes(self):
        self.assertEqual(
            self.request_as("admin", "/patients/1/consultations").status_code,
            403,
        )
        self.assertEqual(
            self.request_as("admin", "/patients/1/documents/1/download").status_code,
            403,
        )

    def test_patient_cannot_access_staff_or_medical_routes(self):
        paths = (
            "/patients",
            "/patients/1",
            "/appointments",
            "/patients/1/consultations",
            "/patients/1/prescriptions/new",
            "/patients/1/documents/1/download",
            "/admin/users",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.request_as("patient", path).status_code, 403)

    def test_patient_portal_uses_only_the_logged_in_account(self):
        patient = {
            "id": 88,
            "full_name": "Patiente Fictive",
            "date_of_birth": None,
            "phone": None,
            "email": "patient@exemple.test",
        }
        prescription = {
            "prescribed_at": datetime(2026, 11, 6, 9, 0),
            "medicines": "Médicament fictif · 1 comprimé le matin",
            "instructions": "Exemple de démonstration",
            "doctor_name": "Dr Médecin Fictif",
        }
        with patch("app.routes.portal.fetch_one", return_value=patient) as patient_lookup, patch(
            "app.routes.portal.fetch_all", side_effect=[[], [], [], [prescription]]
        ) as list_lookup, patch("app.routes.portal.log_action"):
            response = self.request_as("patient", "/espace-patient")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Patiente Fictive", response.data)
        self.assertIn(b"Mon dossier patient", response.data)
        self.assertIn(b"Consultations", response.data)
        self.assertIn(b"Documents m\xc3\xa9dicaux", response.data)
        self.assertIn(b"Ordonnances", response.data)
        self.assertIn(b"M\xc3\xa9dicament fictif", response.data)
        self.assertEqual(patient_lookup.call_args.args[1], (71,))
        self.assertEqual(list_lookup.call_count, 4)
        self.assertTrue(all(call.args[1] == (88,) for call in list_lookup.call_args_list))

    def test_doctor_can_add_a_prescription_to_patient_record(self):
        s3 = MagicMock()
        with patch(
            "app.routes.prescriptions.fetch_one",
            return_value={"id": 88, "full_name": "Patiente Fictive"},
        ), patch("app.routes.prescriptions.s3_client", return_value=s3), patch(
            "app.routes.prescriptions.ensure_bucket"
        ), patch("app.routes.prescriptions.execute_audited") as save_prescription:
            response = self.request_as(
                "medecin",
                "/patients/88/prescriptions/new",
                method="post",
                data={
                    "medicines": "Médicament A · 1 comprimé le matin\n\nMédicament B · 1 gélule le soir",
                    "instructions": "Exemple uniquement",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("INSERT INTO prescriptions", save_prescription.call_args.args[0])
        self.assertIn("INSERT INTO documents", save_prescription.call_args.args[0])
        parameters = save_prescription.call_args.args[1]
        self.assertEqual(parameters[:4], (88, 71, "Médicament A · 1 comprimé le matin\nMédicament B · 1 gélule le soir", "Exemple uniquement"))
        self.assertEqual(parameters[4], 88)
        self.assertEqual(parameters[5], 71)
        self.assertEqual(parameters[6], s3.put_object.call_args.kwargs["Key"])
        self.assertEqual(parameters[7], "Ordonnance médicale")
        self.assertEqual(parameters[8], "application/pdf")
        self.assertTrue(s3.put_object.call_args.kwargs["Body"].startswith(b"%PDF-"))

    def test_patient_document_download_checks_ownership(self):
        document = {"object_key": "documents/fake.pdf", "patient_id": 88}
        client = MagicMock()
        client.generate_presigned_url.return_value = "https://s3.example.test/signed"
        with patch("app.routes.portal.fetch_one", return_value=document) as lookup, patch(
            "app.routes.portal.s3_client", return_value=client
        ), patch("app.routes.portal.log_action"):
            response = self.request_as("patient", "/espace-patient/documents/9/download")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "https://s3.example.test/signed")
        self.assertIn("p.user_id = %s", lookup.call_args.args[0])
        self.assertEqual(lookup.call_args.args[1], (9, 71))
        self.assertEqual(client.generate_presigned_url.call_args.kwargs["ExpiresIn"], 60)

    def test_patient_cannot_download_another_patients_document(self):
        with patch("app.routes.portal.fetch_one", return_value=None) as lookup:
            response = self.request_as("patient", "/espace-patient/documents/99/download")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(lookup.call_args.args[1], (99, 71))

    def test_secretary_cannot_upload_a_medical_document(self):
        response = self.request_as(
            "secretaire",
            "/patients/1/documents",
            method="post",
        )
        self.assertEqual(response.status_code, 403)

    def test_document_lookup_is_scoped_to_patient(self):
        with patch("app.routes.documents.fetch_one", return_value=None) as lookup:
            response = self.request_as("medecin", "/patients/22/documents/9/download")
        self.assertEqual(response.status_code, 404)
        self.assertIn("patient_id = %s", lookup.call_args.args[0])
        self.assertEqual(lookup.call_args.args[1], (9, 22))

    def test_health_and_security_headers(self):
        self.client = self.app.test_client()
        with patch("app.get_user_by_id", return_value=None), patch("app.database_health", return_value=True):
            response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("Content-Security-Policy", response.headers)


if __name__ == "__main__":
    unittest.main()