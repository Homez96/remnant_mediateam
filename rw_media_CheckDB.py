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

# ── 3. 공통 변수 및 디자인 ──────────────────────────────────────────
POSITIONS = ["선택 안 함", "4번 카메라", "5번 카메라", "6번 카메라", "7번 카메라", "PD", "TD",
             "노출", "자막", "LED", "조명", "사진 촬영", "릴스", "FD", "음향"]

st.markdown("""
    <style>
    .main-title { font-size:28px; font-weight:bold; color:#5038B0; text-align:center; margin-bottom:5px; }
    .sub-title { font-size:14px; color:#666666; text-align:center; margin-bottom:20px; }
    .filter-box { background-color: #F1F3FA; padding: 15px; border-radius: 10px; margin-top: 15px; border-left: 5px solid #5038B0; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⛪ 예배 출석 관리</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">모바일과 PC 어디서나 실시간으로 출석을 기록하세요.</div>', unsafe_allow_html=True)

# ── 4. 메인 기능 레이아웃 ───────────────────────────────────────────
selected_date = st.date_input("📅 예배 날짜 선택", date.today())
date_key = str(selected_date)

tab_attend, tab_members = st.tabs(["📋 출석 체크", "👥 예배자 관리"])

# ==========================================
#  TAB 1: 출석 체크 및 실시간 통계 조회
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
        
        # 📊 상단 현황판 통계 산출
        total_count = len(members_df)
        p_count = int((merged["status"] == "출석").sum())
        l_count = int((merged["status"] == "지각").sum())
        a_count = int((merged["status"] == "결석").sum())
        m_count = int(merged["meal"].sum())
        u_count = total_count - (p_count + l_count + a_count)
        
        # 메트릭 대시보드 표시
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("출석", f"{p_count}명")
        col2.metric("지각", f"{l_count}명")
        col3.metric("결석", f"{a_count}명")
        col4.metric("식사", f"{m_count}명")
        col5.metric("미체크", f"{u_count}명")
        
        # ✨ [신규 기능] 통계별 명단 확인용 필터 툴바
        st.write("")
        view_option = st.radio(
            "🔍 명단 모아보기 필터",
            ["전체 명단 보기", f"출석자 ({p_count}명)", f"지각자 ({l_count}명)", f"결석자 ({a_count}명)", f"식사 신청자 ({m_count}명)", f"미체크자 ({u_count}명)"],
            horizontal=True
        )
        
        # 선택한 통계 탭에 따라 명단 필터링 처리
        if "출석자" in view_option:
            filtered_df = merged[merged["status"] == "출석"]
            title_text = "🟢 현재 출석 상태인 인원"
        elif "지각자" in view_option:
            filtered_df = merged[merged["status"] == "지각"]
            title_text = "🟡 현재 지각 상태인 인원"
        elif "결석자" in view_option:
            filtered_df = merged[merged["status"] == "결석"]
            title_text = "🔴 현재 결석 상태인 인원"
        elif "식사 신청자" in view_option:
            filtered_df = merged[merged["meal"] == True]
            title_text = "🍚 오늘 식사하는 인원"
        elif "미체크자" in view_option:
            filtered_df = merged[merged["status"] == "미체크"]
            title_text = "⚪ 아직 출석 체크가 안 된 인원"
        else:
            filtered_df = merged
            title_text = f"📝 전체 체크 명단 ({date_key})"
            
        st.write("---")
        
        # 필터링된 결과가 있을 때만 별도 요약 박스 노출
        if view_option != "전체 명단 보기":
            st.markdown(f"""
                <div class="filter-box">
                    <strong>{title_text}</strong><br>
                    {', '.join(filtered_df['name'].values) if not filtered_df.empty else '해당하는 인원이 없습니다.'}
                </div>
            """, unsafe_allow_html=True)
            st.write("")

        # 메인 데이터 에디터 명단 테이블 (필터링된 명단만 표에 노출)
        display_df = filtered_df[["id", "name", "position", "status", "meal", "reason"]].copy()
        display_df.columns = ["ID", "이름", "포지션", "출석 상태", "🍚 식사 여부", "지각/결석 사유"]
        
        edited_df = st.data_editor(
            display_df,
            column_config={
                "ID": None, 
                "이름": st.column_config.TextColumn(disabled=True),
                "포지션": st.column_config.TextColumn(disabled=True),
                "출석 상태": st.column_config.SelectboxColumn(options=["출석", "지각", "결석", "미체크"], required=True),
                "🍚 식사 여부": st.column_config.CheckboxColumn(),
                "지각/결석 사유": st.column_config.TextColumn() 
            },
            width="stretch",
            key=f"editor_{date_key}_{view_option}" # 필터 전환 시 표가 초기화/리프레시 되도록 키 유동 처리
        )
        
        if st.button("💾 출석 현황 실시간 저장", type="primary", width="stretch"):
            new_attend_rows = []
            for _, row in edited_df.iterrows():
                new_attend_rows.append({
                    "date": date_key,
                    "id": str(row["ID"]),
                    "status": row["출석 상태"],
                    "reason": str(row["지각/결석 사유"]),
                    "meal": bool(row["🍚 식사 여부"])
                })
            
            # 수정한 데이터 반영 및 병합
            for nr in new_attend_rows:
                idx = attend_df[(attend_df["date"] == date_key) & (attend_df["id"] == nr["id"])].index
                if not idx.empty:
                    attend_df.loc[idx, ["status", "reason", "meal"]] = [nr["status"], nr["reason"], nr["meal"]]
                else:
                    attend_df = pd.concat([attend_df, pd.DataFrame([nr])], ignore_index=True)
                    
            attend_df["id"] = attend_df["id"].astype(str)
            
            try:
                conn.update(spreadsheet=clean_url, worksheet="attendance", data=attend_df)
                st.session_state.attend_db = attend_df
                st.success("🎉 데이터베이스(구글 시트)에 실시간으로 저장되었습니다!")
            except Exception as e:
                st.session_state.attend_db = attend_df
                st.success("💾 로컬 세션에 임시 저장되었습니다.")
                
            time.sleep(1)
            st.rerun()

# ==========================================
#  TAB 2: 예배자 관리
# ==========================================
with tab_members:
    st.subheader("👥 등록된 예배자 명단")
    
    if st.session_state.members_db.empty:
        st.write("등록된 예배자가 없습니다.")
    else:
        view_m_df = st.session_state.members_db.copy()
        view_m_df.index = view_m_df.index + 1
        st.dataframe(view_m_df[["name", "position"]].rename(columns={"name":"이름", "position":"포지션"}), width="stretch")
    
    st.write("---")
    
    m_sub_tab1, m_sub_tab2, m_sub_tab3 = st.tabs(["➕ 예배자 추가", "✏️ 정보 수정", "🗑️ 예배자 삭제"])
    
    with m_sub_tab1:
        with st.form("add_member_form", clear_on_submit=True):
            new_name = st.text_input("새로운 예배자 이름 *")
            new_pos = st.selectbox("포지션 선택", POSITIONS, key="add_pos")
            
            if st.form_submit_button("예배자 신규 등록"):
                if not new_name.strip():
                    st.error("이름을 입력해 주세요.")
                elif not st.session_state.members_db.empty and new_name in st.session_state.members_db["name"].values:
                    st.warning(f"'{new_name}'은(는) 이미 등록된 이름입니다.")
                else:
                    new_id = str(int(time.time() * 1000))
                    new_row = pd.DataFrame([{"id": new_id, "name": new_name, "position": new_pos}])
                    updated_members = pd.concat([st.session_state.members_db, new_row], ignore_index=True)
                    updated_members["id"] = updated_members["id"].astype(str)
                    
                    try:
                        conn.update(spreadsheet=clean_url, worksheet="members", data=updated_members)
                        st.session_state.members_db = updated_members
                        st.success(f"👥 {new_name} 님이 성공적으로 등록되었습니다!")
                    except:
                        st.session_state.members_db = updated_members
                        st.success(f"👥 {new_name} 님이 임시 등록되었습니다.")
                    time.sleep(1)
                    st.rerun()

    with m_sub_tab2:
        if st.session_state.members_db.empty:
            st.write("수정할 인원이 없습니다.")
        else:
            edit_target = st.selectbox("수정할 대상 선택", st.session_state.members_db["name"].values, key="edit_tgt")
            target_row = st.session_state.members_db[st.session_state.members_db["name"] == edit_target].iloc[0]
            
            with st.form("edit_member_form"):
                edit_name = st.text_input("이름 수정", value=target_row["name"])
                try:
                    default_pos_idx = POSITIONS.index(target_row["position"])
                except:
                    default_pos_idx = 0
                edit_pos = st.selectbox("포지션 수정", POSITIONS, index=default_pos_idx, key="edit_pos")
                
                if st.form_submit_button("정보 수정 완료"):
                    if not edit_name.strip():
                        st.error("이름은 비워둘 수 없습니다.")
                    else:
                        updated_members = st.session_state.members_db.copy()
                        idx = updated_members[updated_members["id"] == target_row["id"]].index[0]
                        updated_members.at[idx, "name"] = edit_name
                        updated_members.at[idx, "position"] = edit_pos
                        updated_members["id"] = updated_members["id"].astype(str)
                        
                        try:
                            conn.update(spreadsheet=clean_url, worksheet="members", data=updated_members)
                            st.session_state.members_db = updated_members
                            st.success(f"✏️ {edit_target} 님의 정보가 수정되었습니다.")
                        except:
                            st.session_state.members_db = updated_members
                            st.success(f"✏️ {edit_target} 님의 정보가 임시 수정되었습니다.")
                        time.sleep(1)
                        st.rerun()

    with m_sub_tab3:
        if st.session_state.members_db.empty:
            st.write("삭제할 인원이 없습니다.")
        else:
            delete_target = st.selectbox("삭제할 대상 선택", st.session_state.members_db["name"].values, key="del_tgt")
            st.warning(f"⚠️ '{delete_target}' 님을 명단에서 삭제하시겠습니까?")
            
            if st.button("❌ 선택한 예배자 최종 삭제", type="secondary"):
                updated_members = st.session_state.members_db[st.session_state.members_db["name"] != delete_target]
                updated_members["id"] = updated_members["id"].astype(str)
                try:
                    conn.update(spreadsheet=clean_url, worksheet="members", data=updated_members)
                    st.session_state.members_db = updated_members
                    st.success(f"🗑️ '{delete_target}' 님이 명단에서 완전히 삭제되었습니다.")
                except:
                    st.session_state.members_db = updated_members
                    st.success(f"🗑️ '{delete_target}' 님이 임시 삭제되었습니다.")
                    
                time.sleep(1)
                st.rerun()
