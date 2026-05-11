import streamlit as st
import pandas as pd
import re
import io
import zipfile
from collections import defaultdict

st.set_page_config(page_title="엑셀 → 매니저별 연락처 변환기", page_icon="📇", layout="centered")

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
    if not s.startswith("0") and len(s) >= 9:
        s = "0" + s
    return s


def vcf_escape(s):
    """vCard 3.0 텍스트 필드 이스케이프"""
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace("\n", "\\n").replace("\r", "")
    s = s.replace(",", "\\,").replace(";", "\\;")
    return s


def to_vcard(name, phone, org="", nickname="", note=""):
    """단일 연락처를 vCard 3.0 문자열로 변환"""
    clean_phone = normalize_phone(phone)
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{vcf_escape(name)}",
        f"N:{vcf_escape(name)};;;;",
    ]
    if clean_phone:
        lines.append(f"TEL;TYPE=CELL:{clean_phone}")
    if org:
        lines.append(f"ORG:{vcf_escape(org)}")
    if nickname:
        lines.append(f"NICKNAME:{vcf_escape(nickname)}")
    if note:
        lines.append(f"NOTE:{vcf_escape(note)}")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def sanitize_filename(name):
    """파일/폴더명에서 OS 금지문자 제거"""
    name = re.sub(r'[<>:"/\\|?*\r\n\t]', "_", str(name))
    return name.strip().rstrip(".") or "_"


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
        "지점": ["GA3-1지점", "GA3-1지점", "GA3-1지점", "GA3-4지점", "GA3-4지점"],
        "매니저": ["김태현", "김태현", "이현정", "권순", "권순"],
        "대리점": ["A에셋㈜", "A에셋㈜", "B파트너스㈜", "C금융㈜", "C금융㈜"],
        "지사": ["A에셋㈜(강남)", "A에셋㈜(강남)", "B파트너스㈜ 본사", "C금융㈜(부산)", "C금융㈜(부산)"],
        "팀장님명": ["홍길동", "김영희", "이철수", "박민수", "정수연"],
        "휴대폰": ["010-1234-5678", "010-9876-5432", "010-5555-7777", "010-3333-2222", "010-1111-2222"],
        "메모": ["26년5월", "26년5월", "26년5월", "26년5월", "26년5월"],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf


# ── 키워드 매핑 ──
BRANCH_KEYS = ["지점", "branch", "본부"]
MANAGER_KEYS = ["매니저", "manager", "관리자"]
AGENCY_KEYS = ["대리점", "agency"]
SUB_KEYS = ["지사", "subbranch", "sub"]
NAME_KEYS = ["팀장", "이름", "성명", "name", "담당자"]
PHONE_KEYS = ["휴대폰", "연락처", "전화번호", "핸드폰", "phone", "tel", "mobile", "번호"]
NOTE_KEYS = ["메모", "비고", "노트", "note", "memo", "참고", "기타"]


# ── UI ──
st.markdown("## 📇 엑셀 → 매니저별 연락처 변환기")
st.caption("사용인 리스트를 업로드하면 **지점/매니저별 폴더 구조의 ZIP**으로 변환합니다")

