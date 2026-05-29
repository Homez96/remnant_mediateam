import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import requests

# ══════════════════════════════════════════════════════════════════════
# 0. 이미지 업로드 (ImgBB)
# ══════════════════════════════════════════════════════════════════════
UPLOAD_URL = "https://api.imgbb.com/1/upload"

def upload_image_to_storage(file_buffer):
    try:
        api_key = st.secrets["imgbb"]["api_key"]
    except Exception:
        st.warning("⚠️ ImgBB API Key가 secrets.toml에 없습니다. 이미지 업로드를 건너뜁니다.")
        return None
    try:
        response = requests.post(
            UPLOAD_URL,
            data={"key": api_key, "action": "upload"},
            files={"image": (file_buffer.name, file_buffer.getvalue())},
            timeout=20,
        )
        if response.status_code == 200:
            return response.json()["data"]["url"]
    except Exception:
        pass
    return None

# ══════════════════════════════════════════════════════════════════════
# 1. 페이지 설정
# ══════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="RW 미디어팀 통합 관리", page_icon="⛪", layout="wide")

# ══════════════════════════════════════════════════════════════════════
# 2. 세션 상태 초기화
# ══════════════════════════════════════════════════════════════════════
_defaults = {
    "page":              "🏠 홈 (대시보드)",
    "members_db":        pd.DataFrame(columns=["id", "name", "position"]),
    "attend_db":         pd.DataFrame(columns=["date", "id", "status", "reason", "meal"]),
    "cat_db":            pd.DataFrame(columns=["id", "name", "parent_id"]),
    "post_db":           pd.DataFrame(columns=["id", "category_id", "title", "content", "links", "image_urls", "created_at"]),
    "comm_db":           pd.DataFrame(columns=["id", "post_id", "author", "content", "created_at"]),
    "att_loaded":        False,
    "board_loaded":      False,
    "force_refresh":     False,
    "current_filter":    "전체",
    "selected_date_val": date.today(),
    "view_post_id":      None,
    "comm_write_mode":   False,
    "sel_channel_id":    None,   # None = 전체보기, str = 선택된 채널 id
    "sel_sub_cat_id":    None,   # None = 채널 전체, str = 선택된 폴더 id
    "show_add_ch":       False,  # 채널 추가 입력란 표시 여부
    "show_add_sc":       False,  # 폴더(세부 카테고리) 추가 입력란 표시 여부
    # ── 포지션 배치 관리 ──────────────────────────────────
    "pos_map_images":    [],        # [{"id":str, "url":str, "label":str, "icons":[...]}]
    "pos_assign_date":   date.today(),
    "pos_assignments":   [],        # [{"name":str, "position":str}]
    "pos_img_edit_id":   None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

MENU_OPTIONS = ["🏠 홈 (대시보드)", "⛪ 예배 출석 관리", "🎬 포지션 배치 관리", "🏛️ 팀 커뮤니티 게시판"]
POSITIONS    = ["선택 안 함", "4번 카메라", "5번 카메라", "6번 카메라", "7번 카메라",
                "PD", "TD", "노출", "자막", "LED", "조명", "사진 촬영", "릴스", "FD", "음향"]

# ══════════════════════════════════════════════════════════════════════
# 3. 구글 시트 연결 및 유틸
# ══════════════════════════════════════════════════════════════════════
SHEET_URL = "https://docs.google.com/spreadsheets/d/1584S2jzLNFlSJHAgNOBo_w6HjwMwlJ7pUei4jVqeJrU"

conn = None
try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"구글 시트 연결 오류: {e}")

def require_conn() -> bool:
    if conn is None:
        st.error("구글 시트 연결이 필요합니다. 연결 설정을 확인해 주세요.")
        return False
    return True

def get_ttl() -> int:
    return 1 if st.session_state.force_refresh else 600

def clean_id(val) -> str:
    if pd.isna(val): return ""
    s = str(val).strip()
    return s[:-2] if s.endswith(".0") else s

def clean_df(df, schema: dict) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=schema.keys())
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    for col, dtype in schema.items():
        if col not in df.columns:
            continue
        if col in ("id", "post_id", "category_id", "parent_id"):
            df[col] = df[col].apply(clean_id)
        elif dtype == "str":
            df[col] = df[col].astype(str).replace({"nan": "", "None": ""}).str.strip()
        elif dtype == "bool":
            df[col] = df[col].apply(lambda x: str(x).lower() in ("true", "1", "1.0"))
    return df

def load_attendance_data():
    if not require_conn(): return
    with st.spinner("⏳ 출석 데이터 불러오는 중..."):
        try:
            ttl = get_ttl()
            df_m = conn.read(spreadsheet=SHEET_URL, worksheet="members",    ttl=ttl)
            df_a = conn.read(spreadsheet=SHEET_URL, worksheet="attendance", ttl=ttl)
            st.session_state.members_db = clean_df(df_m, {"id":"str","name":"str","position":"str"}).sort_values("name").reset_index(drop=True)
            st.session_state.attend_db  = clean_df(df_a, {"date":"str","id":"str","status":"str","meal":"bool","reason":"str"})
            st.session_state.att_loaded = True
            st.session_state.force_refresh = False
        except Exception as e:
            msg = "🛑 구글 제한이 걸렸습니다. 잠시 후 다시 시도해 주세요." if "429" in str(e) else f"출석 로드 실패: {e}"
            st.error(msg)

def load_community_data():
    if not require_conn(): return
    with st.spinner("⏳ 게시판 데이터 불러오는 중..."):
        try:
            ttl = get_ttl()
            df_m  = conn.read(spreadsheet=SHEET_URL, worksheet="members",    ttl=ttl)
            df_c  = conn.read(spreadsheet=SHEET_URL, worksheet="categories", ttl=ttl)
            df_p  = conn.read(spreadsheet=SHEET_URL, worksheet="posts",      ttl=ttl)
            df_cm = conn.read(spreadsheet=SHEET_URL, worksheet="comments",   ttl=ttl)
            st.session_state.members_db = clean_df(df_m,  {"id":"str","name":"str","position":"str"}).sort_values("name").reset_index(drop=True)
            cat_db = clean_df(df_c, {"id":"str","name":"str","parent_id":"str"})
            if "parent_id" not in cat_db.columns:
                cat_db["parent_id"] = ""
            st.session_state.cat_db     = cat_db
            st.session_state.post_db    = clean_df(df_p,  {"id":"str","category_id":"str","title":"str","content":"str","links":"str","image_urls":"str","created_at":"str"})
            st.session_state.comm_db    = clean_df(df_cm, {"id":"str","post_id":"str","author":"str","content":"str","created_at":"str"})
            st.session_state.board_loaded = True
            st.session_state.force_refresh = False
        except Exception as e:
            msg = "🛑 구글 제한이 걸렸습니다. 잠시 후 다시 시도해 주세요." if "429" in str(e) else f"게시판 로드 실패: {e}"
            st.error(msg)

# ══════════════════════════════════════════════════════════════════════
# 4. 사이드바 메뉴
# ══════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("⛪ RW Media")
    idx = MENU_OPTIONS.index(st.session_state.page) if st.session_state.page in MENU_OPTIONS else 0
    sel = st.radio("메뉴 이동", MENU_OPTIONS, index=idx)
    if sel != st.session_state.page:
        st.session_state.page = sel
        st.session_state.view_post_id   = None
        st.session_state.comm_write_mode = False
        st.rerun()
    st.write("---")
    if st.button("🔄 앱 전체 강제 새로고침"):
        st.session_state.force_refresh   = True
        st.session_state.att_loaded      = False
        st.session_state.board_loaded    = False
        st.session_state.view_post_id    = None
        st.session_state.comm_write_mode = False
        st.rerun()

