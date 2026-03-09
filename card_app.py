import streamlit as st
from PIL import Image, ImageDraw, ImageFont, ImageOps
import qrcode
import io
import textwrap
import os

# ─────────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="메리츠 프로필 카드 메이커",
    page_icon="🪪",
    layout="wide",
)

# ─────────────────────────────────────────────
# 폰트 경로
# ─────────────────────────────────────────────
FONT_DIR = "/usr/share/fonts/opentype/noto"
FONT_REG   = os.path.join(FONT_DIR, "NotoSansCJK-Regular.ttc")
FONT_BOLD  = os.path.join(FONT_DIR, "NotoSansCJK-Bold.ttc")
FONT_BLACK = os.path.join(FONT_DIR, "NotoSansCJK-Black.ttc")
KR_INDEX = 1  # TTC 내 한국어 인덱스

def font(path, size, index=KR_INDEX):
    return ImageFont.truetype(path, size, index=index)

# ─────────────────────────────────────────────
# 색상 팔레트
# ─────────────────────────────────────────────
RED   = (200, 0,  30)
RED_L = (255, 240, 242)
NAVY  = (26,  35, 126)
WHITE = (255, 255, 255)
GRAY1 = (247, 247, 247)
GRAY2 = (220, 220, 220)
GRAY3 = (170, 170, 170)
GRAY4 = (80,  80,  80)
DARK  = (26,  26,  26)

# ─────────────────────────────────────────────
# 헬퍼: 텍스트 줄바꿈
# ─────────────────────────────────────────────
def wrap_text(draw, text, fnt, max_width):
    """픽셀 너비 기준 자동 줄바꿈"""
    words = list(text)  # 한글은 글자 단위로
    lines, line = [], ""
    for ch in text:
        test = line + ch
        w = draw.textlength(test, font=fnt)
        if w > max_width and line:
            lines.append(line)
            line = ch
        else:
            line = test
    if line:
        lines.append(line)
    return lines

def draw_text_wrapped(draw, text, x, y, fnt, max_width, fill, line_spacing=8):
    lines = wrap_text(draw, text, fnt, max_width)
    cy = y
    for line in lines:
        draw.text((x, cy), line, font=fnt, fill=fill)
        cy += fnt.size + line_spacing
    return cy  # 마지막 y 반환

def draw_rounded_rect(draw, xy, radius, fill, outline=None, outline_width=2):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill,
                           outline=outline, width=outline_width if outline else 0)

# ─────────────────────────────────────────────
# QR 코드 생성
# ─────────────────────────────────────────────
def make_qr(phone, size=120):
    phone_clean = phone.replace("-", "").replace(" ", "")
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(f"tel:{phone_clean}" if phone_clean else "MERITZ")
    qr.make(fit=True)
    img = qr.make_image(fill_color=tuple(NAVY), back_color="white")
    img = img.resize((size, size), Image.LANCZOS)
    return img.convert("RGBA")

# ─────────────────────────────────────────────
# 사진 크롭 (원형 or 모서리 둥글게)
# ─────────────────────────────────────────────
def crop_photo(photo_bytes, w, h, circle=False):
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
    # 비율 유지 크롭
    img_ratio = img.width / img.height
    target_ratio = w / h
    if img_ratio > target_ratio:
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    else:
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))
    img = img.resize((w, h), Image.LANCZOS)
    if circle:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, w, h], fill=255)
        img.putalpha(mask)
    return img

# ─────────────────────────────────────────────
# ─── 카드 렌더러 ───────────────────────────
# ─────────────────────────────────────────────

