"""
auto_loader.py — 데이터 자동 로더 + stage 감지 + 설정 머지

[작동 순서]
  1. data/ 폴더에서 최신 파일 3개 자동 선택 (파일명 YYYYMMDD 기준)
     - 파일명의 _, -, 공백 유무와 무관하게 매칭
     - 예) MC_LIST_OUT_20260422.xlsx / MCLISTOUT20260422.xlsx / mc-list-out.xlsx 모두 OK
  2. 3개 파일 outer merge
  3. 병합된 컬럼 + 기준년월로 current_month & stage 자동 감지
  4. config/base.json + config/stages/{stage}.json 로드 (JSON 없으면 .pkl 폴백)
  5. 문자열의 {m}, {m-1} 플레이스홀더를 현재 월 숫자로 치환
  6. base + stage 머지 → 앱 session_state에 주입할 dict 반환

[파일명 규칙 — 느슨하게 매칭]
  data/MC_LIST_OUT_YYYYMMDD.xlsx          (권장)
  data/PRIZE_6_BRIDGE_OUT_YYYYMMDD.xlsx   (권장)
  data/PRIZE_SUM_OUT_YYYYMMDD.xlsx        (권장)
  위와 같이 언더스코어가 있어도 되고, 없어도 됨.
"""
import os
import re
import glob
import json
import pickle
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter

# ──────────────────────────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────────────────────────
DATA_DIR = "data"
CONFIG_DIR = "config"
STAGES_DIR = os.path.join(CONFIG_DIR, "stages")

# 파일 유형별 "정규화 후 포함되어야 할 토큰들"
# 파일명에서 _, -, 공백을 모두 제거하고 대문자로 바꾼 뒤 비교하므로
# MC_LIST_OUT_20260422.xlsx / MCLISTOUT20260422.xlsx / mc-list-out.xlsx 모두 매칭됨
FILE_PATTERNS = [
    ("MC_LIST_OUT",        ["MCLISTOUT"]),
    ("PRIZE_6_BRIDGE_OUT", ["PRIZE6BRIDGEOUT"]),
    ("PRIZE_SUM_OUT",      ["PRIZESUMOUT"]),
]


# ──────────────────────────────────────────────────────────────
# 데이터 파일 스캔
# ──────────────────────────────────────────────────────────────
def _normalize_filename(name):
    """파일명(확장자 제외)에서 _, -, 공백 제거 + 대문자화 → 비교용 키."""
    stem = os.path.splitext(os.path.basename(name))[0]
    return re.sub(r"[\s_\-]+", "", stem).upper()


def _extract_yyyymmdd(filepath):
    m = re.search(r"(\d{8})", os.path.basename(filepath))
    return m.group(1) if m else "00000000"


def find_latest_data_files():
    """각 유형별 최신 파일 1개씩 반환. 언더스코어 유무와 무관하게 매칭."""
    # data/ 폴더의 모든 엑셀 파일 (xlsx, xls 모두)
    all_files = (
        glob.glob(os.path.join(DATA_DIR, "*.xlsx")) +
        glob.glob(os.path.join(DATA_DIR, "*.xls"))
    )
    # Excel 임시파일(~$로 시작) 제외
    all_files = [f for f in all_files if not os.path.basename(f).startswith("~$")]

    result = {}
    for key, tokens in FILE_PATTERNS:
        candidates = [
            f for f in all_files
            if all(tok in _normalize_filename(f) for tok in tokens)
        ]
        if not candidates:
            result[key] = None
            continue
        # YYYYMMDD 있으면 그걸로, 없으면 수정시간으로 최신 우선
        candidates.sort(
            key=lambda p: (_extract_yyyymmdd(p), os.path.getmtime(p)),
            reverse=True,
        )
        result[key] = candidates[0]
    return result


# ──────────────────────────────────────────────────────────────
# 엑셀 로드 + 인코딩 정리 (기존 app.py 로직 재사용)
# ──────────────────────────────────────────────────────────────
def _decode_excel_text(val):
    if pd.isna(val):
        return val
    s = str(val)
    if "_x" not in s:
        return s

    def _sub(m):
        try:
            return chr(int(m.group(1), 16))
        except Exception:
            return m.group(0)

    return re.sub(r"_x([0-9a-fA-F]{4})_", _sub, s)


