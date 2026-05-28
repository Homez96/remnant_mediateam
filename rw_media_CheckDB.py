import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import requests

# ── 0. 외부 스토리지(ImgBB 또는 Freeimage) 설정 ──────────────────────
API_KEY = "6f1ec1ad61b9dc8ff1f25abda8fe4096"
UPLOAD_URL = "https://api.imgbb.com/1/upload"

def upload_image_to_storage(file_buffer):
    if not API_KEY or "여기에" in API_KEY:
        st.error("❌ 이미지 API Key 설정이 필요합니다. 코드를 확인해 주세요.")
        return None
    try:
        payload = {"key": API_KEY, "action": "upload"}
        files = {"image": (file_buffer.name, file_buffer.getvalue())}
        response = requests.post(UPLOAD_URL, data=payload, files=files, timeout=20)
        res_data = response.json()
        if response.status_code == 200:
            return res_data["data"]["url"]
        else:
            return None
    except Exception:
        return None

# ── 1. 페이지 기본 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="RW 미디어팀 통합 관리",
    page_icon="⛪",
    layout="centered",
)

# ── 2. 세션 상태 및 데이터 초기화 ────────────────────────────────────
if "members_db" not in st.session_state:
    st.session_state.members_db = pd.DataFrame(columns=["id", "name", "position"])
if "attend_db" not in st.session_state:
    st.session_state.attend_db = pd.DataFrame(columns=["date", "id", "status", "reason", "meal"])
if "cat_db" not in st.session_state:
    st.session_state.cat_db = pd.DataFrame(columns=["id", "name"])
if "post_db" not in st.session_state:
    st.session_state.post_db = pd.DataFrame(columns=["id", "category_id", "title", "content", "links", "image_urls", "created_at"])
if "comm_db" not in st.session_state:
    st.session_state.comm_db = pd.DataFrame(columns=["id", "post_id", "author", "content", "created_at"])
if "current_filter" not in st.session_state:
    st.session_state.current_filter = "전체"
if "selected_date_val" not in st.session_state:
    st.session_state.selected_date_val = date.today()
if "force_refresh" not in st.session_state:
    st.session_state.force_refresh = False

MENU_OPTIONS = ["🏠 홈 (대시보드)", "⛪ 예배 출석 관리", "🏛️ 팀 커뮤니티 게시판"]
if "page" not in st.session_state:
    st.session_state.page = "🏠 홈 (대시보드)"

if "att_loaded" not in st.session_state:
    st.session_state.att_loaded = False
if "board_loaded" not in st.session_state:
    st.session_state.board_loaded = False

# ── 3. 구글 시트 데이터 로드 함수 ──────────────────────────────────
clean_url = "https://docs.google.com/spreadsheets/d/1584S2jzLNFlSJHAgNOBo_w6HjwMwlJ7pUei4jVqeJrU"

