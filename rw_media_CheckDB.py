import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import requests

# ── 0. 외부 스토리지(ImgBB) 설정 ─────────────────────────────────────
def get_api_key():
    try:
        return st.secrets["imgbb"]["api_key"]
    except Exception:
        return ""

UPLOAD_URL = "https://api.imgbb.com/1/upload"

def upload_image_to_storage(file_buffer):
    api_key = get_api_key()
    if not api_key:
        st.error("❌ ImgBB API Key가 secrets.toml에 설정되지 않았습니다.")
        return None
    try:
        payload = {"key": api_key, "action": "upload"}
        files = {"image": (file_buffer.name, file_buffer.getvalue())}
        response = requests.post(UPLOAD_URL, data=payload, files=files, timeout=20)
        res_data = response.json()
        if response.status_code == 200:
            return res_data["data"]["url"]
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

# ── 3. 구글 시트 데이터 로드 및 정제 함수 ───────────────────────────
clean_url = "https://docs.google.com/spreadsheets/d/1584S2jzLNFlSJHAgNOBo_w6HjwMwlJ7pUei4jVqeJrU"

def clean_id_string(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    if s.endswith(".0"): s = s[:-2]
    return s

def clean_df(df, type_dict):
    if df is None or df.empty: return pd.DataFrame(columns=type_dict.keys())
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

conn = None
try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"구글 시트 연결 오류: {e}")

def require_conn():
    if conn is None:
        st.error("구글 시트 연결이 필요합니다. 연결 설정을 확인해 주세요.")
        return False
    return True

def get_ttl():
    return 1 if st.session_state.force_refresh else 600

def load_members():
    if not require_conn(): return
    df = conn.read(spreadsheet=clean_url, worksheet="members", ttl=get_ttl())
    st.session_state.members_db = clean_df(df, {"id":"str","name":"str","position":"str"}).sort_values("name").reset_index(drop=True)

def load_attendance_data():
    if not require_conn(): return
    with st.spinner("⏳ 구글 시트에서 출석 데이터를 불러오는 중..."):
        try:
            df_m = conn.read(spreadsheet=clean_url, worksheet="members", ttl=get_ttl())
            df_a = conn.read(spreadsheet=clean_url, worksheet="attendance", ttl=get_ttl())
            st.session_state.members_db = clean_df(df_m, {"id":"str","name":"str","position":"str"}).sort_values("name").reset_index(drop=True)
            st.session_state.attend_db = clean_df(df_a, {"date":"str","id":"str","status":"str","meal":"bool","reason":"str"})
            st.session_state.att_loaded = True
            st.session_state.force_refresh = False
        except Exception as e:
            if "429" in str(e): st.error("🛑 구글 제한이 걸렸습니다. 잠시 후 다시 시도해 주세요.")
            else: st.error(f"출석 로드 실패: {e}")

def load_community_data():
    if not require_conn(): return
    with st.spinner("⏳ 구글 시트에서 게시판 데이터를 불러오는 중..."):
        try:
            df_m = conn.read(spreadsheet=clean_url, worksheet="members", ttl=get_ttl())
            df_c = conn.read(spreadsheet=clean_url, worksheet="categories", ttl=get_ttl())
            df_p = conn.read(spreadsheet=clean_url, worksheet="posts", ttl=get_ttl())
            df_cm = conn.read(spreadsheet=clean_url, worksheet="comments", ttl=get_ttl())

            st.session_state.members_db = clean_df(df_m, {"id":"str","name":"str","position":"str"}).sort_values("name").reset_index(drop=True)
            st.session_state.cat_db = clean_df(df_c, {"id":"str","name":"str"})
            st.session_state.post_db = clean_df(df_p, {"id":"str","category_id":"str","title":"str","content":"str","links":"str","image_urls":"str","created_at":"str"})
            st.session_state.comm_db = clean_df(df_cm, {"id":"str","post_id":"str","author":"str","content":"str","created_at":"str"})
            st.session_state.board_loaded = True
            st.session_state.force_refresh = False
        except Exception as e:
            if "429" in str(e): st.error("🛑 구글 제한이 걸렸습니다. 잠시 후 다시 시도해 주세요.")
            else: st.error(f"게시판 로드 실패: {e}")

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