def _clean_key(val):
    if pd.isna(val) or str(val).strip().lower() == "nan":
        return ""
    s = str(val).strip().replace(" ", "").upper()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def _load_excel_clean(path):
    df = pd.read_excel(path)
    df.columns = [_decode_excel_text(c) if isinstance(c, str) else c for c in df.columns]
    for c in df.columns:
        if pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].apply(_decode_excel_text)
    return df


# ──────────────────────────────────────────────────────────────
# 3개 파일 outer merge (기존 app.py 병합 로직 그대로)
# ──────────────────────────────────────────────────────────────

# merge key가 파일에 없을 때 자동으로 찾아볼 후보들.
# 지정 키 → 후보 순서대로 시도 → 모두 실패하면 에러.
_MERGE_KEY_FALLBACKS = {
    "대리점설계사조직코드":   ["대리점설계사조직코드", "현재대리점설계사조직코드"],
    "현재대리점설계사조직코드": ["현재대리점설계사조직코드", "대리점설계사조직코드"],
}


def _resolve_merge_key(df, requested_key, file_label):
    """df에서 requested_key를 찾고, 없으면 fallback 후보를 순회."""
    if requested_key in df.columns:
        return requested_key
    for cand in _MERGE_KEY_FALLBACKS.get(requested_key, []):
        if cand in df.columns:
            return cand
    # 마지막 시도: "대리점설계사조직코드" 또는 "현재대리점설계사조직코드"가 들어간 컬럼 아무거나
    for c in df.columns:
        if "대리점설계사조직코드" in c:
            return c
    raise KeyError(
        f"{file_label} 파일에서 merge key '{requested_key}' 또는 대체 후보를 찾지 못했습니다. "
        f"실제 컬럼 일부: {list(df.columns)[:10]}..."
    )


def merge_three_files(f1, f2, f3, key1, key2, key3):
    df1 = _load_excel_clean(f1)
    df2 = _load_excel_clean(f2)
    df3 = _load_excel_clean(f3)

    # 각 파일에서 실제 사용할 키를 결정 (fallback 포함)
    k1 = _resolve_merge_key(df1, key1, "MC_LIST_OUT")
    k2 = _resolve_merge_key(df2, key2, "PRIZE_6_BRIDGE_OUT")
    k3 = _resolve_merge_key(df3, key3, "PRIZE_SUM_OUT")

    df1["merge_key1"] = df1[k1].apply(_clean_key)
    df2["merge_key2"] = df2[k2].apply(_clean_key)
    df_merged = pd.merge(
        df1, df2,
        left_on="merge_key1", right_on="merge_key2",
        how="outer", suffixes=("_파일1", "_파일2"),
    )

    # 중복 컬럼 combine_first
    for c1 in [c for c in df_merged.columns if c.endswith("_파일1")]:
        base = c1.replace("_파일1", "")
        c2 = base + "_파일2"
        if c2 in df_merged.columns:
            df_merged[base] = df_merged[c1].combine_first(df_merged[c2])
            df_merged.drop(columns=[c1, c2], inplace=True)

    df_merged["_unified_search_key"] = df_merged["merge_key1"].combine_first(df_merged["merge_key2"])

    df3["merge_key3"] = df3[k3].apply(_clean_key)
    df_merged = pd.merge(
        df_merged, df3,
        left_on="_unified_search_key", right_on="merge_key3",
        how="outer", suffixes=("", "_파일3"),
    )
    for c3 in [c for c in df_merged.columns if c.endswith("_파일3")]:
        base = c3.replace("_파일3", "")
        if base in df_merged.columns:
            df_merged[base] = df_merged[base].combine_first(df_merged[c3])
            df_merged.drop(columns=[c3], inplace=True)
        else:
            df_merged.rename(columns={c3: base}, inplace=True)

    if "merge_key3" in df_merged.columns:
        df_merged["_unified_search_key"] = df_merged["_unified_search_key"].combine_first(df_merged["merge_key3"])

    return df_merged


