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
        with connect() as conn:
            return conn.execute('SELECT stock FROM products WHERE id=?',(product['id'],)).fetchone()['stock']

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



    def test_full_product_metadata_and_upload(self):
        import io
        from PIL import Image
        p = self.product()
        image = io.BytesIO()
        Image.new('RGB', (32, 24), 'green').save(image, 'PNG')
        upload = self.client.post('/api/admin/uploads', headers={**self.headers, 'Content-Type': 'image/png'}, content=image.getvalue())
        self.assertEqual(upload.status_code, 200, upload.text)
        image_url = upload.json()['image_url']
        self.assertEqual(self.client.get(image_url).headers['content-type'], 'image/webp')
        values = {'description': 'QA description', 'specifications': 'QA dimensions', 'brand': 'QA BRAND', 'category': 'QA CATEGORY',
                  'species': 'Mèo', 'compare_price_vnd': p['price_vnd'] + 10000, 'image_url': image_url, 'featured': 1}
        response = self.client.patch(f"/api/admin/products/{p['id']}", headers=self.headers, json=values)
        self.assertEqual(response.status_code, 200, response.text)
        for key, value in values.items(): self.assertEqual(response.json()[key], value)
        self.assertEqual(self.client.get('/api/products', params={'q': 'QA BRAND'}).json()[0]['brand'], 'QA BRAND')
        for body in [{'compare_price_vnd': 1}, {'image_url': 'https://qa.invalid/image.svg'}, {'sku': 'NEW-ID'}]:
            self.assertEqual(self.client.patch(f"/api/admin/products/{p['id']}", headers=self.headers, json=body).status_code, 422)
        self.assertEqual(self.client.post('/api/admin/uploads', headers=self.headers, content=b'<svg/>').status_code, 422)
        self.assertEqual(self.client.post('/api/admin/uploads', headers=self.headers, content=b'x' * (5*1024*1024+1)).status_code, 413)
        self.assertEqual(self.client.post('/api/admin/uploads', content=image.getvalue()).status_code, 403)
        draft = self.client.patch(f"/api/admin/products/{p['id']}", headers=self.headers, json={'active': 0, 'price_vnd': 0})
        self.assertEqual(draft.status_code, 200)
        admin_product = next(r for r in self.client.get('/api/admin/products').json() if r['id'] == p['id'])
        self.assertEqual(admin_product['stock_status'], 'draft')

    def test_inventory_dialog_api_ledger_and_threshold(self):
        p = self.product()
        url = '/api/admin/inventory'
        for delta in [None, '', 0, True, 1.5, 10001, -10001]:
            r = self.client.post(url, headers=self.headers, json={'productId': p['id'], 'delta': delta, 'reason': 'QA adjustment'})
            self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(self.stock(p), p['stock'])
        r = self.client.post(url, headers=self.headers, json={'productId': p['id'], 'delta': -p['stock']-1, 'reason': 'QA adjustment'})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.stock(p), p['stock'])
        r = self.client.post(url, headers=self.headers, json={'productId': p['id'], 'delta': 3, 'reason': 'QA adjustment'})
        self.assertEqual(r.json()['stock'], p['stock']+3)
        self.assertTrue(any(e['id']==r.json()['event_id'] and e['delta']==3 for e in self.client.get(url).json()))
        self.client.patch(f"/api/admin/products/{p['id']}", headers=self.headers, json={'stock': 8})
        self.client.patch('/api/admin/settings', headers=self.headers, json={'low_stock_threshold': 5})
        def status(): return next(r for r in self.client.get('/api/admin/products').json() if r['id']==p['id'])['stock_status']
        self.assertEqual(status(), 'available')
        self.client.patch('/api/admin/settings', headers=self.headers, json={'low_stock_threshold': 8})
        self.assertEqual(status(), 'low')
        self.assertEqual(self.client.patch('/api/admin/settings', headers=self.headers, json={'low_stock_threshold': -1}).status_code, 422)
        self.client.patch('/api/admin/settings', headers=self.headers, json={'low_stock_threshold': 5})

    def test_promotion_create_edit_dates_usage_disable(self):
        p = self.product()
        code = 'QA-' + secrets.token_hex(6).upper()
        body = {'code': code, 'discount_type': 'percent', 'discount_value': 10, 'minimum_vnd': 0, 'usage_limit': 2, 'starts_at': '2000-01-01', 'expires_at': '2099-01-01', 'active': 1}
        response = self.client.post('/api/admin/promotions', headers=self.headers, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.post('/api/admin/promotions', headers=self.headers, json=body).status_code, 409)
        url = '/api/admin/promotions/' + code
        for body in [{'discount_value': 101}, {'discount_value': ''}, {'starts_at': '2100-01-01'}, {'code': 'DIFFERENT'}, {'expires_at': 'bad-date'}]:
            self.assertEqual(self.client.patch(url, headers=self.headers, json=body).status_code, 422)
        self.assertEqual(self.order(p, coupon=code).status_code, 200)
        self.assertEqual(self.client.patch(url, headers=self.headers, json={'discount_type': 'fixed', 'discount_value': 1000}).status_code, 200)
        self.client.patch(url, headers=self.headers, json={'starts_at': '2090-01-01'})
        self.assertEqual(self.order(p, coupon=code).status_code, 422)
        self.client.patch(url, headers=self.headers, json={'starts_at': '', 'active': 0})
        self.assertEqual(self.order(p, coupon=code).status_code, 422)

    def test_appointment_forward_only_and_month(self):
        body = {'serviceType': 'vet', 'petName': 'QA', 'petSpecies': 'Chó', 'ownerName': 'QA', 'phone': '0000000000', 'serviceDate': '2051-02-03', 'timeSlot': '10:00'}
        created = self.client.post('/api/bookings', headers=self.headers, json=body)
        self.assertEqual(created.status_code, 200, created.text)
        aid = created.json()['id']; url = f'/api/admin/appointments/{aid}'
        self.assertEqual(self.client.patch(url, headers=self.headers, json={'status': 'confirmed'}).status_code, 200)
        self.assertEqual(self.client.patch(url, headers=self.headers, json={'status': 'requested'}).status_code, 409)
        self.assertEqual(self.client.patch(url, headers=self.headers, json={'status': 'completed'}).status_code, 200)
        self.assertEqual(self.client.patch(url, headers=self.headers, json={'status': 'cancelled'}).status_code, 409)
        self.assertTrue(any(r['id']==aid for r in self.client.get('/api/admin/appointments?month=2051-02').json()))
        self.assertFalse(any(r['id']==aid for r in self.client.get('/api/admin/appointments?month=2051-03').json()))
        self.assertEqual(self.client.get('/api/admin/appointments?month=invalid').status_code, 422)

    def test_customer_detail_archive_and_search(self):
        token = secrets.token_hex(6); email = 'qa-'+token+'@example.invalid'; password = secrets.token_urlsafe(24)
        r = self.client.post('/api/auth/register', headers=self.headers, json={'email': email, 'password': password, 'fullName': 'QA '+token, 'phone': '0000000000'})
        cid = r.json()['id']; self.login(self.client, self.headers)
        url = f'/api/admin/customers/{cid}'
        detail = self.client.get(url).json()
        self.assertEqual(detail['tier'], 'Thành viên mới'); self.assertEqual(detail['orders'], [])
        self.assertNotIn('password_hash', detail)
        self.assertTrue(any(c['id']==cid for c in self.client.get('/api/admin/search', params={'q': token}).json()['customers']))
        self.assertEqual(self.client.patch(url, headers=self.headers, json={'full_name': 'QA UPDATED', 'archived': 1}).status_code, 200)
        self.assertFalse(any(c['id']==cid for c in self.client.get('/api/admin/customers').json()))
        self.assertEqual(self.client.post('/api/auth/login', headers=self.headers, json={'email':email,'password':password}).status_code, 401)
        self.login(self.client, self.headers)
        self.assertEqual(self.client.patch(url, headers=self.headers, json={'archived': 0}).status_code, 200)
        self.assertEqual(self.client.get('/api/admin/search?q=x').status_code, 422)

    def test_date_scoped_reports_and_consistent_definitions(self):
        p = self.product(); first = self.order(p).json(); second = self.order(p).json()
        self.client.patch(f"/api/admin/orders/{second['id']}", headers=self.headers, json={'status':'cancelled'})
        with connect() as conn:
            conn.execute('UPDATE orders SET created_at=? WHERE id IN (?,?)', ('2049-06-10T18:00:00Z', first['id'], second['id']))
        query = '?start=2049-06-11&end=2049-06-11&granularity=day'
        reports = self.client.get('/api/admin/reports'+query).json(); dashboard = self.client.get('/api/admin/dashboard'+query).json()
        for data in [reports, dashboard]:
            self.assertEqual(data['order_count'], 1); self.assertEqual(data['total_order_count'], 2); self.assertEqual(data['cancelled_count'], 1)
            self.assertEqual(data['revenue_vnd'], first['total_vnd']); self.assertEqual(data['series'][0]['month'], '2049-06-11')
        self.assertEqual(self.client.get('/api/admin/reports?start=2049-06-10&end=2049-06-10').json()['order_count'], 0)
        for query in ['start=bad', 'start=2050-01-01&end=2000-01-01', 'granularity=invalid']:
            self.assertEqual(self.client.get('/api/admin/reports?'+query).status_code, 422)
        for status in ['confirmed', 'preparing', 'shipping', 'delivered']:
            self.assertEqual(self.client.patch(f"/api/admin/orders/{first['id']}", headers=self.headers, json={'status':status}).status_code, 200)
        for oid in [first['id'], second['id']]:
            self.assertEqual(self.client.patch(f'/api/admin/orders/{oid}', headers=self.headers, json={'status':'confirmed'}).status_code, 409)


    def test_legacy_schema_migration_preserves_existing_catalog(self):
        import sqlite3
        from unittest.mock import patch
        from backend.database import SCHEMA_PATH
        from backend.deployment_guard import protect_existing_database
        with tempfile.TemporaryDirectory(prefix='pawpaw-legacy-qa-') as folder:
            path = Path(folder) / 'legacy.sqlite3'
            with sqlite3.connect(path) as conn:
                conn.executescript(SCHEMA_PATH.read_text())
                conn.execute("INSERT INTO products(slug,name,category,species,price_vnd,stock,sku) VALUES('qa-legacy','QA LEGACY','QA','QA',12345,3,'QA-LEGACY')")
            with patch.dict(os.environ, {'DATABASE_PATH': str(path)}):
                result = protect_existing_database(folder)
                self.assertTrue(result['catalog_unchanged'])
                with connect() as conn:
                    row = conn.execute('SELECT * FROM products').fetchone()
                    self.assertEqual((row['price_vnd'],row['stock'],row['brand']), (12345,3,''))
                    self.assertEqual(conn.execute('SELECT COUNT(*) FROM products').fetchone()[0], 1)
                self.assertTrue(protect_existing_database(folder)['catalog_unchanged'])

    def test_stale_product_editor_cannot_overwrite_new_stock(self):
        p = self.product()
        self.client.post('/api/admin/inventory', headers=self.headers, json={'productId':p['id'],'delta':2,'reason':'QA stock change'})
        response = self.client.patch(f"/api/admin/products/{p['id']}", headers=self.headers, json={'expected_stock':p['stock'],'stock':p['stock'],'name':'QA STALE'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.stock(p),p['stock']+2)


    def test_public_shop_hides_drafts_unpriced_but_keeps_sold_out(self):
        draft,unpriced,soldout = self.product(),self.product(),self.product()
        with connect() as conn:
            conn.execute('UPDATE products SET active=0 WHERE id=?',(draft['id'],))
            conn.execute('UPDATE products SET price_vnd=0 WHERE id=?',(unpriced['id'],))
            conn.execute('UPDATE products SET stock=0 WHERE id=?',(soldout['id'],))
        for p in (draft,unpriced):
            self.assertEqual(self.client.get('/api/products',params={'q':p['sku']}).json(),[])
            self.assertEqual(self.client.get('/api/products/'+p['slug']).status_code,404)
            self.assertEqual(self.order(p).status_code,422)
            self.assertTrue(any(r['id']==p['id'] for r in self.client.get('/api/admin/products').json()))
        self.assertEqual(self.client.get('/api/products',params={'q':soldout['sku']}).json()[0]['stock'],0)

    def test_coupon_dates_preserved_on_read_cancel_equivalent_and_unrelated_patch(self):
        code='QA-'+secrets.token_hex(6).upper()
        with connect() as conn:
            conn.execute("INSERT INTO coupons(code,discount_type,discount_value,starts_at,expires_at) VALUES(?,'percent',10,?,?)",(code,'02/11/2026','2026-11-30T00:00:00Z'))
        def read(): return next(p for p in self.client.get('/api/admin/promotions').json() if p['code']==code)
        for _ in range(3):
            p=read();self.assertEqual(p['starts_at'],'2026-11-02');self.assertEqual(p['expires_at'],'2026-11-30')
        with connect() as conn:
            self.assertEqual(conn.execute('SELECT starts_at FROM coupons WHERE code=?',(code,)).fetchone()[0],'02/11/2026')
        url='/api/admin/promotions/'+code.lower()
        r=self.client.patch(url,headers=self.headers,json={'discount_value':12})
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(read()['expires_at'],'2026-11-30')
        self.assertEqual(self.client.patch(url,headers=self.headers,json={'starts_at':'','expires_at':''}).status_code,422)
        self.assertEqual(read()['starts_at'],'2026-11-02')
        r=self.client.patch(url,headers=self.headers,json={'clear_dates':1,'starts_at':'','expires_at':''})
        self.assertEqual(r.status_code,200);self.assertEqual(read()['starts_at'],'')

    def test_settings_hydrate_contacts_and_blank_inputs_cannot_erase(self):
        values={'support_phone':'0000000000','support_email':'qa@example.invalid','store_address':'QA ADDRESS'}
        r=self.client.patch('/api/admin/settings',headers=self.headers,json=values)
        self.assertEqual(r.status_code,200,r.text)
        settings=self.client.get('/api/admin/settings').json()
        for k,v in values.items(): self.assertEqual(settings[k],v)
        r=self.client.patch('/api/admin/settings',headers=self.headers,json={k:'' for k in values})
        for k,v in values.items(): self.assertEqual(r.json()[k],v)
        self.assertEqual(self.client.patch('/api/admin/settings',headers=self.headers,json={'store_name':''}).status_code,422)
        self.assertEqual(self.client.patch('/api/admin/settings',headers=self.headers,json={'support_email':'invalid'}).status_code,422)

    def test_explicit_repair_applies_publishes_once_without_touching_others(self):
        broken,other=self.product(),self.product()
        with connect() as conn: conn.execute('UPDATE products SET price_vnd=0,stock=0,active=0 WHERE id=?',(broken['id'],))
        kwargs={'product_repairs':{broken['sku']:(broken['price_vnd'],broken['stock'])},'include_defaults':False,'activate_repaired':True}
        preview=repair_reported_data(**kwargs)
        self.assertEqual(len(preview['actions']),1);self.assertEqual(self.stock(broken),0)
        applied=repair_reported_data(apply=True,**kwargs)
        self.assertTrue(Path(applied['backup']).exists())
        self.assertEqual(self.client.get('/api/products/'+broken['slug']).json()['price_vnd'],broken['price_vnd'])
        self.assertEqual(self.stock(broken),broken['stock']);self.assertEqual(self.stock(other),other['stock'])
        with connect() as conn: before=conn.execute('SELECT COUNT(*) FROM inventory_events WHERE product_id=?',(broken['id'],)).fetchone()[0]
        repair_reported_data(apply=True,**kwargs)
        with connect() as conn: self.assertEqual(conn.execute('SELECT COUNT(*) FROM inventory_events WHERE product_id=?',(broken['id'],)).fetchone()[0],before)

    def test_revenue_reconciles_all_products_discounts_shipping_and_legacy_gaps(self):
        ids=[]
        for _ in range(9):
            p=self.product();ids.append(self.order(p).json()['id'])
        cancelled=self.order(self.product()).json()
        self.client.patch(f"/api/admin/orders/{cancelled['id']}",headers=self.headers,json={'status':'cancelled'})
        with connect() as conn:
            for oid in ids+[cancelled['id']]: conn.execute('UPDATE orders SET created_at=? WHERE id=?',('2058-03-01T00:00:00Z',oid))
            conn.execute('UPDATE orders SET discount_vnd=1000,total_vnd=subtotal_vnd-1000+shipping_vnd WHERE id=?',(ids[0],))
        url='/api/admin/reports?start=2058-03-01&end=2058-03-01'
        data=self.client.get(url).json();x=data['reconciliation']
        self.assertEqual(len(data['best_sellers']),9);self.assertEqual(data['order_count'],9);self.assertEqual(data['cancelled_count'],1)
        self.assertEqual(sum(p['revenue'] for p in data['best_sellers']),x['items_gross_vnd'])
        self.assertEqual(x['items_gross_vnd']-x['discount_vnd']+x['shipping_vnd'],data['revenue_vnd'])
        self.assertEqual(x['orders_needing_review'],[])
        with connect() as conn:
            conn.execute('DELETE FROM order_items WHERE order_id=?',(ids[1],))
            conn.execute('UPDATE orders SET total_vnd=total_vnd+7 WHERE id=?',(ids[2],))
        data=self.client.get(url).json();x=data['reconciliation']
        self.assertEqual(x['items_gross_vnd']+x['subtotal_difference_vnd']-x['discount_vnd']+x['shipping_vnd']+x['total_difference_vnd'],data['revenue_vnd'])
        self.assertEqual(len(x['orders_needing_review']),2);self.assertEqual(x['total_difference_vnd'],7)

if __name__ == '__main__':
    unittest.main()