# ── 5. [페이지 0] 🏠 홈 (대시보드 화면) ─────────────────────────────
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
                # members 정보와 해당 날짜(date_key)의 attendance 데이터 매핑
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

                # 실시간 상단 인원 통계 계산
                p_c = (merged["status"] == "출석").sum()
                l_c = (merged["status"] == "지각").sum()
                a_c = (merged["status"] == "결석").sum()
                u_c = (merged["status"] == "미체크").sum()
                m_c = merged["meal"].sum()

                cols = st.columns(5)
                f_s = st.session_state.current_filter

                def m_btn(col, lab, count, key, val):
                    pre = "🟢 " if f_s == val else ""
                    if col.button(f"{pre}{lab}\n({count}명)", key=key):
                        st.session_state.current_filter = "전체" if f_s == val else val
                        st.rerun()

                m_btn(cols[0], "출석", p_c, "b_p", "출석")
                m_btn(cols[1], "지각", l_c, "b_l", "지각")
                m_btn(cols[2], "결석", a_c, "b_a", "결석")
                m_btn(cols[3], "식사", int(m_c), "b_m", "식사")
                m_btn(cols[4], "미체크", u_c, "b_u", "미체크")

                # 💡 [변경 사항] 명단 요약 텍스트 출력을 주석 처리 혹은 제거하여 보이지 않게 처리했습니다.
                # f_s = st.session_state.current_filter
                # if f_s == "식사":
                #     filtered_names = merged[merged["meal"] == True]["name"].values
                # elif f_s != "전체":
                #     filtered_names = merged[merged["status"] == f_s]["name"].values
                # else:
                #     filtered_names = merged["name"].values
                # st.info(f"**{f_s} 명단 요약** : {', '.join(filtered_names) if len(filtered_names) > 0 else '없음'}")

                # 💡 실제 필터 기능은 아래 폼 내부의 드롭다운 명단(member_names_list) 구성을 통해 정상 작동합니다.
                f_s = st.session_state.current_filter
                if f_s == "식사":
                    filtered_rows = merged[merged["meal"] == True]
                elif f_s != "전체":
                    filtered_rows = merged[merged["status"] == f_s]
                else:
                    filtered_rows = merged

                member_names_list = filtered_rows["name"].tolist()

                st.write("---")
                st.subheader("✍️ 개별 출석 기록 폼")

                if not member_names_list:
                    st.warning(f"⚠️ 선택하신 '{f_s}' 상태에 해당하는 팀원이 없습니다. 상단 버튼을 다시 눌러 전체 명단을 확인하세요.")
                else:
                    with st.form(key=f"individual_attendance_form_{date_key}", clear_on_submit=False):
                        
                        # ① 이름 선택 드롭다운 (필터에 맞춰 실시간 연동되어 나타남)
                        chosen_name = st.selectbox("👤 1. 이름 선택", member_names_list)
                        
                        # 선택된 사용자의 기존 데이터 로우 추출
                        user_current_row = merged[merged["name"] == chosen_name].iloc[0]
                        
                        # ② 포지션 선택 드롭다운 (기존 포지션이 기본 선택되지만 자유롭게 변경 가능)
                        base_position = str(user_current_row["position"]).strip()
                        if base_position in POSITIONS:
                            pos_default_idx = POSITIONS.index(base_position)
                        else:
                            pos_default_idx = 0
                        
                        chosen_position = st.selectbox("🎥 2. 오늘 담당 포지션 선택", POSITIONS, index=pos_default_idx)
                        
                        # ③ 출석 상태 선택 드롭다운
                        STATUS_OPTIONS = ["출석", "지각", "결석", "미체크"]
                        base_status = str(user_current_row["status"]).strip()
                        status_default_idx = STATUS_OPTIONS.index(base_status) if base_status in STATUS_OPTIONS else 3
                        
                        chosen_status = st.selectbox("📊 3. 출석 상태 변경", STATUS_OPTIONS, index=status_default_idx)
                        
                        # ④ 사유 입력 칸
                        base_reason = str(user_current_row["reason"]).strip()
                        chosen_reason = st.text_input("📝 4. 특이사항 / 사유 입력", value=base_reason, placeholder="지각 및 결석 사유 등을 자유롭게 입력하세요.")
                        
                        # ⑤ 식사 신청 여부 체크박스
                        base_meal_bool = bool(user_current_row["meal"])
                        chosen_meal = st.checkbox("🍴 5. 오늘 식사 신청 여부", value=base_meal_bool)
                        
                        st.write("")
                        save_submit_btn = st.form_submit_button("💾 현재 팀원 출석 저장", type="primary", use_container_width=True)

                        if save_submit_btn:
                            if not require_conn():
                                st.stop()
                            
                            target_id = user_current_row["id"]

                            # ── [동기화 작업 1] 구글 members 시트의 포지션 정보 실시간 수정 ──
                            raw_members = st.session_state.members_db.copy()
                            raw_members["id"] = raw_members["id"].astype(str).apply(clean_id_string)
                            
                            m_idx = raw_members[raw_members["id"] == target_id].index[0]
                            raw_members.at[m_idx, "position"] = chosen_position
                            
                            upload_members_df = pd.DataFrame(raw_members, columns=["id", "name", "position"]).astype(str)
                            conn.update(spreadsheet=clean_url, worksheet="members", data=upload_members_df)
                            st.session_state.members_db = raw_members

                            # ── [동기화 작업 2] 구글 attendance 시트 기록 생성 및 수정 ──
                            old_db = st.session_state.attend_db.copy()
                            old_db["id"] = old_db["id"].astype(str).apply(clean_id_string)
                            
                            remain = old_db[(old_db["date"] != date_key) | (old_db["id"] != target_id)] if not old_db.empty else pd.DataFrame()
                            
                            new_record = pd.DataFrame([{
                                "date": date_key,
                                "id": target_id,
                                "status": chosen_status,
                                "reason": chosen_reason.strip(),
                                "meal": chosen_meal
                            }])
                            
                            new_db = pd.concat([remain, new_record], ignore_index=True)
                            upload_attend_df = pd.DataFrame(new_db, columns=["date", "id", "status", "reason", "meal"])
                            conn.update(spreadsheet=clean_url, worksheet="attendance", data=upload_attend_df)
                            
                            st.session_state.attend_db = upload_attend_df
                            st.session_state.force_refresh = True
                            
                            st.success(f"🎉 {chosen_name} 님의 정보(포지션: {chosen_position} / 상태: {chosen_status})가 구글 시트에 안전하게 저장되었습니다!")
                            time.sleep(0.6)
                            st.rerun()

        with tab_mem:
            st.dataframe(st.session_state.members_db[["name", "position"]], use_container_width=True, hide_index=True)
            m_tab1, m_tab2, m_tab3 = st.tabs(["➕ 추가", "✏️ 수정", "🗑️ 삭제"])

            with m_tab1:
                with st.form("add_m"):
                    n_n = st.text_input("새로운 예배자 이름 *")
                    n_p = st.selectbox("포지션 선택", POSITIONS)
                    if st.form_submit_button("예배자 신규 등록"):
                        if not require_conn(): st.stop()
                        if n_n.strip():
                            new_id = f"{int(time.time()*1000)}"
                            new_m = pd.concat([
                                st.session_state.members_db,
                                pd.DataFrame([{"id": new_id, "name": n_n.strip(), "position": n_p}])
                            ], ignore_index=True).sort_values("name").reset_index(drop=True)
                            upload_df = pd.DataFrame(new_m, columns=["id", "name", "position"])
                            conn.update(spreadsheet=clean_url, worksheet="members", data=upload_df)
                            st.session_state.members_db = new_m
                            st.session_state.force_refresh = True
                            st.rerun()
                        else:
                            st.error("이름을 입력해 주세요.")

            with m_tab2:
                if not st.session_state.members_db.empty:
                    edit_tgt = st.selectbox("수정할 대상 선택", st.session_state.members_db["name"].values, key="ed_t")
                    tgt_row = st.session_state.members_db[st.session_state.members_db["name"] == edit_tgt].iloc[0]
                    with st.form("edit_m"):
                        e_n = st.text_input("이름 수정", value=tgt_row["name"])
                        cur_pos_idx = POSITIONS.index(tgt_row["position"]) if tgt_row["position"] in POSITIONS else 0
                        e_p = st.selectbox("포지션 수정", POSITIONS, index=cur_pos_idx)
                        if st.form_submit_button("정보 수정 완료"):
                            if not require_conn(): st.stop()
                            updated = st.session_state.members_db.copy()
                            idx = updated[updated["id"] == tgt_row["id"]].index[0]
                            updated.at[idx, "name"] = e_n.strip()
                            updated.at[idx, "position"] = e_p
                            updated = updated.sort_values("name").reset_index(drop=True)
                            upload_df = pd.DataFrame(updated, columns=["id", "name", "position"])
                            conn.update(spreadsheet=clean_url, worksheet="members", data=upload_df)
                            st.session_state.members_db = updated
                            st.session_state.force_refresh = True
                            st.rerun()

            with m_tab3:
                if not st.session_state.members_db.empty:
                    del_tgt = st.selectbox("삭제할 대상 선택", st.session_state.members_db["name"].values, key="del_t")
                    if st.button("❌ 선택한 예배자 최종 삭제", type="secondary"):
                        if not require_conn(): st.stop()
                        updated = st.session_state.members_db[st.session_state.members_db["name"] != del_tgt]
                        updated = updated.sort_values("name").reset_index(drop=True)
                        upload_df = pd.DataFrame(updated, columns=["id", "name", "position"])
                        conn.update(spreadsheet=clean_url, worksheet="members", data=upload_df)
                        st.session_state.members_db = updated
                        st.session_state.force_refresh = True
                        st.rerun()

