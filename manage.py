import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="지원매니저별 실적 관리 시스템", layout="wide")

# ==========================================
# 1. 데이터 로드 및 전처리
# ==========================================
@st.cache_data
def load_data():
    try:
        # 파일 인코딩은 환경에 따라 'utf-8' 또는 'euc-kr' 혹은 'cp949'로 조정
        df_mc = pd.read_csv("MC_LIST_OUT.csv", encoding='utf-8', errors='replace')
        df_prize = pd.read_csv("PRIZE_SUM_OUT.csv", encoding='utf-8', errors='replace')
        
        # 병합을 위해 기준 키(설계사 코드) 컬럼명 통일
        df_mc.rename(columns={'현재대리점설계사조직코드': '설계사코드', '현재대리점설계사조직명': '설계사명', '매니저코드': '지원매니저코드'}, inplace=True)
        df_prize.rename(columns={'대리점설계사조직코드': '설계사코드', '대리점설계사명': '설계사명'}, inplace=True)
        
        # 두 데이터프레임 병합 (설계사코드 기준)
        df_merged = pd.merge(df_mc, df_prize, on=['설계사코드', '설계사명', '지원매니저코드'], how='outer', suffixes=('_MC', '_PRIZE'))
        return df_merged
    except Exception as e:
        st.error(f"데이터 로드 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

df = load_data()

# ==========================================
# 2. 세션 상태 (관리자 설정 저장용)
# ==========================================
if 'admin_cols' not in st.session_state:
    st.session_state['admin_cols'] = []
if 'admin_goals' not in st.session_state:
    st.session_state['admin_goals'] = {}
if 'admin_categories' not in st.session_state:
    st.session_state['admin_categories'] = []

# ==========================================
# 3. 사이드바 (메뉴 선택)
# ==========================================
st.sidebar.title("메뉴")
menu = st.sidebar.radio("이동할 화면을 선택하세요", ["매니저 화면 (로그인)", "관리자 화면 (설정)"])

# ==========================================
# 4. 관리자 화면 (Admin View)
# ==========================================
if menu == "관리자 화면 (설정)":
    st.title("⚙️ 관리자 설정 화면")
    if df.empty:
        st.warning("데이터 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
        st.stop()

    available_columns = df.columns.tolist()

    st.header("1. 표시할 데이터 항목 및 필터 설정")
    st.markdown("매니저 화면에 보여줄 컬럼을 추가하고, 숫자인 경우 필터 산식(예: `> 0`)을 적용할 수 있습니다.")
    
    col1, col2, col3, col4 = st.columns([3, 2, 3, 1])
    with col1:
        sel_col = st.selectbox("항목 선택", available_columns)
    with col2:
        col_type = st.radio("데이터 타입", ["텍스트", "숫자"], horizontal=True)
    with col3:
        condition = st.text_input("산식 (예: > 0, >= 100000)", help="숫자 타입일 경우에만 적용됩니다.")
    with col4:
        st.write("")
        st.write("")
        if st.button("항목 추가"):
            st.session_state['admin_cols'].append({
                "col": sel_col,
                "type": col_type,
                "condition": condition if col_type == "숫자" else ""
            })
            st.success(f"'{sel_col}' 항목이 추가되었습니다.")

    if st.session_state['admin_cols']:
        st.write(" **[현재 선택된 항목]**")
        for i, item in enumerate(st.session_state['admin_cols']):
            st.write(f"- {item['col']} ({item['type']}) | 조건: {item['condition']}")
        if st.button("설정 초기화 (항목 삭제)"):
            st.session_state['admin_cols'] = []
            st.experimental_rerun()

    st.divider()

    st.header("2. 목표 구간 설정")
    st.markdown("특정 실적 항목에 대해 목표 구간(쉼표로 구분)을 설정하면, 달성 여부와 부족분을 자동으로 계산합니다.")
    goal_col = st.selectbox("목표 구간을 적용할 항목", available_columns, key="goal_col")
    goal_tiers = st.text_input("구간 입력 (예: 100000,200000,300000,500000)", key="goal_tiers")
    if st.button("목표 구간 적용"):
        if goal_tiers:
            tiers_list = [float(x.strip()) for x in goal_tiers.split(",") if x.strip().isdigit()]
            st.session_state['admin_goals'][goal_col] = sorted(tiers_list)
            st.success(f"{goal_col} 항목에 목표 구간({tiers_list})이 설정되었습니다.")
            
    if st.session_state['admin_goals']:
        st.write(st.session_state['admin_goals'])

    st.divider()

    st.header("3. 맞춤형 분류 섹션")
    st.markdown("조건을 만족하는 설계사에게 특정 분류명(태그)을 부여합니다.")
    cat_col = st.selectbox("분류 기준 항목", available_columns, key="cat_col")
    cat_cond = st.text_input("조건 (예: >= 500000)", key="cat_cond")
    cat_name = st.text_input("부여할 분류명 (예: VIP 우수설계사)", key="cat_name")
    if st.button("분류 기준 추가"):
        st.session_state['admin_categories'].append({
            "col": cat_col, "condition": cat_cond, "name": cat_name
        })
        st.success("분류 기준이 추가되었습니다.")
        
    if st.session_state['admin_categories']:
        st.write(st.session_state['admin_categories'])

# ==========================================
# 5. 매니저 화면 (Manager View)
# ==========================================
elif menu == "매니저 화면 (로그인)":
    st.title("👤 매니저 전용 실적 현황")
    
    if df.empty:
        st.warning("데이터를 불러오지 못했습니다.")
        st.stop()
        
    manager_code = st.text_input("🔑 매니저 코드를 입력하세요 (예: 18000498, 25015504 등)", type="password")
    
    if st.button("로그인 및 조회") or manager_code:
        # 1. 매니저 코드로 데이터 필터링 (데이터의 형식에 따라 _x0033_ 같은 엑셀 특수문자 전처리 적용 필요할 수 있음)
        # 엑셀 변환 시 발생한 특수문자 정리 로직 (필요시)
        df['지원매니저코드_클린'] = df['지원매니저코드'].astype(str).str.replace(r'_x[0-9a-fA-F]{4}_', '', regex=True)
        
        my_df = df[df['지원매니저코드_클린'].str.contains(manager_code, na=False)].copy()
        
        if my_df.empty:
            st.error("일치하는 매니저 코드가 없거나 산하 설계사가 없습니다.")
        else:
            st.success(f"총 {len(my_df)}명의 설계사 데이터가 조회되었습니다.")
            
            # 기본 출력 컬럼 준비
            # 대리점명, 지사명 등은 원본 컬럼명에 맞게 조정 (여기서는 샘플명 사용)
            display_cols = ['현재대리점설계사조직명_MC', '현재대리점지사명', '설계사명', '설계사코드']
            available_disp = [c for c in display_cols if c in my_df.columns]
            
            # 2. 관리자가 추가한 항목 및 필터 적용
            for item in st.session_state['admin_cols']:
                col_name = item['col']
                if col_name not in available_disp:
                    available_disp.append(col_name)
                
                # 조건 필터 적용 (숫자인 경우)
                if item['type'] == '숫자' and item['condition']:
                    # my_df = my_df.query(f"`{col_name}` {item['condition']}") # query 엔진 대안
                    try:
                        my_df[col_name] = pd.to_numeric(my_df[col_name], errors='coerce').fillna(0)
                        # eval을 통한 마스킹 연산
                        mask = my_df.eval(f"`{col_name}` {item['condition']}")
                        my_df = my_df[mask]
                    except Exception as e:
                        st.warning(f"필터 적용 실패 ({col_name}): {e}")
            
            # 3. 목표 구간 및 부족분 계산 로직
            for g_col, tiers in st.session_state['admin_goals'].items():
                if g_col in my_df.columns:
                    my_df[g_col] = pd.to_numeric(my_df[g_col], errors='coerce').fillna(0)
                    
                    def calc_shortfall(val):
                        for t in tiers:
                            if val < t:
                                return pd.Series([f"{t:,.0f} 구간", t - val])
                        return pd.Series(["최고 구간 달성", 0])
                    
                    my_df[[f'{g_col}_다음목표', f'{g_col}_부족금액']] = my_df[g_col].apply(calc_shortfall)
                    available_disp.extend([f'{g_col}_다음목표', f'{g_col}_부족금액'])

            # 4. 맞춤형 분류(태그) 지정 로직
            if st.session_state['admin_categories']:
                my_df['맞춤분류'] = ""
                for cat in st.session_state['admin_categories']:
                    c_col = cat['col']
                    c_cond = cat['condition']
                    c_name = cat['name']
                    try:
                        mask = my_df.eval(f"`{c_col}` {c_cond}")
                        my_df.loc[mask, '맞춤분류'] += f"[{c_name}] "
                    except:
                        pass
                available_disp.insert(4, '맞춤분류')
            
            # 최종 데이터 프레임 출력
            final_df = my_df[available_disp]
            st.dataframe(final_df, use_container_width=True)