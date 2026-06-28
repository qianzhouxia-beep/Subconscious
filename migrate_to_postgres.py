#!/usr/bin/env python3
"""
SQLite → PostgreSQL 数据迁移脚本
==================================
从现有的 SQLite 数据库（/data/mirror_data.db）迁移到 PostgreSQL。

使用方法：
1. 在 Zeabur 添加 PostgreSQL 服务
2. 复制自动生成的 DATABASE_URL
3. 在 Web Service 环境变量中添加 DATABASE_URL
4. 重启服务后，PostgreSQL 表会自动创建
5. 然后运行此脚本迁移数据：
   python3 migrate_to_postgres.py
"""

import os
import sys
import sqlite3
from contextlib import contextmanager

# ─── 配置 ───
SQLITE_PATH = os.environ.get("DB_FILE", "/data/mirror_data.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# 需要迁移的表（按依赖顺序）
TABLES_IN_ORDER = [
    "users",
    "email_tokens",
    "entitlements",
    "user_orders",
    "license_keys",
    "crypto_payments",
    "referrals",
    "referral_logs",
    "payments",
    "orders",
    "chat_sessions",
    "chat_messages",
    "dream_reports",
    "dream_journal",
    "dream_patterns",
    "tarot_readings",
]


def migrate():
    if not DATABASE_URL:
        print("❌ 错误：未设置 DATABASE_URL 环境变量")
        print("请先在 Zeabur 创建 PostgreSQL 服务，并将 DATABASE_URL 添加到环境变量")
        sys.exit(1)

    if not os.path.exists(SQLITE_PATH):
        print(f"❌ 错误：SQLite 文件不存在: {SQLITE_PATH}")
        sys.exit(1)

    print(f"📂 源数据库 (SQLite): {SQLITE_PATH}")
    print(f"🎯 目标数据库 (PostgreSQL): {DATABASE_URL.split('@')[-1]}")
    print()

    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("❌ 缺少 psycopg2，请先安装: pip install psycopg2-binary")
        sys.exit(1)

    # 连接 SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    # 连接 PostgreSQL
    try:
        pg_conn = psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ PostgreSQL 连接失败: {e}")
        sys.exit(1)

    # 先确保 PostgreSQL 表已创建
    print("🔧 正在创建 PostgreSQL 表结构...")
    try:
        # 触发 main.py 初始化（导入以运行 init_db）
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import main
        main.init_db()
        print("✅ PostgreSQL 表结构创建完成")
    except Exception as e:
        print(f"⚠️  警告：自动创建表失败，请手动运行: {e}")
        print("   你可以临时把 DATABASE_URL 清空，部署后让服务创建表，再恢复 DATABASE_URL")

    print()
    print("🚀 开始迁移数据...")
    print("=" * 60)

    total_migrated = 0
    total_tables = 0
    pg_cursor = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    for table in TABLES_IN_ORDER:
        # 检查 SQLite 中是否存在该表
        sqlite_cursor = sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if not sqlite_cursor.fetchone():
            print(f"⏭️  跳过 {table}（SQLite 中不存在）")
            continue

        # 检查 PostgreSQL 中是否存在该表
        pg_cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
        """, (table,))
        if not pg_cursor.fetchone()['exists']:
            print(f"⏭️  跳过 {table}（PostgreSQL 中不存在）")
            continue

        # 读取 SQLite 数据
        try:
            rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        except Exception as e:
            print(f"❌ 读取 {table} 失败: {e}")
            continue

        if not rows:
            print(f"⏭️  {table}: 空表，跳过")
            continue

        # 写入 PostgreSQL
        columns = rows[0].keys()
        placeholders = ", ".join(["%s"] * len(columns))
        column_names = ", ".join([f'"{c}"' for c in columns])

        # 转换 INSERT OR REPLACE 逻辑为 ON CONFLICT
        # 简化处理：先尝试 INSERT，失败则 UPDATE
        inserted = 0
        updated = 0
        skipped = 0

        for row in rows:
            values = tuple(row[c] for c in columns)
            # 跳过包含 PostgreSQL 保留类型问题的值
            try:
                # 简单 INSERT（如果主键冲突会跳过）
                pg_cursor.execute(
                    f"INSERT INTO {table} ({column_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                    values
                )
                if pg_cursor.rowcount > 0:
                    inserted += 1
                else:
                    updated += 1  # 记录为"已存在"
            except Exception as e:
                skipped += 1
                if skipped <= 3:
                    print(f"   ⚠️  跳过一行 ({table}): {str(e)[:80]}")

        pg_conn.commit()
        total_migrated += inserted
        total_tables += 1
        status = f"✅ {inserted} 新增"
        if updated > 0:
            status += f" / {updated} 已存在"
        if skipped > 0:
            status += f" / ⚠️  {skipped} 跳过"
        print(f"📊 {table}: {status} (共 {len(rows)} 行)")

    print()
    print("=" * 60)
    print(f"✨ 迁移完成！共处理 {total_tables} 张表，{total_migrated} 行新数据写入")

    # 验证关键表
    print()
    print("🔍 关键表验证:")
    for t in ["users", "entitlements", "payments", "orders"]:
        pg_cursor.execute(f"SELECT COUNT(*) as cnt FROM {t}")
        cnt = pg_cursor.fetchone()['cnt']
        print(f"   {t}: {cnt} 行")

    sqlite_conn.close()
    pg_conn.close()

    print()
    print("✅ 全部完成！现在你可以:")
    print("   1. 在 Zeabur 重新部署服务")
    print("   2. 验证数据是否正常（访问 /api/health）")
    print("   3. 备份并删除 SQLite 文件（/data/mirror_data.db）")


if __name__ == "__main__":
    migrate()