# ── 7. [페이지 2] 팀 커뮤니티 게시판 ────────────────────────────────
elif st.session_state.page == "🏛️ 팀 커뮤니티 게시판":
    st.header("🏛️ 팀 커뮤니티 게시판")

    if not st.session_state.board_loaded:
        st.warning("⚠️ 현재 구글 시트에서 게시판 데이터를 가져오기 전입니다.")
        if st.button("🔄 게시판 데이터 불러오기 (API 호출)", type="primary", use_container_width=True):
            load_community_data()
            st.rerun()
    else:
        b_tab_view, b_tab_write, b_tab_admin = st.tabs(["📖 게시글 보기", "📝 글쓰기", "⚙️ 카테고리 관리"])
        cat_df = st.session_state.cat_db

        # 7-1. 카테고리 관리
        with b_tab_admin:
            st.subheader("⚙️ 카테고리 설정 (최대 10개)")
            if not cat_df.empty:
                cat_list_str = " | ".join([f"📁 {name}" for name in cat_df["name"].values])
                st.markdown(f"**현재 생성된 카테고리:**\n`{cat_list_str}`")
            else:
                st.info("현재 생성된 카테고리가 없습니다.")
            st.write("")

            c1, c2 = st.columns(2)
            with c1:
                new_cat_name = st.text_input("새 카테고리 이름")
                if st.button("카테고리 추가"):
                    if not require_conn(): st.stop()
                    if len(cat_df) >= 10:
                        st.error("카테고리는 최대 10개까지만 생성할 수 있습니다.")
                    elif not new_cat_name.strip():
                        st.error("카테고리 이름을 입력해 주세요.")
                    elif new_cat_name.strip() in cat_df["name"].values:
                        st.warning("중복된 게시판 이름입니다.")
                    else:
                        new_cat = pd.concat([cat_df, pd.DataFrame([{"id": str(int(time.time()*1000)), "name": new_cat_name.strip()}])], ignore_index=True)
                        upload_df = pd.DataFrame(new_cat, columns=["id", "name"]).astype(str)
                        conn.update(spreadsheet=clean_url, worksheet="categories", data=upload_df)
                        st.session_state.cat_db = new_cat
                        st.session_state.force_refresh = True
                        st.rerun()
            with c2:
                if not cat_df.empty:
                    del_cat = st.selectbox("삭제/수정할 카테고리 선택", cat_df["name"].values)
                    c_rename = st.text_input("카테고리 이름 변경 (원할 때만 입력)")

                    col_btn1, col_btn2 = st.columns(2)
                    if col_btn1.button("이름 변경 실행"):
                        if not require_conn(): st.stop()
                        if c_rename.strip():
                            if c_rename.strip() in cat_df["name"].values:
                                st.warning("중복된 게시판 이름입니다.")
                            else:
                                updated_cat = cat_df.copy()
                                updated_cat.loc[updated_cat["name"] == del_cat, "name"] = c_rename.strip()
                                upload_df = pd.DataFrame(updated_cat, columns=["id", "name"]).astype(str)
                                conn.update(spreadsheet=clean_url, worksheet="categories", data=upload_df)
                                st.session_state.cat_db = updated_cat
                                st.session_state.force_refresh = True
                                st.rerun()
                    if col_btn2.button("카테고리 삭제", type="secondary"):
                        if not require_conn(): st.stop()
                        tgt_id = cat_df[cat_df["name"] == del_cat]["id"].values[0]
                        updated_cat = cat_df[cat_df["id"] != tgt_id]
                        upload_df = pd.DataFrame(updated_cat, columns=["id", "name"]).astype(str)
                        conn.update(spreadsheet=clean_url, worksheet="categories", data=upload_df)
                        st.session_state.cat_db = updated_cat
                        st.session_state.force_refresh = True
                        st.rerun()

        # 7-2. 글쓰기
        with b_tab_write:
            if cat_df.empty:
                st.warning("카테고리를 먼저 만들어주세요.")
            else:
                with st.form("write_post", clear_on_submit=True):
                    p_cat = st.selectbox("카테고리 선택", cat_df["name"].values)
                    p_title = st.text_input("제목 *")
                    p_content = st.text_area("내용 *", height=200)
                    p_links = st.text_input("링크 첨부 (쉼표 구분 - 유튜브나 동영상 링크 가능)")
                    p_files = st.file_uploader("🖼️ 사진 업로드", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

                    if st.form_submit_button("게시글 등록"):
                        if not require_conn(): st.stop()
                        c_id = str(cat_df[cat_df["name"] == p_cat]["id"].values[0])

                        if not p_title.strip() or not p_content.strip():
                            st.error("제목과 내용을 입력해주세요.")
                        elif not st.session_state.post_db.empty and p_title.strip() in st.session_state.post_db[st.session_state.post_db["category_id"] == c_id]["title"].values:
                            st.warning("같은 카테고리에 동일한 제목의 게시글이 있습니다.")
                        else:
                            with st.spinner("⏳ 등록 중..."):
                                p_id = str(int(time.time() * 1000))

                                uploaded_urls = []
                                for f in p_files:
                                    url_result = upload_image_to_storage(f)
                                    if url_result:
                                        uploaded_urls.append(url_result)

                                new_p = pd.DataFrame([{
                                    "id": p_id, "category_id": c_id,
                                    "title": p_title.strip(), "content": p_content,
                                    "links": p_links if p_links else "",
                                    "image_urls": ",".join(uploaded_urls) if uploaded_urls else "",
                                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                                }])

                                updated_p = pd.concat([st.session_state.post_db, new_p], ignore_index=True)
                                upload_df = pd.DataFrame(updated_p, columns=["id", "category_id", "title", "content", "links", "image_urls", "created_at"]).astype(str)
                                conn.update(spreadsheet=clean_url, worksheet="posts", data=upload_df)
                                st.session_state.post_db = updated_p
                                st.session_state.force_refresh = True
                                st.success("🎉 등록되었습니다!")
                                time.sleep(1)
                                st.rerun()

        # 7-3. 게시글 보기 및 댓글 관리
        with b_tab_view:
            sel_cat_name = st.selectbox("📂 카테고리 필터링", ["전체 보기"] + list(cat_df["name"].values))
            full_p_db = st.session_state.post_db.copy()

            if sel_cat_name != "전체 보기" and not full_p_db.empty:
                if not cat_df.empty and sel_cat_name in cat_df["name"].values:
                    sel_c_id = cat_df[cat_df["name"] == sel_cat_name]["id"].values[0]
                    display_posts = full_p_db[full_p_db["category_id"] == sel_c_id]
                else:
                    display_posts = pd.DataFrame()
            else:
                display_posts = full_p_db

            if display_posts.empty:
                st.info("등록된 글이 없습니다.")
            else:
                for _, post in display_posts[::-1].iterrows():
                    c_row = cat_df[cat_df["id"] == post["category_id"]] if not cat_df.empty else pd.DataFrame()
                    c_name = c_row["name"].values[0] if not c_row.empty else "미분류"

                    with st.expander(f"[{c_name}] {post['title']} ({post['created_at']})"):
                        edit_mode = st.checkbox("✏️ 이 글 수정/삭제하기", key=f"e_mode_{post['id']}")
                        
                        if edit_mode:
                            with st.form(f"form_ed_{post['id']}"):
                                ed_title = st.text_input("제목 변경", value=post['title'])
                                ed_content = st.text_area("내용 변경", value=post['content'], height=150)
                                ed_links = st.text_input("링크 변경", value=post['links'])
                                
                                btn_col1, btn_col2 = st.columns([1, 1])
                                if btn_col1.form_submit_button("💾 수정 완료 저장", type="primary"):
                                    if not require_conn(): st.stop()
                                    full_p_db.loc[full_p_db["id"] == post["id"], ["title", "content", "links"]] = [
                                        str(ed_title), str(ed_content), str(ed_links)
                                    ]
                                    upload_df = pd.DataFrame(full_p_db, columns=["id", "category_id", "title", "content", "links", "image_urls", "created_at"]).astype(str)
                                    conn.update(spreadsheet=clean_url, worksheet="posts", data=upload_df)
                                    st.session_state.post_db = full_p_db
                                    st.session_state.force_refresh = True
                                    st.success("게시글이 수정되었습니다.")
                                    time.sleep(0.5)
                                    st.rerun()
                                    
                                if btn_col2.form_submit_button("🗑️ 이 게시글 삭제", type="secondary"):
                                    if not require_conn(): st.stop()
                                    updated_posts = full_p_db[full_p_db["id"] != post["id"]]
                                    upload_df = pd.DataFrame(updated_posts, columns=["id", "category_id", "title", "content", "links", "image_urls", "created_at"]).astype(str)
                                    conn.update(spreadsheet=clean_url, worksheet="posts", data=upload_df)
                                    st.session_state.post_db = updated_posts
                                    st.session_state.force_refresh = True
                                    st.warning("게시글물이 삭제되었습니다.")
                                    time.sleep(0.5)
                                    st.rerun()
                        else:
                            st.write(post['content'])

                            if isinstance(post['image_urls'], str) and post['image_urls'].strip():
                                for url in post['image_urls'].split(","):
                                    if url.strip():
                                        st.image(url.strip(), use_container_width=True)

                            if isinstance(post['links'], str) and post['links'].strip():
                                for link in post['links'].split(","):
                                    cleaned_link = link.strip()
                                    if cleaned_link:
                                        is_youtube = "youtube.com" in cleaned_link or "youtu.be" in cleaned_link
                                        is_video_file = any(cleaned_link.lower().endswith(ext) for ext in [".mp4", ".mov", ".avi", ".webm"])
                                        if is_youtube or is_video_file:
                                            st.video(cleaned_link)
                                        else:
                                            st.link_button("🔗 첨부 링크 연결", cleaned_link)

                        st.write("---")
                        st.markdown("**💬 댓글 목록**")

                        comm_db = st.session_state.comm_db.copy()
                        current_post_id = clean_id_string(str(post["id"]))

                        if not comm_db.empty:
                            comm_db["post_id"] = comm_db["post_id"].apply(clean_id_string)
                            p_comms = comm_db[comm_db["post_id"] == current_post_id]
                        else:
                            p_comms = pd.DataFrame()

                        if not p_comms.empty:
                            for _, citem in p_comms.iterrows():
                                cid_clean = clean_id_string(citem['id'])

                                c_col1, c_col2 = st.columns([5, 1])
                                with c_col1:
                                    st.caption(f"**{citem['author']}** ({citem['created_at']})")

                                    c_edit_active = st.session_state.get(f"cedit_act_{cid_clean}", False)
                                    if c_edit_active:
                                        new_c_body = st.text_area("댓글 수정 내용", value=citem['content'], key=f"txt_cedit_{cid_clean}", height=70)
                                        cs1, cs2 = st.columns(2)
                                        if cs1.button("💾 완료", key=f"btn_csave_{cid_clean}", type="primary"):
                                            if not require_conn(): st.stop()
                                            raw_comm = st.session_state.comm_db.copy()
                                            raw_comm["id"] = raw_comm["id"].apply(clean_id_string)
                                            raw_comm.loc[raw_comm["id"] == cid_clean, "content"] = str(new_c_body.strip())

                                            upload_df = pd.DataFrame(raw_comm, columns=["id", "post_id", "author", "content", "created_at"]).astype(str)
                                            conn.update(spreadsheet=clean_url, worksheet="comments", data=upload_df)

                                            st.session_state.comm_db = raw_comm
                                            st.session_state[f"cedit_act_{cid_clean}"] = False
                                            st.session_state.force_refresh = True
                                            st.success("댓글이 수정되었습니다.")
                                            time.sleep(0.4)
                                            st.rerun()
                                        if cs2.button("❌ 취소", key=f"btn_ccancel_{cid_clean}"):
                                            st.session_state[f"cedit_act_{cid_clean}"] = False
                                            st.rerun()
                                    else:
                                        st.write(citem['content'])

                                with c_col2:
                                    act1, act2 = st.columns(2)
                                    if act1.button("✏️", key=f"edit_c_{cid_clean}", help="댓글 수정"):
                                        st.session_state[f"cedit_act_{cid_clean}"] = True
                                        st.rerun()

                                    if act2.button("🗑️", key=f"del_c_{cid_clean}", help="댓글 삭제"):
                                        if not require_conn(): st.stop()
                                        raw_comm = st.session_state.comm_db.copy()
                                        raw_comm["id"] = raw_comm["id"].apply(clean_id_string)
                                        updated_cm = raw_comm[raw_comm["id"] != cid_clean]
                                        
                                        upload_df = pd.DataFrame(updated_cm, columns=["id", "post_id", "author", "content", "created_at"]).astype(str)
                                        conn.update(spreadsheet=clean_url, worksheet="comments", data=upload_df)
                                        
                                        st.session_state.comm_db = updated_cm
                                        st.session_state.force_refresh = True
                                        st.warning("댓글이 삭제되었습니다.")
                                        time.sleep(0.4)
                                        st.rerun()
