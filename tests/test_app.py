import os
import tempfile
import unittest
from pathlib import Path

os.environ["APP_ENV"] = "development"
os.environ["ADMIN_EMAIL"] = "admin@test.pawpaw"
os.environ["ADMIN_PASSWORD"] = "PawpawTestAdmin!2026"
_tmp = tempfile.TemporaryDirectory(prefix="pawpaw-tests-")
os.environ["DATABASE_PATH"] = str(Path(_tmp.name) / "test.sqlite3")

from fastapi.testclient import TestClient
from main import app


class PawPawApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()
        cls.csrf = cls.client.get("/api/csrf").json()["csrfToken"]
        cls.headers = {"X-CSRF-Token": cls.csrf}

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        _tmp.cleanup()

    def test_health_and_catalog(self):
        self.assertEqual(self.client.get("/api/health").json()["status"], "ok")
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/static/style.css").status_code, 200)
        self.assertEqual(self.client.get("/api/unknown").status_code, 404)
        self.assertEqual(self.client.get("/").headers.get("x-frame-options"), "DENY")
        rows = self.client.get("/api/products?q=PuppyCare").json()
        self.assertEqual(len(rows), 1)
        self.assertGreater(rows[0]["stock"], 0)

    def test_order_transaction_decrements_stock_and_lookup_works(self):
        product = self.client.get("/api/products/hat-dinh-duong-puppycare").json()
        before = product["stock"]
        response = self.client.post("/api/orders", headers=self.headers, json={
            "items": [{"productId": product["id"], "quantity": 2}],
            "customer": {"name": "Nguyen An", "phone": "0901234567", "address": "Ha Noi"},
            "paymentMethod": "cod",
        })
        self.assertEqual(response.status_code, 200, response.text)
        order = response.json()
        after = self.client.get("/api/products/hat-dinh-duong-puppycare").json()["stock"]
        self.assertEqual(after, before - 2)
        found = self.client.post("/api/orders/lookup", headers=self.headers, json={"code": order["order_code"], "phone": "0901234567"})
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json()["total_vnd"], 640000)

    def test_checkout_rejects_online_payment_before_provider_is_configured(self):
        product = self.client.get("/api/products/hat-dinh-duong-puppycare").json()
        response = self.client.post("/api/orders", headers=self.headers, json={
            "items": [{"productId": product["id"], "quantity": 1}],
            "customer": {"name": "Nguyen An", "phone": "0901234567", "address": "Ha Noi"},
            "paymentMethod": "card",
        })
        self.assertEqual(response.status_code, 422)

    def test_customer_login_and_admin_guard(self):
        register = self.client.post("/api/auth/register", headers=self.headers, json={
            "email": "customer@example.com", "fullName": "Paw Customer", "phone": "0901234567", "password": "CustomerPass!26"
        })
        self.assertEqual(register.status_code, 200, register.text)
        self.assertEqual(self.client.get("/api/admin/dashboard").status_code, 403)
        self.client.post("/api/auth/logout", headers=self.headers)
        login = self.client.post("/api/auth/login", headers=self.headers, json={"email":"admin@test.pawpaw","password":"PawpawTestAdmin!2026"})
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(self.client.get("/api/admin/dashboard").status_code, 200)

    def test_booking_slot_is_unique(self):
        body = {"serviceType":"grooming","petName":"Bo","petSpecies":"Chó","ownerName":"An","phone":"0901234567","serviceDate":"2032-05-12","timeSlot":"10:00"}
        first = self.client.post("/api/bookings", headers=self.headers, json=body)
        second = self.client.post("/api/bookings", headers=self.headers, json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 409)


if __name__ == "__main__":
    unittest.main()
