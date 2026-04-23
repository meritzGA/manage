# 메리츠 실적 관리 시스템 — 자동화 버전

> **매주 할 일**: `data/` 폴더의 엑셀 3개 파일을 최신 파일로 교체하고 `git push`. 끝.

---

## 📂 Repo 구조

```
your-repo/
├── app.py                              # Streamlit 메인 (패치 필요)
├── auto_loader.py                      # ✨ 새 파일 — 자동 로드 모듈
├── admin_view.py                       # ✨ 새 파일 — 관리자 상태 뷰
├── requirements.txt                    # streamlit, pandas, openpyxl
├── data/                               # ← 🔥 매주 여기 3개 파일 교체
│   ├── MC_LIST_OUT_YYYYMMDD.xlsx
│   ├── PRIZE_6_BRIDGE_OUT_YYYYMMDD.xlsx
│   └── PRIZE_SUM_OUT_YYYYMMDD.xlsx
└── config/
    ├── base.json                       # 공통 고정 설정 (매니저 열, 병합 키, 분류)
    └── stages/
        ├── stage_1_week1_early.json    # 월초 (연속가동만)
        ├── stage_2_week2.json          # 2주차 (브릿지 등장)
        ├── stage_3_week3.json          # 3주차 (주차연속가동 등장)
        ├── stage_4_week4.json          # 4주차 (전체 완성)
        └── stage_5_week5.json          # 5주차 (5주 있는 달 대비, stage_4 기반 확장)
```

---

## ⚙️ 작동 방식

### 파일 업로드 → 앱 로드 과정

1. 앱이 시작하면 `data/` 폴더를 스캔해 각 파일명 패턴별 **최신 YYYYMMDD 파일** 1개씩 자동 선택
2. 3개 파일을 `대리점설계사조직코드` 기준으로 outer merge
3. 병합 데이터의 **기준년월 최빈값**으로 `current_month` 감지 (예: 4월)
4. 병합 컬럼에서 **stage 자동 감지**:
   - `실적_4주차` 값이 있으면 → `stage_4_week4`
   - `실적_3주차` 있고 `실적_4주차` 없으면 → `stage_3_week3`
   - `실적_2주차` 있고 `실적_3주차` 없으면 → `stage_2_week2`
   - 그 외 → `stage_1_week1_early`
5. `config/base.json` + `config/stages/{detected}.json` 로드
6. 모든 문자열의 `{m}`, `{m-1}` 플레이스홀더를 실제 월 숫자로 치환
   - 예: `연속가동실적_{m}월` → `연속가동실적_4월`, `{m}월 1주차 실적` → `4월 1주차 실적`
7. base + stage 머지 → `session_state`에 주입 → 매니저 뷰 즉시 동작

### 월 전환 자동 처리

`5월 1일`에 `data/MC_LIST_OUT_20260501.xlsx` 등을 push 하면:
- `기준년월` = 202605 로 감지
- `{m}` = `5`, `{m-1}` = `4`
- 템플릿이 자동으로 `5월 1주차 실적`, `브릿지 4월/5월` 등으로 치환됨
- **config 파일 수정 불필요**

---

## 🩹 app.py 패치 5곳

기존 `app.py` (첨부 주신 1,470 줄 버전 기준)에 아래 5 군데만 수정하면 됩니다.

### ① 상단 import 추가

```python
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
# ... 기존 import들 ...

# ✨ 아래 2줄 추가
import auto_loader as al
from admin_view import render_admin_view
```

---

### ② `load_data_and_config()` 함수 전체 대체

기존 `load_data_and_config()` 함수 (약 50줄)를 통째로 아래 내용으로 바꿉니다.

```python
def load_data_and_config():
    """자동 로더로 data/ + config/ 읽어서 session_state 채우기."""
    try:
        force = st.session_state.get('_stage_override')
        result = al.auto_load(force_stage=force)
        if 'error' in result:
            st.session_state['_autoload_error'] = result['error']
            return
        st.session_state['_autoload_error'] = None
        st.session_state['df_merged'] = result['df_merged']
        for k, v in result['config'].items():
            st.session_state[k] = v
        st.session_state['_autoload_info'] = {
            'detected_stage': result['detected_stage'],
            'current_month':  result['current_month'],
            'files':          result['files'],
        }
    except Exception as e:
        st.session_state['_autoload_error'] = str(e)
```

