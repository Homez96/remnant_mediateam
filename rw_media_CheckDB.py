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
# 세션 상태(session_state)에 기본 변수들이 없으면 강제로 먼저 생성해 줍니다 (에러 방지)
if "members_db" not in st.session_state:
    st.session_state.members_db = pd.DataFrame(columns=["id", "name", "position"])
if "attend_db" not in st.session_state:
    st.session_state.attend_db = pd.DataFrame(columns=["date", "id", "status", "reason", "meal"])

# 구글 스프레드시트 실시간 데이터 로드 시도
try:
    from streamlit_gsheets import GSheetsConnection
    # Secrets에 등록된 설정으로 구글 시트 연결
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 구글 시트에서 최신 데이터 읽어오기
    # (주의: 구글 시트 하단 탭 이름이 각각 'members', 'attendance'여야 합니다)
    sheets_members = conn.read(worksheet="members", ttl=0) # ttl=0 은 캐싱 없이 실시간으로 가져옴
    sheets_attend = conn.read(worksheet="attendance", ttl=0)
    
    # 데이터가 정상적으로 비어있지 않다면 세션에 갱신
    if sheets_members is not None and not sheets_members.empty:
        st.session_state.members_db = sheets_members
    if sheets_attend is not None and not sheets_attend.empty:
        st.session_state.attend_db = sheets_attend

except Exception as e:
    # 만약 구글 시트 연결에 실패하면 안내 메시지를 띄우고 가상 데모 데이터로 작동하게 합니다.
    st.warning("⚠️ 구글 스프레드시트 연결에 실패하여 데모 모드로 작동 중입니다. (Advanced settings 설정을 확인해 주세요)")
    
    # 임시 데모 데이터 세팅 (한 번도 세팅된 적이 없을 때만)
    if len(st.session_state.members_db) == 0:
        st.session_state.members_db = pd.DataFrame([
            {"id": "1", "name": "홍길동", "position": "PD"},
            {"id": "2", "name": "김철수", "position": "4번 카메라"},
            {"id": "3", "name": "이영희", "position": "자막"},
        ])

# ── 3. 공통 변수 및 디자인 ──────────────────────────────────────────
POSITIONS = ["선택 안 함", "4번 카메라", "5번 카메라", "6번 카메라", "7번 카메라", "PD", "TD",
             "노출", "자막", "LED", "조명", "사진 촬영", "릴스", "FD", "음향"]

