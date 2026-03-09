<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>메리츠 프로필 카드 생성기</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<style>
:root {
  --meritz-red: #C8001E;
  --meritz-navy: #1A237E;
  --meritz-pink: #FFE4E8;
  --meritz-light: #FFF5F7;
  --gray-50: #FAFAFA;
  --gray-200: #EEEEEE;
  --gray-500: #9E9E9E;
  --gray-700: #424242;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: 'Noto Sans KR', sans-serif;
  background: #F0F0F5;
  min-height: 100vh;
}

/* ─── HEADER ─── */
.site-header {
  background: var(--meritz-navy);
  color: white;
  padding: 1rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.5rem;
  box-shadow: 0 2px 12px rgba(0,0,0,0.2);
}
.site-header .logo {
  font-size: 1.5rem;
  font-weight: 900;
  color: white;
  letter-spacing: -0.5px;
}
.site-header .logo span { color: #FEE500; }
.site-header p { font-size: 0.85rem; color: rgba(255,255,255,0.7); }

/* ─── LAYOUT ─── */
.main-layout {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 2rem;
  max-width: 1300px;
  margin: 2rem auto;
  padding: 0 2rem;
}

/* ─── FORM PANEL ─── */
.form-panel {
  background: white;
  border-radius: 16px;
  padding: 2rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  height: fit-content;
  position: sticky;
  top: 1rem;
}
.form-panel h2 {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--meritz-navy);
  margin-bottom: 1.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid var(--meritz-red);
}

.form-section {
  margin-bottom: 1.5rem;
}
.form-section h3 {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--gray-500);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 0.75rem;
}

.field-group { margin-bottom: 0.9rem; }
label {
  display: block;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--gray-700);
  margin-bottom: 0.3rem;
}
input[type="text"], input[type="tel"], input[type="email"], textarea, select {
  width: 100%;
  padding: 0.6rem 0.9rem;
  border: 1.5px solid var(--gray-200);
  border-radius: 8px;
  font-family: 'Noto Sans KR', sans-serif;
  font-size: 0.88rem;
  color: var(--gray-700);
  transition: border-color 0.2s;
  background: var(--gray-50);
}
input:focus, textarea:focus {
  outline: none;
  border-color: var(--meritz-red);
  background: white;
}
textarea { resize: vertical; min-height: 70px; line-height: 1.5; }

/* Photo Upload */
.photo-upload-area {
  border: 2px dashed var(--gray-200);
  border-radius: 12px;
  padding: 1.2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--gray-50);
  position: relative;
}
.photo-upload-area:hover { border-color: var(--meritz-red); background: var(--meritz-light); }
.photo-upload-area input[type="file"] {
  position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
}
.photo-preview {
  width: 80px; height: 80px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid var(--meritz-red);
  margin: 0 auto 0.5rem;
  display: none;
}
.photo-icon { font-size: 2rem; margin-bottom: 0.3rem; }
.photo-upload-area p { font-size: 0.8rem; color: var(--gray-500); }

