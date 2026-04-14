"""
30일 경과 서브도메인 자동 회수 스크립트.

crontab 예시 (매일 오전 3시):
    0 3 * * * cd /opt/subdomain-service && /usr/bin/python3 cleanup.py >> /var/log/subdomain-cleanup.log 2>&1
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import db
import route53_client as r53


def main():
    expired = db.get_expired()
    if not expired:
        print(f"[{datetime.utcnow():%Y-%m-%d %H:%M}] 회수 대상 없음.")
        return

    print(f"[{datetime.utcnow():%Y-%m-%d %H:%M}] 회수 대상 {len(expired)}건")
    success, failed = 0, 0
    for row in expired:
        try:
            r53.delete_delegation(row["label"], row["ns_records"])
            db.delete_subdomain(row["label"])
            print(f"  ✓ {row['fqdn']} 회수 완료")
            success += 1
        except Exception as e:
            print(f"  ✗ {row['fqdn']} 회수 실패: {e}")
            failed += 1
    print(f"완료: 성공 {success}, 실패 {failed}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)
