import streamlit as st
import pandas as pd
from datetime import date
import time

# ── 1. 페이지 기본 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="예배 출석 관리",
    page_icon="⛪",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ── 2. 데이터베이스(구글 시트) 연결 및 세션 초기화 ───────────────────
if "members_db" not in st.session_state:
    st.session_state.members_db = pd.DataFrame(columns=["id", "name", "position"])
if "attend_db" not in st.session_state:
    st.session_state.attend_db = pd.DataFrame(columns=["date", "id", "status", "reason", "meal"])
if "current_filter" not in st.session_state:
    st.session_state.current_filter = "전체"

try:
    from streamlit_gsheets import GSheetsConnection
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    clean_url = "https://docs.google.com/spreadsheets/d/1584S2jzLNFlSJHAgNOBo_w6HjwMwlJ7pUei4jVqeJrU"
    
    sheets_members = conn.read(spreadsheet=clean_url, worksheet="members", ttl=0)
    sheets_attend = conn.read(spreadsheet=clean_url, worksheet="attendance", ttl=0)
    
    if sheets_members is not None and not sheets_members.empty:
        sheets_members["id"] = sheets_members["id"].astype(str)
        st.session_state.members_db = sheets_members
    if sheets_attend is not None and not sheets_attend.empty:
        sheets_attend["id"] = sheets_attend["id"].astype(str)
        st.session_state.attend_db = sheets_attend

except Exception as e:
    st.error(f"❌ 구글 시트 연결 실패 원인: {str(e)}")
    if len(st.session_state.members_db) == 0:
        st.session_state.members_db = pd.DataFrame([
            {"id": "1", "name": "홍길동", "position": "PD"},
            {"id": "2", "name": "김철수", "position": "4번 카메라"},
            {"id": "3", "name": "이영희", "position": "자막"},
        ])

# ── 3. 공통 변수 및 디자인 (CSS 속성 주입 방식 변경) ─────────────────
POSITIONS = ["선택 안 함", "4번 카메라", "5번 카메라", "6번 카메라", "7번 카메라", "PD", "TD",
             "노출", "자막", "LED", "조명", "사진 촬영", "릴스", "FD", "음향"]

# ✨ class_name 에러를 우회하기 위해 마크다운 전용 묵시적 스타일 시트 적용
st.markdown("""
    <style>
    .main-title { font-size:28px; font-weight:bold; color:#5038B0; text-align:center; margin-bottom:5px; }
    .sub-title { font-size:14px; color:#666666; text-align:center; margin-bottom:20px; }
    .filter-box { background-color: #F1F3FA; padding: 12px; border-radius: 10px; margin-top: 10px; border-left: 5px solid #5038B0; font-size: 14px; }
    
    /* 🎨 기본 상단 대시보드 버튼 스타일 공통 적용 */
    div[data-testid="stHorizontalBlock"] div.stButton > button {
        width: 100% !important;
        background-color: #ffffff;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 5px !important;
        text-align: center;
        white-space: pre-line; /* \n 줄바꿈이 정상 작동하도록 설정 */
        font-weight: normal;
        color: #333333;
        transition: all 0.2s ease;
    }
    
    div[data-testid="stHorizontalBlock"] div.stButton > button:hover {
        border-color: #5038B0 !important;
        background-color: #F8FAFC;
        color: #5038B0;
    }

    /* 🎯 팁: 하이라이트된 버튼을 가리키는 특수 가상 데이터 어트리뷰트 제어 수식 (Streamlit용 예외 처리) */
    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="🟢"],
    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="🟡"],
    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="🔴"],
    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="🔵"],
    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="⚪"] {
        background-color: #5038B0 !important;
        color: white !important;
        border-color: #5038B0 !important;
        font-weight: bold !important;
        box-shadow: 0px 4px 8px rgba(80, 56, 176, 0.25);
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⛪ 예배 출석 관리</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">모바일과 PC 어디서나 실시간으로 출석을 기록하세요.</div>', unsafe_allow_html=True)

# ── 4. 메인 기능 레이아웃 ───────────────────────────────────────────
selected_date = st.date_input("📅 예배 날짜 선택", date.today())
date_key = str(selected_date)

tab_attend, tab_members = st.tabs(["📋 출석 체크", "👥 예배자 관리"])

if "last_date" not in st.session_state or st.session_state.last_date != date_key:
    st.session_state.last_date = date_key
    st.session_state.current_filter = "전체"

# ==========================================
#  TAB 1: 출석 체크
# ==========================================
with tab_attend:
    members_df = st.session_state.members_db.copy()
    attend_df = st.session_state.attend_db.copy()
    
    if members_df.empty:
        st.info("먼저 [예배자 관리] 탭에서 예배자를 추가해 주세요.")
    else:
        if "date" in attend_df.columns and not attend_df.empty:
            current_attend = attend_df[attend_df["date"] == date_key]
        else:
            current_attend = pd.DataFrame(columns=["date", "id", "status", "reason", "meal"])
        
        merged = pd.merge(members_df, current_attend, on="id", how="left")
        
        merged["status"] = merged["status"].fillna("미체크").astype(str)
        merged["reason"] = merged["reason"].fillna("").astype(str)
        merged["meal"] = merged["meal"].apply(lambda x: True if x is True or str(x).lower() == 'true' or x == 1 else False)
        
        total_count = len(members_df)
        p_count = int((merged["status"] == "출석").sum())
        l_count = int((merged["status"] == "지각").sum())
        a_count = int((merged["status"] == "결석").sum())
        m_count = int(merged["meal"].sum())
        u_count = total_count - (p_count + l_count + a_count)
        
        # ── 🎯 메트릭 버튼 생성 (class_name 속성 제거 및 접두사 이모지로 선택 판별) ──
        col1, col2, col3, col4, col5 = st.columns(5)
        f_status = st.session_state.current_filter
        
        with col1:
            prefix1 = "🟢 " if f_status == "출석" else ""
            if st.button(f"{prefix1}출석\n\n{p_count}명", key="btn_p", help="클릭하여 출석자만 보기"):
                st.session_state.current
