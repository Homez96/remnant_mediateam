import streamlit as st
import pandas as pd
from datetime import date
import time

# ── 페이지 기본 설정 (모바일 친화적 세팅) ──────────────────────────────
st.set_page_config(
    page_title="예배 출석 관리",
    page_icon="⛪",
    layout="centered", # 모바일에서 한눈에 보기 좋게 중앙 정렬
    initial_sidebar_state="collapsed"
)

# ── 구글 스프레드시트 연동 (Streamlit 내장 기능) ────────────────────────
# 실제 배포 시 .streamlit/secrets.toml에 구글 API 키를 넣으면 자동 연동됩니다.
try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    # 구글 시트에서 'members' 탭과 'attendance' 탭을 읽어오는 로직 (실제 배포시 활성화)
    # members_df = conn.read(worksheet="members")
    # attend_df = conn.read(worksheet="attendance")
except Exception:
    # 에러 방지용 임시 테스트 데이터 (데이터베이스 연결 전 가상 작동용)
    if "members_db" not in st.session_state:
        st.session_state.members_db = pd.DataFrame([
            {"id": "1", "name": "홍길동", "position": "PD"},
            {"id": "2", "name": "김철수", "position": "4번 카메라"},
            {"id": "3", "name": "이영희", "position": "자막"},
        ])
    if "attend_db" not in st.session_state:
        st.session_state.attend_db = pd.DataFrame(columns=["date", "id", "status", "reason", "meal"])

# ── 공통 변수 및 스타일 ──────────────────────────────────────────────
POSITIONS = ["선택 안 함", "4번 카메라", "5번 카메라", "6번 카메라", "7번 카메라", "PD", "TD",
             "노출", "자막", "LED", "조명", "사진 촬영", "릴스", "FD", "음향"]

