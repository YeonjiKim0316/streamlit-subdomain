import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import streamlit as st
import db
import route53_client as r53

APP_PASSWORD = os.getenv("APP_PASSWORD")
PARENT_DOMAIN = os.getenv("PARENT_DOMAIN", "ai-engineering.site")
LEASE_DAYS = int(os.getenv("LEASE_DAYS", "30"))

st.set_page_config(page_title="Subdomain Service", page_icon="🌐", layout="wide")


# -------- 로그인 --------
def require_login():
    if st.session_state.get("authed"):
        return
    st.title("🔒 Subdomain Service")
    st.caption(f"부모 도메인: `{PARENT_DOMAIN}`")
    with st.form("login"):
        pw = st.text_input("비밀번호", type="password")
        ok = st.form_submit_button("입장")
    if ok:
        if pw == APP_PASSWORD:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("비밀번호가 틀렸습니다.")
    st.stop()


require_login()

# -------- 메인 --------
st.title("🌐 Route53 서브도메인 발급")
st.caption(
    f"`*.{PARENT_DOMAIN}` 서브도메인을 발급하고, 본인 AWS 계정의 Route53 호스팅 영역으로 NS 위임합니다. "
    f"임대 기간은 **{LEASE_DAYS}일**이며 자동 회수됩니다."
)

tab_create, tab_list, tab_guide = st.tabs(["➕ 발급", "📋 목록", "📘 사용 가이드"])

# -------- 발급 탭 --------
with tab_create:
    st.subheader("새 서브도메인 발급")
    st.info(
        "**먼저 본인 AWS 계정에서 Route53 호스팅 영역을 만들고 NS 4개를 복사해 오세요.** "
        "가이드 탭에 순서 있습니다."
    )
    with st.form("create"):
        col1, col2 = st.columns([2, 3])
        with col1:
            label = st.text_input(
                "서브도메인 라벨",
                placeholder="student01",
                help=f"결과: <라벨>.{PARENT_DOMAIN}",
            )
            owner_note = st.text_input(
                "식별용 메모",
                placeholder="김연지 / 3조",
                help="누구 것인지 구분용 (만료/회수시 참고)",
            )
        with col2:
            ns_raw = st.text_area(
                "Route53 NS 값 4개",
                placeholder=(
                    "ns-123.awsdns-12.com\n"
                    "ns-456.awsdns-34.net\n"
                    "ns-789.awsdns-56.org\n"
                    "ns-012.awsdns-78.co.uk"
                ),
                height=140,
            )
        submitted = st.form_submit_button("🚀 발급하기", type="primary")

    if submitted:
        try:
            clean_label = r53.validate_label(label)
            if db.label_exists(clean_label):
                st.error(f"`{clean_label}`은 이미 사용 중입니다.")
                st.stop()
            ns_list = r53.validate_ns_records(ns_raw)
            fqdn = r53.create_delegation(clean_label, ns_list)
            db.insert_subdomain(clean_label, fqdn, ns_list, owner_note or "")
            st.success(f"✅ `{fqdn}` 위임 완료!")
            st.balloons()
            st.markdown(
                f"""
**다음 단계**
1. 본인 Route53 호스팅 영역에서 A/CNAME 레코드 자유롭게 생성
2. 전파 확인: `dig NS {fqdn} @8.8.8.8`
3. ACM에서 `*.{fqdn}` 와일드카드 인증서 발급 가능
"""
            )
        except r53.ValidationError as e:
            st.error(f"입력 오류: {e}")
        except Exception as e:
            st.error(f"위임 실패: {e}")

# -------- 목록 탭 --------
with tab_list:
    st.subheader("발급된 서브도메인")
    rows = db.list_subdomains()
    if not rows:
        st.info("아직 발급된 서브도메인이 없습니다.")
    else:
        for r in rows:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.markdown(f"### `{r['fqdn']}`")
                    st.caption(f"메모: {r['owner_note'] or '-'}")
                with c2:
                    remaining = (r["expires_at"] - datetime.utcnow()).days
                    st.metric("남은 일수", f"{max(remaining, 0)}일")
                    st.caption(f"만료: {r['expires_at']:%Y-%m-%d %H:%M} UTC")
                with c3:
                    if st.button("회수", key=f"del_{r['id']}"):
                        try:
                            r53.delete_delegation(r["label"], r["ns_records"])
                            db.delete_subdomain(r["label"])
                            st.success(f"{r['fqdn']} 회수 완료")
                            st.rerun()
                        except Exception as e:
                            st.error(f"회수 실패: {e}")
                with st.expander("NS 레코드"):
                    for ns in r["ns_records"]:
                        st.code(ns)

# -------- 가이드 탭 --------
with tab_guide:
    st.subheader("📘 학생용 발급 절차")
    st.markdown(
        f"""
### 1단계: 본인 AWS 계정에서 Route53 호스팅 영역 생성
1. AWS 콘솔 → Route53 → **호스팅 영역 생성**
2. 도메인 이름: `<원하는라벨>.{PARENT_DOMAIN}` (예: `student01.{PARENT_DOMAIN}`)
3. 유형: **퍼블릭 호스팅 영역**
4. 생성 후 자동으로 만들어진 **NS 레코드 값 4개를 복사**

### 2단계: 이 페이지의 '발급' 탭에서 제출
- 라벨과 NS 4개를 붙여넣고 발급 버튼 클릭
- 서버가 `{PARENT_DOMAIN}` 부모 영역에 NS 레코드를 꽂아 위임 완료

### 3단계: 전파 확인
```bash
dig NS student01.{PARENT_DOMAIN} @8.8.8.8
```
`awsdns`로 끝나는 NS 4개가 보이면 성공.

### 4단계: 자유롭게 레코드 생성
본인 호스팅 영역에서:
- A 레코드 → EC2 / ALB 연결
- ACM DNS 검증 → 와일드카드 SSL 인증서
- CNAME → CloudFront, S3 등

---

### ⚠️ 주의사항
- 임대 기간 **{LEASE_DAYS}일** 후 자동 회수
- 회수 시 부모 영역의 NS 레코드만 제거되며, 본인 호스팅 영역은 직접 삭제 필요 (비용 발생)
- 예약어(admin, mail, www 등)는 사용 불가
"""
    )