# ──────────────────────────────────────────────────────────────
# 현재 월 감지 (기준년월 최빈값)
# ──────────────────────────────────────────────────────────────
def detect_current_month(df):
    if "기준년월" in df.columns:
        vals = df["기준년월"].dropna().astype(str)
        months = []
        for v in vals:
            v_clean = v.replace(".", "").replace("-", "").strip()
            if v_clean.endswith(".0"):
                v_clean = v_clean[:-2]
            if len(v_clean) >= 6:  # YYYYMM...
                try:
                    months.append(int(v_clean[4:6]))
                except Exception:
                    pass
            elif 1 <= len(v_clean) <= 2:
                try:
                    months.append(int(v_clean))
                except Exception:
                    pass
        if months:
            return Counter(months).most_common(1)[0][0]
    return datetime.now().month


# ──────────────────────────────────────────────────────────────
# stage 자동 감지 — "어느 주차까지 실적이 찍혔는지" 기준 (1~6주차 일반화)
# ──────────────────────────────────────────────────────────────
MAX_WEEK_SUPPORTED = 6  # 필요 시 7, 8도 확장 가능. config/stages/stage_N_weekN.json 있어야 함.


def detect_stage(df):
    cols = set(df.columns)
    has_monthly_연속 = any(re.match(r"^연속가동실적_\d+월$", c) for c in cols)

    # 컬럼이 있어도 값이 전부 0이면 "아직 집계 전" — 상위 stage로 안 올라감
    def _has_value(col):
        if col not in df.columns:
            return False
        try:
            num = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            ).fillna(0)
            return (num != 0).any()
        except Exception:
            return False

    # 값이 실제로 찍힌 가장 높은 주차 찾기 (2주차 이상부터 체크 — 1주차는 base)
    max_week_with_value = 0
    for n in range(2, MAX_WEEK_SUPPORTED + 1):
        col = f"실적_{n}주차"
        if col in cols and _has_value(col):
            max_week_with_value = n

    if max_week_with_value >= 2:
        return f"stage_{max_week_with_value}_week{max_week_with_value}"

    # 아직 2주차 값이 없으면 1주차 단계
    if "실적_1주차" in cols or has_monthly_연속:
        return "stage_1_week1_early"
    return "stage_1_week1_early"


# ──────────────────────────────────────────────────────────────
# 플레이스홀더 치환 ({m} → current_month, {m-1} → prev_month)
# ──────────────────────────────────────────────────────────────
def substitute_placeholders(obj, current_month):
    prev_m = current_month - 1 if current_month > 1 else 12
    if isinstance(obj, dict):
        return {k: substitute_placeholders(v, current_month) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_placeholders(v, current_month) for v in obj]
    if isinstance(obj, str):
        # {m-1} 먼저 (m을 포함하므로)
        return obj.replace("{m-1}", str(prev_m)).replace("{m}", str(current_month))
    return obj


# ──────────────────────────────────────────────────────────────
# JSON 우선, PKL 폴백 로더
# ──────────────────────────────────────────────────────────────
def _load_json_or_pkl(json_path, pkl_path):
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    if os.path.exists(pkl_path):
        with open(pkl_path, "rb") as f:
            return pickle.load(f)
    return None


def load_base_config():
    return _load_json_or_pkl(
        os.path.join(CONFIG_DIR, "base.json"),
        os.path.join(CONFIG_DIR, "base.pkl"),
    )


def load_stage_config(stage_id):
    return _load_json_or_pkl(
        os.path.join(STAGES_DIR, f"{stage_id}.json"),
        os.path.join(STAGES_DIR, f"{stage_id}.pkl"),
    )


def list_available_stages():
    stages = set()
    for ext in ("*.json", "*.pkl"):
        for fp in glob.glob(os.path.join(STAGES_DIR, ext)):
            stages.add(os.path.splitext(os.path.basename(fp))[0])
    return sorted(stages)