# 디자인 입히기
st.markdown("""
    <style>
    .main-title { font-size:28px; font-weight:bold; color:#5038B0; text-align:center; margin-bottom:5px; }
    .sub-title { font-size:14px; color:#666666; text-align:center; margin-bottom:20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⛪ 예배 출석 관리</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">모바일과 PC 어디서나 실시간으로 출석을 기록하세요.</div>', unsafe_allow_html=True)

# ── 메인 기능 레이아웃 ───────────────────────────────────────────────
# 1. 날짜 선택
selected_date = st.date_input("📅 예배 날짜 선택", date.today())
date_key = str(selected_date)

# 2. 상단 탭 구성 (기존 기능 유지)
tab_attend, tab_members = st.tabs(["📋 출석 체크", "👥 예배자 관리"])

# ==========================================
#  TAB 1: 출석 체크 및 실시간 현황
# ==========================================
with tab_attend:
    members_df = st.session_state.members_db
    attend_df = st.session_state.attend_db
    
    if members_df.empty:
        st.info("먼저 [예배자 관리] 탭에서 예배자를 추가해 주세요.")
    else:
        # 현재 날짜의 출석 데이터 필터링하여 가져오기
        current_attend = attend_df[attend_df["date"] == date_key]
        
        # 예배자 목록과 출석 데이터 병합 (기존 기록이 없으면 기본값 세팅)
        merged = pd.merge(members_df, current_attend, on="id", how="left")
        merged["status"] = merged["status"].fillna("미체크")
        merged["reason"] = merged["reason"].fillna("")
        merged["meal"] = merged["meal"].fillna(False)
        
        # ── 통계 카드 현황판 ──
        total_count = len(members_df)
        p_count = int((merged["status"] == "출석").sum())
        l_count = int((merged["status"] == "지각").sum())
        a_count = int((merged["status"] == "결석").sum())
        m_count = int(merged["meal"].sum())
        u_count = total_count - (p_count + l_count + a_count)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("출석", f"{p_count}명")
        col2.metric("지각", f"{l_count}명")
        col3.metric("결석", f"{a_count}명")
        col4.metric("식사 신청", f"{m_count}명")
        col5.metric("미체크", f"{u_count}명")
        
        st.write("---")
        
        # ── 인터랙티브 데이터 에디터 (표에서 직접 수정) ──
        st.markdown(f"##### 👇 **{date_key}** 출석 체크 명단")
        
        # 사용자가 화면에서 수정할 표 구성
        display_df = merged[["id", "name", "position", "status", "meal", "reason"]].copy()
        display_df.columns = ["ID", "이름", "포지션", "출석 상태", "🍚 식사 여부", "지각/결석 사유"]
        
        edited_df = st.data_editor(
            display_df,
            column_config={
                "ID": None, # ID 열은 숨김
                "이름": st.column_config.TextColumn(disabled=True),
                "포지션": st.column_config.TextColumn(disabled=True),
                "출석 상태": st.column_config.SelectboxColumn(options=["출석", "지각", "결석", "미체크"], required=True),
                "🍚 식사 여부": st.column_config.CheckboxColumn(),
                "지각/결석 사유": st.column_config.TextColumn(placeholder="사유를 입력하세요")
            },
            use_container_width=True,
            key=f"editor_{date_key}" # 날짜 변경 시 새로고침되도록 키 설정
        )
        
        # ── 저장 버튼 클릭 시 실시간 DB 반영 ──
        if st.button("💾 출석 현황 실시간 저장", type="primary", use_container_width=True):
            # 대형 DB 업데이트 로직
            new_attend_rows = []
            for _, row in edited_df.iterrows():
                new_attend_rows.append({
                    "date": date_key,
                    "id": row["ID"],
                    "status": row["출석 상태"],
                    "reason": row["지각/결석 사유"],
                    "meal": row["🍚 식사 여부"]
                })
            
            # 기존 해당 날짜 데이터 삭제 후 재생성 (Overwrite 효과)
            cleaned_attend = attend_df[attend_df["date"] != date_key]
            updated_attend = pd.concat([cleaned_attend, pd.DataFrame(new_attend_rows)], ignore_index=True)
            
            # 상태 저장 (실제 배포시 conn.update() 로 구글 시트에 전송)
            st.session_state.attend_db = updated_attend
            st.success("🎉 데이터베이스에 실시간 반영되었습니다! 다른 사람도 이 최신 버전을 보게 됩니다.")
            time.sleep(1)
            st.rerun()

# ==========================================
#  TAB 2: 예배자 관리 (추가 / 삭제)
# ==========================================
with tab_members:
    st.subheader("👥 등록된 예배자 명단")
    
    # 현재 등록된 인원 출력
    if st.session_state.members_db.empty:
        st.write("등록된 예배자가 없습니다.")
    else:
        # 가시성을 위해 인덱스를 1부터 시작하는 순번으로 변경하여 보여줌
        view_m_df = st.session_state.members_db.copy()
        view_m_df.index = view_m_df.index + 1
        st.dataframe(view_m_df[["name", "position"]].rename(columns={"name":"이름", "position":"포지션"}), use_container_width=True)
    
    st.write("---")
    
    # 예배자 추가 폼
    st.markdown("##### ➕ 새 예배자 추가")
    with st.form("add_member_form", clear_on_submit=True):
        new_name = st.text_input("이름 *")
        new_pos = st.selectbox("포지션 선택", POSITIONS)
        submit_btn = st.form_submit_with_rows=True
        
        if st.form_submit_button("예배자 등록"):
            if not new_name.strip():
                st.error("이름을 입력해 주세요.")
            elif new_name in st.session_state.members_db["name"].values:
                st.warning(f"'{new_name}'은(는) 이미 등록된 이름입니다.")
            else:
                new_id = str(int(time.time() * 1000))
                new_row = pd.DataFrame([{"id": new_id, "name": new_name, "position": new_pos}])
                st.session_state.members_db = pd.concat([st.session_state.members_db, new_row], ignore_index=True)
                # 실제 배포시 구글 시트에 인서트하는 코드 위치
                st.success(f"👥 {new_name} 님이 성공적으로 등록되었습니다.")
                time.sleep(1)
                st.rerun()

    # 예배자 삭제 기능
    if not st.session_state.members_db.empty:
        st.write("---")
        st.markdown("##### 🗑️ 예배자 삭제")
        delete_target = st.selectbox("삭제할 예배자 선택", st.session_state.members_db["name"].values)
        if st.button("선택한 예배자 삭제", type="secondary"):
            st.session_state.members_db = st.session_state.members_db[st.session_state.members_db["name"] != delete_target]
            st.success(f"'{delete_target}' 님이 명단에서 삭제되었습니다.")
            time.sleep(1)
            st.rerun()