# Step 1: 파일 업로드
st.markdown('<span class="step-badge">1</span> **엑셀 파일 업로드**', unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col2:
    st.download_button(
        "📥 양식 다운로드",
        data=create_sample_excel(),
        file_name="사용인리스트_양식.xlsx",
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

    # 헤더가 첫 행이 아닌 경우 자동 탐지 (앞부분에 빈 행이 있을 때)
    if df.columns.isnull().any() or all(str(c).startswith("Unnamed") for c in df.columns):
        try:
            uploaded.seek(0)
            for skip in range(0, 5):
                uploaded.seek(0)
                tmp = pd.read_excel(uploaded, engine="openpyxl", skiprows=skip)
                if not any(str(c).startswith("Unnamed") for c in tmp.columns):
                    df = tmp
                    break
        except Exception:
            pass

    if df.empty:
        st.warning("데이터가 없습니다. 엑셀 파일을 확인해주세요.")
        st.stop()

    headers = list(df.columns)

    # Step 2: 컬럼 매핑
    st.markdown("---")
    st.markdown('<span class="step-badge">2</span> **컬럼 매핑 확인**', unsafe_allow_html=True)

    auto_branch = detect_column(headers, BRANCH_KEYS)
    auto_manager = detect_column(headers, MANAGER_KEYS)
    auto_agency = detect_column(headers, AGENCY_KEYS)
    auto_sub = detect_column(headers, SUB_KEYS)
    auto_name = detect_column(headers, NAME_KEYS)
    auto_phone = detect_column(headers, PHONE_KEYS)
    auto_note = detect_column(headers, NOTE_KEYS)

    options_with_none = ["— 선택 안함 —"] + headers

    def sel(label, auto, required=False):
        idx = options_with_none.index(auto) if auto in options_with_none else 0
        suffix = " *" if required else ""
        return st.selectbox(label + suffix, options=options_with_none, index=idx)

    c1, c2 = st.columns(2)
    with c1:
        branch_col = sel("지점", auto_branch, required=True)
        agency_col = sel("대리점", auto_agency)
        name_col = sel("팀장명/이름", auto_name, required=True)
        note_col = sel("메모", auto_note)
    with c2:
        manager_col = sel("매니저", auto_manager, required=True)
        sub_col = sel("지사", auto_sub)
        phone_col = sel("휴대폰", auto_phone, required=True)

    # None 처리
    def n(v): return None if v == "— 선택 안함 —" else v
    branch_col = n(branch_col)
    manager_col = n(manager_col)
    agency_col = n(agency_col)
    sub_col = n(sub_col)
    name_col = n(name_col)
    phone_col = n(phone_col)
    note_col = n(note_col)

    if not (branch_col and manager_col and name_col and phone_col):
        st.warning("지점, 매니저, 팀장명, 휴대폰 컬럼은 필수입니다.")
        st.stop()

    # 유효 데이터 필터
    valid_df = df[df[name_col].notna() & df[phone_col].notna() & df[branch_col].notna()].copy()
    valid_df["_전화번호"] = valid_df[phone_col].apply(normalize_phone)
    valid_df = valid_df[valid_df["_전화번호"] != ""].copy()

    # Step 3: 미리보기 & 통계
    st.markdown("---")
    st.markdown(
        f'<span class="step-badge">3</span> **미리보기 & 통계** &nbsp; <span class="count-badge">👤 {len(valid_df)}건</span>',
        unsafe_allow_html=True,
    )

    # 지점/매니저별 인원 수
    summary = (
        valid_df.assign(
            _매니저=valid_df[manager_col].fillna("(미지정)").replace("", "(미지정)")
        )
        .groupby([branch_col, "_매니저"]).size().reset_index(name="인원수")
        .sort_values([branch_col, "_매니저"])
    )
    summary.columns = ["지점", "매니저", "인원수"]
    st.dataframe(summary, use_container_width=True, hide_index=True, height=300)

    # Step 4: ZIP 생성
    st.markdown("---")
    st.markdown('<span class="step-badge">4</span> **VCF ZIP 생성**', unsafe_allow_html=True)

    # 지점 → 매니저 → 레코드 그룹화
    groups = defaultdict(lambda: defaultdict(list))
    for _, row in valid_df.iterrows():
        branch = str(row[branch_col]).strip()
        manager = row[manager_col]
        manager = str(manager).strip() if pd.notna(manager) and str(manager).strip() else "_매니저미지정"
        name = str(row[name_col]).strip()
        phone = row["_전화번호"]
        # 소속 = 지사 우선, 없으면 대리점
        org = ""
        if sub_col and pd.notna(row[sub_col]) and str(row[sub_col]).strip():
            org = str(row[sub_col]).strip()
        elif agency_col and pd.notna(row[agency_col]) and str(row[agency_col]).strip():
            org = str(row[agency_col]).strip()
        note = ""
        if note_col and pd.notna(row[note_col]) and str(row[note_col]).strip():
            note = str(row[note_col]).strip()
        # FN: "이름 (소속)" 형식
        fn = f"{name} ({org})" if org else name
        groups[branch][manager].append((fn, phone, org, note))

    # ZIP 빌드 (UTF-8 BOM + vCards per manager)
    zip_buf = io.BytesIO()
    file_count = 0
    contact_count = 0
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for branch in sorted(groups.keys()):
            for manager in sorted(groups[branch].keys()):
                rows = groups[branch][manager]
                cnt = len(rows)
                fname = f"{sanitize_filename(manager)}_{cnt}.vcf"
                arcname = f"{sanitize_filename(branch)}/{fname}"
                body = "﻿"  # UTF-8 BOM
                for (fn, phone, org, note) in rows:
                    body += to_vcard(fn, phone, org=org, note=note)
                zf.writestr(arcname, body.encode("utf-8"))
                file_count += 1
                contact_count += cnt

    zip_buf.seek(0)

    st.download_button(
        f"📦 ZIP 다운로드 ({len(groups)}지점 · {file_count}파일 · {contact_count}건)",
        data=zip_buf.getvalue(),
        file_name=f"연락처_매니저별_{contact_count}건.zip",
        mime="application/zip",
        use_container_width=True,
        type="primary",
    )

    st.markdown(
        f'<div class="success-box">✅ ZIP 안에 <b>지점별 폴더</b>가 있고, 각 폴더 안에 <b>매니저명_인원수.vcf</b> 파일이 들어있습니다.<br>'
        f'· 지점: {len(groups)}개 &nbsp; · VCF 파일: {file_count}개 &nbsp; · 연락처: {contact_count}건</div>',
        unsafe_allow_html=True,
    )

# 사용 가이드
st.markdown("---")
st.markdown(
    """<div class="guide-box">
💡 <b>사용 방법</b><br>
<b>1.</b> 양식 다운로드 → 지점/매니저/대리점/지사/팀장님명/휴대폰/메모 입력 후 저장<br>
<b>2.</b> 엑셀 파일 업로드 → 컬럼 자동 매핑 (필요 시 수동 변경)<br>
<b>3.</b> 미리보기에서 지점/매니저별 인원수 확인<br>
<b>4.</b> ZIP 다운로드 → 압축 풀면 <b>지점 폴더 / 매니저_인원수.vcf</b> 구조<br><br>
📌 <b>구조 예시:</b><br>
&nbsp;&nbsp;GA3-1지점/김태현_814.vcf<br>
&nbsp;&nbsp;GA3-1지점/이현정_729.vcf<br>
&nbsp;&nbsp;GA3-4지점/권순_394.vcf<br><br>
📌 <b>vCard 형식:</b> FN(팀장명+지사), TEL, ORG(지사), NOTE(메모) 포함 — vCard 3.0
</div>""",
    unsafe_allow_html=True,
)
