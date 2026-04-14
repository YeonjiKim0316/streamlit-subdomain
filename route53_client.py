import os
import re
import boto3
from botocore.exceptions import ClientError

PARENT_DOMAIN = os.getenv("PARENT_DOMAIN", "thisispaperdoll.site")
PARENT_ZONE_ID = os.getenv("PARENT_ZONE_ID")

# 금지어: 피싱·혼동 유발 라벨
RESERVED_LABELS = {
    "www", "mail", "admin", "root", "api", "login", "secure", "ssl",
    "paypal", "bank", "google", "woori", "woorifis", "apple", "amazon",
    "aws", "ns", "ns1", "ns2", "mx", "smtp", "imap", "pop", "ftp",
    "cdn", "static", "assets", "test",
}

LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")


class ValidationError(Exception):
    pass


def validate_label(label: str) -> str:
    label = (label or "").strip().lower()
    if not LABEL_RE.match(label):
        raise ValidationError(
            "라벨은 소문자/숫자/하이픈만 허용되며 2~32자여야 합니다. "
            "하이픈으로 시작하거나 끝날 수 없습니다."
        )
    if label in RESERVED_LABELS:
        raise ValidationError(f"'{label}'은(는) 예약어라 사용할 수 없습니다.")
    return label


def validate_ns_records(raw: str) -> list:
    """줄바꿈/공백으로 구분된 NS 값을 파싱 후 검증."""
    tokens = [t.strip().rstrip(".") for t in re.split(r"[\s,]+", raw or "") if t.strip()]
    if len(tokens) != 4:
        raise ValidationError(f"NS 레코드는 정확히 4개여야 합니다 (현재: {len(tokens)}개).")
    for ns in tokens:
        if "awsdns" not in ns:
            raise ValidationError(
                f"'{ns}'은(는) Route53 NS 값이 아닌 것 같습니다. "
                "AWS가 아닌 NS는 허용하지 않습니다."
            )
    # Route53은 FQDN에 끝점(.)을 요구
    return [ns + "." for ns in tokens]


def _client():
    return boto3.client("route53")


def create_delegation(label: str, ns_records: list) -> str:
    fqdn = f"{label}.{PARENT_DOMAIN}"
    client = _client()
    try:
        client.change_resource_record_sets(
            HostedZoneId=PARENT_ZONE_ID,
            ChangeBatch={
                "Comment": f"Delegate {fqdn}",
                "Changes": [
                    {
                        "Action": "UPSERT",
                        "ResourceRecordSet": {
                            "Name": fqdn,
                            "Type": "NS",
                            "TTL": 300,
                            "ResourceRecords": [{"Value": ns} for ns in ns_records],
                        },
                    }
                ],
            },
        )
    except ClientError as e:
        raise RuntimeError(f"Route53 위임 실패: {e.response['Error']['Message']}")
    return fqdn


def delete_delegation(label: str, ns_records: list):
    fqdn = f"{label}.{PARENT_DOMAIN}"
    client = _client()
    try:
        client.change_resource_record_sets(
            HostedZoneId=PARENT_ZONE_ID,
            ChangeBatch={
                "Comment": f"Revoke {fqdn}",
                "Changes": [
                    {
                        "Action": "DELETE",
                        "ResourceRecordSet": {
                            "Name": fqdn,
                            "Type": "NS",
                            "TTL": 300,
                            "ResourceRecords": [{"Value": ns} for ns in ns_records],
                        },
                    }
                ],
            },
        )
    except ClientError as e:
        # 이미 삭제된 레코드는 무시
        msg = str(e).lower()
        if "not found" in msg or "invalidchangebatch" in msg:
            return
        raise
