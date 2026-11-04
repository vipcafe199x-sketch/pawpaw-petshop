"""Bounded, read-only evidence from current SQLite and known backup locations.

Does not restore records or infer that absence proves a deletion never happened.
Only public catalog identifiers, coupon dates and contact-presence flags are emitted.
"""
import json
import sqlite3
import unicodedata
from pathlib import Path
from backend.database import db_path


def folded(value):
    return ''.join(c for c in unicodedata.normalize('NFD',str(value).casefold()) if not unicodedata.combining(c))


def inspect_database(path):
    conn=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    conn.row_factory=sqlite3.Row
    try:
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result={'source':Path(path).name}
        if 'products' in tables:
            products=[dict(r) for r in conn.execute('SELECT sku,name,slug,price_vnd,stock,active FROM products')]
            result['pp005']=[p for p in products if p['sku']=='PP-005']
            result['strawberry_matches']=[p for p in products if any(s in folded(p['name']) for s in ('dau tay','banh thuong'))]
            result['abc']=[p for p in products if p['sku']=='PP-2FF7ED']
        if 'coupons' in tables:
            columns={r[1] for r in conn.execute('PRAGMA table_info(coupons)')}
            fields=[key for key in ('code','starts_at','expires_at') if key in columns]
            result['coupons']=[dict(r) for r in conn.execute('SELECT '+','.join(fields)+' FROM coupons ORDER BY code')]
        if 'settings' in tables:
            settings={r['key']:bool(r['value'].strip()) for r in conn.execute("SELECT key,value FROM settings WHERE key IN ('support_phone','support_email','store_address')")}
            result['contacts_configured']={k:settings.get(k,False) for k in ('support_phone','support_email','store_address')}
        if 'order_items' in tables:
            result['strawberry_order_line_count']=sum(any(s in folded(r[0]) for s in ('dau tay','banh thuong')) for r in conn.execute('SELECT product_name FROM order_items'))
        if 'orders' in tables:
            result['welcome_order_count']=conn.execute("SELECT COUNT(*) FROM orders WHERE coupon_code='WELCOME10' COLLATE NOCASE").fetchone()[0]
        return result
    finally:
        conn.close()


def evidence(path=None, limit=100):
    current=Path(path or db_path()).resolve()
    root=current.parent
    candidates=sorted(set(root.glob('deploy-backups/*.sqlite3'))|set(root.glob('*.before-repair-*.bak')))
    safe=[p for p in candidates if not p.is_symlink() and p.resolve().is_relative_to(root)]
    results=[]
    for p in [current,*safe[:limit]]:
        try: results.append(inspect_database(p))
        except (sqlite3.Error,OSError): results.append({'source':p.name,'unreadable':True})
    return {'read_only':True,'available_backups':len(safe),'backups_scanned':min(len(safe),limit),'truncated':len(safe)>limit,'snapshots':results,'limitation':'Snapshots and current records cannot prove an unlogged deletion or rename never occurred.'}


if __name__=='__main__':
    print(json.dumps(evidence(),ensure_ascii=False))