def render_classic(data):
    """클래식 레드 템플릿"""
    W, H = 900, 1200
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # ── 상단 헤더 배경 ──
    header_h = 340
    d.rectangle([0, 0, W, header_h], fill=RED)
    # 장식 원
    d.ellipse([W-180, -80, W+80, 180], fill=(220, 20, 50, 180))

    # MERITZ 로고
    fnt_logo = font(FONT_BLACK, 48)
    d.text((50, 45), "MERITZ", font=fnt_logo, fill=WHITE)

    # 이름
    fnt_name = font(FONT_BLACK, 80)
    d.text((50, 110), data["name"], font=fnt_name, fill=WHITE)

    # 직책
    fnt_role = font(FONT_BOLD, 32)
    d.text((50, 205), data["title"], font=fnt_role,
           fill=(255, 200, 200))

    # 사진
    photo_x, photo_y = W - 290, 60
    photo_w, photo_h = 230, 275
    if data["photo"]:
        ph = crop_photo(data["photo"], photo_w, photo_h)
        # 모서리 둥글게
        mask = Image.new("L", (photo_w, photo_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, photo_w, photo_h], radius=18, fill=255)
        img.paste(ph, (photo_x, photo_y), mask)
    else:
        d.rounded_rectangle(
            [photo_x, photo_y, photo_x+photo_w, photo_y+photo_h],
            radius=18, fill=(220, 30, 60))
        fnt_icon = font(FONT_BOLD, 80)
        d.text((photo_x + photo_w//2 - 35, photo_y + photo_h//2 - 45),
               "👤", font=fnt_icon, fill=WHITE)

    # ── 슬로건 박스 ──
    q_y = header_h + 30
    q_h = 100
    d.rounded_rectangle([40, q_y, W-40, q_y+q_h], radius=14, fill=RED_L)
    d.rectangle([40, q_y, 55, q_y+q_h], fill=RED)  # 왼쪽 바
    fnt_q = font(FONT_BOLD, 30)
    lines = wrap_text(d, data["tagline"], fnt_q, W - 140)
    qtext = "\n".join(lines[:3])
    d.text((75, q_y + 18), qtext, font=fnt_q, fill=NAVY)

    # ── 업무 박스 ──
    duty_y = q_y + q_h + 28
    duty_lines = data["duties"]
    duty_h = 55 + len(duty_lines) * 52
    d.rounded_rectangle([40, duty_y, W-40, duty_y+duty_h],
                        radius=14, fill=GRAY1)
    fnt_dt = font(FONT_BOLD, 28)
    d.text((70, duty_y + 18), "제 업무는요:", font=fnt_dt, fill=DARK)
    fnt_di = font(FONT_REG, 27)
    cy = duty_y + 60
    for item in duty_lines:
        d.text((72, cy), "✓", font=font(FONT_BLACK, 27), fill=RED)
        d.text((108, cy), item, font=fnt_di, fill=GRAY4)
        cy += 52

    # ── 구분선 ──
    stripe_y = duty_y + duty_h + 28
    d.rectangle([0, stripe_y, W, stripe_y+8], fill=RED)

    # ── 연락처 영역 ──
    contact_y = stripe_y + 28
    qr = make_qr(data["phone"], size=140)
    img.paste(qr, (50, contact_y), qr)

    info_x = 220
    fnt_cn = font(FONT_BLACK, 34)
    d.text((info_x, contact_y), data["name"], font=fnt_cn, fill=DARK)
    fnt_ct = font(FONT_REG, 26)
    d.text((info_x + d.textlength(data["name"], font=fnt_cn) + 14,
            contact_y + 6), data["title"], font=fnt_ct, fill=GRAY3)

    rows = [
        ("📞", data["phone"]),
        ("💛", data["kakao"]),
        ("✉",  data["email"]),
    ]
    cy2 = contact_y + 52
    fnt_row = font(FONT_REG, 26)
    for icon, val in rows:
        if val:
            d.text((info_x, cy2), icon, font=font(FONT_REG, 26), fill=GRAY4)
            d.text((info_x + 40, cy2), val, font=fnt_row, fill=GRAY4)
            cy2 += 42

    # ── 소속 푸터 ──
    d.rectangle([0, H-80, W, H], fill=NAVY)
    fnt_ft = font(FONT_BOLD, 30)
    ft_w = d.textlength(data["branch"], font=fnt_ft)
    d.text(((W - ft_w) // 2, H - 58), data["branch"], font=fnt_ft, fill=WHITE)

    return img


def render_bold(data):
    """볼드 레드 템플릿"""
    W, H = 900, 1200
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    header_h = 360

    # 헤더
    d.rectangle([0, 0, W, header_h], fill=RED)
    # 장식
    d.ellipse([-60, -60, 260, 260], fill=(220, 20, 50))
    d.ellipse([W-200, header_h-140, W+60, header_h+60],
              fill=(180, 0, 20))

    # MERITZ
    fnt_logo = font(FONT_BLACK, 38)
    d.text((50, 42), "MERITZ", font=fnt_logo,
           fill=(255, 255, 255, 160))

    # 사진 (오른쪽, 헤더 하단에 걸침)
    photo_w, photo_h = 220, 280
    photo_x = W - photo_w - 40
    photo_y = header_h - photo_h
    if data["photo"]:
        ph = crop_photo(data["photo"], photo_w, photo_h)
        mask = Image.new("L", (photo_w, photo_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, photo_w, photo_h], radius=18, fill=255)
        img.paste(ph, (photo_x, photo_y), mask)
    else:
        d.rounded_rectangle(
            [photo_x, photo_y, photo_x+photo_w, photo_y+photo_h],
            radius=18, fill=(180, 0, 20))

    # 이름
    fnt_name = font(FONT_BLACK, 90)
    d.text((50, 110), data["name"], font=fnt_name, fill=WHITE)
    fnt_role = font(FONT_BOLD, 30)
    d.text((50, 215), data["title"], font=fnt_role, fill=(255, 180, 180))

    # ── 바디 ──
    body_y = header_h + 30

    # 슬로건
    d.rectangle([50, body_y, 58, body_y + 70], fill=RED)
    fnt_q = font(FONT_BOLD, 30)
    draw_text_wrapped(d, data["tagline"], 78, body_y + 4,
                      fnt_q, W - 130, NAVY)

    # 업무 박스
    duty_y = body_y + 100
    duty_h = 55 + len(data["duties"]) * 52
    d.rounded_rectangle([40, duty_y, W-40, duty_y+duty_h],
                        radius=14, fill=GRAY1)
    fnt_dt = font(FONT_BOLD, 28)
    d.text((70, duty_y + 18), "제 업무는요:", font=fnt_dt, fill=DARK)
    fnt_di = font(FONT_REG, 27)
    cy = duty_y + 60
    for item in data["duties"]:
        d.text((72, cy), "✓", font=font(FONT_BLACK, 27), fill=RED)
        d.text((108, cy), item, font=fnt_di, fill=GRAY4)
        cy += 52

    # 구분선
    sep_y = duty_y + duty_h + 28
    d.rectangle([40, sep_y, W-40, sep_y+1], fill=GRAY2)

    # 연락처
    contact_y = sep_y + 24
    qr = make_qr(data["phone"], size=130)
    img.paste(qr, (50, contact_y), qr)

    info_x = 210
    fnt_cn = font(FONT_BLACK, 32)
    d.text((info_x, contact_y), data["name"], font=fnt_cn, fill=DARK)
    fnt_ct = font(FONT_REG, 24)
    d.text((info_x + d.textlength(data["name"], font=fnt_cn) + 12,
            contact_y + 6), data["title"], font=fnt_ct, fill=GRAY3)
    cy2 = contact_y + 48
    fnt_row = font(FONT_REG, 26)
    for icon, val in [("📞", data["phone"]),
                      ("💛", data["kakao"]),
                      ("✉",  data["email"])]:
        if val:
            d.text((info_x, cy2), icon, font=fnt_row, fill=GRAY4)
            d.text((info_x + 42, cy2), val, font=fnt_row, fill=GRAY4)
            cy2 += 40

    # 푸터
    d.rectangle([0, H-80, W, H], fill=NAVY)
    fnt_ft = font(FONT_BOLD, 30)
    ft_w = d.textlength(data["branch"], font=fnt_ft)
    d.text(((W - ft_w) // 2, H - 58), data["branch"], font=fnt_ft, fill=WHITE)

    return img


def render_elegant(data):
    """엘레강트 네이비 템플릿"""
    W, H = 900, 1200
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    header_h = 360
    d.rectangle([0, 0, W, header_h], fill=NAVY)

    # 장식 삼각형 그라디언트 느낌
    d.polygon([(W//2, 0), (W, 0), (W, header_h)], fill=(200, 0, 30))
    d.ellipse([-80, header_h-100, 160, header_h+140],
              fill=(15, 25, 110))

    # MERITZ
    fnt_logo = font(FONT_BOLD, 34)
    d.text((50, 42), "M E R I T Z", font=fnt_logo,
           fill=(255, 255, 255, 120))

    # 사진
    photo_w, photo_h = 200, 250
    photo_x = W - photo_w - 50
    photo_y = 70
    if data["photo"]:
        ph = crop_photo(data["photo"], photo_w, photo_h)
        mask = Image.new("L", (photo_w, photo_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, photo_w, photo_h], radius=14, fill=255)
        img.paste(ph, (photo_x, photo_y), mask)
        # 테두리
        d.rounded_rectangle(
            [photo_x-2, photo_y-2, photo_x+photo_w+2, photo_y+photo_h+2],
            radius=15, outline=(255, 255, 255, 80), width=2)
    else:
        d.rounded_rectangle(
            [photo_x, photo_y, photo_x+photo_w, photo_y+photo_h],
            radius=14, fill=(35, 50, 150))

    # 이름 (세리프 느낌 - Black 폰트)
    fnt_name = font(FONT_BLACK, 76)
    d.text((50, 110), data["name"], font=fnt_name, fill=WHITE)
    fnt_role = font(FONT_REG, 28)
    d.text((50, 202), data["title"], font=fnt_role,
           fill=(180, 190, 255))

    # 슬로건 인라인
    fnt_qi = font(FONT_REG, 26)
    d.text((52, 248), f""{data['tagline']}"", font=fnt_qi,
           fill=(200, 210, 255))

    # ── 바디 ──
    body_y = header_h + 35

    # 업무 목록
    fnt_dt = font(FONT_BOLD, 26)
    d.text((50, body_y), "주  요  업  무", font=fnt_dt, fill=GRAY3)
    cy = body_y + 45
    fnt_di = font(FONT_REG, 27)
    for item in data["duties"]:
        # 점 불릿
        d.ellipse([52, cy+9, 62, cy+19], fill=RED)
        d.text((80, cy), item, font=fnt_di, fill=GRAY4)
        cy += 52

    # 구분선
    sep_y = cy + 20
    d.rectangle([40, sep_y, W-40, sep_y+1], fill=GRAY2)

    # 연락처
    contact_y = sep_y + 30
    qr = make_qr(data["phone"], size=130)
    img.paste(qr, (50, contact_y), qr)
    info_x = 210
    fnt_cn = font(FONT_BLACK, 32)
    d.text((info_x, contact_y), data["name"], font=fnt_cn, fill=DARK)
    fnt_ct = font(FONT_REG, 24)
    d.text((info_x + d.textlength(data["name"], font=fnt_cn) + 12,
            contact_y + 6), data["title"], font=fnt_ct, fill=GRAY3)
    cy2 = contact_y + 48
    fnt_row = font(FONT_REG, 26)
    for icon, val in [("📞", data["phone"]),
                      ("💛", data["kakao"]),
                      ("✉",  data["email"])]:
        if val:
            d.text((info_x, cy2), icon, font=fnt_row, fill=GRAY4)
            d.text((info_x + 42, cy2), val, font=fnt_row, fill=GRAY4)
            cy2 += 40

    # 푸터
    d.rectangle([0, H-80, W, H], fill=RED)
    fnt_ft = font(FONT_BOLD, 30)
    ft_w = d.textlength(data["branch"], font=fnt_ft)
    d.text(((W - ft_w) // 2, H - 58), data["branch"], font=fnt_ft, fill=WHITE)

    return img


def render_minimal(data):
    """미니멀 템플릿"""
    W, H = 900, 1200
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # 왼쪽 레드 세로 바
    d.rectangle([0, 0, 10, H], fill=RED)

    # MERITZ
    fnt_logo = font(FONT_BLACK, 28)
    d.text((50, 50), "MERITZ", font=fnt_logo, fill=RED)

    # 이름
    fnt_name = font(FONT_BLACK, 88)
    d.text((50, 110), data["name"], font=fnt_name, fill=DARK)

    # 직책
    fnt_role = font(FONT_REG, 30)
    d.text((50, 215), data["title"], font=fnt_role, fill=GRAY3)

    # 사진
    if data["photo"]:
        photo_w, photo_h = 210, 250
        photo_x = W - photo_w - 50
        photo_y = 60
        ph = crop_photo(data["photo"], photo_w, photo_h)
        mask = Image.new("L", (photo_w, photo_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, photo_w, photo_h], radius=14, fill=255)
        img.paste(ph, (photo_x, photo_y), mask)

    # 슬로건
    q_y = 310
    d.rounded_rectangle([40, q_y, W-40, q_y+90], radius=12, fill=GRAY1)
    fnt_q = font(FONT_BOLD, 28)
    draw_text_wrapped(d, data["tagline"], 65, q_y + 22,
                      fnt_q, W - 130, GRAY4)

    # 구분선
    sep1 = q_y + 110
    d.rectangle([40, sep1, W-40, sep1+1], fill=GRAY2)

    # 업무
    duty_y = sep1 + 30
    fnt_dt = font(FONT_BOLD, 24)
    d.text((50, duty_y), "업 무 소 개", font=fnt_dt, fill=RED)
    cy = duty_y + 48
    fnt_di = font(FONT_REG, 27)
    for i, item in enumerate(data["duties"]):
        num = f"{i+1:02d}"
        d.text((50, cy), num, font=font(FONT_BLACK, 26), fill=RED)
        d.text((90, cy), item, font=fnt_di, fill=GRAY4)
        cy += 52

    # 연락처 박스
    box_y = cy + 30
    d.rounded_rectangle([40, box_y, W-40, box_y+180],
                        radius=14, outline=GRAY2, width=2, fill=WHITE)
    qr = make_qr(data["phone"], size=120)
    img.paste(qr, (60, box_y + 30), qr)
    info_x = 210
    fnt_cn = font(FONT_BLACK, 30)
    d.text((info_x, box_y + 28), data["name"], font=fnt_cn, fill=DARK)
    fnt_ct = font(FONT_REG, 22)
    d.text((info_x + d.textlength(data["name"], font=fnt_cn) + 10,
            box_y + 34), data["title"], font=fnt_ct, fill=GRAY3)
    cy2 = box_y + 70
    fnt_row = font(FONT_REG, 24)
    for icon, val in [("📞", data["phone"]),
                      ("💛", data["kakao"]),
                      ("✉",  data["email"])]:
        if val:
            d.text((info_x, cy2), icon, font=fnt_row, fill=GRAY4)
            d.text((info_x + 38, cy2), val, font=fnt_row, fill=GRAY4)
            cy2 += 36

    # 푸터
    d.rectangle([0, H-80, W, H], fill=NAVY)
    fnt_ft = font(FONT_BOLD, 30)
    ft_w = d.textlength(data["branch"], font=fnt_ft)
    d.text(((W - ft_w) // 2, H - 58), data["branch"], font=fnt_ft, fill=WHITE)

    return img


RENDERERS = {
    "🔴 클래식 레드": render_classic,
    "🔥 볼드 레드":   render_bold,
    "💎 엘레강트":    render_elegant,
    "⬜ 미니멀":      render_minimal,
}


def img_to_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(300, 300))
    return buf.getvalue()


# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

.main-title {
    background: #1A237E;
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    display: flex; align-items: center; gap: .75rem;
}
.main-title h1 { font-size: 1.3rem; margin: 0; font-weight: 900; }
.main-title p  { font-size: .8rem; margin: 0; opacity: .7; }

.section-head {
    font-size: .7rem; font-weight: 700;
    letter-spacing: 1.5px; text-transform: uppercase;
    color: #AAA; border-bottom: 1px solid #EEE;
    padding-bottom: .4rem; margin: 1.2rem 0 .75rem;
}
div[data-testid="stDownloadButton"] button {
    width: 100%;
    background: #C8001E !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border: none !important;
    border-radius: 10px !important;
    padding: .8rem !important;
}
div[data-testid="stDownloadButton"] button:hover {
    background: #A0001A !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-title">
  <div>🪪</div>
  <div>
    <h1>메리츠 프로필 카드 메이커</h1>
    <p>GA 설계매니저 명함형 프로필 이미지 생성기</p>
  </div>
</div>
""", unsafe_allow_html=True)

col_form, col_preview = st.columns([1, 1], gap="large")

# ─────────────────────────────────────────────
# 왼쪽: 입력 폼
# ─────────────────────────────────────────────
with col_form:

    st.markdown('<div class="section-head">① 템플릿 선택</div>',
                unsafe_allow_html=True)
    template = st.radio(
        "템플릿", list(RENDERERS.keys()),
        horizontal=True, label_visibility="collapsed"
    )

    st.markdown('<div class="section-head">② 사진 (선택)</div>',
                unsafe_allow_html=True)
    photo_file = st.file_uploader(
        "사진 업로드", type=["jpg", "jpeg", "png"],
        label_visibility="collapsed"
    )
    photo_bytes = photo_file.read() if photo_file else None

    st.markdown('<div class="section-head">③ 기본 정보</div>',
                unsafe_allow_html=True)
    name   = st.text_input("이름",   value="홍길동")
    title  = st.text_input("직책",   value="설계매니저")
    branch = st.text_input("소속 지점", value="메리츠화재 GA3-2지점")

    st.markdown('<div class="section-head">④ 슬로건 / 한마디</div>',
                unsafe_allow_html=True)
    tagline = st.text_area(
        "슬로건", value="팀장님 영업에 도움이 되는 설계매니저 되겠습니다.",
        height=80, label_visibility="collapsed"
    )

    st.markdown('<div class="section-head">⑤ 연락처</div>',
                unsafe_allow_html=True)
    phone = st.text_input("📞 전화번호", value="010-1234-5678")
    kakao = st.text_input("💛 카카오 ID", value="@abcdef")
    email = st.text_input("✉️ 이메일",   value="abcdef@meritz.com")

    st.markdown('<div class="section-head">⑥ 제 업무는요 (최대 5개)</div>',
                unsafe_allow_html=True)

    default_duties = [
        "보험 상품 포인트 정리 및 화법 제공",
        "영업에 바로 활용할 수 있는 가입설계서 지원",
        "보험료 변동 및 신상품 정보 빠르게 전달",
    ]
    duties = []
    for i in range(5):
        default = default_duties[i] if i < len(default_duties) else ""
        val = st.text_input(
            f"업무 {i+1}", value=default,
            placeholder=f"업무 항목 {i+1} (비워두면 표시 안 됨)",
            label_visibility="collapsed" if i > 0 else "visible"
        )
        if val.strip():
            duties.append(val.strip())

# ─────────────────────────────────────────────
# 카드 데이터
# ─────────────────────────────────────────────
card_data = {
    "name":    name   or "이름",
    "title":   title  or "직책",
    "branch":  branch or "소속지점",
    "tagline": tagline or "",
    "phone":   phone,
    "kakao":   kakao,
    "email":   email,
    "duties":  duties or ["업무 내용을 입력해주세요"],
    "photo":   photo_bytes,
}

# ─────────────────────────────────────────────
# 오른쪽: 미리보기 + 다운로드
# ─────────────────────────────────────────────
with col_preview:
    st.markdown('<div class="section-head">실시간 미리보기</div>',
                unsafe_allow_html=True)

    try:
        render_fn = RENDERERS[template]
        card_img = render_fn(card_data)
        st.image(card_img, use_container_width=True)

        png_bytes = img_to_bytes(card_img)
        st.download_button(
            label="⬇️ PNG 이미지로 저장",
            data=png_bytes,
            file_name=f"메리츠_{name}_프로필카드.png",
            mime="image/png",
        )
        st.caption("💡 저장한 이미지를 카카오톡에서 첨부하여 공유하세요")

    except Exception as e:
        st.error(f"카드 생성 오류: {e}")
        import traceback
        st.code(traceback.format_exc())
