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

if "selected_date_val" not in st.session_state:
    st.session_state.selected_date_val = date.today()

# ✨ [할당량 초과 방지] 강제 리프레시 플래그 세션 초기화
if "force_refresh" not in st.session_state:
    st.session_state.force_refresh = False

try:
    from streamlit_gsheets import GSheetsConnection
    
    conn = st.connection("gsheets", type=GSheetsConnection)
    clean_url = "https://docs.google.com/spreadsheets/d/1584S2jzLNFlSJHAgNOBo_w6HjwMwlJ7pUei4jVqeJrU"
    
    # ✨ [핵심 수정] 강제 새로고침 플래그가 켜졌을 때만 ttl=0으로 읽고, 평소에는 5분 캐싱(ttl=300) 적용
    current_ttl = 0 if st.session_state.force_refresh else 300
    
    sheets_members = conn.read(spreadsheet=clean_url, worksheet="members", ttl=current_ttl)
    sheets_attend = conn.read(spreadsheet=clean_url, worksheet="attendance", ttl=current_ttl)
    
    # 강제로 새로 읽어왔다면 플래그를 다시 꺼줍니다.
    if st.session_state.force_refresh:
        st.session_state.force_refresh = False
    
    if sheets_members is not None and not sheets_members.empty:
        sheets_members["id"] = sheets_members["id"].astype(str)
        sheets_members = sheets_members.sort_values(by="name", ascending=True).reset_index(drop=True)
        st.session_state.members_db = sheets_members
        
    if sheets_attend is not None and not sheets_attend.empty:
        sheets_attend["date"] = sheets_attend["date"].astype(str)
        sheets_attend["id"] = sheets_attend["id"].astype(str)
        sheets_attend["status"] = sheets_attend["status"].fillna("미체크").astype(str)
        sheets_attend["reason"] = sheets_attend["reason"].fillna("").astype(str)
        sheets_attend["meal"] = sheets_attend["meal"].apply(lambda x: True if x is True or str(x).lower() == 'true' or x == 1 else False)
        st.session_state.attend_db = sheets_attend

except Exception as e:
    # 구글이 완전히 차단했을 때 앱이 뻗지 않고 기존 세션 데이터나 샘플 데이터로 구동되도록 방어막 구축
    if st.session_state.members_db.empty:
        st.error(f"⚠️ 구글 호출 제한 상태입니다. 잠시 후 자동 정상화됩니다. (오류: {str(e)})")
        st.session_state.members_db = pd.DataFrame([
            {"id": "2", "name": "김철수", "position": "4번 카메라"},
            {"id": "3", "name": "이영희", "position": "자막"},
            {"id": "1", "name": "홍길동", "position": "PD"},
        ])

# ── 3. 공통 변수 및 디자인 ──────────────────────────────────────────
POSITIONS = ["선택 안 함", "4번 카메라", "5번 카메라", "6번 카메라", "7번 카메라", "PD", "TD",
             "노출", "자막", "LED", "조명", "사진 촬영", "릴스", "FD", "음향"]

