import json
import os
import pymysql
from contextlib import contextmanager
from datetime import datetime, timedelta

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}

LEASE_DAYS = int(os.getenv("LEASE_DAYS", "30"))


@contextmanager
def get_conn():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def label_exists(label: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM subdomains WHERE label = %s", (label,))
            return cur.fetchone() is not None


def insert_subdomain(label: str, fqdn: str, ns_records: list, owner_note: str):
    now = datetime.utcnow()
    expires = now + timedelta(days=LEASE_DAYS)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subdomains (label, fqdn, ns_records, owner_note, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (label, fqdn, json.dumps(ns_records), owner_note, now, expires),
            )


def list_subdomains() -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, label, fqdn, ns_records, owner_note, created_at, expires_at "
                "FROM subdomains ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
            for r in rows:
                r["ns_records"] = json.loads(r["ns_records"])
            return rows


def delete_subdomain(label: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM subdomains WHERE label = %s", (label,))


def get_expired() -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT label, fqdn, ns_records FROM subdomains WHERE expires_at <= UTC_TIMESTAMP()"
            )
            rows = cur.fetchall()
            for r in rows:
                r["ns_records"] = json.loads(r["ns_records"])
            return rows
