"""
auto_loader.py — 데이터 자동 로더 + stage 감지 + 설정 머지

[성능 최적화 (2026-05-27)]
  - @st.cache_data 로 파일별 + 머지 결과 캐싱 → 매 rerun/새 세션마다 다시 안 읽음
  - parquet 우선 로딩 (xlsx보다 30~50배 빠름) → *.parquet 있으면 그걸 사용
  - calamine 엔진 폴백 (openpyxl보다 5~10배 빠름) → parquet 없을 때 사용

[작동 순서]
  1. data/ 폴더에서 최신 파일 3개 자동 선택 (파일명 YYYYMMDD 기준)
     - 같은 YYYYMMDD에 .parquet, .xlsx 둘 다 있으면 .parquet 우선
  2. 3개 파일 outer merge
  3. 병합된 컬럼 + 기준년월로 current_month & stage 자동 감지
  4. config/base.json + config/stages/{stage}.json 로드
  5. {m}, {m-1} 플레이스홀더 치환
"""
import os
import re
import glob
import json
import pickle
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter

# Streamlit 캐싱 — Streamlit이 없는 환경에서도 import 가능하도록 안전 폴백
try:
    import streamlit as st
    _cache_data = st.cache_data
except Exception:
    def _cache_data(*args, **kwargs):
        # decorator 인자 유무 모두 처리
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        def deco(fn):
            return fn
        return deco

# ──────────────────────────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────────────────────────
DATA_DIR = "data"
CONFIG_DIR = "config"
STAGES_DIR = os.path.join(CONFIG_DIR, "stages")

FILE_PATTERNS = [
    ("MC_LIST_OUT",        ["MCLISTOUT"]),
    ("PRIZE_6_BRIDGE_OUT", ["PRIZE6BRIDGEOUT"]),
    ("PRIZE_SUM_OUT",      ["PRIZESUMOUT"]),
]


# ──────────────────────────────────────────────────────────────
# 파일 스캔 — parquet 우선
# ──────────────────────────────────────────────────────────────
def _normalize_filename(name):
    stem = os.path.splitext(os.path.basename(name))[0]
    return re.sub(r"[\s_\-]+", "", stem).upper()


def _extract_yyyymmdd(filepath):
    m = re.search(r"(\d{8})", os.path.basename(filepath))
    return m.group(1) if m else "00000000"


def _pick_best_format(candidates):
    """같은 YYYYMMDD 그룹에서 parquet > xlsx 우선순위로 선택."""
    if not candidates:
        return None
    # 최신 날짜 그룹만 추출
    candidates_sorted = sorted(
        candidates,
        key=lambda p: (_extract_yyyymmdd(p), os.path.getmtime(p)),
        reverse=True,
    )
    top_date = _extract_yyyymmdd(candidates_sorted[0])
    top_group = [p for p in candidates_sorted if _extract_yyyymmdd(p) == top_date]
    # parquet 우선
    parquets = [p for p in top_group if p.lower().endswith(".parquet")]
    if parquets:
        return parquets[0]
    return top_group[0]


def find_latest_data_files():
    """각 유형별 최신 파일 1개씩 반환 (parquet 우선, xlsx/xls 폴백)."""
    all_files = (
        glob.glob(os.path.join(DATA_DIR, "*.parquet")) +
        glob.glob(os.path.join(DATA_DIR, "*.xlsx")) +
        glob.glob(os.path.join(DATA_DIR, "*.xls"))
    )
    all_files = [f for f in all_files if not os.path.basename(f).startswith("~$")]

    result = {}
    for key, tokens in FILE_PATTERNS:
        candidates = [
            f for f in all_files
            if all(tok in _normalize_filename(f) for tok in tokens)
        ]
        result[key] = _pick_best_format(candidates)
    return result


# ──────────────────────────────────────────────────────────────
# 엑셀/parquet 로드 + 인코딩 정리
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


def _read_excel_fast(path):
    """xlsx를 가능한 한 빠르게 읽기 — calamine 우선, openpyxl 폴백."""
    try:
        return pd.read_excel(path, engine="calamine")
    except Exception:
        return pd.read_excel(path, engine="openpyxl")


# 파일 경로 + mtime 키로 캐싱 — 새 날짜 파일 push되면 자동 무효화
@_cache_data(show_spinner=False)
def _load_file_clean(path, _mtime):  # _mtime은 캐시 키 변동용
    """parquet/xlsx 자동 판별 + 인코딩 정리 + 캐싱."""
    if path.lower().endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = _read_excel_fast(path)
    df.columns = [_decode_excel_text(c) if isinstance(c, str) else c for c in df.columns]
    for c in df.columns:
        if pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].apply(_decode_excel_text)
    return df