### ③ `save_*` 함수들을 no-op 처리 (선택)

기존 `save_data_and_config()`, `save_config()`, `save_data()` 는 삭제하거나 아래처럼 비워둡니다 (매니저 뷰 경로에서 호출되지 않음, 관리자 뷰 교체 후 완전 불사용).

```python
def save_data_and_config(): pass
def save_config(): pass
def save_data(): pass
```

---

### ④ 사이드바 "💾 설정 백업 / 복원" expander 제거

아래 블록을 통째로 **삭제**합니다 (현재 약 30줄).

```python
# ━━━ 삭제 대상 (시작) ━━━
if st.session_state.get('admin_authenticated', False) and menu == "관리자 화면 (설정)":
    st.sidebar.divider()
    with st.sidebar.expander("💾 설정 백업 / 복원"):
        # ... 복원 관련 코드 30여 줄 ...
    with st.sidebar.expander("⚠️ 시스템 초기화 (주의)"):
        # ...
# ━━━ 삭제 대상 (끝) ━━━
```

백업 다운로드는 새 관리자 뷰(`admin_view.py`) 안에 들어가 있습니다.

---

### ⑤ 관리자 뷰 전체 블록 교체

기존 `app.py` 의

```python
if menu == "관리자 화면 (설정)":
    st.title("⚙️ 관리자 설정 화면")
    # ... 섹션 1~10번 전부 (약 800줄) ...
elif menu == "매니저 화면 (로그인)":
    # ...
```

에서 `if menu == "관리자 화면 (설정)":` 블록 **전체**를 아래 한 줄로 교체합니다.

```python
if menu == "관리자 화면 (설정)":
    render_admin_view()
elif menu == "매니저 화면 (로그인)":
    # ... 매니저 뷰는 그대로 유지 ...
```

추가로, 매니저 뷰 시작부에 자동 로드 에러 체크 한 줄 추가 (옵션):

```python
elif menu == "매니저 화면 (로그인)":
    st.session_state['admin_authenticated'] = False

    # ✨ 자동 로드 에러 표시
    if st.session_state.get('_autoload_error'):
        st.error(f"⚠️ 자동 로드 실패: {st.session_state['_autoload_error']}")
        st.info("data/ 폴더에 MC_LIST_OUT, PRIZE_6_BRIDGE_OUT, PRIZE_SUM_OUT 3개 파일이 있는지 확인하세요.")
        st.stop()

    df_check = st.session_state.get('df_merged', pd.DataFrame())
    # ... 이하 기존 매니저 뷰 로직 그대로 ...
```

---

## 🔄 매주 운영 워크플로우

### 주간 데이터 업데이트 (매주)

```bash
# 1. 회사 시스템에서 최신 엑셀 3개 다운로드
# 2. 파일명 확인 (YYYYMMDD 포함)
#    MC_LIST_OUT_20260427.xlsx
#    PRIZE_6_BRIDGE_OUT_20260427.xlsx  
#    PRIZE_SUM_OUT_20260427.xlsx

# 3. repo에 복사
cp ~/Downloads/MC_LIST_OUT_20260427.xlsx data/
cp ~/Downloads/PRIZE_6_BRIDGE_OUT_20260427.xlsx data/
cp ~/Downloads/PRIZE_SUM_OUT_20260427.xlsx data/

# 4. (선택) 이전 주 파일 삭제 — 최신 1개만 있어도 되고, 여러 개 있어도 최신만 씀
git rm data/MC_LIST_OUT_20260420.xlsx data/PRIZE_6_BRIDGE_OUT_20260420.xlsx data/PRIZE_SUM_OUT_20260420.xlsx

# 5. commit + push
git add data/
git commit -m "2026-04-27 주간 데이터 업데이트"
git push
```

Streamlit Cloud가 push 감지 → 자동 재배포 → 앱이 새 데이터로 동작.

### 이게 끝입니다. 앱은 알아서:
- 최신 YYYYMMDD 파일 3개 선택
- 병합 + 월/stage 감지
- 적절한 stage config 로드 + `{m}` 치환
- 매니저 뷰 즉시 동작

---

## 🛠️ 언제 코드 수정이 필요한가