st.markdown("""
    <style>
    .main-title { font-size:28px; font-weight:bold; color:#5038B0; text-align:center; margin-bottom:5px; }
    .sub-title { font-size:14px; color:#666666; text-align:center; margin-bottom:20px; }
    
    div[data-testid="stHorizontalBlock"] div.stButton > button {
        width: 100% !important;
        border-radius: 10px;
        padding: 8px 2px !important;
        text-align: center;
        transition: all 0.2s ease;
    }

    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="🟢"],
    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="🟡"],
    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="🔴"],
    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="🔵"],
    div[data-testid="stHorizontalBlock"] div.stButton > button[aria-label*="⚪"] {
        background-color: #5038B0 !important;
        color: white !important;
        border-color: #5038B0 !important;
        font-weight: bold !important;
        box-shadow: 0px 4px 8px rgba(80, 56, 176, 0.35);
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">⛪ 예배 출석 관리</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">모바일과 PC 어디서나 실시간으로 출석을 기록하세요.</div>', unsafe_allow_html=True)

# ── 4. 메인 기능 레이아웃 ───────────────────────────────────────────
selected_date = st.date_input("📅 예배 날짜 선택", st.session_state.selected_date_val)
date_key = str(selected_date)

if "last_date" not in st.session_state or st.session_state.last_date != date_key:
    st.session_state.last_date = date_key
    st.session_state.selected_date_val = selected_date
    st.session_state.current_filter = "전체"

tab_attend, tab_members = st.tabs(["📋 출석 체크", "👥 예배자 관리"])

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
        
        # ── 🎯 메트릭형 버튼 배치 ──────────────────────────────────
        col1, col2, col3, col4, col5 = st.columns(5)
        f_status = st.session_state.current_filter
        
        # 중요: 이 버튼들을 누를 때는 구글 시트를 찌르지 않고(force_refresh=False) 내부 세션 필터만 바꿉니다.
        with col1:
            prefix1 = "🟢 " if f_status == "출석" else ""
            if st.button(f"{prefix1}출석 ({p_count}명)", key="btn_p"):
                st.session_state.current_filter = "전체" if f_status == "출석" else "출석"
                st.rerun()
                
        with col2:
            prefix2 = "🟡 " if f_status == "지각" else ""
            if st.button(f"{prefix2}지각 ({l_count}명)", key="btn_l"):
                st.session_state.current_filter = "전체" if f_status == "지각" else "지각"
                st.rerun()
                
        with col3:
            prefix3 = "🔴 " if f_status == "결석" else ""
            if st.button(f"{prefix3}결석 ({a_count}명)", key="btn_a"):
                st.session_state.current_filter = "전체" if f_status == "결석" else "결석"
                st.rerun()
                
        with col4:
            prefix4 = "🔵 " if f_status == "식사" else ""
            if st.button(f"{prefix4}식사 ({m_count}명)", key="btn_m"):
                st.session_state.current_filter = "전체" if f_status == "식사" else "식사"
                st.rerun()
                
        with col5:
            prefix5 = "⚪ " if f_status == "미체크" else ""
            if st.button(f"{prefix5}미체크 ({u_count}명)", key="btn_u"):
                st.session_state.current_filter = "전체" if f_status == "미체크" else "미체크"
                st.rerun()
        
        # ── 필터링 연동 데이터 바인딩 ──────────────────────────────────
        if f_status == "출석":
            filtered_df = merged[merged["status"] == "출석"]
            title_text = "🟢 [출석] 상태인 인원만 표시 중"
        elif f_status == "지각":
            filtered_df = merged[merged["status"] == "지각"]
            title_text = "🟡 [지각] 상태인 인원만 표시 중"
        elif f_status == "결석":
            filtered_df = merged[merged["status"] == "결석"]
            title_text = "🔴 [결석] 상태인 인원만 표시 중"
        elif f_status == "식사":
            filtered_df = merged[merged["meal"] == True]
            title_text = "🍚 [식사 신청] 인원만 표시 중"
        elif f_status == "미체크":
            filtered_df = merged[merged["status"] == "미체크"]
            title_text = "⚪ [미체크] 상태인 인원만 표시 중"
        else:
            filtered_df = merged
            title_text = f"📝 전체 명단 표시 중 ({date_key})"
            
        st.write("---")
        
        names_list = ', '.join(filtered_df['name'].values) if not filtered_df.empty else '해당하는 인원이 없습니다.'
        st.info(f"**{title_text}** (현황 수치를 한 번 더 누르면 전체 명단으로 돌아옵니다.)\n\n💡 {names_list}")
        st.write("")

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
            key=f"editor_{date_key}_{f_status}"
        )
        
        if st.button("💾 출석 현황 실시간 저장", type="primary", width="stretch"):
            edited_rows = []
            for _, row in edited_df.iterrows():
                edited_rows.append({
                    "date": date_key,
                    "id": str(row["ID"]),
                    "status": str(row["출석 상태"]),
                    "reason": str(row["지각/결석 사유"]),
                    "meal": bool(row["🍚 식사 여부"])
                })
            edited_patch_df = pd.DataFrame(edited_rows)
            
            if not attend_df.empty and "id" in attend_df.columns:
                target_ids = edited_patch_df["id"].unique()
                remain_attend_df = attend_df[
                    ~((attend_df["date"] == date_key) & (attend_df["id"].isin(target_ids)))
                ]
                updated_attend = pd.concat([remain_attend_df, edited_patch_df], ignore_index=True)
            else:
                updated_attend = edited_patch_df
            
            updated_attend["date"] = updated_attend["date"].astype(str)
            updated_attend["id"] = updated_attend["id"].astype(str)
            updated_attend["status"] = updated_attend["status"].astype(str)
            updated_attend["reason"] = updated_attend["reason"].astype(str)
            updated_attend["meal"] = updated_attend["meal"].astype(bool)
            
            try:
                conn.update(spreadsheet=clean_url, worksheet="attendance", data=updated_attend)
                st.session_state.attend_db = updated_attend
                # ✨ 저장이 성공하면 다음 렌더링 때 구글 시트에서 무조건 새로 긁어오도록 동기화 플래그 ON
                st.session_state.force_refresh = True
                st.success("🎉 데이터베이스(구글 시트)에 실시간으로 저장되었습니다!")
            except Exception as e:
                st.session_state.attend_db = updated_attend
                st.error(f"⚠️ 저장 실패 원인: {str(e)}")
                st.success("💾 대신 로컬 세션에 임시 저장되었습니다.")
                
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
                    updated_members = updated_members.sort_values(by="name", ascending=True).reset_index(drop=True)
                    
                    try:
                        conn.update(spreadsheet=clean_url, worksheet="members", data=updated_members)
                        st.session_state.members_db = updated_members
                        st.session_state.force_refresh = True  # 강제 갱신 플래그 ON
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
                        updated_members = updated_members.sort_values(by="name", ascending=True).reset_index(drop=True)
                        
                        try:
                            conn.update(spreadsheet=clean_url, worksheet="members", data=updated_members)
                            st.session_state.members_db = updated_members
                            st.session_state.force_refresh = True  # 강제 갱신 플래그 ON
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
                updated_members = updated_members.sort_values(by="name", ascending=True).reset_index(drop=True)
                
                try:
                    conn.update(spreadsheet=clean_url, worksheet="members", data=updated_members)
                    st.session_state.members_db = updated_members
                    st.session_state.force_refresh = True  # 강제 갱신 플래그 ON
                    st.success(f"🗑️ '{delete_target}' 님이 명단에서 완전히 삭제되었습니다.")
                except:
                    st.session_state.members_db = updated_members
                    st.success(f"🗑️ '{delete_target}' 님이 임시 삭제되었습니다.")
                    
                time.sleep(1)
                st.rerun()
