#!/usr/bin/env python3
"""Check database location and content"""
import os
import sqlite3

# Check environment
db_file = os.environ.get("DB_FILE", "/data/mirror_data.db")
database_url = os.environ.get("DATABASE_URL", "")

print(f"DATABASE_URL: {database_url if database_url else '(not set)'}")
print(f"DB_FILE: {db_file}")
print(f"DB_FILE exists: {os.path.exists(db_file)}")
print()

if os.path.exists(db_file):
    print(f"Database file size: {os.path.getsize(db_file)} bytes")
    print()
    
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    
    # Get all tables
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    
    print(f"Tables ({len(tables)}):")
    for t in tables:
        name = t['name']
        count = conn.execute(f"SELECT COUNT(*) as cnt FROM {name}").fetchone()['cnt']
        print(f"  - {name}: {count} rows")
    print()
    
    # Show sample data from key tables
    if 'users' in [t['name'] for t in tables]:
        users = conn.execute("SELECT id, email, created_at FROM users LIMIT 5").fetchall()
        print(f"Recent users:")
        for u in users:
            print(f"  - {u['email']} (id={u['id'][:8]}..., created={u['created_at'][:10]})")
        print()
    
    if 'entitlements' in [t['name'] for t in tables]:
        ents = conn.execute("SELECT user_id, plan_type, remaining, total_count, is_expired FROM entitlements LIMIT 10").fetchall()
        print(f"Entitlements:")
        for e in ents:
            print(f"  - user={e['user_id'][:8]}... plan={e['plan_type']} remaining={e['remaining']}/{e['total_count']} expired={e['is_expired']}")
        print()
    
    if 'payments' in [t['name'] for t in tables]:
        pays = conn.execute("SELECT email, plan_type, amount, status, created_at FROM payments ORDER BY created_at DESC LIMIT 5").fetchall()
        print(f"Recent payments:")
        for p in pays:
            print(f"  - {p['email']} plan={p['plan_type']} amount={p['amount']} status={p['status']} date={p['created_at'][:10]}")
    
    conn.close()
else:
    print(f"ERROR: Database file not found at {db_file}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Files in current directory: {os.listdir('.')}")
