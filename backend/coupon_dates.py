"""Read legacy Vietnamese/ISO dates without mutating stored coupons."""
from datetime import date, datetime
from fastapi import HTTPException


def coupon_date(value):
    if value is None or value == '':
        return ''
    if not isinstance(value, str):
        raise HTTPException(422, 'Ngày khuyến mãi không hợp lệ; cần kiểm tra dữ liệu gốc')
    value = value.strip()
    if not value:
        return ''
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        pass
    try:
        return datetime.strptime(value, '%d/%m/%Y').date().isoformat()
    except ValueError:
        pass
    try:
        if 'T' in value or ' ' in value:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).date().isoformat()
    except ValueError:
        pass
    raise HTTPException(422, 'Ngày khuyến mãi không đọc được; không mở form trống để tránh mất dữ liệu')


def coupon_view(row):
    values = dict(row)
    for key in ('starts_at', 'expires_at'):
        values[key] = coupon_date(values.get(key))
    return values