st.markdown("""
    <style>
    .main-title { font-size:28px; font-weight:bold; color:#5038B0; text-align:center; margin-bottom:5px; }
    .sub-title { font-size:14px; color:#666666; text-align:center; margin-bottom:20px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⛪ 예배 출석 관리</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">모바일과 PC 어디서나 실시간으로 출석을 기록하세요.</div>', unsafe_allow_html=True)

# ── 4. 메인 기능 레이아웃 ───────────────────────────────────────────
selected_date = st.date_input("📅 예배 날짜 선택", date.today())
date_key = str(selected_date)

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
        # 현재 날짜의 출석 데이터 필터링
        current_attend = attend_df[attend_df["date"] == date_key] if "date" in attend_df.columns else pd.DataFrame()
        
        # 병합 및 기본값 채우기
        merged = pd.merge(members_df, current_attend, on="id", how="left")
        merged["status"] = merged["status"].fillna("미체크")
        merged["reason"] = merged["reason"].fillna("")
        merged["meal"] = merged["meal"].fillna(False)
        
        # 통계 현황판
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
        col4.metric("식사", f"{m_count}명")
        col5.metric("미체크", f"{u_count}명")
        
        st.write("---")
        st.markdown(f"##### 👇 **{date_key}** 출석 체크 명단")
        
        display_df = merged[["id", "name", "position", "status", "meal", "reason"]].copy()
        display_df.columns = ["ID", "이름", "포지션", "출석 상태", "🍚 식사 여부", "지각/결석 사유"]
        
        edited_df = st.data_editor(
            display_df,
            column_config={
                "ID": None, 
                "이름": st.column_config.TextColumn(disabled=True),
                "포지션": st.column_config.TextColumn(disabled=True),
                "출석 상태": st.column_config.SelectboxColumn(options=["출석", "지각", "결석", "미체크"], required=True),
                "🍚 식사 여부": st.column_config.CheckboxColumn(),
                "지각/결석 사유": st.column_config.TextColumn(placeholder="사유를 입력하세요")
            },
            use_container_width=True,
            key=f"editor_{date_key}"
        )
        
        if st.button("💾 출석 현황 실시간 저장", type="primary", use_container_width=True):
            new_attend_rows = []
            for _, row in edited_df.iterrows():
                new_attend_rows.append({
                    "date": date_key,
                    "id": str(row["ID"]),
                    "status": row["출석 상태"],
                    "reason": row["지각/결석 사유"],
                    "meal": bool(row["🍚 식사 여부"])
                })
            
            # 해당 날짜 데이터 교체
            if not attend_df.empty and "date" in attend_df.columns:
                cleaned_attend = attend_df[attend_df["date"] != date_key]
            else:
                cleaned_attend = pd.DataFrame(columns=["date", "id", "status", "reason", "meal"])
                
            updated_attend = pd.concat([cleaned_attend, pd.DataFrame(new_attend_rows)], ignore_index=True)
            
            # 구글 시트 업데이트 및 세션 반영
            try:
                conn.update(worksheet="attendance", data=updated_attend)
                st.session_state.attend_db = updated_attend
                st.success("🎉 데이터베이스(구글 시트)에 실시간으로 저장되었습니다!")
            except:
                st.session_state.attend_db = updated_attend
                st.success("💾 로컬 세션에 임시 저장되었습니다. (구글 시트 연동 확인 필요)")
                
            time.sleep(1)
            st.rerun()

# ==========================================
#  TAB 2: 예배자 관리 (추가 / 삭제)
# ==========================================
with tab_members:
    st.subheader("👥 등록된 예배자 명단")
    
    if st.session_state.members_db.empty:
        st.write("등록된 예배자가 없습니다.")
    else:
        view_m_df = st.session_state.members_db.copy()
        view_m_df.index = view_m_df.index + 1
        st.dataframe(view_m_df[["name", "position"]].rename(columns={"name":"이름", "position":"포지션"}), use_container_width=True)
    
    st.write("---")
    st.markdown("##### ➕ 새 예배자 추가")
    with st.form("add_member_form", clear_on_submit=True):
        new_name = st.text_input("이름 *")
        new_pos = st.selectbox("포지션 선택", POSITIONS)
        
        if st.form_submit_button("예배자 등록"):
            if not new_name.strip():
                st.error("이름을 입력해 주세요.")
            elif not st.session_state.members_db.empty and new_name in st.session_state.members_db["name"].values:
                st.warning(f"'{new_name}'은(는) 이미 등록된 이름입니다.")
            else:
                new_id = str(int(time.time() * 1000))
                new_row = pd.DataFrame([{"id": new_id, "name": new_name, "position": new_pos}])
                updated_members = pd.concat([st.session_state.members_db, new_row], ignore_index=True)
                
                try:
                    conn.update(worksheet="members", data=updated_members)
                    st.session_state.members_db = updated_members
                    st.success(f"👥 {new_name} 님이 구글 시트에 등록되었습니다!")
                except:
                    st.session_state.members_db = updated_members
                    st.success(f"👥 {new_name} 님이 임시 등록되었습니다.")
                
                time.sleep(1)
                st.rerun()

    if not st.session_state.members_db.empty:
        st.write("---")
        st.markdown("##### 🗑️ 예배자 삭제")
        delete_target = st.selectbox("삭제할 예배자 선택", st.session_state.members_db["name"].values)
        if st.button("선택한 예배자 삭제", type="secondary"):
            updated_members = st.session_state.members_db[st.session_state.members_db["name"] != delete_target]
            try:
                conn.update(worksheet="members", data=updated_members)
                st.session_state.members_db = updated_members
                st.success(f"'{delete_target}' 님이 구글 시트에서 삭제되었습니다.")
            except:
                st.session_state.members_db = updated_members
                st.success(f"'{delete_target}' 님이 임시 삭제되었습니다.")
                
            time.sleep(1)
            st.rerun()