/* Duties */
.duty-list { display: flex; flex-direction: column; gap: 0.4rem; }
.duty-item {
  display: flex; align-items: center; gap: 0.5rem;
}
.duty-item input[type="text"] { flex: 1; }
.duty-item .del-btn {
  width: 28px; height: 28px;
  background: #FFEBEE; color: var(--meritz-red);
  border: none; border-radius: 6px;
  cursor: pointer; font-size: 1rem;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.add-duty-btn {
  margin-top: 0.5rem;
  padding: 0.4rem 0.8rem;
  background: var(--meritz-light);
  color: var(--meritz-red);
  border: 1.5px dashed var(--meritz-red);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 600;
  width: 100%;
  transition: all 0.2s;
}
.add-duty-btn:hover { background: #FFD6DA; }

/* Template selector */
.template-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}
.template-btn {
  padding: 0.6rem;
  border: 2px solid var(--gray-200);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 600;
  text-align: center;
  transition: all 0.2s;
  background: white;
}
.template-btn.active { border-color: var(--meritz-red); background: var(--meritz-light); color: var(--meritz-red); }

/* Action Buttons */
.action-btns {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
.btn-download {
  padding: 0.9rem;
  background: var(--meritz-red);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 1rem;
  font-weight: 700;
  font-family: 'Noto Sans KR', sans-serif;
  cursor: pointer;
  transition: all 0.2s;
  display: flex; align-items: center; justify-content: center; gap: 0.5rem;
}
.btn-download:hover { background: #A0001A; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(200,0,30,0.3); }
.btn-share {
  padding: 0.75rem;
  background: #FEE500;
  color: #1A1A1A;
  border: none;
  border-radius: 10px;
  font-size: 0.9rem;
  font-weight: 700;
  font-family: 'Noto Sans KR', sans-serif;
  cursor: pointer;
  transition: all 0.2s;
  display: flex; align-items: center; justify-content: center; gap: 0.5rem;
}
.btn-share:hover { background: #F0D800; }

/* ─── PREVIEW PANEL ─── */
.preview-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}
.preview-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--gray-500);
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ─── CARD ─── */
#profile-card {
  width: 420px;
  background: white;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 8px 40px rgba(0,0,0,0.15);
  font-family: 'Noto Sans KR', sans-serif;
}

/* Card Header */
.card-header {
  background: white;
  padding: 1.5rem 1.5rem 0;
  position: relative;
}
.card-logo {
  font-size: 1.4rem;
  font-weight: 900;
  color: var(--meritz-navy);
  letter-spacing: -0.5px;
  margin-bottom: 0.8rem;
}
.card-hero {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}
.card-hero-text {
  flex: 1;
}
.card-name {
  font-size: 1.5rem;
  font-weight: 900;
  color: var(--meritz-red);
  line-height: 1.2;
  margin-bottom: 0.25rem;
}
.card-sub-name {
  font-size: 1rem;
  font-weight: 500;
  color: #333;
  margin-bottom: 0.2rem;
}
.card-title {
  font-size: 0.85rem;
  color: var(--gray-500);
  font-weight: 500;
}
.card-photo-wrap {
  width: 110px;
  height: 130px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  background: linear-gradient(135deg, #f0f0f0 0%, #e0e0e0 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-photo-wrap img {
  width: 100%; height: 100%;
  object-fit: cover;
}
.card-photo-placeholder {
  font-size: 2.5rem;
  color: #ccc;
}

/* Tagline */
.card-tagline {
  margin: 1rem 1.5rem;
  background: linear-gradient(135deg, #FFF0F2 0%, #FFE8EC 100%);
  border-radius: 10px;
  padding: 0.9rem 1.1rem;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--meritz-navy);
  line-height: 1.5;
  border-left: 4px solid var(--meritz-red);
}
.card-tagline::before { content: '"'; color: var(--meritz-red); font-size: 1.2rem; }
.card-tagline::after  { content: '"'; color: var(--meritz-red); font-size: 1.2rem; }

/* Duties */
.card-duties {
  margin: 0 1.5rem 1rem;
  background: #FAFAFA;
  border-radius: 10px;
  padding: 1rem 1.1rem;
}
.card-duties-title {
  font-size: 0.85rem;
  font-weight: 700;
  color: #333;
  margin-bottom: 0.7rem;
}
.card-duty-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.82rem;
  color: #555;
  margin-bottom: 0.45rem;
  line-height: 1.4;
}
.card-duty-check {
  color: var(--meritz-red);
  font-weight: 700;
  font-size: 0.9rem;
  flex-shrink: 0;
  margin-top: 1px;
}

/* Divider */
.card-divider {
  height: 6px;
  background: linear-gradient(90deg, var(--meritz-red) 0%, #FF6B6B 50%, #FFB3B3 100%);
}

/* Contact Section */
.card-contact {
  padding: 1.2rem 1.5rem;
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}
.card-qr {
  width: 80px;
  height: 80px;
  flex-shrink: 0;
  border: 2px solid var(--gray-200);
  border-radius: 8px;
  overflow: hidden;
  background: white;
}
.card-qr canvas { width: 80px !important; height: 80px !important; }
.card-qr img { width: 80px !important; height: 80px !important; }
.card-contact-info { flex: 1; }
.card-contact-name {
  font-size: 1rem;
  font-weight: 700;
  color: #222;
  margin-bottom: 0.5rem;
}
.card-contact-name small {
  font-size: 0.75rem;
  color: var(--gray-500);
  font-weight: 400;
  margin-left: 0.4rem;
}
.contact-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.82rem;
  color: #444;
  margin-bottom: 0.3rem;
}
.contact-icon {
  width: 20px; height: 20px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.7rem;
  flex-shrink: 0;
}
.icon-phone { background: #E3F2FD; color: #1565C0; }
.icon-kakao { background: #FEE500; color: #1A1A1A; }
.icon-email { background: #FCE4EC; color: var(--meritz-red); }

/* Branch */
.card-branch {
  background: var(--meritz-navy);
  color: white;
  padding: 0.7rem 1.5rem;
  font-size: 0.82rem;
  font-weight: 500;
  text-align: center;
  letter-spacing: 0.3px;
}

/* Mini photo bottom */
.card-bottom {
  background: linear-gradient(135deg, #FFF5F7 0%, #FFE8EC 100%);
  padding: 1rem 1.5rem;
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}
.card-bottom-photo {
  width: 60px; height: 60px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  border: 3px solid white;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.card-bottom-photo-placeholder {
  width: 60px; height: 60px;
  border-radius: 50%;
  background: white;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  border: 3px solid white;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.card-bottom-duties { flex: 1; }
.card-bottom-duties .card-duties-title { font-size: 0.8rem; margin-bottom: 0.5rem; }
.card-bottom-duties .card-duty-item { font-size: 0.78rem; margin-bottom: 0.3rem; }

/* Bottom footer */
.card-footer {
  background: var(--meritz-red);
  color: white;
  padding: 0.6rem 1.5rem;
  font-size: 0.8rem;
  font-weight: 600;
  text-align: center;
}

/* Template variations */
#profile-card.template-navy .card-logo { color: white; }
#profile-card.template-navy .card-header { background: var(--meritz-navy); }
#profile-card.template-navy .card-name { color: #FFE08A; }
#profile-card.template-navy .card-sub-name, #profile-card.template-navy .card-title { color: rgba(255,255,255,0.8); }

#profile-card.template-minimal .card-bottom { display: none; }
#profile-card.template-minimal .card-header { padding-bottom: 1.5rem; }

/* Loading overlay */
.downloading {
  position: fixed; inset: 0;
  background: rgba(26,35,126,0.85);
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  z-index: 1000; color: white;
  font-size: 1.2rem; font-weight: 700;
  gap: 1rem; display: none;
}
.spinner {
  width: 48px; height: 48px;
  border: 5px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .main-layout { grid-template-columns: 1fr; }
  .form-panel { position: static; }
  #profile-card { width: 100%; max-width: 420px; }
}
</style>
</head>
<body>

<div class="downloading" id="downloadOverlay">
  <div class="spinner"></div>
  <span>이미지 생성 중...</span>
</div>

<header class="site-header">
  <div>
    <div class="logo">MERITZ <span>PROFILE</span></div>
    <p>GA 설계매니저 프로필 카드 생성기</p>
  </div>
</header>

<div class="main-layout">

  <!-- ─── FORM PANEL ─── -->
  <div class="form-panel">
    <h2>📝 정보 입력</h2>

    <!-- 템플릿 선택 -->
    <div class="form-section">
      <h3>디자인 선택</h3>
      <div class="template-grid">
        <button class="template-btn active" onclick="setTemplate('default', this)">🔴 메리츠 레드</button>
        <button class="template-btn" onclick="setTemplate('navy', this)">🔵 네이비 다크</button>
        <button class="template-btn" onclick="setTemplate('minimal', this)">⬜ 심플</button>
      </div>
    </div>

    <!-- 사진 -->
    <div class="form-section">
      <h3>프로필 사진 (선택)</h3>
      <div class="photo-upload-area" id="uploadArea">
        <input type="file" id="photoInput" accept="image/*" onchange="handlePhoto(this)">
        <img class="photo-preview" id="photoPreview" src="" alt="미리보기">
        <div id="photoPlaceholder">
          <div class="photo-icon">📷</div>
          <p>사진을 클릭하여 업로드<br><small>JPG, PNG · 업로드 안 해도 됩니다</small></p>
        </div>
      </div>
      <button onclick="removePhoto()" id="removePhotoBtn" style="display:none;margin-top:0.4rem;width:100%;padding:0.4rem;background:#FFF;border:1px solid #ccc;border-radius:6px;cursor:pointer;font-size:0.8rem;color:#999">사진 제거</button>
    </div>

    <!-- 기본 정보 -->
    <div class="form-section">
      <h3>기본 정보</h3>
      <div class="field-group">
        <label>이름</label>
        <input type="text" id="f_name" value="김은영" oninput="updateCard()" placeholder="이름 입력">
      </div>
      <div class="field-group">
        <label>직책</label>
        <input type="text" id="f_title" value="GA 설계매니저 (SM)" oninput="updateCard()" placeholder="예: GA 설계매니저">
      </div>
      <div class="field-group">
        <label>소속 지점</label>
        <input type="text" id="f_branch" value="메리츠화재 호남GA본부 12지점" oninput="updateCard()" placeholder="예: 메리츠화재 서울GA본부">
      </div>
    </div>

    <!-- 한마디 -->
    <div class="form-section">
      <h3>슬로건 / 한마디</h3>
      <div class="field-group">
        <textarea id="f_tagline" oninput="updateCard()" placeholder="예: 팀장님 영업에 도움이 되는 설계매니저 되겠습니다.">팀장님 영업에 도움이 되는 설계매니저 되겠습니다.</textarea>
      </div>
    </div>

    <!-- 연락처 -->
    <div class="form-section">
      <h3>연락처</h3>
      <div class="field-group">
        <label>📞 전화번호</label>
        <input type="tel" id="f_phone" value="010-1234-5678" oninput="updateCard(); updateQR()" placeholder="010-0000-0000">
      </div>
      <div class="field-group">
        <label>💛 카카오 ID</label>
        <input type="text" id="f_kakao" value="@kykim" oninput="updateCard()" placeholder="@아이디">
      </div>
      <div class="field-group">
        <label>✉️ 이메일</label>
        <input type="email" id="f_email" value="kykim@meritz.com" oninput="updateCard()" placeholder="이메일 주소">
      </div>
    </div>

    <!-- 업무 소개 -->
    <div class="form-section">
      <h3>제 업무는요 <small style="font-weight:400;text-transform:none;font-size:0.75rem;color:#aaa">(최대 5개)</small></h3>
      <div class="duty-list" id="dutyList"></div>
      <button class="add-duty-btn" onclick="addDuty()">+ 항목 추가</button>
    </div>

    <!-- 다운로드 -->
    <div class="action-btns">
      <button class="btn-download" onclick="downloadCard()">
        ⬇️ 이미지로 저장 (PNG)
      </button>
      <button class="btn-share" onclick="shareCard()">
        💬 카카오톡으로 공유
      </button>
    </div>
  </div>

  <!-- ─── PREVIEW PANEL ─── -->
  <div class="preview-panel">
    <p class="preview-label">실시간 미리보기</p>

    <!-- THE CARD -->
    <div id="profile-card">

      <div class="card-header">
        <div class="card-logo">MERITZ</div>
        <div class="card-hero">
          <div class="card-hero-text">
            <div class="card-name" id="c_name">김은영</div>
            <div class="card-sub-name" id="c_subname">메리츠 김은영</div>
            <div class="card-title" id="c_title">GA 설계매니저</div>
          </div>
          <div class="card-photo-wrap" id="c_photoWrap">
            <div class="card-photo-placeholder">👤</div>
          </div>
        </div>
      </div>

      <div class="card-tagline" id="c_tagline">
        팀장님 영업에 도움이 되는 설계매니저 되겠습니다.
      </div>

      <div class="card-duties">
        <div class="card-duties-title">제 업무는요:</div>
        <div id="c_duties"></div>
      </div>

      <div class="card-divider"></div>

      <div class="card-contact">
        <div class="card-qr" id="qrContainer"></div>
        <div class="card-contact-info">
          <div class="card-contact-name" id="c_contactName">
            김은영 <small>GA설계매니저 (SM)</small>
          </div>
          <div class="contact-row">
            <div class="contact-icon icon-phone">📞</div>
            <span id="c_phone">010-1234-5678</span>
          </div>
          <div class="contact-row">
            <div class="contact-icon icon-kakao">💛</div>
            <span id="c_kakao">@kykim</span>
          </div>
          <div class="contact-row">
            <div class="contact-icon icon-email">✉️</div>
            <span id="c_email"><a href="/cdn-cgi/l/email-protection" class="__cf_email__" data-cfemail="2f44564446426f424a5d465b55014c4042">[email&#160;protected]</a></span>
          </div>
        </div>
      </div>

      <div class="card-branch" id="c_branch">메리츠화재 호남GA본부 12지점</div>

      <div class="card-bottom" id="c_bottomSection">
        <div id="c_bottomPhoto">
          <div class="card-bottom-photo-placeholder">👤</div>
        </div>
        <div class="card-bottom-duties">
          <div class="card-duties-title">제 업무는요:</div>
          <div id="c_bottomDuties"></div>
        </div>
      </div>

      <div class="card-footer" id="c_footer">메리츠화재 호남GA본부 12지점</div>

    </div>
    <!-- END CARD -->

    <p style="font-size:0.78rem;color:#aaa;text-align:center;max-width:420px">
      💡 정보를 입력하면 카드가 실시간으로 업데이트됩니다<br>
      다운로드 버튼을 눌러 PNG 이미지로 저장하세요
    </p>
  </div>

</div>

<script data-cfasync="false" src="/cdn-cgi/scripts/5c5dd728/cloudflare-static/email-decode.min.js"></script><script>
// ─── Default duties ───
const defaultDuties = [
  "보험 상품 포인토 정리 및 비교자료 제공",
  "영업에 바로 활용할 수 있는 멘토 지원",
  "보험로 번등 및 신상품 빠르게 전달"
];

let photoDataURL = null;
let qrInstance = null;
let currentTemplate = 'default';

// ─── Init ───
window.addEventListener('DOMContentLoaded', () => {
  defaultDuties.forEach(d => addDuty(d));
  updateCard();
  updateQR();
});

// ─── Photo handling ───
function handlePhoto(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    photoDataURL = e.target.result;
    document.getElementById('photoPreview').src = photoDataURL;
    document.getElementById('photoPreview').style.display = 'block';
    document.getElementById('photoPlaceholder').style.display = 'none';
    document.getElementById('removePhotoBtn').style.display = 'block';
    updateCard();
  };
  reader.readAsDataURL(file);
}

function removePhoto() {
  photoDataURL = null;
  document.getElementById('photoPreview').style.display = 'none';
  document.getElementById('photoPlaceholder').style.display = 'block';
  document.getElementById('removePhotoBtn').style.display = 'none';
  document.getElementById('photoInput').value = '';
  updateCard();
}

// ─── Duty management ───
function addDuty(text = '') {
  const list = document.getElementById('dutyList');
  if (list.children.length >= 5) return;
  const div = document.createElement('div');
  div.className = 'duty-item';
  div.innerHTML = `
    <input type="text" value="${text}" placeholder="업무 내용 입력" oninput="updateCard()">
    <button class="del-btn" onclick="this.parentElement.remove(); updateCard()">✕</button>
  `;
  list.appendChild(div);
  updateCard();
}

function getDuties() {
  return Array.from(document.querySelectorAll('.duty-item input'))
    .map(i => i.value.trim())
    .filter(Boolean);
}

// ─── Template ───
function setTemplate(tpl, btn) {
  currentTemplate = tpl;
  document.querySelectorAll('.template-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const card = document.getElementById('profile-card');
  card.className = tpl === 'default' ? '' : `template-${tpl}`;
}

// ─── QR Code ───
function updateQR() {
  const phone = document.getElementById('f_phone').value || '010-0000-0000';
  const container = document.getElementById('qrContainer');
  container.innerHTML = '';
  try {
    new QRCode(container, {
      text: `tel:${phone.replace(/-/g,'')}`,
      width: 80, height: 80,
      colorDark: '#1A237E', colorLight: '#ffffff',
      correctLevel: QRCode.CorrectLevel.M
    });
  } catch(e) {}
}

// ─── Update card ───
function updateCard() {
  const name   = document.getElementById('f_name').value   || '이름';
  const title  = document.getElementById('f_title').value  || '직책';
  const branch = document.getElementById('f_branch').value || '소속지점';
  const tagline= document.getElementById('f_tagline').value|| '';
  const phone  = document.getElementById('f_phone').value  || '';
  const kakao  = document.getElementById('f_kakao').value  || '';
  const email  = document.getElementById('f_email').value  || '';
  const duties = getDuties();

  // Text fields
  document.getElementById('c_name').textContent    = name;
  document.getElementById('c_subname').textContent = `메리츠 ${name}`;
  document.getElementById('c_title').textContent   = title;
  document.getElementById('c_tagline').textContent = tagline;
  document.getElementById('c_phone').textContent   = phone;
  document.getElementById('c_kakao').textContent   = kakao;
  document.getElementById('c_email').textContent   = email;
  document.getElementById('c_branch').textContent  = branch;
  document.getElementById('c_footer').textContent  = branch;
  document.getElementById('c_contactName').innerHTML = `${name} <small>${title}</small>`;

  // Photo
  const photoWrap = document.getElementById('c_photoWrap');
  photoWrap.innerHTML = photoDataURL
    ? `<img src="${photoDataURL}" alt="프로필">`
    : `<div class="card-photo-placeholder">👤</div>`;

  const bottomPhoto = document.getElementById('c_bottomPhoto');
  bottomPhoto.innerHTML = photoDataURL
    ? `<img class="card-bottom-photo" src="${photoDataURL}" alt="프로필">`
    : `<div class="card-bottom-photo-placeholder">👤</div>`;

  // Duties
  const dutyHTML = duties.map(d =>
    `<div class="card-duty-item"><span class="card-duty-check">✓</span><span>${d}</span></div>`
  ).join('');
  document.getElementById('c_duties').innerHTML = dutyHTML;
  document.getElementById('c_bottomDuties').innerHTML = dutyHTML;
}

// ─── Download ───
async function downloadCard() {
  const overlay = document.getElementById('downloadOverlay');
  overlay.style.display = 'flex';

  // Wait for fonts/images
  await new Promise(r => setTimeout(r, 300));

  const card = document.getElementById('profile-card');
  try {
    const canvas = await html2canvas(card, {
      scale: 3,
      useCORS: true,
      allowTaint: true,
      backgroundColor: '#ffffff',
      logging: false,
    });
    const link = document.createElement('a');
    const name = document.getElementById('f_name').value || '프로필';
    link.download = `메리츠_${name}_프로필카드.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  } catch(e) {
    alert('이미지 생성 중 오류가 발생했습니다. 다시 시도해주세요.');
    console.error(e);
  }
  overlay.style.display = 'none';
}

// ─── Share (Web Share API or fallback) ───
async function shareCard() {
  const overlay = document.getElementById('downloadOverlay');
  overlay.style.display = 'flex';
  await new Promise(r => setTimeout(r, 300));

  const card = document.getElementById('profile-card');
  try {
    const canvas = await html2canvas(card, { scale: 2, useCORS: true, backgroundColor: '#fff' });
    canvas.toBlob(async (blob) => {
      overlay.style.display = 'none';
      if (navigator.share && navigator.canShare) {
        const file = new File([blob], '프로필카드.png', { type: 'image/png' });
        try {
          await navigator.share({ files: [file], title: '메리츠 프로필 카드' });
        } catch(e) {
          fallbackSave(canvas);
        }
      } else {
        fallbackSave(canvas);
      }
    });
  } catch(e) {
    overlay.style.display = 'none';
    alert('공유 중 오류가 발생했습니다.');
  }
}

function fallbackSave(canvas) {
  const link = document.createElement('a');
  link.downlo