### 수정 **불필요** (자동)
- 매주 데이터 업데이트
- 월 전환 (4월 → 5월)
- 주차 진행 (1주 → 2주 → 3주 → 4주)

### 수정 **필요** (분기 1회 수준)
- 새로운 시상금 시책 구조가 도입됨 → 해당 `stage_X.json` 편집
- 회사 데이터 스키마 변경 (컬럼명 바뀜) → `base.json` 또는 `stage_X.json` 편집
- 6주차 이상 등장 → `config/stages/stage_6_week6.json` 추가 + `auto_loader.MAX_WEEK_SUPPORTED` 값 조정 (현재 5주차까지 지원)

### 긴급 오버라이드
관리자 화면 → "Stage 수동 오버라이드" 드롭다운에서 다른 stage 선택.
(세션 단위로만 유지됨, 새로고침하면 다시 자동 감지로 복구)

---

## 📆 5주차가 있는 달은?

2026년 기준으로 **1월·5월·8월·10월** 등 5주차가 있는 달이 1년에 4~5회 발생합니다.
`stage_5_week5.json` 이 포함되어 있어 해당 달에 `실적_5주차` 컬럼에 값이 찍히면 **자동으로 `stage_5` 가 적용**됩니다.

### 감지 우선순위 (자동)

1. `auto_loader.detect_stage()` 는 1~6주차까지 일반화되어 있습니다 (`MAX_WEEK_SUPPORTED=6`)
2. **값이 실제로 찍힌 가장 높은 주차** 기준으로 stage 판정 — 컬럼만 있고 값이 0이면 하위 stage 유지
3. 감지된 stage 파일이 없으면 **가장 가까운 하위 stage 로 자동 폴백** (예: stage_6 감지됐는데 파일 없으면 stage_4로 내려감)

### stage_5 템플릿은 자동 생성된 "추정치"입니다

`stage_5_week5.json` 은 `stage_4` 를 기반으로 패턴 확장 (5주차 실적 + 연속가동 5주 + 5주차 시책 + 4~5주 브릿지) 해서 만든 템플릿입니다. 실제 5주차 데이터가 들어왔을 때 한 번만 확인이 필요합니다:

- `주차연속가동_5주실적` 컬럼이 회사 스키마에 실제로 존재하는지
- 5주차 시상금 컬럼명 (`추가13회예정금_5주` 등)이 실제와 맞는지
- "4~5주 브릿지" 시책이 실제 존재하는지

만약 일부가 다르면 `config/stages/stage_5_week5.json` 을 열어 해당 항목만 수정 후 git push. 이후 매 5주차 달마다 자동 적용됩니다.

### 6주차 이상이 필요할 때

`MAX_WEEK_SUPPORTED` 를 늘리고 `stage_6_week6.json` 을 추가하면 끝. 현재로선 실무적으로 거의 발생하지 않습니다.

---

## 📝 config/base.json 편집 예시

매니저 코드 열 이름을 바꿔야 할 때:

```json
{
  "manager_col": "지원매니저코드",      ← 여기만 수정
  "manager_col2": "매니저코드",
  "manager_name_col": "지원매니저명",
  ...
}
```

Git commit + push. 끝.

---

## 📝 config/stages/stage_X.json 편집 예시

2주차에 새 시상금 시책 추가 시:

```json
{
  "prize_config": [
    {"name": "4월 1주차", ...},
    {"name": "월초 연속가동 시책", ...},
    {
      "name": "2주차 신규 시상",         ← 이 블록 추가
      "category": "weekly",
      "type": "구간 시책",
      "col_code": "대리점설계사조직코드",
      "col_val": "실적_2주차",
      "tiers": [[300000, 200], [100000, 100]],
      "prize_items": [
        {"label": "신규 시상", "col_prize": "신규시상금_2주", "col_eligible": ""}
      ]
    }
  ]
}
```

Git commit + push. 끝.

문자열에 월 숫자를 넣을 땐 `{m}` / `{m-1}` 플레이스홀더 사용 (예: `"연속가동실적_{m}월"`).

---

## 🧪 로컬에서 테스트

```bash
pip install -r requirements.txt
streamlit run app.py
```

`data/` 에 테스트용 파일 3개 두고 로컬에서 확인 후 push.
