"""Focused audit regressions against the existing isolated QA fixture."""
import os
import secrets
import tempfile
import unittest
from pathlib import Path
import test_app
from fastapi.testclient import TestClient
from backend.database import connect

class AuditRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(test_app.app)
        cls.client.__enter__()
        cls.headers={'X-CSRF-Token':cls.client.get('/api/csrf').json()['csrfToken']}

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None,None,None)

    setUp=test_app.PawPawApiTests.setUp
    login=test_app.PawPawApiTests.login
    product=test_app.PawPawApiTests.product
    order=test_app.PawPawApiTests.order
    stock=test_app.PawPawApiTests.stock

    def test_audit_idempotency_and_order_note(self):
        p=self.product(); body={'items':[{'productId':p['id'],'quantity':2}],'customer':{'name':'QA','phone':'0000000000','address':'QA'},'note':'Please ring the bell'}
        headers={**self.headers,'Idempotency-Key':secrets.token_hex(24)}; before=self.stock(p)
        a=self.client.post('/api/orders',headers=headers,json=body);b=self.client.post('/api/orders',headers=headers,json=body)
        self.assertEqual(a.status_code,200,a.text); self.assertEqual(b.json(),a.json());self.assertEqual(self.stock(p),before-2)
        recovered=self.client.get('/api/orders/idempotency',headers={'Idempotency-Key':headers['Idempotency-Key']});self.assertEqual(recovered.status_code,200);self.assertEqual(recovered.json(),a.json())
        self.assertEqual(self.client.get('/api/orders/idempotency',headers={'Idempotency-Key':secrets.token_hex(24)}).status_code,404)
        changed=self.client.post('/api/orders',headers=headers,json={**body,'note':'different'})
        self.assertEqual(changed.status_code,409);self.assertEqual(self.stock(p),before-2)
        with connect() as conn:
            row=conn.execute('SELECT note FROM orders WHERE id=?',(a.json()['id'],)).fetchone();self.assertEqual(row['note'],'Please ring the bell')
        lookup=self.client.post('/api/orders/lookup',headers=self.headers,json={'code':a.json()['order_code'],'phone':'0000000000'}).json()
        for field in ('phone','address','email','user_id','customer_name','note'):self.assertNotIn(field,lookup)

    def test_audit_booking_cancel_releases_slot_and_validates_hours(self):
        from datetime import date, timedelta
        day=(date.today()+timedelta(days=100)).isoformat()
        body={'serviceType':'vet','petName':'QA','petSpecies':'Chó','ownerName':'QA','phone':'0000000000','serviceDate':day,'timeSlot':'10:00'}
        a=self.client.post('/api/bookings',headers=self.headers,json=body);self.assertEqual(a.status_code,200,a.text)
        self.assertNotIn('10:00',self.client.get('/api/bookings/availability',params={'serviceDate':day}).json()['available'])
        self.assertEqual(self.client.patch('/api/admin/appointments/'+str(a.json()['id']),headers=self.headers,json={'status':'cancelled'}).status_code,200)
        self.assertIn('10:00',self.client.get('/api/bookings/availability',params={'serviceDate':day}).json()['available'])
        self.assertEqual(self.client.post('/api/bookings',headers=self.headers,json=body).status_code,200)
        self.assertEqual(self.client.post('/api/bookings',headers=self.headers,json={**body,'timeSlot':'99:99'}).status_code,422)

    def test_audit_return_policy_and_legacy_review(self):
        p=self.product();order=self.order(p).json();data={'orderCode':order['order_code'],'phone':'0000000000','reason':'QA'}
        self.assertEqual(self.client.post('/api/returns',headers=self.headers,json=data).status_code,422)
        for status in ('confirmed','preparing','shipping','delivered'):
            r=self.client.patch('/api/admin/orders/'+str(order['id']),headers=self.headers,json={'status':status});self.assertEqual(r.status_code,200,r.text)
        r=self.client.post('/api/returns',headers=self.headers,json=data);self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()['manual_review'])
        with connect() as conn: conn.execute("UPDATE orders SET delivered_at='2000-01-01T00:00:00+00:00' WHERE id=?",(order['id'],))
        self.assertEqual(self.client.post('/api/returns',headers=self.headers,json=data).status_code,422)
        with connect() as conn: conn.execute('UPDATE orders SET delivered_at=NULL WHERE id=?',(order['id'],))
        self.assertTrue(self.client.post('/api/returns',headers=self.headers,json=data).json()['manual_review'])

    def test_audit_catalog_pagination_filter_and_exact_ids(self):
        category='QA-PAGE-'+secrets.token_hex(6)
        with connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            for i in range(105):
                conn.execute('INSERT INTO products(slug,name,category,species,price_vnd,stock,sku,brand) VALUES(?,?,?,?,?,?,?,?)',(category+str(i),'QA '+str(i),category,'Chó',1500000+i,3,category+str(i),'QA-Brand'))
            conn.execute('COMMIT')
        one=self.client.get('/api/products',params={'category':category,'limit':60,'offset':0}).json()
        two=self.client.get('/api/products',params={'category':category,'limit':60,'offset':60}).json()
        self.assertEqual(len(one),60);self.assertEqual(len(two),45)
        self.assertEqual(len(set(r['id'] for r in one+two)),105)
        exact=self.client.get('/api/products',params={'ids':str(two[-1]['id'])}).json();self.assertEqual(exact[0]['id'],two[-1]['id'])
        self.assertEqual(len(self.client.get('/api/products',params={'category':category,'maxPrice':1499999}).json()),0)
        self.assertEqual(len(self.client.get('/api/products',params={'category':category,'brand':'QA-Brand'}).json()),60)

    def test_audit_legacy_appointment_migration_preserves_rows(self):
        import sqlite3
        from unittest.mock import patch
        from backend.database import init_db, SCHEMA_PATH
        sql=SCHEMA_PATH.read_text(); start=sql.index('CREATE TABLE IF NOT EXISTS appointments (');end=sql.index('CREATE INDEX IF NOT EXISTS idx_appointments_date_status',start)
        part=sql[start:end];part=part.replace("  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))\n);", "  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),\n  UNIQUE(service_date, time_slot, staff_name)\n);")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'legacy.sqlite'; raw=sqlite3.connect(path);raw.executescript(sql[:start]+part+sql[end:]);raw.execute("INSERT INTO appointments(service_type,pet_name,pet_species,owner_name,phone,service_date,time_slot,staff_name,price_vnd,status) VALUES('vet','QA','Chó','QA','0000000000','2050-01-01','10:00','Chuyên viên PawPaw',99000,'cancelled')");raw.commit();raw.close()
            with patch.dict(os.environ,{'DATABASE_PATH':str(path)}):
                init_db();init_db()
                with connect() as c:
                    self.assertEqual(c.execute('SELECT count(*) n FROM appointments').fetchone()['n'],1)
                    c.execute("INSERT INTO appointments(service_type,pet_name,pet_species,owner_name,phone,service_date,time_slot,staff_name,price_vnd) VALUES('vet','QA','Chó','QA','0000000000','2050-01-01','10:00','Chuyên viên PawPaw',99000)")
                    self.assertEqual(c.execute('SELECT count(*) n FROM appointments').fetchone()['n'],2)

    def test_audit_deploy_rollback_with_fake_docker(self):
        import subprocess
        from unittest.mock import patch
        script=Path(__file__).resolve().parents[1]/'deploy/aws/safe-release.sh'
        fake_docker="""#!/usr/bin/env python3
import os,sys
from pathlib import Path
root=Path(os.environ['FAKE_STATE']);args=sys.argv[1:]
with (root/'commands').open('a') as f: f.write(' '.join(args)+'\\n')
cmd=args[0]
if cmd=='inspect': sys.exit(0 if (root/args[-1]).exists() else 1)
if cmd=='build': sys.exit(0)
if cmd=='stop': sys.exit(0 if (root/args[1]).exists() else 1)
if cmd=='run' and '--network' in args: sys.exit(1 if os.environ.get('FAIL_GUARD') else 0)
if cmd=='rename': (root/args[1]).rename(root/args[2]);sys.exit(0)
if cmd=='run' and '-d' in args: (root/'pawpaw').touch();sys.exit(0)
if cmd=='rm': (root/args[-1]).unlink(missing_ok=True);sys.exit(0)
if cmd=='start': (root/'restarted').touch();sys.exit(0 if (root/args[-1]).exists() else 1)
if cmd=='tag': sys.exit(0)
sys.exit(2)
"""
        fake_curl="#!/usr/bin/env bash\n[ -z \"${FAIL_HEALTH:-}\" ]\n"
        with tempfile.TemporaryDirectory(prefix='pawpaw-deploy-qa-') as tmp:
            root=Path(tmp);bindir=root/'bin';bindir.mkdir()
            for name,content in [('docker',fake_docker),('curl',fake_curl),('sleep','#!/usr/bin/env bash\nexit 0\n')]:
                path=bindir/name;path.write_text(content);path.chmod(0o755)
            for failure in ('','FAIL_GUARD','FAIL_HEALTH'):
                state=root/('state-'+(failure or 'ok'));state.mkdir();(state/'pawpaw').touch()
                env={**os.environ,'PATH':str(bindir)+':'+os.environ['PATH'],'FAKE_STATE':str(state),'PAWPAW_ROOT':str(root),'GITHUB_SHA':'qa'}
                if failure:env[failure]='1'
                result=subprocess.run(['bash',str(script)],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode==0,not bool(failure),result.stderr)
                self.assertTrue((state/'pawpaw').exists())
                self.assertFalse((state/'pawpaw-rollback').exists())
                self.assertEqual((state/'restarted').exists(),bool(failure))

