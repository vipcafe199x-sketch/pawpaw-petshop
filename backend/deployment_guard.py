"""Offline pre-deploy guard: existing data volume, SQLite backup, no catalog reseed."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.database import connect, db_path, init_db


def catalog_fingerprint():
    with connect() as conn:
        rows = [dict(row) for row in conn.execute('SELECT * FROM products ORDER BY id')]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def protect_existing_database(data_root):
    path, root = db_path(), Path(data_root).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError('Existing database missing or outside the mounted data directory; deploy stopped before seeding')
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='products'").fetchone():
            raise RuntimeError('Database does not contain the existing catalog; deploy stopped')
        backup_dir = root / 'deploy-backups'
        backup_dir.mkdir(exist_ok=True)
        backup = backup_dir / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
        with sqlite3.connect(backup) as target:
            conn.backup(target)
    before = catalog_fingerprint()
    init_db()
    if catalog_fingerprint() != before:
        raise RuntimeError('Catalog changed during startup initialization; deploy stopped. Restore the pre-deploy backup before retrying.')
    return {'existing_database': True, 'backup_created': True, 'catalog_unchanged': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True)
    print(json.dumps(protect_existing_database(parser.parse_args().data_root)))