# [버그 수정] ID 값들의 소수점(.0) 변환 현상을 원천 차단하는 정제 함수
def clean_id_string(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.endswith(".0"): s = s[:-2]
    return s

def clean_df(df, type_dict):
    if df is None or df.empty: return pd.DataFrame(columns=type_dict.keys())
    # 먼저 모든 컬럼명을 소문자/공백 제거하여 동기화 유도
    df.columns = [c.strip() for c in df.columns]
    
    for col, dtype in type_dict.items():
        if col in df.columns:
            if col in ["id", "post_id", "category_id"]:
                df[col] = df[col].apply(clean_id_string)
            elif dtype == "str": 
                df[col] = df[col].astype(str).replace("nan", "").replace("None", "").str.strip()
            elif dtype == "bool": 
                df[col] = df[col].apply(lambda x: True if str(x).lower() in ['true','1','1.0'] else False)
    return df

try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    ttl_value = 0 if st.session_state.force_refresh else 600

    def load_attendance_data():
        with st.spinner("⏳ 구글 시트에서 출석 데이터를 불러오는 중..."):
            try:
                df_m = conn.read(spreadsheet=clean_url, worksheet="members", ttl=ttl_value)
                df_a = conn.read(spreadsheet=clean_url, worksheet="attendance", ttl=ttl_value)
                st.session_state.members_db = clean_df(df_m, {"id":"str", "name":"str", "position":"str"}).sort_values("name").reset_index(drop=True)
                st.session_state.attend_db = clean_df(df_a, {"date":"str", "id":"str", "status":"str", "meal":"bool", "reason":"str"})
                st.session_state.att_loaded = True
            except Exception as e:
                if "429" in str(e): st.error("🛑 구글 제한이 걸렸습니다. 잠시 후 다시 시도해 주세요.")
                else: st.error(f"출석 로드 실패: {e}")

    def load_community_data():
        with st.spinner("⏳ 구글 시트에서 게시판 데이터를 불러오는 중..."):
            try:
                df_m = conn.read(spreadsheet=clean_url, worksheet="members", ttl=ttl_value)
                df_c = conn.read(spreadsheet=clean_url, worksheet="categories", ttl=ttl_value)
                df_p = conn.read(spreadsheet=clean_url, worksheet="posts", ttl=ttl_value)
                df_cm = conn.read(spreadsheet=clean_url, worksheet="comments", ttl=ttl_value)
                
                st.session_state.members_db = clean_df(df_m, {"id":"str", "name":"str", "position":"str"}).sort_values("name").reset_index(drop=True)
                st.session_state.cat_db = clean_df(df_c, {"id":"str", "name":"str"})
                st.session_state.post_db = clean_df(df_p, {"id":"str", "category_id":"str", "title":"str", "content":"str", "links":"str", "image_urls":"str", "created_at":"str"})
                st.session_state.comm_db = clean_df(df_cm, {"id":"str", "post_id":"str", "author":"str", "content":"str", "created_at":"str"})
                st.session_state.board_loaded = True
            except Exception as e:
                if "429" in str(e): st.error("🛑 구글 제한이 걸렸습니다. 잠시 후 다시 시도해 주세요.")
                else: st.error(f"게시판 로드 실패: {e}")

    if st.session_state.force_refresh:
        st.session_state.force_refresh = False

except Exception as e:
    st.error(f"연결 오류: {e}")

# ── 4. 사이드바 메뉴 ────────────────────────────────────────────────
with st.sidebar:
    st.title("⛪ RW Media")
    
    default_idx = MENU_OPTIONS.index(st.session_state.page) if st.session_state.page in MENU_OPTIONS else 0
    selected_menu = st.radio("메뉴 이동", MENU_OPTIONS, index=default_idx)
    
    if selected_menu != st.session_state.page:
        st.session_state.page = selected_menu
        st.rerun()
        
    st.write("---")
    if st.button("🔄 앱 전체 강제 새로고침"):
        st.session_state.force_refresh = True
        st.session_state.att_loaded = False
        st.session_state.board_loaded = False
        st.rerun()

# ── 5. [페이지 0] 🏠 홈 (대시보드 화면) ──────────────────────────────
if st.session_state.page == "🏠 홈 (대시보드)":
    st.title("🏠 RW 미디어팀 시스템")
    st.markdown("---")
    st.subheader("👋 반갑습니다!")
    st.info("원하시는 작업을 선택한 후 이동하여 데이터를 불러와 주세요!")
    st.write("")
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 📋 출석부 기록/수정")
        st.write("미디어팀원들의 예배 출석 상태 및 포지션 배정, 식사 여부를 관리합니다.")
        if st.button("🚀 예배 출석 관리 바로가기", use_container_width=True, type="primary"):
            st.session_state.page = "⛪ 예배 출석 관리"
            st.rerun()
            
    with c2:
        st.markdown("### 🏛️ 팀 커뮤니티 게시판")
        st.write("공지사항 공유, 카테고리별 게시글 작성 및 댓글 소통 공간입니다.")
        if st.button("🚀 팀 커뮤니티 게시판 바로가기", use_container_width=True, type="primary"):
            st.session_state.page = "🏛️ 팀 커뮤니티 게시판"
            st.rerun()

# ── 6. [페이지 1] 예배 출석 관리 ────────────────────────────────────
elif st.session_state.page == "⛪ 예배 출석 관리":
    st.header("⛪ 예배 출석 관리")
    
    if not st.session_state.att_loaded:
        st.warning("⚠️ 현재 구글 시트에서 출석 데이터를 가져오기 전입니다.")
        if st.button("🔄 출석 데이터 불러오기 (API 호출)", type="primary", use_container_width=True):
            load_attendance_data()
            st.rerun()
    else:
        POSITIONS = ["선택 안 함", "4번 카메라", "5번 카메라", "6번 카메라", "7번 카메라", "PD", "TD",
                     "노출", "자막", "LED", "조명", "사진 촬영", "릴스", "FD", "음향"]
        
        selected_date = st.date_input("📅 날짜 선택", st.session_state.selected_date_val)
        date_key = str(selected_date)
        
        if "last_date" not in st.session_state or st.session_state.last_date != date_key:
            st.session_state.last_date = date_key
            st.session_state.selected_date_val = selected_date
            st.session_state.current_filter = "전체"

        tab_att, tab_mem = st.tabs(["📋 출석 체크", "👥 예배자 관리"])
        
        with tab_att:
            m_df = st.session_state.members_db.copy()
            a_df = st.session_state.attend_db.copy()
            
            if m_df.empty:
                st.info("등록된 예배자가 없습니다. 예배자를 등록하거나 다시 불러와보세요.")
            else:
                curr_a = a_df[a_df["date"] == date_key] if not a_df.empty else pd.DataFrame()
                if not curr_a.empty:
                    merged = pd.merge(m_df, curr_a, on="id", how="left")
                else:
                    merged = m_df.copy()
                    merged["status"] = None
                    merged["meal"] = None
                    merged["reason"] = None
                    
                merged["status"] = merged["status"].fillna("미체크")
                merged["meal"] = merged["meal"].fillna(False)
                merged["reason"] = merged["reason"].fillna("")
                
                p_c, l_c, a_c, m_c = (merged["status"]=="출석").sum(), (merged["status"]=="지각").sum(), (merged["status"]=="결석").sum(), merged["meal"].sum()
                u_c = len(m_df) - (p_c + l_c + a_c)
                
                cols = st.columns(5)
                f_s = st.session_state.current_filter
                def m_btn(col, lab, count, key, val):
                    pre = "🟢 " if f_s == val else ""
                    if col.button(f"{pre}{lab}\n({count}명)", key=key):
                        st.session_state.current_filter = "전체" if f_s == val else val
                        st.rerun()
                
                m_btn(cols[0], "출석", p_c, "b_p", "출석")
                m_btn(cols[1], "지각", l_c, "b_l", "지각")
                m_btn(cols[2], "결석", a_c, "b_