# ══════════════════════════════════════════════════════════════════════
# 5. 홈 대시보드
# ══════════════════════════════════════════════════════════════════════
if st.session_state.page == "🏠 홈 (대시보드)":
    st.title("🏠 RW 미디어팀 시스템")
    st.markdown("---")
    st.subheader("👋 반갑습니다!")
    st.info("원하시는 작업을 선택한 후 이동하여 데이터를 불러와 주세요!")
    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 📋 출석부 기록/수정")
        st.write("미디어팀원들의 예배 출석 상태 및 포지션 배정, 식사 여부를 관리합니다.")
        if st.button("🚀 예배 출석 관리 바로가기", use_container_width=True, type="primary"):
            st.session_state.page = "⛪ 예배 출석 관리"
            st.rerun()
    with c2:
        st.markdown("### 🎬 포지션 배치 관리")
        st.write("배치도 이미지를 관리하고 날짜별 팀원 포지션 배치 명단을 생성·공유합니다.")
        if st.button("🚀 포지션 배치 관리 바로가기", use_container_width=True, type="primary"):
            st.session_state.page = "🎬 포지션 배치 관리"
            st.rerun()
    with c3:
        st.markdown("### 🏛️ 팀 커뮤니티 게시판")
        st.write("공지사항 공유, 카테고리별 게시글 작성 및 댓글 소통 공간입니다.")
        if st.button("🚀 팀 커뮤니티 게시판 바로가기", use_container_width=True, type="primary"):
            st.session_state.page = "🏛️ 팀 커뮤니티 게시판"
            st.rerun()

# ══════════════════════════════════════════════════════════════════════
# 6. 예배 출석 관리
# ══════════════════════════════════════════════════════════════════════
elif st.session_state.page == "⛪ 예배 출석 관리":
    st.header("⛪ 예배 출석 관리")

    if not st.session_state.att_loaded:
        st.warning("⚠️ 구글 시트에서 출석 데이터를 가져오기 전입니다.")
        if st.button("🔄 출석 데이터 불러오기", type="primary", use_container_width=True):
            load_attendance_data()
            st.rerun()
    else:
        selected_date = st.date_input("📅 날짜 선택", st.session_state.selected_date_val)
        date_key = str(selected_date)

        if st.session_state.get("last_date") != date_key:
            st.session_state.last_date         = date_key
            st.session_state.selected_date_val = selected_date
            st.session_state.current_filter    = "전체"

        tab_att, tab_mem = st.tabs(["📋 출석 체크", "👥 예배자 관리"])

        with tab_att:
            m_df = st.session_state.members_db.copy()
            a_df = st.session_state.attend_db.copy()

            if m_df.empty:
                st.info("등록된 예배자가 없습니다.")
            else:
                curr_a = a_df[a_df["date"] == date_key] if not a_df.empty else pd.DataFrame()
                if not curr_a.empty:
                    merged = pd.merge(m_df, curr_a, on="id", how="left")
                else:
                    merged = m_df.copy()
                    for col in ("status", "meal", "reason"):
                        merged[col] = None

                merged["status"] = merged["status"].fillna("미체크")
                merged["meal"]   = merged["meal"].fillna(False)
                merged["reason"] = merged["reason"].fillna("")

                p_c = (merged["status"] == "출석").sum()
                l_c = (merged["status"] == "지각").sum()
                a_c = (merged["status"] == "결석").sum()
                u_c = (merged["status"] == "미체크").sum()
                m_c = int(merged["meal"].sum())

                cols = st.columns(5)
                f_s  = st.session_state.current_filter

                def m_btn(col, lab, count, key, val):
                    pre = "🟢 " if f_s == val else ""
                    if col.button(f"{pre}{lab}\n({count}명)", key=key):
                        st.session_state.current_filter = "전체" if f_s == val else val
                        st.rerun()

                m_btn(cols[0], "출석",   p_c, "b_p", "출석")
                m_btn(cols[1], "지각",   l_c, "b_l", "지각")
                m_btn(cols[2], "결석",   a_c, "b_a", "결석")
                m_btn(cols[3], "식사",   m_c, "b_m", "식사")
                m_btn(cols[4], "미체크", u_c, "b_u", "미체크")

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
                    st.warning(f"⚠️ '{f_s}' 상태에 해당하는 팀원이 없습니다. 상단 버튼을 다시 눌러 전체 명단을 확인하세요.")
                else:
                    with st.form(key=f"individual_attendance_form_{date_key}", clear_on_submit=False):
                        chosen_name = st.selectbox("👤 1. 이름 선택", member_names_list)
                        user_row    = merged[merged["name"] == chosen_name].iloc[0]

                        base_pos = str(user_row["position"]).strip()
                        pos_idx  = POSITIONS.index(base_pos) if base_pos in POSITIONS else 0
                        chosen_position = st.selectbox("🎥 2. 오늘 담당 포지션 선택", POSITIONS, index=pos_idx)

                        STATUS_OPTIONS = ["출석", "지각", "결석", "미체크"]
                        base_status    = str(user_row["status"]).strip()
                        status_idx     = STATUS_OPTIONS.index(base_status) if base_status in STATUS_OPTIONS else 3
                        chosen_status  = st.selectbox("📊 3. 출석 상태 변경", STATUS_OPTIONS, index=status_idx)

                        chosen_reason = st.text_input(
                            "📝 4. 특이사항 / 사유 입력",
                            value=str(user_row["reason"]).strip(),
                            placeholder="지각 및 결석 사유 등을 자유롭게 입력하세요.",
                        )
                        chosen_meal = st.checkbox("🍴 5. 오늘 식사 신청 여부", value=bool(user_row["meal"]))

                        st.write("")
                        save_btn = st.form_submit_button("💾 현재 팀원 출석 저장", type="primary", use_container_width=True)

                        if save_btn:
                            if not require_conn(): st.stop()
                            target_id = user_row["id"]

                            raw_members = st.session_state.members_db.copy()
                            raw_members["id"] = raw_members["id"].astype(str).apply(clean_id)
                            m_idx = raw_members[raw_members["id"] == target_id].index[0]
                            raw_members.at[m_idx, "position"] = chosen_position
                            conn.update(
                                spreadsheet=SHEET_URL, worksheet="members",
                                data=pd.DataFrame(raw_members, columns=["id","name","position"]).astype(str),
                            )
                            st.session_state.members_db = raw_members

                            old_db = st.session_state.attend_db.copy()
                            old_db["id"] = old_db["id"].astype(str).apply(clean_id)
                            remain = old_db[
                                ~((old_db["date"] == date_key) & (old_db["id"] == target_id))
                            ] if not old_db.empty else pd.DataFrame()

                            new_record = pd.DataFrame([{
                                "date":   date_key,
                                "id":     target_id,
                                "status": chosen_status,
                                "reason": chosen_reason.strip(),
                                "meal":   chosen_meal,
                            }])
                            new_db    = pd.concat([remain, new_record], ignore_index=True)
                            upload_df = pd.DataFrame(new_db, columns=["date","id","status","reason","meal"])
                            conn.update(spreadsheet=SHEET_URL, worksheet="attendance", data=upload_df)

                            st.session_state.attend_db     = upload_df
                            st.session_state.force_refresh = True
                            st.success(f"🎉 {chosen_name} 님 저장 완료! (포지션: {chosen_position} / 상태: {chosen_status})")
                            time.sleep(0.6)
                            st.rerun()

        with tab_mem:
            st.dataframe(st.session_state.members_db[["name","position"]], use_container_width=True, hide_index=True)
            m_tab1, m_tab2, m_tab3 = st.tabs(["➕ 추가", "✏️ 수정", "🗑️ 삭제"])

            with m_tab1:
                with st.form("add_m"):
                    n_n = st.text_input("새로운 예배자 이름 *")
                    n_p = st.selectbox("포지션 선택", POSITIONS)
                    if st.form_submit_button("예배자 신규 등록"):
                        if not require_conn(): st.stop()
                        if n_n.strip():
                            new_m = pd.concat([
                                st.session_state.members_db,
                                pd.DataFrame([{"id": str(int(time.time()*1000)), "name": n_n.strip(), "position": n_p}])
                            ], ignore_index=True).sort_values("name").reset_index(drop=True)
                            conn.update(spreadsheet=SHEET_URL, worksheet="members", data=pd.DataFrame(new_m, columns=["id","name","position"]))
                            st.session_state.members_db    = new_m
                            st.session_state.force_refresh = True
                            st.rerun()
                        else:
                            st.error("이름을 입력해 주세요.")

            with m_tab2:
                if not st.session_state.members_db.empty:
                    edit_tgt = st.selectbox("수정할 대상 선택", st.session_state.members_db["name"].values, key="ed_t")
                    tgt_row  = st.session_state.members_db[st.session_state.members_db["name"] == edit_tgt].iloc[0]
                    with st.form("edit_m"):
                        e_n = st.text_input("이름 수정", value=tgt_row["name"])
                        e_p = st.selectbox("포지션 수정", POSITIONS,
                                           index=POSITIONS.index(tgt_row["position"]) if tgt_row["position"] in POSITIONS else 0)
                        if st.form_submit_button("정보 수정 완료"):
                            if not require_conn(): st.stop()
                            updated = st.session_state.members_db.copy()
                            idx = updated[updated["id"] == tgt_row["id"]].index[0]
                            updated.at[idx, "name"]     = e_n.strip()
                            updated.at[idx, "position"] = e_p
                            updated = updated.sort_values("name").reset_index(drop=True)
                            conn.update(spreadsheet=SHEET_URL, worksheet="members", data=pd.DataFrame(updated, columns=["id","name","position"]))
                            st.session_state.members_db    = updated
                            st.session_state.force_refresh = True
                            st.rerun()

            with m_tab3:
                if not st.session_state.members_db.empty:
                    del_tgt = st.selectbox("삭제할 대상 선택", st.session_state.members_db["name"].values, key="del_t")
                    if st.button("❌ 선택한 예배자 최종 삭제", type="secondary"):
                        if not require_conn(): st.stop()
                        updated = st.session_state.members_db[st.session_state.members_db["name"] != del_tgt].sort_values("name").reset_index(drop=True)
                        conn.update(spreadsheet=SHEET_URL, worksheet="members", data=pd.DataFrame(updated, columns=["id","name","position"]))
                        st.session_state.members_db    = updated
                        st.session_state.force_refresh = True
                        st.rerun()

