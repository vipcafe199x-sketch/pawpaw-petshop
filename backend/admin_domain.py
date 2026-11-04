"""Validated admin writes and date-scoped reporting. No destructive cleanup."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
import unicodedata
from fastapi import HTTPException
from backend.database import connect

BUSINESS_ZONE = ZoneInfo('Asia/Ho_Chi_Minh')
ORDER_TRANSITIONS = {'pending': ['confirmed','cancelled'], 'confirmed':['preparing','cancelled'], 'preparing':['shipping','cancelled'], 'shipping':['delivered'], 'delivered':[], 'cancelled':[]}
APPOINTMENT_TRANSITIONS = {'requested':['confirmed','cancelled'], 'confirmed':['completed','cancelled'], 'completed':[], 'cancelled':[]}

def integer(value, minimum=0, maximum=2147483647):
    if isinstance(value,bool) or not isinstance(value,(int,str)) or not re.fullmatch(r'-?\d+',str(value).strip()):
        raise HTTPException(422,'Cần nhập số nguyên hợp lệ, không để trống')
    number=int(value)
    if not minimum<=number<=maximum: raise HTTPException(422,f'Giá trị phải từ {minimum} đến {maximum}')
    return number

def text(value, maximum=10000):
    if not isinstance(value,str) or len(value)>maximum: raise HTTPException(422,'Nội dung không hợp lệ hoặc quá dài')
    return value.strip()

def low_threshold(conn):
    row=conn.execute("SELECT value FROM settings WHERE key='low_stock_threshold'").fetchone()
    return int(row['value']) if row else 5

def stock_status(product, threshold):
    if not product['active'] or product['price_vnd']<=0: return 'draft'
    if product['stock']==0: return 'out'
    return 'low' if product['stock']<=threshold else 'available'

def catalog_admin(conn):
    threshold=low_threshold(conn)
    return [{**dict(p),'stock_status':stock_status(p,threshold),'low_stock_threshold':threshold} for p in conn.execute('SELECT * FROM products ORDER BY id DESC')]

def product_values(body, current=None):
    if not isinstance(body,dict): raise HTTPException(422,'Dữ liệu sản phẩm không hợp lệ')
    base=dict(current) if current else {'active':1,'stock':0,'compare_price_vnd':0,'featured':0,'emoji':'🐾','category':'Phụ kiện','species':'Chó','description':'','brand':'','specifications':'','image_url':''}
    allowed={'name','sku','slug','category','species','description','brand','specifications','image_url','price_vnd','compare_price_vnd','stock','active','featured','emoji'}
    base.update({k:v for k,v in body.items() if k in allowed})
    for key in ('name','category','species','brand','description','specifications','image_url','emoji'):
        base[key]=text(base.get(key,''),10000 if key in ('description','specifications') else 300)
    if len(base['name'])<3 or not base['category'] or not base['species']: raise HTTPException(422,'Nhập tên, danh mục và loài thú cưng')
    for key in ('active','featured'): base[key]=integer(base[key],0,1)
    base['price_vnd']=integer(base.get('price_vnd'),1 if base['active'] else 0)
    base['compare_price_vnd']=integer(base['compare_price_vnd'])
    base['stock']=integer(base['stock'])
    if base['compare_price_vnd'] and base['compare_price_vnd']<base['price_vnd']: raise HTTPException(422,'Giá gốc phải lớn hơn hoặc bằng giá bán')
    if base['image_url'] and not re.fullmatch(r'/uploads/[a-f0-9]{32}\.webp',base['image_url']): raise HTTPException(422,'Vui lòng tải ảnh bằng chức năng upload')
    if not current:
        base['sku']=text(base.get('sku',''),80)
        if not re.fullmatch(r'[A-Za-z0-9_-]{2,80}',base['sku']): raise HTTPException(422,'SKU cần 2–80 ký tự chữ/số/gạch ngang')
        source=text(base.get('slug') or base['name'],300)
        source=unicodedata.normalize('NFKD',source).encode('ascii','ignore').decode().lower()
        base['slug']=re.sub(r'[^a-z0-9]+','-',source).strip('-')
        if not base['slug']: raise HTTPException(422,'Đường dẫn sản phẩm không hợp lệ')
    elif any(k in body and body[k]!=current[k] for k in ('sku','slug')): raise HTTPException(422,'SKU và đường dẫn được giữ cố định khi sửa')
    return {k:base[k] for k in allowed if k in base}

def write_product(body, admin_id, product_id=None):
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            current=conn.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone() if product_id else None
            if product_id and not current: raise HTTPException(404,'Không tìm thấy sản phẩm')
            if current and 'expected_stock' in body and integer(body['expected_stock'])!=current['stock']:
                raise HTTPException(409,'Tồn kho đã thay đổi. Hãy mở lại form để tải dữ liệu mới trước khi lưu.')
            values=product_values(body,current)
            if current:
                conn.execute('UPDATE products SET '+','.join(k+'=?' for k in values)+' WHERE id=?',list(values.values())+[product_id])
                delta=values['stock']-current['stock']
            else:
                cursor=conn.execute('INSERT INTO products('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',list(values.values()))
                product_id=cursor.lastrowid;delta=values['stock']
            if delta: conn.execute('INSERT INTO inventory_events(product_id,delta,reason,actor_id) VALUES(?,?,?,?)',(product_id,delta,'Sửa sản phẩm' if current else 'Tạo sản phẩm',admin_id))
            result=dict(conn.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone());conn.execute('COMMIT');return result
        except Exception as error:
            conn.execute('ROLLBACK')
            if 'UNIQUE constraint failed' in str(error): raise HTTPException(409,'SKU hoặc đường dẫn đã tồn tại')
            raise

def promotion_values(body, current=None):
    values=dict(current) if current else {'discount_type':'percent','minimum_vnd':0,'usage_limit':0,'active':1,'starts_at':'','expires_at':''}
    values.update({k:v for k,v in body.items() if k in {'code','discount_type','discount_value','minimum_vnd','usage_limit','active','starts_at','expires_at'}})
    values['code']=text(values.get('code',''),40).upper()
    if not re.fullmatch(r'[A-Z0-9_-]{4,40}',values['code']): raise HTTPException(422,'Mã cần 4–40 ký tự chữ/số/gạch ngang')
    if current and values['code']!=current['code']: raise HTTPException(422,'Không đổi mã đã tạo; hãy tạo mã mới')
    if values['discount_type'] not in ('percent','fixed'): raise HTTPException(422,'Loại giảm giá không hợp lệ')
    values['discount_value']=integer(values.get('discount_value'),1,100 if values['discount_type']=='percent' else 2147483647)
    for key in ('minimum_vnd','usage_limit'): values[key]=integer(values[key])
    values['active']=integer(values['active'],0,1)
    for key in ('starts_at','expires_at'):
        values[key]=str(values.get(key) or '').strip()
        try:
            if values[key]: date.fromisoformat(values[key])
        except ValueError: raise HTTPException(422,'Ngày ưu đãi không hợp lệ')
    if values['starts_at'] and values['expires_at'] and values['starts_at']>values['expires_at']: raise HTTPException(422,'Ngày kết thúc phải từ ngày bắt đầu')
    if current and values['usage_limit'] and values['usage_limit']<current['used_count']: raise HTTPException(422,'Giới hạn không thể nhỏ hơn số lượt đã dùng')
    return {k:values[k] for k in ('code','discount_type','discount_value','minimum_vnd','usage_limit','active','starts_at','expires_at')}

def tier(spent):
    return 'Thành viên mới' if spent<=0 else 'Bạc' if spent<3000000 else 'Vàng' if spent<10000000 else 'Kim cương'

def date_bounds(start='',end=''):
    try:
        a=date.fromisoformat(start) if start else None;b=date.fromisoformat(end) if end else None
    except ValueError: raise HTTPException(422,'Khoảng ngày không hợp lệ')
    if a and b and a>b: raise HTTPException(422,'Ngày kết thúc phải từ ngày bắt đầu')
    return a,b

def report_data(start='',end='',granularity='day'):
    a,b=date_bounds(start,end)
    if granularity not in ('day','week','month'): raise HTTPException(422,'Độ chi tiết không hợp lệ')
    where=' WHERE 1=1';params=[]
    if a: where+=" AND date(created_at,'+7 hours')>=?";params.append(a.isoformat())
    if b: where+=" AND date(created_at,'+7 hours')<=?";params.append(b.isoformat())
    with connect() as conn:
        orders=[dict(o) for o in conn.execute('SELECT id,total_vnd,status,created_at FROM orders'+where+' ORDER BY created_at',params)]
        customers=conn.execute("SELECT COUNT(*) n FROM users"+where+" AND role='customer' AND archived=0",params).fetchone()['n']
        valid=[o for o in orders if o['status']!='cancelled'];buckets={};months={}
        for order in valid:
            instant=datetime.fromisoformat(order['created_at'].replace('Z','+00:00'))
            local=instant.replace(tzinfo=timezone.utc).astimezone(BUSINESS_ZONE) if instant.tzinfo is None else instant.astimezone(BUSINESS_ZONE)
            key=local.strftime('%Y-%m') if granularity=='month' else (local.date()-timedelta(days=local.weekday())).isoformat() if granularity=='week' else local.date().isoformat()
            for mapping,label in ((buckets,key),(months,local.strftime('%Y-%m'))):
                row=mapping.setdefault(label,{'month':label,'revenue':0,'orders':0});row['revenue']+=order['total_vnd'];row['orders']+=1
        ids=[o['id'] for o in valid];best=[]
        if ids:
            best=[dict(r) for r in conn.execute('SELECT product_name,SUM(quantity) units,SUM(unit_price_vnd*quantity) revenue FROM order_items WHERE order_id IN ('+','.join('?' for _ in ids)+') GROUP BY product_name ORDER BY units DESC LIMIT 8',ids)]
        returns_count=conn.execute('SELECT COUNT(*) n FROM returns'+(' WHERE order_id IN ('+','.join('?' for _ in ids)+')' if ids else ' WHERE 0'),ids).fetchone()['n']
    return {'start':start,'end':end,'granularity':granularity,'series':list(buckets.values()),'months':list(months.values()),'best_sellers':best,'returns_count':returns_count,'revenue_vnd':sum(o['total_vnd'] for o in valid),'order_count':len(valid),'total_order_count':len(orders),'cancelled_count':len(orders)-len(valid),'customer_count':customers,'pending_count':sum(o['status']=='pending' for o in valid),'order_definition':'Đơn hợp lệ = tất cả trạng thái trừ đã hủy; doanh thu gồm tổng tiền các đơn hợp lệ.'}
