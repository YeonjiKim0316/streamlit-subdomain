# Subdomain Service

`thisispaperdoll.site` 부모 도메인 아래에 서브도메인을 발급하고, 학생 본인의 AWS Route53 호스팅 영역으로 NS를 위임해주는 Streamlit 기반 서비스.

## 구성
- `app.py` — Streamlit 프론트 + 발급/회수 로직
- `db.py` — MySQL 접근 계층
- `route53_client.py` — Route53 API 래퍼 및 입력 검증
- `cleanup.py` — 30일 경과 서브도메인 자동 회수 (cron)
- `schema.sql` — MySQL 테이블 정의
- `.env.example` — 환경변수 템플릿

## 설치

```bash
pip install -r requirements.txt
```

## 설정

1. `.env.example` 을 `.env` 로 복사 후 값 채우기
    ```bash
    cp .env.example .env
    ```
2. 특히 다음 값을 반드시 채울 것:
   - `PARENT_ZONE_ID` — Route53 콘솔에서 `thisispaperdoll.site` 호스팅 영역 ID
   - `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — 아래 IAM 정책이 붙은 키
   - `DB_*` — MySQL 접속 정보

3. MySQL 테이블 생성
    ```bash
    mysql -u root -p < schema.sql
    ```

## IAM 최소 권한 정책

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "route53:ChangeResourceRecordSets",
        "route53:GetChange",
        "route53:ListResourceRecordSets"
      ],
      "Resource": "arn:aws:route53:::hostedzone/ZXXXXXXXXXXXXX"
    },
    {
      "Effect": "Allow",
      "Action": "route53:GetChange",
      "Resource": "arn:aws:route53:::change/*"
    }
  ]
}
```

## 실행

```bash
streamlit run app.py
```

접속 후 비밀번호: `.env` 의 `APP_PASSWORD` 값 (기본 `Woorifisa!6`)

## cron 등록 (자동 회수)

```bash
crontab -e
```

```
0 3 * * * cd /opt/subdomain-service && /usr/bin/python3 cleanup.py >> /var/log/subdomain-cleanup.log 2>&1
```

## 학생 사용 절차

1. 본인 AWS 콘솔 → Route53 → 호스팅 영역 생성
   - 도메인 이름: `<원하는라벨>.thisispaperdoll.site`
   - 유형: 퍼블릭 호스팅 영역
2. 자동 생성된 NS 레코드 4개 복사
3. 이 서비스의 "발급" 탭에 라벨 + NS 4개 입력 후 제출
4. `dig NS <라벨>.thisispaperdoll.site @8.8.8.8` 로 전파 확인
5. 본인 호스팅 영역에서 A/CNAME/ACM 레코드 자유 설정

## 주의

- 비밀번호는 단일 공유 방식이므로 사후 추적은 `owner_note` 필드로 대체
- 회수 시 부모 영역의 NS 레코드만 제거됨. 학생 본인의 호스팅 영역은 직접 삭제 필요 (비용 발생)