def _load_excel_clean(path):
    """외부에서 호출하는 안정 API. 내부는 캐시된 _load_file_clean 사용."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    return _load_file_clean(path, mtime)


# ──────────────────────────────────────────────────────────────
# merge key 자동 해석
# ──────────────────────────────────────────────────────────────
_MERGE_KEY_FALLBACKS = {
    "대리점설계사조직코드":   ["대리점설계사조직코드", "현재대리점설계사조직코드"],
    "현재대리점설계사조직코드": ["현재대리점설계사조직코드", "대리점설계사조직코드"],
}


def _resolve_merge_key(df, requested_key, file_label):
    if requested_key in df.columns:
        return requested_key
    for cand in _MERGE_KEY_FALLBACKS.get(requested_key, []):
        if cand in df.columns:
            return cand
    for c in df.columns:
        if "대리점설계사조직코드" in c:
            return c
    raise KeyError(
        f"{file_label} 파일에서 merge key '{requested_key}' 또는 대체 후보를 찾지 못했습니다. "
        f"실제 컬럼 일부: {list(df.columns)[:10]}..."
    )


# ──────────────────────────────────────────────────────────────
# 3개 파일 outer merge — 캐시 가능
# ──────────────────────────────────────────────────────────────
@_cache_data(show_spinner="데이터 머지 중...", ttl=3600)
def _merge_three_cached(f1, f2, f3, m1, m2, m3, key1, key2, key3):
    """경로+mtime 기반 캐싱. 같은 파일 조합이면 머지 결과 즉시 반환."""
    df1 = _load_file_clean(f1, m1)
    df2 = _load_file_clean(f2, m2)
    df3 = _load_file_clean(f3, m3)

    k1 = _resolve_merge_key(df1, key1, "MC_LIST_OUT")
    k2 = _resolve_merge_key(df2, key2, "PRIZE_6_BRIDGE_OUT")
    k3 = _resolve_merge_key(df3, key3, "PRIZE_SUM_OUT")

    df1 = df1.copy()
    df2 = df2.copy()
    df3 = df3.copy()

    df1["merge_key1"] = df1[k1].apply(_clean_key)
    df2["merge_key2"] = df2[k2].apply(_clean_key)
    df_merged = pd.merge(
        df1, df2,
        left_on="merge_key1", right_on="merge_key2",
        how="outer", suffixes=("_파일1", "_파일2"),
    )

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


def merge_three_files(f1, f2, f3, key1, key2, key3):
    """캐시 wrapper."""
    def _mt(p):
        try: return os.path.getmtime(p)
        except OSError: return 0
    return _merge_three_cached(f1, f2, f3, _mt(f1), _mt(f2), _mt(f3), key1, key2, key3)


# ──────────────────────────────────────────────────────────────
# 현재 월 / stage 감지
# ──────────────────────────────────────────────────────────────
def detect_current_month(df):
    if "기준년월" in df.columns:
        vals = df["기준년월"].dropna().astype(str)
        months = []
        for v in vals:
            v_clean = v.replace(".", "").replace("-", "").strip()
            if v_clean.endswith(".0"):
                v_clean = v_clean[:-2]
            if len(v_clean) >= 6:
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


MAX_WEEK_SUPPORTED = 6


def detect_stage(df):
    cols = set(df.columns)
    has_monthly_연속 = any(re.match(r"^연속가동실적_\d+월$", c) for c in cols)

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

    max_week_with_value = 0
    for n in range(2, MAX_WEEK_SUPPORTED + 1):
        col = f"실적_{n}주차"
        if col in cols and _has_value(col):
            max_week_with_value = n

    if max_week_with_value >= 2:
        return f"stage_{max_week_with_value}_week{max_week_with_value}"

    if "실적_1주차" in cols or has_monthly_연속:
        return "stage_1_week1_early"
    return "stage_1_week1_early"


def substitute_placeholders(obj, current_month):
    prev_m = current_month - 1 if current_month > 1 else 12
    if isinstance(obj, dict):
        return {k: substitute_placeholders(v, current_month) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_placeholders(v, current_month) for v in obj]
    if isinstance(obj, str):
        return obj.replace("{m-1}", str(prev_m)).replace("{m}", str(current_month))
    return obj


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
