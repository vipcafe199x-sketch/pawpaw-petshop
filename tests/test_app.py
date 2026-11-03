"""Isolated QA database. Every scenario creates its own random test-only products.

No production contacts, order identifiers, SKUs, prices or stock snapshots are used.
"""
import os
import secrets
import tempfile
import unittest
from pathlib import Path

os.environ['APP_ENV'] = 'development'
os.environ['ADMIN_EMAIL'] = 'qa-admin@example.invalid'
os.environ['ADMIN_PASSWORD'] = secrets.token_urlsafe(24)
_tmp = tempfile.TemporaryDirectory(prefix='pawpaw-tests-')
os.environ['DATABASE_PATH'] = str(Path(_tmp.name) / 'qa.sqlite3')

from fastapi.testclient import TestClient
from main import app
from backend.database import connect
from backend.repair_reported_data import repair_reported_data


class PawPawApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.client.__enter__()
        cls.headers = {'X-CSRF-Token': cls.client.get('/api/csrf').json()['csrfToken']}

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        _tmp.cleanup()

    def setUp(self):
        self.login(self.client, self.headers)

    def login(self, client, headers):
        response = client.post('/api/auth/login', headers=headers, json={
            'email': os.environ['ADMIN_EMAIL'], 'password': os.environ['ADMIN_PASSWORD']})
        self.assertEqual(response.status_code, 200, response.text)

    def product(self):
        token = secrets.token_hex(6)
        response = self.client.post('/api/admin/products', headers=self.headers, json={
            'name': 'SYNTHETIC QA ' + token, 'slug': 'qa-' + token,
            'sku': 'QA-' + token, 'price_vnd': secrets.randbelow(10000) + 10000,
            'stock': secrets.randbelow(10) + 30, 'category': 'Phụ kiện', 'species': 'Chó'})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def order(self, product, quantity=1, coupon='', payment='cod'):
        return self.client.post('/api/orders', headers=self.headers, json={
            'items': [{'productId': product['id'], 'quantity': quantity}],
            'customer': {'name': 'SYNTHETIC QA', 'phone': '0000000000', 'address': 'TEST ADDRESS'},
            'coupon': coupon, 'paymentMethod': payment})

    def stock(self, product):
        return self.client.get('/api/products/' + product['slug']).json()['stock']

    def test_health_catalog_search_sort(self):
        p = self.product()
        self.assertEqual(self.client.get('/api/health').json()['status'], 'ok')
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/').headers['x-frame-options'], 'DENY')
        self.assertEqual(self.client.get('/static/product-editor.js').status_code, 200)
        rows = self.client.get('/api/products', params={'q': p['sku'], 'category': p['category'], 'species': p['species'], 'sort': 'price-asc'}).json()
        self.assertEqual([r['id'] for r in rows], [p['id']])
        self.assertEqual(self.client.get('/api/unknown').status_code, 404)

    def test_customer_login_and_admin_guard(self):
        email = 'qa-' + secrets.token_hex(6) + '@example.invalid'
        password = secrets.token_urlsafe(24)
        response = self.client.post('/api/auth/register', headers=self.headers, json={
            'email': email, 'fullName': 'SYNTHETIC CUSTOMER', 'phone': '0000000000', 'password': password})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get('/api/admin/dashboard').status_code, 403)
        self.client.post('/api/auth/logout', headers=self.headers)
        self.assertEqual(self.client.post('/api/auth/login', headers=self.headers, json={'email': email, 'password': password}).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me').json()['role'], 'customer')

    def test_booking_slot_is_unique(self):
        body = {'serviceType': 'grooming', 'petName': 'QA', 'petSpecies': 'Chó',
                'ownerName': 'SYNTHETIC QA', 'phone': '0000000000',
                'serviceDate': '2050-01-01', 'timeSlot': '10:00'}
        self.assertEqual(self.client.post('/api/bookings', headers=self.headers, json=body).status_code, 200)
        self.assertEqual(self.client.post('/api/bookings', headers=self.headers, json=body).status_code, 409)

    def test_cod_stock_and_lookup(self):
        p = self.product()
        response = self.order(p, quantity=2)
        self.assertEqual(response.status_code, 200, response.text)
        order = response.json()
        self.assertEqual(self.stock(p), p['stock'] - 2)
        lookup = self.client.post('/api/orders/lookup', headers=self.headers, json={'code': order['order_code'], 'phone': '0000000000'})
        self.assertEqual(lookup.status_code, 200)
        self.assertEqual(lookup.json()['subtotal_vnd'], p['price_vnd'] * 2)
        self.assertEqual(lookup.json()['total_vnd'], order['total_vnd'])

    def test_online_payment_is_rejected(self):
        p = self.product()
        self.assertEqual(self.order(p, payment='card').status_code, 422)
        self.assertEqual(self.stock(p), p['stock'])

    def test_product_patch_validation_preserves_values(self):
        p = self.product()
        url = f"/api/admin/products/{p['id']}"
        for field, values in [('price_vnd', [None, '', ' ', 0, -1, 1.5, True]), ('stock', [None, '', -1, 1.5, True])]:
            for value in values:
                self.assertEqual(self.client.patch(url, headers=self.headers, json={field: value}).status_code, 422)
                current = self.client.get('/api/products/' + p['slug']).json()
                self.assertEqual((current['price_vnd'], current['stock']), (p['price_vnd'], p['stock']))
        changed = self.client.patch(url, headers=self.headers, json={'price_vnd': str(p['price_vnd'] + 1), 'stock': '0'})
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()['price_vnd'], p['price_vnd'] + 1)
        self.assertEqual(changed.json()['stock'], 0)

    def test_zero_price_cannot_checkout(self):
        p = self.product()
        with connect() as conn:
            conn.execute('UPDATE products SET price_vnd=0 WHERE id=?', (p['id'],))
        self.assertEqual(self.order(p).status_code, 422)
        self.assertEqual(self.stock(p), p['stock'])

    def test_free_shipping_before_coupon_at_boundary(self):
        p = self.product()
        threshold = p['price_vnd'] * 3
        self.client.patch('/api/admin/settings', headers=self.headers, json={'free_shipping_from_vnd': str(threshold)})
        coupon = 'QA-' + secrets.token_hex(6)
        with connect() as conn:
            conn.execute("INSERT INTO coupons(code,discount_type,discount_value,minimum_vnd) VALUES(?,'percent',10,0)", (coupon,))
        response = self.order(p, quantity=3, coupon=coupon)
        self.assertEqual(response.status_code, 200, response.text)
        order = response.json()
        self.assertEqual(order['subtotal_vnd'], threshold)
        self.assertGreater(order['discount_vnd'], 0)
        self.assertEqual(order['shipping_vnd'], 0)
        self.assertEqual(order['total_vnd'], threshold - order['discount_vnd'])
        self.assertEqual(self.order(p, quantity=2).json()['shipping_vnd'], 30000)

    def test_cancel_restores_once_and_excludes_revenue(self):
        p = self.product()
        before = self.client.get('/api/admin/dashboard').json()['revenue_vnd']
        reports = sum(m['revenue'] for m in self.client.get('/api/admin/reports').json()['months'])
        order = self.order(p, quantity=2).json()
        for _ in range(2):
            response = self.client.patch(f"/api/admin/orders/{order['id']}", headers=self.headers, json={'status': 'cancelled'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'cancelled')
            self.assertIn('items', response.json())
        self.assertEqual(self.stock(p), p['stock'])
        self.assertEqual(self.client.get('/api/admin/dashboard').json()['revenue_vnd'], before)
        self.assertEqual(sum(m['revenue'] for m in self.client.get('/api/admin/reports').json()['months']), reports)
        self.assertEqual(self.client.patch(f"/api/admin/orders/{order['id']}", headers=self.headers, json={'status': 'confirmed'}).status_code, 409)

    def test_cancel_rolls_back_if_ledger_write_fails(self):
        p = self.product()
        order = self.order(p).json()
        with connect() as conn:
            conn.execute("CREATE TRIGGER qa_block_restore BEFORE INSERT ON inventory_events WHEN NEW.delta>0 BEGIN SELECT RAISE(ABORT,'qa failure'); END")
        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                headers = {'X-CSRF-Token': client.get('/api/csrf').json()['csrfToken']}
                self.login(client, headers)
                self.assertEqual(client.patch(f"/api/admin/orders/{order['id']}", headers=headers, json={'status': 'cancelled'}).status_code, 500)
            with connect() as conn:
                self.assertEqual(conn.execute('SELECT status FROM orders WHERE id=?', (order['id'],)).fetchone()['status'], 'pending')
            self.assertEqual(self.stock(p), p['stock'] - 1)
        finally:
            with connect() as conn:
                conn.execute('DROP TRIGGER qa_block_restore')

    def test_legacy_cancel_repair_preview_and_idempotence(self):
        p = self.product()
        order = self.order(p, quantity=2).json()
        with connect() as conn:
            conn.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order['id'],))
        preview = repair_reported_data(cancelled_codes=[order['order_code']])
        self.assertFalse(preview['applied'])
        self.assertEqual(self.stock(p), p['stock'] - 2)
        result = repair_reported_data(apply=True, cancelled_codes=[order['order_code']])
        self.assertTrue(Path(result['backup']).exists())
        self.assertEqual(self.stock(p), p['stock'])
        again = repair_reported_data(apply=True, cancelled_codes=[order['order_code']])
        self.assertTrue(any('skipped' in action for action in again['actions']))
        self.assertEqual(self.stock(p), p['stock'])

    def test_quote_matches_final_order_without_mutating_stock_or_coupon(self):
        p = self.product()
        self.client.patch(f"/api/admin/products/{p['id']}", headers=self.headers, json={'price_vnd': 110000})
        self.client.patch('/api/admin/settings', headers=self.headers, json={'free_shipping_from_vnd': '299000'})
        coupon = 'QA-' + secrets.token_hex(6)
        with connect() as conn:
            conn.execute("INSERT INTO coupons(code,discount_type,discount_value,minimum_vnd) VALUES(?,'percent',10,0)", (coupon,))
            before_orders = conn.execute('SELECT COUNT(*) n FROM orders').fetchone()['n']
        payload = {'items': [{'productId': p['id'], 'quantity': 3}], 'coupon': coupon}
        preview = self.client.post('/api/orders/quote', headers=self.headers, json=payload)
        self.assertEqual(preview.status_code, 200, preview.text)
        quote = preview.json()
        self.assertEqual((quote['subtotal_vnd'], quote['discount_vnd'], quote['shipping_vnd'], quote['total_vnd']), (330000,33000,0,297000))
        self.assertEqual(self.stock(p), p['stock'])
        with connect() as conn:
            self.assertEqual(conn.execute('SELECT used_count FROM coupons WHERE code=?', (coupon,)).fetchone()['used_count'], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) n FROM orders').fetchone()['n'], before_orders)
        payload.update(customer={'name':'SYNTHETIC QA','phone':'0000000000','address':'TEST ADDRESS'}, expectedTotalVnd=quote['total_vnd'])
        order = self.client.post('/api/orders', headers=self.headers, json=payload)
        self.assertEqual(order.status_code, 200, order.text)
        for key in ('subtotal_vnd','discount_vnd','shipping_vnd','total_vnd'):
            self.assertEqual(order.json()[key], quote[key])
        self.client.patch(f"/api/admin/products/{p['id']}", headers=self.headers, json={'price_vnd': 110001})
        stale = self.client.post('/api/orders', headers=self.headers, json=payload)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.stock(p), p['stock']-3)
        payload['coupon'] = 'QA-INVALID'
        self.assertEqual(self.client.post('/api/orders/quote', headers=self.headers, json=payload).status_code, 422)

    def test_init_and_deploy_guard_preserve_existing_catalog(self):
        from backend.database import init_db, db_path
        from backend.deployment_guard import protect_existing_database, catalog_fingerprint
        from unittest.mock import patch
        p = self.product()
        with connect() as conn:
            conn.execute('UPDATE products SET stock=3,price_vnd=0 WHERE id=?', (p['id'],))
        before = catalog_fingerprint()
        init_db()
        self.assertEqual(catalog_fingerprint(), before)
        guarded = protect_existing_database(db_path().parent)
        self.assertTrue(guarded['backup_created'])
        self.assertTrue(guarded['catalog_unchanged'])
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory)/'missing.sqlite3')
            with patch.dict(os.environ, {'APP_ENV':'production','ALLOW_DATABASE_INIT':'0','DATABASE_PATH':missing}):
                with self.assertRaises(RuntimeError):
                    init_db()
                self.assertFalse(Path(missing).exists())

    def test_repair_product_by_sku_and_price_only_preserves_other_stock(self):
        p, unpriced, untouched = self.product(), self.product(), self.product()
        with connect() as conn:
            conn.execute("UPDATE products SET name='RENAMED QA',price_vnd=0,stock=0 WHERE id=?", (p['id'],))
            conn.execute('UPDATE products SET price_vnd=0,active=0 WHERE id=?', (unpriced['id'],))
        preview = repair_reported_data(product_repairs={p['sku']:(p['price_vnd'],p['stock'])}, price_repairs={unpriced['sku']:unpriced['price_vnd']})
        self.assertFalse(preview['applied'])
        self.assertEqual(self.stock(p), 0)
        repair_reported_data(True, product_repairs={p['sku']:(p['price_vnd'],p['stock'])}, price_repairs={unpriced['sku']:unpriced['price_vnd']})
        self.assertEqual(self.stock(p), p['stock'])
        restored = self.client.get('/api/products/'+p['slug']).json()
        self.assertEqual(restored['price_vnd'],p['price_vnd'])
        self.assertEqual(self.stock(unpriced),unpriced['stock'])
        self.assertEqual(self.stock(untouched),untouched['stock'])
        repair_reported_data(True, product_repairs={p['sku']:(p['price_vnd']+1,999)})
        self.assertEqual(self.stock(p),p['stock'])

    def test_partial_legacy_cancel_restores_each_product_only_once(self):
        a, b = self.product(), self.product()
        response = self.client.post('/api/orders', headers=self.headers, json={'items':[{'productId':a['id'],'quantity':2},{'productId':b['id'],'quantity':2}], 'customer':{'name':'SYNTHETIC QA','phone':'0000000000','address':'TEST ADDRESS'}})
        self.assertEqual(response.status_code,200,response.text)
        order = response.json()
        with connect() as conn:
            conn.execute("UPDATE orders SET status='cancelled' WHERE id=?",(order['id'],))
            conn.execute('UPDATE products SET stock=stock+1 WHERE id=?',(a['id'],))
            conn.execute('INSERT INTO inventory_events(product_id,delta,reason) VALUES(?,?,?)',(a['id'],1,'Hủy đơn '+order['order_code']))
        for _ in range(2):
            repair_reported_data(True,cancelled_codes=[order['order_code']])
            self.assertEqual(self.stock(a),a['stock'])
            self.assertEqual(self.stock(b),b['stock'])

    def test_status_rejection_readback_and_audited_manual_rewind(self):
        p = self.product();order = self.order(p).json()
        for status in ['confirmed','preparing']:
            self.assertEqual(self.client.patch(f"/api/admin/orders/{order['id']}",headers=self.headers,json={'status':status}).status_code,200)
        rejected = self.client.patch(f"/api/admin/orders/{order['id']}",headers=self.headers,json={'status':'confirmed'})
        self.assertEqual(rejected.status_code,409)
        self.assertEqual(self.client.get(f"/api/admin/orders/{order['id']}").json()['status'],'preparing')
        stock = self.stock(p)
        repair_reported_data(rewind_codes=[order['order_code']])
        self.assertEqual(self.client.get(f"/api/admin/orders/{order['id']}").json()['status'],'preparing')
        repair_reported_data(True,rewind_codes=[order['order_code']])
        self.assertEqual(self.client.get(f"/api/admin/orders/{order['id']}").json()['status'],'confirmed')
        self.assertEqual(self.stock(p),stock)
        with connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) n FROM operational_adjustments WHERE subject_id=?',(str(order['id']),)).fetchone()['n'],1)


if __name__ == '__main__':
    unittest.main()
