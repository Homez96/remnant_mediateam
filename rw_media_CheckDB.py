import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import requests

# ── 0. 외부 스토리지(ImgBB) 설정 ─────────────────────────────────────
def get_api_key():
    try: return st.secrets["imgbb"]["api_key"]
    except Exception: return ""

UPLOAD_URL = "https://api.imgbb.com/1/upload"

def upload_image_to_storage(file_buffer):
    api_key = get_api_key()
    if not api_key: return None
    try:
        payload = {"key": api_key, "action": "upload"}
        files = {"image": (file_buffer.name, file_buffer.getvalue())}
        response = requests.post(UPLOAD_URL, data=payload, files=files, timeout=20)
        if response.status_code == 200: return response.json()["data"]["url"]
        return None
    except Exception: return None

# ── 1. 페이지 기본 설정 ──────────────────────────────────────────────
st.set_page_config(page_title="RW 미디어팀 통합 관리", page_icon="⛪", layout="centered")

# ── 2. 세션 상태 초기화 ──────────────────────────────────────────────
if "members_db" not in st.session_state: st.session_state.members_db = pd.DataFrame(columns=["id", "name", "position"])
if "attend_db" not in st.session_state: st.session_state.attend_db = pd.DataFrame(columns=["date", "id", "status", "reason", "meal"])
if "cat_db" not in st.session_state: st.session_state.cat_db = pd.DataFrame(columns=["id", "name"])
if "post_db" not in st.session_state: st.session_state.post_db = pd.DataFrame(columns=["id", "category_id", "title", "content", "links", "image_urls", "created_at"])
if "comm_db" not in st.session_state: st.session_state.comm_db = pd.DataFrame(columns=["id", "post_id", "author", "content", "created_at"])
if "page" not in st.session_state: st.session_state.page = "🏠 홈 (대시보드)"
if "force_refresh" not in st.session_state: st.session_state.force_refresh = False

# ── 3. 구글 시트 연결 및 로드 ─────────────────────────────────────────
clean_url = "https://docs.google.com/spreadsheets/d/1584S2jzLNFlSJHAgNOBo_w6HjwMwlJ7pUei4jVqeJrU"
def clean_id_string(val):
    s = str(val).strip()
    return s[:-2] if s.endswith(".0") else s

def clean_df(df, type_dict):
    if df is None or df.empty: return pd.DataFrame(columns=type_dict.keys())
    df.columns = [c.strip() for c in df.columns]
    return df # 간단하게 처리

try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
except: conn = None

def get_ttl(): return 1 if st.session_state.force_refresh else 600

# [생략된 로드 함수들 (이전 코드와 동일하게 유지하세요)]
# ... load_members(), load_attendance_data(), load_community_data() 함수를 여기에 두세요 ...

# ── 4. 사이드바 및 메인 로직 ─────────────────────────────────────────
# ... (사이드바 및 홈, 출석 관리 페이지 로직 동일) ...

# ── 7. [페이지 2] 팀 커뮤니티 게시판 ────────────────────────────────
elif st.session_state.page == "🏛️ 팀 커뮤니티 게시판":
    st.header("🏛️ 팀 커뮤니티 게시판")
    if not st.session_state.get("board_loaded", False):
        if st.button("🔄 데이터 불러오기"): load_community_data(); st.rerun()
    else:
        b_tab_view, b_tab_write, b_tab_admin = st.tabs(["📖 게시글 보기", "📝 글쓰기", "⚙️ 카테고리 관리"])
        
        # 7-3. 게시글 보기 (수정된 섹션)
        with b_tab_view:
            full_p_db = st.session_state.post_db.copy()
            if "view_post_id" not in st.session_state: st.session_state.view_post_id = None

            if st.session_state.view_post_id:
                if st.button("⬅️ 목록으로 돌아가기"): st.session_state.view_post_id = None; st.rerun()
                
                post = full_p_db[full_p_db["id"] == st.session_state.view_post_id].iloc[0]
                st.title(post['title'])
                st.write(post['content'])
                
                # --- 댓글 영역 ---
                st.write("---")
                st.markdown("**💬 댓글**")
                # 여기에 댓글 작성/조회 로직 추가
                
            else:
                # 리스트 모드
                st.subheader("📋 게시글 목록")
                for _, post in full_p_db[::-1].iterrows():
                    if st.button(f"📄 {post['title']}", key=f"p_{post['id']}"):
                        st.session_state.view_post_id = post['id']; st.rerun()

        # 7-2, 7-1 로직 유지...