# ══════════════════════════════════════════════════════════════════════
# 7. 팀 커뮤니티 게시판 — Slack 스타일 UI v3
#    변경사항:
#    - 아웃채널(사이드바): 채널 목록 자체가 드래그 가능 (multi_containers)
#      → "현재 채널" 컨테이너로 끌어다 놓으면 선택, "채널 목록" 안에서 끌면 순서 변경
#    - 인채널(메인): 노션 페이지 스타일 폴더(세부 카테고리) UI
#      → 폴더 추가/삭제는 모두 인채널 영역에서
# ══════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# 7. 포지션 배치 관리
# ══════════════════════════════════════════════════════════════════════
elif st.session_state.page == "🎬 포지션 배치 관리":
    st.header("🎬 포지션 배치 관리")

    tab_img, tab_assign, tab_roster = st.tabs(["🖼️ 배치도 이미지 관리", "📝 날짜·포지션 배정", "📋 명단 확인 & 복사"])

    # ── 탭1: 배치도 이미지 관리 ──────────────────────────────────────
    with tab_img:
        st.subheader("🖼️ 배치도 이미지 관리")
        st.caption("배치도 이미지를 업로드하고, 이미지 위 각 포지션 아이콘 좌표를 설정하면 클릭 시 안내 문구가 표시됩니다.")

        # 이미지 업로드
        with st.expander("➕ 새 배치도 이미지 추가", expanded=len(st.session_state.pos_map_images) == 0):
            up_label = st.text_input("배치도 이름 (예: 1부 예배 배치도)", key="pos_img_label_input")
            up_file  = st.file_uploader("이미지 파일 선택", type=["png", "jpg", "jpeg", "webp"], key="pos_img_upload")
            if st.button("☁️ 업로드 & 저장", type="primary", key="pos_img_upload_btn"):
                if not up_file:
                    st.error("❌ 이미지 파일을 선택해 주세요.")
                elif not up_label.strip():
                    st.error("❌ 배치도 이름을 입력해 주세요.")
                else:
                    with st.spinner("업로드 중..."):
                        url = upload_image_to_storage(up_file)
                    if url:
                        new_img = {
                            "id":    str(int(time.time() * 1000)),
                            "url":   url,
                            "label": up_label.strip(),
                            "icons": [],
                        }
                        st.session_state.pos_map_images.append(new_img)
                        st.success(f"✅ '{up_label.strip()}' 배치도가 등록되었습니다!")
                        st.rerun()
                    else:
                        # ImgBB 없으면 base64로 메모리 저장
                        import base64
                        b64 = base64.b64encode(up_file.getvalue()).decode()
                        ext = up_file.name.rsplit(".", 1)[-1].lower()
                        data_url = f"data:image/{ext};base64,{b64}"
                        new_img = {
                            "id":    str(int(time.time() * 1000)),
                            "url":   data_url,
                            "label": up_label.strip(),
                            "icons": [],
                        }
                        st.session_state.pos_map_images.append(new_img)
                        st.success(f"✅ '{up_label.strip()}' 배치도가 등록되었습니다! (로컬 저장)")
                        st.rerun()

        # 이미지 목록 표시
        if not st.session_state.pos_map_images:
            st.info("📭 등록된 배치도 이미지가 없습니다. 위에서 추가해 주세요.")
        else:
            for img_item in st.session_state.pos_map_images:
                img_id    = img_item["id"]
                img_label = img_item["label"]
                img_url   = img_item["url"]
                img_icons = img_item.get("icons", [])

                with st.container(border=True):
                    col_title, col_del = st.columns([6, 1])
                    with col_title:
                        st.markdown(f"#### 🗺️ {img_label}")
                    with col_del:
                        if st.button("🗑️", key=f"del_img_{img_id}", help="이미지 삭제"):
                            st.session_state.pos_map_images = [
                                x for x in st.session_state.pos_map_images if x["id"] != img_id
                            ]
                            if st.session_state.pos_img_edit_id == img_id:
                                st.session_state.pos_img_edit_id = None
                            st.rerun()

                    # 이미지 표시 + 아이콘 클릭 안내 (HTML)
                    # 아이콘들을 이미지 위에 오버레이로 표시
                    icons_html = ""
                    for ic in img_icons:
                        pos_label = ic.get("label") or ic.get("pos", "")
                        guide     = ic.get("guide", "포지션 안내 문구 없음")
                        icons_html += f"""
                        <div class="pos-icon" style="left:{ic['x']}%;top:{ic['y']}%;"
                             onclick="toggleGuide(this)"
                             data-guide="{pos_label}: {guide}">
                            <span class="icon-dot">📍</span>
                            <span class="icon-label">{pos_label}</span>
                            <div class="guide-bubble">{pos_label}<br>{guide}</div>
                        </div>"""

                    html_block = f"""
                    <style>
                    .pos-map-wrap {{
                        position: relative; display: inline-block; width: 100%; max-width: 800px;
                    }}
                    .pos-map-wrap img {{
                        width: 100%; border-radius: 8px; display: block;
                    }}
                    .pos-icon {{
                        position: absolute; transform: translate(-50%, -50%);
                        cursor: pointer; text-align: center; z-index: 10;
                    }}
                    .icon-dot {{ font-size: 1.6rem; display: block; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.6)); }}
                    .icon-label {{
                        display: block; background: rgba(0,0,0,0.72); color: #fff;
                        font-size: 0.65rem; border-radius: 4px; padding: 1px 5px; white-space: nowrap;
                        margin-top: 2px;
                    }}
                    .guide-bubble {{
                        display: none; position: absolute; bottom: 110%; left: 50%; transform: translateX(-50%);
                        background: #1e3a5f; color: #fff; border-radius: 8px; padding: 8px 12px;
                        font-size: 0.82rem; white-space: nowrap; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
                        min-width: 140px; z-index: 100;
                    }}
                    .guide-bubble.show {{ display: block; }}
                    </style>
                    <div class="pos-map-wrap">
                        <img src="{img_url}" alt="{img_label}">
                        {icons_html}
                    </div>
                    <script>
                    function toggleGuide(el) {{
                        var b = el.querySelector('.guide-bubble');
                        // close all others first
                        document.querySelectorAll('.guide-bubble.show').forEach(function(x){{
                            if (x !== b) x.classList.remove('show');
                        }});
                        b.classList.toggle('show');
                    }}
                    </script>
                    """
                    st.components.v1.html(html_block, height=max(350, 60 + len(img_icons)*0), scrolling=False)

                    # 아이콘 편집 패널
                    edit_mode = st.session_state.pos_img_edit_id == img_id
                    if st.button(
                        "✏️ 아이콘 편집 닫기" if edit_mode else "📍 포지션 아이콘 추가/편집",
                        key=f"toggle_edit_{img_id}",
                    ):
                        st.session_state.pos_img_edit_id = None if edit_mode else img_id
                        st.rerun()

                    if edit_mode:
                        st.markdown("---")
                        st.markdown("**📍 새 아이콘 추가**")
                        st.caption("이미지 좌측 상단을 (0%, 0%), 우측 하단을 (100%, 100%)으로 입력하세요.")
                        with st.form(f"add_icon_{img_id}", clear_on_submit=True):
                            ic_col1, ic_col2 = st.columns(2)
                            ic_x     = ic_col1.number_input("X 위치 (%)", min_value=0.0, max_value=100.0, value=50.0, step=0.5, key=f"icx_{img_id}")
                            ic_y     = ic_col2.number_input("Y 위치 (%)", min_value=0.0, max_value=100.0, value=50.0, step=0.5, key=f"icy_{img_id}")
                            ic_label = st.text_input("포지션 명칭 (예: 카메라1, 조명, LED)", key=f"iclabel_{img_id}")
                            ic_guide = st.text_area("포지션 안내 문구", placeholder="예) 4번 카메라: 무대 정면 촬영 담당", height=80, key=f"icguide_{img_id}")
                            if st.form_submit_button("➕ 아이콘 추가", type="primary"):
                                if ic_label.strip():
                                    for img in st.session_state.pos_map_images:
                                        if img["id"] == img_id:
                                            img["icons"].append({
                                                "x": ic_x, "y": ic_y,
                                                "label": ic_label.strip(),
                                                "guide": ic_guide.strip(),
                                            })
                                    st.success(f"✅ 아이콘 '{ic_label.strip()}' 추가!")
                                    st.rerun()
                                else:
                                    st.error("포지션 명칭을 입력해 주세요.")

                        # 기존 아이콘 목록
                        if img_icons:
                            st.markdown("**현재 등록된 아이콘**")
                            for i, ic in enumerate(img_icons):
                                ic_r1, ic_r2, ic_r3 = st.columns([3, 4, 1])
                                ic_r1.write(f"📍 **{ic.get('label','')}** ({ic['x']}%, {ic['y']}%)")
                                ic_r2.caption(ic.get("guide", ""))
                                if ic_r3.button("🗑️", key=f"del_ic_{img_id}_{i}"):
                                    for img in st.session_state.pos_map_images:
                                        if img["id"] == img_id:
                                            img["icons"].pop(i)
                                    st.rerun()

    # ── 탭2: 날짜·포지션 배정 ───────────────────────────────────────
    with tab_assign:
        st.subheader("📝 날짜 & 포지션 배정")

        # 날짜 선택 (항상 오늘 날짜 기본값)
        assign_date = st.date_input(
            "📅 예배 날짜 선택",
            value=st.session_state.pos_assign_date,
            key="pos_date_picker",
        )
        if assign_date != st.session_state.pos_assign_date:
            st.session_state.pos_assign_date = assign_date
        st.markdown(f"**선택된 날짜:** `{assign_date.strftime('%Y년 %m월 %d일')} ({['월','화','수','목','금','토','일'][assign_date.weekday()]}요일)`")
        st.markdown("---")

        # 자체 이름 목록 관리 (구글 시트 독립적)
        if "pos_name_list" not in st.session_state:
            st.session_state.pos_name_list = []

        with st.expander("👥 이름 목록 관리 (추가/삭제)", expanded=len(st.session_state.pos_name_list) == 0):
            with st.form("name_list_form", clear_on_submit=True):
                new_name_input = st.text_input("새 이름 추가", placeholder="팀원 이름 입력 후 추가")
                if st.form_submit_button("➕ 이름 추가"):
                    n = new_name_input.strip()
                    if not n:
                        st.error("이름을 입력해 주세요.")
                    elif n in st.session_state.pos_name_list:
                        st.warning(f"'{n}'은 이미 목록에 있습니다.")
                    else:
                        st.session_state.pos_name_list.append(n)
                        st.rerun()

            if st.session_state.pos_name_list:
                st.markdown("**현재 이름 목록:**")
                nl_cols = st.columns(4)
                for ni, nm in enumerate(st.session_state.pos_name_list):
                    with nl_cols[ni % 4]:
                        if st.button(f"❌ {nm}", key=f"del_name_{ni}", help="목록에서 제거"):
                            st.session_state.pos_name_list.pop(ni)
                            st.rerun()

        st.markdown("#### 👤 팀원 포지션 배정")

        name_opts = ["선택하세요"] + st.session_state.pos_name_list if st.session_state.pos_name_list else None

        with st.form("pos_add_form", clear_on_submit=True):
            pa_col1, pa_col2 = st.columns(2)
            if name_opts:
                chosen_name_pa = pa_col1.selectbox("이름 선택", name_opts, key="pa_name_sel")
                direct_name_pa = ""
            else:
                chosen_name_pa = ""
                direct_name_pa = pa_col1.text_input("이름 직접 입력", placeholder="위 목록에 이름을 먼저 추가하거나 여기 입력", key="pa_name_direct")

            chosen_pos_pa = pa_col2.selectbox("포지션 선택", POSITIONS, key="pa_pos_sel")

            if st.form_submit_button("➕ 배정 추가", type="primary", use_container_width=True):
                final_name = (chosen_name_pa if name_opts else direct_name_pa.strip())
                if not final_name or final_name == "선택하세요":
                    st.error("❌ 이름을 선택하거나 입력해 주세요.")
                elif chosen_pos_pa == "선택 안 함":
                    st.error("❌ 포지션을 선택해 주세요.")
                else:
                    existing = [a for a in st.session_state.pos_assignments if a["name"] != final_name]
                    existing.append({"name": final_name, "position": chosen_pos_pa})
                    st.session_state.pos_assignments = existing
                    st.success(f"✅ {final_name} → {chosen_pos_pa} 배정 완료!")
                    st.rerun()

        # 현재 배정 목록
        if st.session_state.pos_assignments:
            st.markdown("---")
            st.markdown("#### 📋 현재 배정 목록")
            for i, asgn in enumerate(st.session_state.pos_assignments):
                a_c1, a_c2, a_c3 = st.columns([3, 3, 1])
                a_c1.write(f"👤 **{asgn['name']}**")
                a_c2.write(f"🎥 {asgn['position']}")
                if a_c3.button("🗑️", key=f"del_asgn_{i}"):
                    st.session_state.pos_assignments.pop(i)
                    st.rerun()
            if st.button("🗑️ 배정 전체 초기화", type="secondary"):
                st.session_state.pos_assignments = []
                st.rerun()
        else:
            st.info("아직 배정된 팀원이 없습니다. 위 폼에서 추가하세요.")

    # ── 탭3: 명단 확인 & 복사 ───────────────────────────────────────
    with tab_roster:
        st.subheader("📋 최종 포지션 명단")

        date_str = st.session_state.pos_assign_date.strftime("%Y년 %m월 %d일")
        weekday_str = ["월", "화", "수", "목", "금", "토", "일"][st.session_state.pos_assign_date.weekday()]
        full_date_str = f"{date_str} ({weekday_str}요일)"

        if not st.session_state.pos_assignments:
            st.info("📭 배정된 팀원이 없습니다. '날짜·포지션 배정' 탭에서 먼저 배정해 주세요.")
        else:
            # 포지션 순서로 정렬 (POSITIONS 순서 기준)
            sorted_asgn = sorted(
                st.session_state.pos_assignments,
                key=lambda x: POSITIONS.index(x["position"]) if x["position"] in POSITIONS else 999
            )

            # 시각적 명단 표시
            st.markdown(f"### 📅 {full_date_str} 예배 포지션 명단")
            st.markdown("---")

            # 배치도 이미지 선택 표시
            if st.session_state.pos_map_images:
                img_labels = ["(배치도 선택 안 함)"] + [img["label"] for img in st.session_state.pos_map_images]
                sel_img_label = st.selectbox("🗺️ 배치도 이미지 함께 보기", img_labels, key="roster_img_sel")
                if sel_img_label != "(배치도 선택 안 함)":
                    sel_img = next((x for x in st.session_state.pos_map_images if x["label"] == sel_img_label), None)
                    if sel_img:
                        st.image(sel_img["url"], caption=sel_img["label"], use_container_width=True)
                st.markdown("---")

            # 포지션별 카드 표시
            cols_per_row = 3
            rows = [sorted_asgn[i:i+cols_per_row] for i in range(0, len(sorted_asgn), cols_per_row)]
            for row in rows:
                rcols = st.columns(cols_per_row)
                for ci, asgn in enumerate(row):
                    with rcols[ci]:
                        st.markdown(
                            f"""<div style="background:#1e3a5f;border-radius:10px;padding:14px 16px;margin-bottom:8px;text-align:center;">
                            <div style="font-size:1.3rem;font-weight:bold;color:#fff;">{asgn['name']}</div>
                            <div style="font-size:0.95rem;color:#a8d1ff;margin-top:6px;">🎥 {asgn['position']}</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )

            st.markdown("---")

            # 복사용 텍스트 생성
            copy_lines = [f"📅 {full_date_str} 예배 포지션 명단", ""]
            for asgn in sorted_asgn:
                copy_lines.append(f"• {asgn['name']} — {asgn['position']}")

            # 배치도 이미지 링크 추가 (URL인 경우)
            if st.session_state.pos_map_images:
                sel_label_for_copy = st.session_state.get("roster_img_sel", "(배치도 선택 안 함)")
                if sel_label_for_copy != "(배치도 선택 안 함)":
                    sel_img_c = next((x for x in st.session_state.pos_map_images if x["label"] == sel_label_for_copy), None)
                    if sel_img_c and sel_img_c["url"].startswith("http"):
                        copy_lines.append("")
                        copy_lines.append(f"🗺️ 배치도: {sel_img_c['url']}")

            copy_text = "\n".join(copy_lines)

            st.markdown("#### 📋 복사용 텍스트")
            st.text_area(
                "아래 텍스트를 복사하여 붙여넣기 하세요",
                value="\n".join(copy_lines),
                height=max(150, 60 + len(sorted_asgn) * 28),
                key="copy_text_area",
            )
            # 클립보드 복사 버튼 (JavaScript)
            copy_js = copy_text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            st.components.v1.html(f"""
            <button onclick="navigator.clipboard.writeText(`{copy_js}`).then(()=>{{
                this.textContent='✅ 복사 완료!'; setTimeout(()=>this.textContent='📋 클립보드에 복사',2000);
            }})"
            style="background:#1e3a5f;color:#fff;border:none;padding:10px 24px;border-radius:8px;
                   font-size:1rem;cursor:pointer;margin-top:8px;font-weight:bold;">
            📋 클립보드에 복사</button>
            """, height=60)


elif st.session_state.page == "🏛️ 팀 커뮤니티 게시판":

    st.markdown("""
    <style>
    /* 아웃채널 배경 (사이드바 컬럼) */
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child {
        background-color: #3f0e40;
        min-height: 80vh;
        padding: 8px 6px;
    }
    /* 사이드바 내부 텍스트 색상 */
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child .stMarkdown p,
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child h3 {
        color: #fff;
    }
    /* sort_items 컨테이너 헤더 흰색 */
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child h2 {
        color: #fff !important; font-size:12px !important;
        letter-spacing:1px; text-transform:uppercase;
        margin: 8px 4px 4px !important;
    }
    /* sort_items 아이템 스타일 */
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child ul {
        padding-left: 0 !important; list-style: none;
    }
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child li {
        background:#4a154b; color:#fff; padding:8px 12px;
        margin:3px 0; border-radius:4px; cursor:grab;
        font-size:14px; border:1px solid #5e3060;
    }
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child li:hover {
        background:#5a1d5b;
    }
    /* 게시글 카드 */
    .post-title   { font-size:15px; font-weight:600; color:#1d1c1d; }
    .post-preview { font-size:13px; color:#616061; margin-top:2px; }
    .post-meta    { font-size:12px; color:#97979a; margin-top:6px; }
    /* 댓글 */
    .comment-block {
        border-left:3px solid #e8e8e8;
        padding:6px 12px; margin:6px 0;
        background:#fafafa; border-radius:0 6px 6px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    if not st.session_state.board_loaded:
        st.header("🏛️ 팀 커뮤니티 게시판")
        st.warning("⚠️ 구글 시트에서 게시판 데이터를 가져오기 전입니다.")
        if st.button("🔄 게시판 데이터 불러오기", type="primary", use_container_width=True):
            load_community_data()
            st.rerun()

    else:
        cat_df    = st.session_state.cat_db.copy()
        full_p_db = st.session_state.post_db.copy()

        if "parent_id" not in cat_df.columns:
            cat_df["parent_id"] = ""

        # ── 헬퍼 ─────────────────────────────────────────────────────
        def get_channels(df):
            return df[df["parent_id"] == ""].reset_index(drop=True)

        def get_sub_cats(df, ch_id):
            return df[df["parent_id"] == ch_id].reset_index(drop=True)

        def get_display_posts():
            ch_id_l = st.session_state.sel_channel_id
            sc_id_l = st.session_state.sel_sub_cat_id
            if ch_id_l is None:
                return full_p_db
            if sc_id_l is not None:
                return full_p_db[full_p_db["category_id"] == sc_id_l]
            sub_ids = cat_df[cat_df["parent_id"] == ch_id_l]["id"].tolist()
            return full_p_db[full_p_db["category_id"].isin([ch_id_l] + sub_ids)]

        def save_categories(new_cat_df):
            conn.update(
                spreadsheet=SHEET_URL, worksheet="categories",
                data=pd.DataFrame(new_cat_df, columns=["id","name","parent_id"]).astype(str),
            )
            st.session_state.cat_db = new_cat_df.reset_index(drop=True)
            st.session_state.force_refresh = True

        channels = get_channels(st.session_state.cat_db)
        ch_id = st.session_state.sel_channel_id
        sc_id = st.session_state.sel_sub_cat_id

        col_sidebar, col_main = st.columns([1, 3.5], gap="small")

        # ════════════════════════════════════════════════════════════
        # 아웃채널 영역 (사이드바)
        # ════════════════════════════════════════════════════════════
        with col_sidebar:
            st.markdown(
                "<div style='color:#fff;font-size:18px;font-weight:700;padding:8px 8px 4px;'>⛪ RW 미디어팀</div>",
                unsafe_allow_html=True,
            )

            # 전체 보기 버튼
            is_all = ch_id is None
            if st.button(
                ("🔵 " if is_all else "   ") + "# 전체 보기",
                key="btn_ch_all",
                use_container_width=True,
                type="primary" if is_all else "secondary",
            ):
                st.session_state.sel_channel_id  = None
                st.session_state.sel_sub_cat_id  = None
                st.session_state.comm_write_mode = False
                st.session_state.view_post_id    = None
                st.rerun()

            # 드래그 가능한 채널 목록 (현재 채널 / 모든 채널 두 컨테이너)
            if not channels.empty:
                ch_names_all = list(channels["name"].values)
                current_name = None
                if ch_id:
                    row = channels[channels["id"] == ch_id]
                    if not row.empty:
                        current_name = row["name"].values[0]

                if current_name and current_name in ch_names_all:
                    current_items = [current_name]
                    other_items   = [n for n in ch_names_all if n != current_name]
                else:
                    current_items = []
                    other_items   = list(ch_names_all)

                try:
                    from streamlit_sortables import sort_items

                    result = sort_items(
                        [
                            {"header": "🔵 현재 채널",            "items": current_items},
                            {"header": "📂 채널 (드래그로 이동)", "items": other_items},
                        ],
                        multi_containers=True,
                        direction="vertical",
                        key="ch_sort_mc",
                    )

                    new_curr = result[0]["items"] if len(result) > 0 else []
                    new_oth  = result[1]["items"] if len(result) > 1 else []

                    if new_curr != current_items or new_oth != other_items:
                        # 현재 채널 컨테이너에 여러 개 들어오면 첫 번째만 현재로, 나머지는 목록으로
                        if new_curr:
                            new_sel_name = new_curr[0]
                            overflow     = new_curr[1:]
                            final_others = overflow + new_oth
                        else:
                            new_sel_name = None
                            final_others = new_oth

                        new_sel_id = None
                        if new_sel_name:
                            mch = channels[channels["name"] == new_sel_name]
                            if not mch.empty:
                                new_sel_id = mch["id"].values[0]

                        final_order = ([new_sel_name] if new_sel_name else []) + final_others
                        name_to_row = {r["name"]: r.to_dict() for _, r in channels.iterrows()}
                        new_channels_df = pd.DataFrame(
                            [name_to_row[n] for n in final_order if n in name_to_row]
                        ).reset_index(drop=True)
                        non_ch = st.session_state.cat_db[st.session_state.cat_db["parent_id"] != ""]
                        new_cat_df = pd.concat([new_channels_df, non_ch], ignore_index=True)

                        if require_conn():
                            save_categories(new_cat_df)
                            st.session_state.sel_channel_id  = new_sel_id
                            st.session_state.sel_sub_cat_id  = None
                            st.session_state.comm_write_mode = False
                            st.session_state.view_post_id    = None
                            st.rerun()

                except ImportError:
                    # 폴백: 클릭형 버튼 + ↑↓ 순서 변경
                    st.caption("⚠️ 드래그 기능: `pip install streamlit-sortables`")
                    for i, (_, ch) in enumerate(channels.iterrows()):
                        is_sel = ch_id == ch["id"]
                        c_btn, c_up, c_dn = st.columns([5, 1, 1])
                        with c_btn:
                            if st.button(
                                ("🔵 " if is_sel else "   ") + f"# {ch['name']}",
                                key=f"btn_ch_{ch['id']}",
                                use_container_width=True,
                                type="primary" if is_sel else "secondary",
                            ):
                                st.session_state.sel_channel_id  = ch["id"]
                                st.session_state.sel_sub_cat_id  = None
                                st.session_state.comm_write_mode = False
                                st.session_state.view_post_id    = None
                                st.rerun()
                        with c_up:
                            if i > 0 and st.button("↑", key=f"up_{ch['id']}", use_container_width=True):
                                rows = [r.to_dict() for _, r in channels.iterrows()]
                                rows[i], rows[i-1] = rows[i-1], rows[i]
                                new_channels = pd.DataFrame(rows).reset_index(drop=True)
                                non_ch = st.session_state.cat_db[st.session_state.cat_db["parent_id"] != ""]
                                new_cat = pd.concat([new_channels, non_ch], ignore_index=True)
                                if require_conn():
                                    save_categories(new_cat)
                                    st.rerun()
                        with c_dn:
                            if i < len(channels) - 1 and st.button("↓", key=f"dn_{ch['id']}", use_container_width=True):
                                rows = [r.to_dict() for _, r in channels.iterrows()]
                                rows[i], rows[i+1] = rows[i+1], rows[i]
                                new_channels = pd.DataFrame(rows).reset_index(drop=True)
                                non_ch = st.session_state.cat_db[st.session_state.cat_db["parent_id"] != ""]
                                new_cat = pd.concat([new_channels, non_ch], ignore_index=True)
                                if require_conn():
                                    save_categories(new_cat)
                                    st.rerun()

            # 채널 추가
            st.markdown("<hr style='border-color:#5e3060;margin:8px 0;'>", unsafe_allow_html=True)

            if not st.session_state.show_add_ch:
                if st.button("➕ 채널 추가", key="btn_open_add_ch", use_container_width=True):
                    st.session_state.show_add_ch = True
                    st.rerun()
            else:
                new_ch_name = st.text_input("새 채널 이름", key="new_ch_input",
                                            placeholder="채널명 입력", label_visibility="collapsed")
                ca1, ca2 = st.columns(2)
                if ca1.button("추가", key="confirm_add_ch", type="primary"):
                    if new_ch_name.strip() and require_conn():
                        new_ch  = pd.DataFrame([{"id": str(int(time.time()*1000)),
                                                 "name": new_ch_name.strip(),
                                                 "parent_id": ""}])
                        new_cat = pd.concat([st.session_state.cat_db, new_ch], ignore_index=True)
                        save_categories(new_cat)
                        st.session_state.show_add_ch = False
                        st.rerun()
                if ca2.button("취소", key="cancel_add_ch"):
                    st.session_state.show_add_ch = False
                    st.rerun()

        # ════════════════════════════════════════════════════════════
        # 인채널 영역 (메인 콘텐츠)
        # ════════════════════════════════════════════════════════════
        with col_main:
            # 현재 위치 헤더
            if ch_id is None:
                header_text = "전체 보기"
            else:
                ch_row  = st.session_state.cat_db[st.session_state.cat_db["id"] == ch_id]
                ch_name = ch_row["name"].values[0] if not ch_row.empty else "채널"
                if sc_id is not None:
                    sc_row  = st.session_state.cat_db[st.session_state.cat_db["id"] == sc_id]
                    sc_name = sc_row["name"].values[0] if not sc_row.empty else ""
                    header_text = f"{ch_name}  /  📁 {sc_name}"
                else:
                    header_text = ch_name

            st.markdown(
                f"<div style='font-size:20px;font-weight:700;padding-bottom:4px;'># {header_text}</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<hr style='margin:4px 0 12px;'>", unsafe_allow_html=True)

            # ── 폴더 영역 (Notion 페이지 스타일) ───────────────────
            # 채널 진입 + 글쓰기/상세 모드가 아닐 때만 표시
            show_folders = (
                ch_id is not None
                and not st.session_state.comm_write_mode
                and st.session_state.view_post_id is None
            )
            if show_folders:
                sub_cats = get_sub_cats(st.session_state.cat_db, ch_id)

                st.markdown(
                    "<div style='color:#3f0e40;font-size:13px;font-weight:600;margin:4px 0;'>📂 폴더 (페이지)</div>",
                    unsafe_allow_html=True,
                )

                num_folders = len(sub_cats)
                total_cells = num_folders + 2  # 전체 + 폴더들 + 추가
                btn_cols = st.columns(max(total_cells, 4))

                # 전체 폴더
                is_all_sc = sc_id is None
                if btn_cols[0].button(
                    ("📁 " if is_all_sc else "📂 ") + "전체",
                    key="sc_pill_all",
                    use_container_width=True,
                    type="primary" if is_all_sc else "secondary",
                ):
                    st.session_state.sel_sub_cat_id = None
                    st.rerun()

                # 각 폴더
                for i, (_, sc) in enumerate(sub_cats.iterrows()):
                    is_active = sc_id == sc["id"]
                    if btn_cols[i + 1].button(
                        ("📁 " if is_active else "📂 ") + sc["name"],
                        key=f"sc_pill_{sc['id']}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                    ):
                        st.session_state.sel_sub_cat_id = sc["id"]
                        st.rerun()

                # 폴더 추가 버튼
                if btn_cols[num_folders + 1].button(
                    "➕ 폴더",
                    key="sc_pill_add",
                    use_container_width=True,
                ):
                    st.session_state.show_add_sc = not st.session_state.show_add_sc
                    st.rerun()

                # 폴더 추가 입력란
                if st.session_state.show_add_sc:
                    cf1, cf2, cf3 = st.columns([4, 1, 1])
                    with cf1:
                        new_sc_name = st.text_input(
                            "폴더명", key="new_sc_input",
                            placeholder="새 폴더(파트) 이름 입력",
                            label_visibility="collapsed",
                        )
                    with cf2:
                        if st.button("추가", key="confirm_sc", type="primary", use_container_width=True):
                            if new_sc_name.strip() and require_conn():
                                new_sc  = pd.DataFrame([{
                                    "id": str(int(time.time()*1000)),
                                    "name": new_sc_name.strip(),
                                    "parent_id": ch_id,
                                }])
                                new_cat = pd.concat([st.session_state.cat_db, new_sc], ignore_index=True)
                                save_categories(new_cat)
                                st.session_state.show_add_sc = False
                                st.rerun()
                    with cf3:
                        if st.button("취소", key="cancel_sc", use_container_width=True):
                            st.session_state.show_add_sc = False
                            st.rerun()

                # 현재 폴더 삭제 (특정 폴더 선택 중일 때만)
                if sc_id is not None:
                    if st.button("🗑️ 현재 폴더 삭제", key="del_sc_main", type="secondary"):
                        if require_conn():
                            new_cat = st.session_state.cat_db[st.session_state.cat_db["id"] != sc_id].reset_index(drop=True)
                            save_categories(new_cat)
                            st.session_state.sel_sub_cat_id = None
                            st.rerun()

                st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)

            # ── 글쓰기 모드 ─────────────────────────────────────────
            if st.session_state.comm_write_mode:
                if st.button("⬅️ 목록으로", key="back_from_write"):
                    st.session_state.comm_write_mode = False
                    st.rerun()

                st.subheader("✏️ 새 게시글 작성")

                # 글쓰기 카테고리 결정
                cat_options = []
                if ch_id is not None:
                    sub_cats_w = get_sub_cats(st.session_state.cat_db, ch_id)
                    if not sub_cats_w.empty:
                        cat_options = [(r["id"], r["name"]) for _, r in sub_cats_w.iterrows()]
                        if sc_id is not None and any(c[0] == sc_id for c in cat_options):
                            default_cat_idx = next(i for i, c in enumerate(cat_options) if c[0] == sc_id)
                        else:
                            default_cat_idx = 0
                    else:
                        ch_row2 = st.session_state.cat_db[st.session_state.cat_db["id"] == ch_id]
                        ch_name2 = ch_row2["name"].values[0] if not ch_row2.empty else "채널"
                        cat_options = [(ch_id, ch_name2)]
                        default_cat_idx = 0
                else:
                    all_chs = get_channels(st.session_state.cat_db)
                    cat_options = [(r["id"], r["name"]) for _, r in all_chs.iterrows()]
                    default_cat_idx = 0

                if not cat_options:
                    st.warning("⚠️ 먼저 채널을 추가해주세요.")
                else:
                    with st.form("write_post", clear_on_submit=True):
                        cat_labels   = [label for _, label in cat_options]
                        chosen_label = st.selectbox("게시 위치 (폴더) 선택", cat_labels, index=default_cat_idx)
                        chosen_cat_id = cat_options[cat_labels.index(chosen_label)][0]

                        p_title   = st.text_input("제목 *")
                        p_content = st.text_area("내용 *", height=200)
                        p_links   = st.text_input("🔗 링크 첨부 (쉼표로 구분, 유튜브 가능)")
                        p_files   = st.file_uploader("🖼️ 사진 업로드", type=["png","jpg","jpeg"], accept_multiple_files=True)

                        if st.form_submit_button("📝 게시글 등록", type="primary", use_container_width=True):
                            if not require_conn(): st.stop()
                            if not p_title.strip() or not p_content.strip():
                                st.error("제목과 내용을 모두 입력해 주세요.")
                            elif (not full_p_db.empty and
                                  p_title.strip() in full_p_db[full_p_db["category_id"] == chosen_cat_id]["title"].values):
                                st.warning("같은 위치에 동일한 제목의 게시글이 있습니다.")
                            else:
                                with st.spinner("⏳ 등록 중..."):
                                    p_id          = str(int(time.time()*1000))
                                    uploaded_urls = [u for f in p_files if (u := upload_image_to_storage(f))]
                                    new_p = pd.DataFrame([{
                                        "id": p_id, "category_id": chosen_cat_id,
                                        "title": p_title.strip(), "content": p_content,
                                        "links": p_links or "",
                                        "image_urls": ",".join(uploaded_urls),
                                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    }])
                                    updated_p = pd.concat([full_p_db, new_p], ignore_index=True)
                                    conn.update(spreadsheet=SHEET_URL, worksheet="posts",
                                                data=pd.DataFrame(updated_p, columns=["id","category_id","title","content","links","image_urls","created_at"]).astype(str))
                                    st.session_state.post_db       = updated_p
                                    st.session_state.force_refresh = True
                                    st.session_state.comm_write_mode = False
                                    st.success("🎉 게시글이 등록되었습니다!")
                                    time.sleep(0.8)
                                    st.rerun()

            # ── 게시글 상세 ─────────────────────────────────────────
            elif st.session_state.view_post_id is not None:
                pid = st.session_state.view_post_id

                if st.button("⬅️ 목록으로 돌아가기", key="back_from_detail"):
                    st.session_state.view_post_id = None
                    st.rerun()

                if full_p_db.empty or pid not in full_p_db["id"].values:
                    st.warning("게시글을 찾을 수 없습니다. 목록으로 돌아가세요.")
                    st.stop()

                post  = full_p_db[full_p_db["id"] == pid].iloc[0]
                p_cat = st.session_state.cat_db[st.session_state.cat_db["id"] == post["category_id"]]
                if not p_cat.empty:
                    p_cat_row = p_cat.iloc[0]
                    if p_cat_row["parent_id"]:
                        par = st.session_state.cat_db[st.session_state.cat_db["id"] == p_cat_row["parent_id"]]
                        par_name = par["name"].values[0] if not par.empty else ""
                        breadcrumb = f"{par_name} / 📁 {p_cat_row['name']}"
                    else:
                        breadcrumb = p_cat_row["name"]
                else:
                    breadcrumb = "미분류"

                st.caption(f"# {breadcrumb}")
                st.markdown(f"## {post['title']}")
                st.caption(f"🕐 {post['created_at']}")
                st.markdown("---")

                edit_mode = st.checkbox("✏️ 이 글 수정하기", key=f"e_mode_{pid}")
                if edit_mode:
                    with st.form(f"form_ed_{pid}"):
                        ed_title   = st.text_input("제목 변경", value=post["title"])
                        ed_content = st.text_area("내용 변경", value=post["content"], height=200)
                        ed_links   = st.text_input("링크 변경", value=post["links"])
                        if st.form_submit_button("💾 수정 완료 저장", type="primary"):
                            if not require_conn(): st.stop()
                            full_p_db.loc[full_p_db["id"] == pid, ["title","content","links"]] = [
                                str(ed_title), str(ed_content), str(ed_links)
                            ]
                            conn.update(spreadsheet=SHEET_URL, worksheet="posts",
                                        data=pd.DataFrame(full_p_db, columns=["id","category_id","title","content","links","image_urls","created_at"]).astype(str))
                            st.session_state.post_db       = full_p_db
                            st.session_state.force_refresh = True
                            st.rerun()
                else:
                    st.write(post["content"])
                    if isinstance(post["image_urls"], str) and post["image_urls"].strip():
                        for url in post["image_urls"].split(","):
                            if url.strip():
                                st.image(url.strip(), use_container_width=True)
                    if isinstance(post["links"], str) and post["links"].strip():
                        for link in post["links"].split(","):
                            lnk = link.strip()
                            if not lnk: continue
                            if "youtube.com" in lnk or "youtu.be" in lnk or any(lnk.lower().endswith(e) for e in (".mp4",".mov",".avi",".webm")):
                                st.video(lnk)
                            else:
                                st.link_button("🔗 첨부 링크 열기", lnk)

                st.markdown("---")

                # 댓글
                st.markdown("**💬 댓글**")
                comm_db = st.session_state.comm_db.copy()
                current_post_id = clean_id(str(pid))

                if not comm_db.empty:
                    comm_db["post_id"] = comm_db["post_id"].apply(clean_id)
                    p_comms = comm_db[comm_db["post_id"] == current_post_id]
                else:
                    p_comms = pd.DataFrame()

                if p_comms.empty:
                    st.caption("아직 작성된 댓글이 없습니다.")
                else:
                    for _, citem in p_comms.iterrows():
                        cid = clean_id(citem["id"])
                        st.markdown(
                            f"<div class='comment-block'>"
                            f"<span style='font-weight:600;font-size:13px;'>{citem['author']}</span>"
                            f" <span style='color:#97979a;font-size:12px;'>({citem['created_at']})</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        c_col1, c_col2 = st.columns([6, 1])
                        with c_col1:
                            c_edit_active = st.session_state.get(f"cedit_act_{cid}", False)
                            if c_edit_active:
                                new_body = st.text_area("댓글 수정", value=citem["content"],
                                                        key=f"txt_cedit_{cid}", height=70)
                                cs1, cs2 = st.columns(2)
                                if cs1.button("💾 완료", key=f"btn_csave_{cid}", type="primary"):
                                    if not require_conn(): st.stop()
                                    raw = st.session_state.comm_db.copy()
                                    raw["id"] = raw["id"].apply(clean_id)
                                    raw.loc[raw["id"] == cid, "content"] = str(new_body.strip())
                                    conn.update(spreadsheet=SHEET_URL, worksheet="comments",
                                                data=pd.DataFrame(raw, columns=["id","post_id","author","content","created_at"]).astype(str))
                                    st.session_state.comm_db = raw
                                    st.session_state[f"cedit_act_{cid}"] = False
                                    st.session_state.force_refresh = True
                                    time.sleep(0.3)
                                    st.rerun()
                                if cs2.button("❌ 취소", key=f"btn_ccancel_{cid}"):
                                    st.session_state[f"cedit_act_{cid}"] = False
                                    st.rerun()
                            else:
                                st.write(citem["content"])
                        with c_col2:
                            if st.button("✏️", key=f"edit_c_{cid}", help="수정"):
                                st.session_state[f"cedit_act_{cid}"] = True
                                st.rerun()
                            if st.button("🗑️", key=f"del_c_{cid}", help="삭제"):
                                if not require_conn(): st.stop()
                                raw = st.session_state.comm_db.copy()
                                raw["id"] = raw["id"].apply(clean_id)
                                updated_cm = raw[raw["id"] != cid]
                                conn.update(spreadsheet=SHEET_URL, worksheet="comments",
                                            data=pd.DataFrame(updated_cm, columns=["id","post_id","author","content","created_at"]).astype(str))
                                st.session_state.comm_db       = updated_cm
                                st.session_state.force_refresh = True
                                time.sleep(0.3)
                                st.rerun()

                st.markdown("---")
                with st.form(f"comm_{pid}", clear_on_submit=True):
                    st.markdown("**💬 댓글 달기**")
                    member_names    = ["선택하세요"] + list(st.session_state.members_db["name"].values) + ["[직접 입력]"]
                    selected_author = st.selectbox("작성자 선택", member_names)
                    custom_auth     = ""
                    if selected_author == "[직접 입력]":
                        custom_auth = st.text_input("작성자명 직접 입력", placeholder="이름 입력")
                    c_txt = st.text_area("댓글 내용", height=70, placeholder="댓글을 입력하세요...")

                    if st.form_submit_button("댓글 등록", type="primary", use_container_width=True):
                        if not require_conn(): st.stop()
                        final_author = custom_auth.strip() if selected_author == "[직접 입력]" else (
                            selected_author if selected_author != "선택하세요" else "")
                        if not final_author:
                            st.error("❌ 작성자를 선택하거나 직접 입력해 주세요.")
                        elif not c_txt.strip():
                            st.error("❌ 댓글 내용을 입력해 주세요.")
                        else:
                            new_c = pd.DataFrame([{
                                "id":         str(int(time.time()*1000)),
                                "post_id":    current_post_id,
                                "author":     final_author,
                                "content":    c_txt.strip(),
                                "created_at": datetime.now().strftime("%m-%d %H:%M"),
                            }])
                            updated_cm = pd.concat([st.session_state.comm_db, new_c], ignore_index=True)
                            conn.update(spreadsheet=SHEET_URL, worksheet="comments",
                                        data=pd.DataFrame(updated_cm, columns=["id","post_id","author","content","created_at"]).astype(str))
                            st.session_state.comm_db       = updated_cm
                            st.session_state.force_refresh = True
                            st.success("댓글이 등록되었습니다!")
                            time.sleep(0.3)
                            st.rerun()

                st.markdown("---")
                if st.button("🗑️ 이 게시글 전체 삭제", type="secondary", key="del_post_btn"):
                    if not require_conn(): st.stop()
                    updated_p = full_p_db[full_p_db["id"] != pid]
                    conn.update(spreadsheet=SHEET_URL, worksheet="posts",
                                data=pd.DataFrame(updated_p, columns=["id","category_id","title","content","links","image_urls","created_at"]).astype(str))
                    st.session_state.post_db = updated_p
                    raw = st.session_state.comm_db.copy()
                    raw["post_id"] = raw["post_id"].apply(clean_id)
                    updated_cm = raw[raw["post_id"] != current_post_id]
                    conn.update(spreadsheet=SHEET_URL, worksheet="comments",
                                data=pd.DataFrame(updated_cm, columns=["id","post_id","author","content","created_at"]).astype(str))
                    st.session_state.comm_db       = updated_cm
                    st.session_state.view_post_id  = None
                    st.session_state.force_refresh = True
                    st.success("게시글과 관련 댓글이 삭제되었습니다.")
                    time.sleep(0.8)
                    st.rerun()

            # ── 게시글 목록 ─────────────────────────────────────────
            else:
                # 채널 진입 시에만 새 글 작성 버튼 표시
                if ch_id is not None:
                    if st.button("✏️ 새 글 작성", key="btn_write_main", type="primary"):
                        st.session_state.comm_write_mode = True
                        st.rerun()
                    st.write("")

                display_posts = get_display_posts()

                if display_posts.empty:
                    if ch_id is None:
                        st.info("📭 게시글이 없습니다.")
                    elif sc_id is not None:
                        st.info("📭 이 폴더에 아직 게시글이 없습니다. 새 글을 작성해 보세요!")
                    else:
                        st.info("📭 이 채널에 아직 게시글이 없습니다. 폴더(파트)를 만들거나 새 글을 작성해 보세요!")
                else:
                    for _, post in display_posts[::-1].iterrows():
                        p_cat = st.session_state.cat_db[st.session_state.cat_db["id"] == post["category_id"]]
                        if not p_cat.empty:
                            p_cat_row = p_cat.iloc[0]
                            if p_cat_row["parent_id"]:
                                par = st.session_state.cat_db[st.session_state.cat_db["id"] == p_cat_row["parent_id"]]
                                par_name = par["name"].values[0] if not par.empty else ""
                                cat_label = f"{par_name} / 📁 {p_cat_row['name']}"
                            else:
                                cat_label = p_cat_row["name"]
                        else:
                            cat_label = "미분류"

                        comm_db_tmp = st.session_state.comm_db.copy()
                        if not comm_db_tmp.empty:
                            comm_db_tmp["post_id"] = comm_db_tmp["post_id"].apply(clean_id)
                            c_cnt = len(comm_db_tmp[comm_db_tmp["post_id"] == clean_id(str(post["id"]))])
                        else:
                            c_cnt = 0

                        preview_text = str(post["content"])
                        if len(preview_text) > 100:
                            preview_text = preview_text[:100] + "..."

                        with st.container(border=True):
                            col_info, col_open = st.columns([5, 1])
                            with col_info:
                                st.markdown(
                                    f"<div class='post-title'>{post['title']}</div>"
                                    f"<div class='post-preview'>{preview_text}</div>"
                                    f"<div class='post-meta'>📁 {cat_label} &nbsp;·&nbsp; 💬 댓글 {c_cnt}개 &nbsp;·&nbsp; 🕐 {post['created_at']}</div>",
                                    unsafe_allow_html=True,
                                )
                            with col_open:
                                st.write("")
                                if st.button("열기 →", key=f"goto_{post['id']}", use_container_width=True):
                                    st.session_state.view_post_id    = post["id"]
                                    st.session_state.comm_write_mode = False
                                    st.rerun()
