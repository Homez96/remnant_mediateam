import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import requests
from streamlit_gsheets import GSheetsConnection

# ── 1. 페이지 설정 및 초기화 ──────────────────────────────────────────
st.set_page_config(page_title="RW 미디어팀 통합 관리", layout="centered")

if "page" not in st.session_state: st.session_state.page = "🏠 홈 (대시보드)"
if "post_db" not in st.session_state: st.session_state.post_db = pd.DataFrame()
if "cat_db" not in st.session_state: st.session_state.cat_db = pd.DataFrame()
if "view_post_id" not in st.session_state: st.session_state.view_post_id = None

# (로드 함수 및 기타 DB 설정은 이전과 동일하게 유지하세요...)

# ── 4. 사이드바 메뉴 ────────────────────────────────────────────────
with st.sidebar:
    st.title("⛪ RW Media")
    menu = st.radio("메뉴 이동", ["🏠 홈 (대시보드)", "⛪ 예배 출석 관리", "🏛️ 팀 커뮤니티 게시판"])
    if menu != st.session_state.page:
        st.session_state.page = menu
        st.rerun()

# ── 5. 메인 로직 ───────────────────────────────────────────────────
if st.session_state.page == "🏠 홈 (대시보드)":
    st.title("🏠 RW 미디어팀 시스템")

elif st.session_state.page == "⛪ 예배 출석 관리":
    st.header("⛪ 예배 출석 관리")
    # ... 출석 관리 로직 ...

elif st.session_state.page == "🏛️ 팀 커뮤니티 게시판":
    st.header("🏛️ 팀 커뮤니티 게시판")
    
    # 데이터 로드 체크
    if not st.session_state.get("board_loaded", False):
        if st.button("🔄 게시판 데이터 불러오기"):
            # load_community_data() 호출
            st.session_state.board_loaded = True
            st.rerun()
    else:
        b_tab_view, b_tab_write, b_tab_admin = st.tabs(["📖 게시글 보기", "📝 글쓰기", "⚙️ 카테고리 관리"])
        
        # 7-3. 게시글 보기 및 댓글 관리
        with b_tab_view:
            # 💡 여기서 변수를 정의해야 에러가 나지 않습니다.
            full_p_db = st.session_state.post_db.copy()
            
            # 상세 페이지 모드
            if st.session_state.view_post_id:
                if st.button("⬅️ 목록으로 돌아가기"):
                    st.session_state.view_post_id = None
                    st.rerun()
                
                # 데이터가 있을 때만 상세 보기
                if not full_p_db.empty and st.session_state.view_post_id in full_p_db["id"].values:
                    post = full_p_db[full_p_db["id"] == st.session_state.view_post_id].iloc[0]
                    st.title(post['title'])
                    st.write(post['content'])
                    st.write("---")
                    st.markdown("**💬 댓글**")
                    # (여기에 댓글 관련 로직을 추가하세요)

            # 리스트 모드
            else:
                st.subheader("📋 게시글 목록")
                if not full_p_db.empty:
                    for _, post in full_p_db[::-1].iterrows():
                        if st.button(f"📄 {post['title']}", key=f"btn_{post['id']}"):
                            st.session_state.view_post_id = post['id']
                            st.rerun()
                else:
                    st.info("등록된 게시글이 없습니다.")

        # 7-2, 7-1 (글쓰기, 카테고리) 로직은 여기 아래에 작성하세요.
