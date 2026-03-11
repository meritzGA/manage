import streamlit as st
import pandas as pd
import re
import io

st.set_page_config(page_title="엑셀 → 연락처 변환기", page_icon="📇", layout="centered")

# ── 스타일 ──
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    h1, h2, h3 { color: #1e293b !important; }
    .step-badge {
        display: inline-flex; align-items: center; justify-content: center;
        background: #2563eb; color: #fff; width: 26px; height: 26px;
        border-radius: 50%; font-size: 13px; font-weight: 700; margin-right: 8px;
    }
    .count-badge {
        background: #dbeafe; color: #2563eb;
        padding: 4px 14px; border-radius: 20px; font-weight: 600; font-size: 14px;
    }
    .success-box {
        background: #f0fdf4; border: 1px solid #bbf7d0;
        border-radius: 12px; padding: 16px 20px; color: #16a34a; margin-top: 12px;
    }
    .guide-box {
        background: #f1f5f9; border: 1px solid #e2e8f0;
        border-radius: 12px; padding: 18px 22px; color: #475569; font-size: 14px; line-height: 2;
    }
</style>
""", unsafe_allow_html=True)


# ── 함수 ──
def normalize_phone(raw):
    """전화번호 정규화: 하이픈 제거, 국제번호 변환, 앞자리 0 복원"""
    if pd.isna(raw):
        return ""
    s = re.sub(r"[^0-9+]", "", str(raw).strip())
    if s.startswith("+82"):
        s = "0" + s[3:]
    elif s.startswith("82") and len(s) > 10:
        s = "0" + s[2:]
    # 엑셀에서 숫자로 저장되어 앞자리 0이 빠진 경우 복원
    if not s.startswith("0") and len(s) >= 9:
        s = "0" + s
    return s


def to_vcard(name, phone, org="", nickname="", note=""):
    """단일 연락처를 vCard 3.0 문자열로 변환"""
    clean_phone = normalize_phone(phone)
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{name}",
        f"N:;{name};;;",
    ]
    if clean_phone:
        lines.append(f"TEL;TYPE=CELL:{clean_phone}")
    if org:
        lines.append(f"ORG:{org}")
    if nickname:
        lines.append(f"NICKNAME:{nickname}")
    if note:
        lines.append(f"NOTE:{note}")
    lines.append("END:VCARD")
    return "\r\n".join(lines)


def detect_column(headers, keywords):
    """키워드 목록으로 컬럼 자동 감지"""
    for h in headers:
        h_lower = str(h).lower().strip()
        for kw in keywords:
            if kw in h_lower:
                return h
    return None


def create_sample_excel():
    """샘플 엑셀 파일 생성"""
    df = pd.DataFrame({
        "이름": ["홍길동", "김영희", "이철수"],
        "연락처": ["010-1234-5678", "010-9876-5432", "010-5555-7777"],
        "소속": ["메리츠화재 서울지점", "메리츠화재 부산지점", "메리츠화재 대전지점"],
        "닉네임": ["길동이", "영희", "철수"],
        "메모": ["서울 담당 매니저", "부산 신규 입사", "대전 우수 실적자"],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf


# ── 키워드 매핑 ──
NAME_KEYS = ["이름", "성명", "name", "담당자"]
PHONE_KEYS = ["연락처", "전화번호", "핸드폰", "휴대폰", "phone", "tel", "mobile", "번호"]
ORG_KEYS = ["소속", "회사", "조직", "기관", "org", "company", "부서", "지점"]
NICK_KEYS = ["닉네임", "별명", "별칭", "nickname", "nick", "애칭"]
NOTE_KEYS = ["메모", "비고", "노트", "note", "memo", "참고", "기타"]


# ── UI ──
st.markdown("## 📇 엑셀 → 연락처 변환기")
st.caption("엑셀 파일을 업로드하면 핸드폰에 바로 저장 가능한 vCard(.vcf) 파일로 변환합니다")

# Step 1: 파일 업로드
st.markdown('<span class="step-badge">1</span> **엑셀 파일 업로드**', unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col2:
    st.download_button(
        "📥 양식 다운로드",
        data=create_sample_excel(),
        file_name="연락처_양식.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

uploaded = st.file_uploader(
    "파일 선택 (.xlsx, .xls, .csv)",
    type=["xlsx", "xls", "csv"],
    label_visibility="collapsed",
)

if uploaded:
    # 파일 읽기
    try:
        if uploaded.name.endswith(".csv"):
            # csv는 인코딩 자동 감지
            try:
                df = pd.read_csv(uploaded, encoding="utf-8")
            except UnicodeDecodeError:
                uploaded.seek(0)
                df = pd.read_csv(uploaded, encoding="euc-kr")
        else:
            df = pd.read_excel(uploaded, engine="openpyxl")
    except Exception as e:
        st.error(f"파일을 읽을 수 없습니다: {e}")
        st.stop()

    if df.empty:
        st.warning("데이터가 없습니다. 엑셀 파일을 확인해주세요.")
        st.stop()

    headers = list(df.columns)

    # Step 2: 컬럼 매핑
    st.markdown("---")
    st.markdown('<span class="step-badge">2</span> **컬럼 매핑 확인**', unsafe_allow_html=True)

    # 자동 감지
    auto_name = detect_column(headers, NAME_KEYS)
    auto_phone = detect_column(headers, PHONE_KEYS)
    auto_org = detect_column(headers, ORG_KEYS)
    auto_nick = detect_column(headers, NICK_KEYS)
    auto_note = detect_column(headers, NOTE_KEYS)

    options_with_none = ["— 선택 안함 —"] + headers

    c1, c2, c3 = st.columns(3)
    with c1:
        name_col = st.selectbox(
            "이름 *",
            options=options_with_none,
            index=options_with_none.index(auto_name) if auto_name else 0,
        )
    with c2:
        phone_col = st.selectbox(
            "연락처 *",
            options=options_with_none,
            index=options_with_none.index(auto_phone) if auto_phone else 0,
        )
    with c3:
        org_col = st.selectbox(
            "소속",
            options=options_with_none,
            index=options_with_none.index(auto_org) if auto_org else 0,
        )

    c4, c5 = st.columns(2)
    with c4:
        nick_col = st.selectbox(
            "닉네임",
            options=options_with_none,
            index=options_with_none.index(auto_nick) if auto_nick else 0,
        )
    with c5:
        note_col = st.selectbox(
            "메모",
            options=options_with_none,
            index=options_with_none.index(auto_note) if auto_note else 0,
        )

    name_col = None if name_col == "— 선택 안함 —" else name_col
    phone_col = None if phone_col == "— 선택 안함 —" else phone_col
    org_col = None if org_col == "— 선택 안함 —" else org_col
    nick_col = None if nick_col == "— 선택 안함 —" else nick_col
    note_col = None if note_col == "— 선택 안함 —" else note_col

    if not name_col or not phone_col:
        st.warning("이름과 연락처 컬럼을 선택해주세요.")
        st.stop()

    # 유효 데이터 필터링
    valid_df = df[df[name_col].notna() | df[phone_col].notna()].copy()
    valid_df["_전화번호"] = valid_df[phone_col].apply(normalize_phone)

    # Step 3: 미리보기
    st.markdown("---")
    st.markdown(
        f'<span class="step-badge">3</span> **미리보기** &nbsp; <span class="count-badge">👤 {len(valid_df)}건</span>',
        unsafe_allow_html=True,
    )

    preview_cols = {name_col: "이름", "_전화번호": "연락처"}
    if org_col:
        preview_cols[org_col] = "소속"
    if nick_col:
        preview_cols[nick_col] = "닉네임"
    if note_col:
        preview_cols[note_col] = "메모"

    st.dataframe(
        valid_df[list(preview_cols.keys())].rename(columns=preview_cols).head(20),
        use_container_width=True,
        hide_index=True,
    )
    if len(valid_df) > 20:
        st.caption(f"... 외 {len(valid_df) - 20}건 더")

    # Step 4: VCF 생성
    st.markdown("---")

    vcards = []
    for _, row in valid_df.iterrows():
        name = str(row[name_col]) if pd.notna(row[name_col]) else ""
        phone = row[phone_col]
        org = str(row[org_col]) if org_col and pd.notna(row[org_col]) else ""
        nickname = str(row[nick_col]) if nick_col and pd.notna(row[nick_col]) else ""
        note = str(row[note_col]) if note_col and pd.notna(row[note_col]) else ""
        if name or phone:
            vcards.append(to_vcard(name, phone, org, nickname, note))

    vcf_data = "\r\n".join(vcards)

    st.download_button(
        f"📱 VCF 파일 생성 ({len(vcards)}건)",
        data=vcf_data.encode("utf-8"),
        file_name=f"연락처_{len(vcards)}건.vcf",
        mime="text/vcard",
        use_container_width=True,
        type="primary",
    )

    st.markdown(
        '<div class="success-box">✅ 다운로드된 .vcf 파일을 핸드폰에서 열면 연락처에 자동 추가됩니다</div>',
        unsafe_allow_html=True,
    )

# 사용 가이드
st.markdown("---")
st.markdown(
    """<div class="guide-box">
💡 <b>사용 방법</b><br>
<b>1.</b> 양식 다운로드 → 이름, 연락처, 소속, 닉네임, 메모 입력 후 저장<br>
<b>2.</b> 엑셀 파일 업로드 → 컬럼 자동 매핑 확인<br>
<b>3.</b> VCF 파일 생성 → 다운로드<br>
<b>4.</b> 핸드폰에서 .vcf 파일 열기 → 연락처 자동 저장<br><br>
📌 <b>팁:</b> 카카오톡/메일로 vcf 파일을 본인에게 보낸 뒤 핸드폰에서 열면 편합니다
</div>""",
    unsafe_allow_html=True,
)