# ──────────────────────────────────────────────────────────────
# base + stage 머지 → 앱이 쓰는 config dict
# ──────────────────────────────────────────────────────────────
def merge_base_and_stage(base, stage):
    if not base:
        return {}
    stage = stage or {}

    admin_cols = list(base.get("admin_cols_common", [])) + list(stage.get("admin_cols_stage", []))
    common_disp = [x["display_name"] for x in base.get("admin_cols_common", [])]

    stage_order = list(stage.get("col_order_stage", []))
    col_order = []
    if "맞춤분류" in stage_order:
        col_order.append("맞춤분류")
        stage_order = [c for c in stage_order if c != "맞춤분류"]
    col_order.extend(common_disp)
    col_order.extend(stage_order)

    return {
        "manager_col":       base.get("manager_col", ""),
        "manager_col2":      base.get("manager_col2", ""),
        "manager_name_col":  base.get("manager_name_col", ""),
        "merge_key1_col":    base.get("merge_key1_col", ""),
        "merge_key2_col":    base.get("merge_key2_col", ""),
        "merge_key3_col":    base.get("merge_key3_col", ""),
        "admin_categories":  base.get("admin_categories", []),
        "admin_cols":        admin_cols,
        "admin_goals":       stage.get("admin_goals", []) or base.get("admin_goals", []),
        "col_order":         col_order,
        "col_groups":        stage.get("col_groups", []),
        "prize_config":      stage.get("prize_config", []),
        "clip_footer":       stage.get("clip_footer", "") or base.get("clip_footer_default", ""),
    }


# ──────────────────────────────────────────────────────────────
# 메인 진입점
# ──────────────────────────────────────────────────────────────
def auto_load(force_stage=None):
    """
    Returns:
        성공: {'df_merged', 'config', 'detected_stage', 'current_month', 'files'}
        실패: {'error': 메시지}
    """
    files = find_latest_data_files()
    missing = [k for k, v in files.items() if not v]
    if missing:
        return {"error": f"data/ 폴더에 다음 파일이 없습니다: {', '.join(missing)}"}

    base = load_base_config()
    if not base:
        return {"error": "config/base.json (또는 .pkl)을 찾을 수 없습니다."}

    try:
        df = merge_three_files(
            files["MC_LIST_OUT"],
            files["PRIZE_6_BRIDGE_OUT"],
            files["PRIZE_SUM_OUT"],
            base["merge_key1_col"],
            base["merge_key2_col"],
            base["merge_key3_col"],
        )
    except Exception as e:
        return {"error": f"파일 병합 실패: {e}"}

    current_month = detect_current_month(df)
    stage_id = force_stage or detect_stage(df)

    stage = load_stage_config(stage_id)

    # 폴백: 감지된 stage 파일이 없으면 가장 가까운 하위 stage로 내려감
    if not stage:
        available = set(list_available_stages())
        m = re.match(r"stage_(\d+)_week\d+", stage_id)
        if m:
            detected_n = int(m.group(1))
            fallback_id = None
            for n in range(detected_n - 1, 0, -1):
                candidates = [s for s in available if s.startswith(f"stage_{n}_")]
                if candidates:
                    fallback_id = sorted(candidates)[0]
                    break
            if fallback_id:
                stage = load_stage_config(fallback_id)
                if stage:
                    stage_id = f"{fallback_id} (감지: {stage_id} — 해당 stage 파일 없음, 하위 stage로 폴백)"
        if not stage:
            return {"error": f"stage '{stage_id}'의 설정 파일(config/stages/{stage_id}.json 또는 .pkl)을 찾을 수 없습니다."}

    base_r = substitute_placeholders(base, current_month)
    stage_r = substitute_placeholders(stage, current_month)
    config = merge_base_and_stage(base_r, stage_r)

    # data_date: 파일명 YYYYMMDD는 수집일이고, 실제 데이터는 전일 기준.
    # 파일명 20260422 → data_date = 2026.04.21 (월·연 경계 자동 처리)
    m = re.search(r"(\d{8})", os.path.basename(files["MC_LIST_OUT"]))
    if m:
        try:
            collected = datetime.strptime(m.group(1), "%Y%m%d")
            data_dt = collected - timedelta(days=1)
            config["data_date"] = data_dt.strftime("%Y.%m.%d")
        except ValueError:
            ymd = m.group(1)
            config["data_date"] = f"{ymd[:4]}.{ymd[4:6]}.{ymd[6:8]}"
    else:
        config["data_date"] = (datetime.now() - timedelta(days=1)).strftime("%Y.%m.%d")

    return {
        "df_merged":      df,
        "config":         config,
        "detected_stage": stage_id,
        "current_month":  current_month,
        "files":          files,
    }
