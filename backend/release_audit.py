"""Read-only deployment checks. Does not seed, repair, place orders or edit data."""
import json
from urllib.request import urlopen
from backend.database import connect
from backend.admin_domain import report_data
from backend.coupon_dates import coupon_view


def audit():
    with connect() as conn:
        products=[dict(r) for r in conn.execute('SELECT sku,name,slug,price_vnd,stock,active FROM products ORDER BY sku')]
        coupons=[coupon_view(r) for r in conn.execute("SELECT code,starts_at,expires_at FROM coupons WHERE code='WELCOME10' COLLATE NOCASE")]
        settings={r['key']:bool(r['value'].strip()) for r in conn.execute("SELECT key,value FROM settings WHERE key IN ('support_phone','support_email','store_address')")}
    with urlopen('http://127.0.0.1:8000/api/products?limit=100',timeout=15) as response:
        public=json.load(response)
    if any(not p['active'] or p['price_vnd']<=0 for p in public):
        raise RuntimeError('Draft/unpriced product leaked into public catalog')
    report=report_data()
    return {'read_only':True,'catalog_targets':[p for p in products if p['sku'] in ('PP-005','PP-006','PP-007','PP-2FF7ED')],
            'strawberry_name_matches':[{'sku':p['sku'],'name':p['name']} for p in products if any(term in p['name'].lower() for term in ('dâu tây','bánh thưởng'))],
            'promotion_dates':coupons,'contacts_configured':settings,'public_product_count':len(public),'hidden_unpriced_verified':True,
            'report':{k:report[k] for k in ('order_count','total_order_count','cancelled_count','revenue_vnd','reconciliation')}}


if __name__=='__main__':
    print(json.dumps(audit(),ensure_ascii=False))
