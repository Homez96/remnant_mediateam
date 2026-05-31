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
    # FIX #2: att_loaded → members_loaded / attend_loaded 로 분리
    "members_loaded":    False,
    "attend_loaded":     False,
    "board_loaded":      False,
    "force_refresh":     False,
    "current_filter":    "전체",
    "selected_date_val": date.today(),
    "view_post_id":      None,
    "comm_write_mode":   False,
    "sel_channel_id":    None,
    "sel_sub_cat_id":    None,
    "show_add_ch":       False,
    "show_add_sc":       False,
    # 포지션 배치 관리 (신규)
    "pos_fixed_image":   None,   # {"id","url","label"} 또는 None
    "pos_pins":          [],     # [{"id","label","x","y","desc","image_url","post_ids":[]}]
    "pos_active_pin_id": None,
    "pos_edit_pin_id":   None,
    "pos_add_mode":      False,
    "pos_assign_date":   date.today(),
    "pos_assignments":   [],
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
_conn_error = ""
try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    _conn_error = str(e)

def require_conn() -> bool:
    if conn is None:
        st.error(f"구글 시트 연결 오류: {_conn_error}" if _conn_error else "구글 시트 연결이 필요합니다. 연결 설정을 확인해 주세요.")
        return False
    return True

def get_ttl() -> int:
    # FIX #1: force_refresh 플래그를 여기서 소비하지 않음 — 로드 함수 안에서만 리셋
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
    try:
        ttl = get_ttl()
        df_m = conn.read(spreadsheet=SHEET_URL, worksheet="members",    ttl=ttl)
        df_a = conn.read(spreadsheet=SHEET_URL, worksheet="attendance", ttl=ttl)
        st.session_state.members_db   = clean_df(df_m, {"id":"str","name":"str","position":"str"}).sort_values("name").reset_index(drop=True)
        st.session_state.attend_db    = clean_df(df_a, {"date":"str","id":"str","status":"str","meal":"bool","reason":"str"})
        # FIX #2: 두 플래그 모두 설정
        st.session_state.members_loaded = True
        st.session_state.attend_loaded  = True
        st.session_state.force_refresh  = False  # FIX #1: 로드 완료 후에만 리셋
    except Exception as e:
        msg = "🛑 구글 제한이 걸렸습니다. 잠시 후 다시 시도해 주세요." if "429" in str(e) else f"출석 로드 실패: {e}"
        st.error(msg)

def load_members_only():
    """멤버 목록만 조용히 불러옴 (포지션 배치 탭용)"""
    if not require_conn():
        return False
    try:
        df_m = conn.read(spreadsheet=SHEET_URL, worksheet="members", ttl=get_ttl())
        st.session_state.members_db     = clean_df(df_m, {"id":"str","name":"str","position":"str"}).sort_values("name").reset_index(drop=True)
        st.session_state.members_loaded = True  # FIX #2: members_loaded만 설정 (attend_loaded는 건드리지 않음)
        st.session_state.force_refresh  = False
        return True
    except Exception as e:
        st.error(f"멤버 로드 실패: {e}")
        return False

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
            st.session_state.cat_db      = cat_db
            st.session_state.post_db     = clean_df(df_p,  {"id":"str","category_id":"str","title":"str","content":"str","links":"str","image_urls":"str","created_at":"str"})
            st.session_state.comm_db     = clean_df(df_cm, {"id":"str","post_id":"str","author":"str","content":"str","created_at":"str"})
            st.session_state.board_loaded   = True
            st.session_state.members_loaded = True  # FIX #2
            st.session_state.force_refresh  = False  # FIX #1
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
        st.session_state.view_post_id    = None
        st.session_state.comm_write_mode = False
        # FIX #5: 페이지 이동 시 폴더 추가창도 닫기
        st.session_state.show_add_ch     = False
        st.session_state.show_add_sc     = False
        st.rerun()
    st.write("---")
    if st.button("🔄 앱 전체 강제 새로고침"):
        st.session_state.force_refresh   = True
        st.session_state.members_loaded  = False  # FIX #2
        st.session_state.attend_loaded   = False  # FIX #2
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

    # FIX #2: attend_loaded 기준으로 판단
    if not st.session_state.attend_loaded:
        st.warning("⚠️ 구글 시트에서 출석 데이터를 가져오기 전입니다.")
        if st.button("🔄 출석 데이터 불러오기", type="primary", use_container_width=True):
            with st.spinner("⏳ 출석 데이터 불러오는 중..."):
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
# 7. 포지션 배치 관리 — 인터파크 스타일 핀 맵 + 우측 배정 패널
# ══════════════════════════════════════════════════════════════════════
elif st.session_state.page == "🎬 포지션 배치 관리":

    # ── CSS ─────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');
    .pos-root * { font-family: 'Noto Sans KR', sans-serif; box-sizing: border-box; }

    .pos-header {
        background: linear-gradient(135deg,#0f1923 0%,#1a2b3c 100%);
        color:#fff; padding:16px 22px 12px; border-radius:12px; margin-bottom:14px;
        box-shadow:0 4px 20px rgba(0,0,0,0.3);
    }
    .pos-header h2 { margin:0; font-size:1.2rem; font-weight:900; letter-spacing:-0.5px; }
    .pos-header p  { margin:2px 0 0; font-size:0.78rem; color:#7faacc; }

    .map-outer {
        background:#111820; border-radius:14px; padding:10px;
        box-shadow:0 8px 32px rgba(0,0,0,0.4);
    }
    .map-stage {
        background:linear-gradient(180deg,#1b2e42 0%,#0d1b2a 100%);
        border-radius:6px 6px 0 0; text-align:center; padding:7px 0 5px;
        font-size:0.72rem; font-weight:700; letter-spacing:4px; color:#5a8eb5;
        margin-bottom:6px; border-bottom:2px solid #1e3a5f;
    }
    .map-wrap { position:relative; display:block; width:100%; border-radius:8px; overflow:hidden; }
    .map-wrap img { width:100%; display:block; border-radius:8px; }

    .pin-outer {
        position:absolute; transform:translate(-50%,-100%);
        display:flex; flex-direction:column; align-items:center;
        z-index:20; pointer-events:none;
    }
    .pin-circle {
        width:34px; height:34px; border-radius:50%;
        display:flex; align-items:center; justify-content:center;
        font-size:0.65rem; font-weight:800; color:#fff;
        border:2.5px solid rgba(255,255,255,0.5);
        box-shadow:0 2px 8px rgba(0,0,0,0.5);
    }
    .pin-circle.idle     { background:linear-gradient(135deg,#2563eb,#1d4ed8); }
    .pin-circle.active   { background:linear-gradient(135deg,#f59e0b,#d97706); border-color:#fff; }
    .pin-circle.assigned { background:linear-gradient(135deg,#16a34a,#15803d); }
    .pin-needle { width:3px; height:9px; border-radius:0 0 3px 3px; margin-top:-2px; }
    .pin-needle.idle     { background:#2563eb; }
    .pin-needle.active   { background:#f59e0b; }
    .pin-needle.assigned { background:#16a34a; }
    .pin-label {
        background:rgba(0,0,0,0.82); color:#fff;
        font-size:0.58rem; font-weight:700; padding:2px 5px;
        border-radius:4px; white-space:nowrap; margin-top:2px;
    }

    .legend {
        display:flex; gap:12px; flex-wrap:wrap; padding:7px 10px;
        background:rgba(255,255,255,0.04); border-radius:8px; margin-top:8px;
    }
    .legend-item { display:flex; align-items:center; gap:5px; font-size:0.72rem; color:#8aaccc; font-weight:500; }
    .legend-dot  { width:12px; height:12px; border-radius:50%; border:2px solid rgba(255,255,255,0.3); }

    .detail-panel {
        background:linear-gradient(160deg,#12203a 0%,#0d1825 100%);
        border:1px solid #1e3a5f; border-radius:14px; padding:18px; margin-top:10px;
        animation:slideDown 0.22s ease; box-shadow:0 8px 24px rgba(0,0,0,0.4);
    }
    @keyframes slideDown {
        from { opacity:0; transform:translateY(-10px); }
        to   { opacity:1; transform:translateY(0); }
    }
    .detail-title { font-size:1rem; font-weight:800; color:#f0f6ff; margin:0 0 3px; }
    .detail-tag   {
        display:inline-block; background:#1e3a5f; color:#7faacc;
        font-size:0.68rem; font-weight:700; padding:2px 8px;
        border-radius:12px; margin-bottom:8px;
    }
    .detail-desc {
        font-size:0.83rem; color:#a8c4de; line-height:1.65; white-space:pre-wrap;
        border-left:3px solid #1e3a5f; padding-left:10px; margin:6px 0;
    }

    .assign-panel {
        background:#f8fafc; border-radius:14px; border:1px solid #e2e8f0;
        padding:16px; height:fit-content;
    }
    .assign-title {
        font-size:0.95rem; font-weight:800; color:#1e293b;
        margin:0 0 12px; padding-bottom:8px; border-bottom:2px solid #e2e8f0;
    }
    .assign-card {
        background:linear-gradient(135deg,#1e3a5f,#0f2340); border-radius:10px;
        padding:9px 13px; margin:4px 0;
        display:flex; align-items:center; justify-content:space-between; color:#fff;
    }
    .assign-card .aname { font-size:0.88rem; font-weight:700; }
    .assign-card .apos  { font-size:0.75rem; color:#7faacc; margin-top:1px; }

    .add-banner {
        background:linear-gradient(135deg,#f59e0b,#d97706); color:#fff;
        border-radius:10px; padding:9px 14px; font-size:0.82rem; font-weight:700;
        text-align:center; margin-bottom:8px;
        animation:pulse 1.6s ease-in-out infinite;
    }
    @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.72;} }
    </style>
    """, unsafe_allow_html=True)

    # ── 헬퍼 ────────────────────────────────────────────────────────
    def _get_pin(pid):
        return next((p for p in st.session_state.pos_pins if p["id"] == pid), None)

    def _save_pin(pin):
        pins = st.session_state.pos_pins
        idx  = next((i for i, p in enumerate(pins) if p["id"] == pin["id"]), -1)
        if idx >= 0: pins[idx] = pin
        else:        pins.append(pin)
        st.session_state.pos_pins = pins

    def _del_pin(pid):
        st.session_state.pos_pins = [p for p in st.session_state.pos_pins if p["id"] != pid]
        if st.session_state.pos_active_pin_id == pid: st.session_state.pos_active_pin_id = None
        if st.session_state.pos_edit_pin_id   == pid: st.session_state.pos_edit_pin_id   = None

    def _is_assigned(label):
        return any(a["position"] == label for a in st.session_state.pos_assignments)

    def _all_posts():
        if st.session_state.board_loaded and not st.session_state.post_db.empty:
            return st.session_state.post_db
        return pd.DataFrame(columns=["id","category_id","title","content","created_at"])

    # ── 헤더 ────────────────────────────────────────────────────────
    st.markdown("""<div class="pos-root pos-header">
        <h2>🎬 포지션 배치 관리</h2>
        <p>배치도 핀을 눌러 포지션 정보를 확인하고, 우측에서 팀원을 배정하세요</p>
    </div>""", unsafe_allow_html=True)

    col_map, col_right = st.columns([1.6, 1], gap="medium")

    # ════════════════════════════════════════════════════════════════
    # 좌측: 배치도 + 핀 UI
    # ════════════════════════════════════════════════════════════════
    with col_map:
        fixed_img = st.session_state.pos_fixed_image

        # ── 배치도 미등록 ─────────────────────────────────────────
        if fixed_img is None:
            st.markdown("#### 🗺️ 배치도 이미지 등록")
            st.info("배치도 이미지를 한 장 등록하면 핀을 추가할 수 있습니다.")
            with st.form("fixed_img_form", clear_on_submit=True):
                img_label = st.text_input("배치도 이름", placeholder="예) 본당 예배 배치도")
                img_file  = st.file_uploader("이미지 선택", type=["png","jpg","jpeg","webp"])
                if st.form_submit_button("📌 배치도 등록", type="primary", use_container_width=True):
                    if not img_file:
                        st.error("이미지를 선택해 주세요.")
                    elif not img_label.strip():
                        st.error("배치도 이름을 입력해 주세요.")
                    else:
                        with st.spinner("업로드 중..."):
                            url = upload_image_to_storage(img_file)
                        if not url:
                            import base64 as _b64
                            _b  = _b64.b64encode(img_file.getvalue()).decode()
                            _ex = img_file.name.rsplit(".",1)[-1].lower()
                            url = f"data:image/{_ex};base64,{_b}"
                        st.session_state.pos_fixed_image = {
                            "id": str(int(time.time()*1000)),
                            "url": url, "label": img_label.strip(),
                        }
                        st.rerun()

        # ── 배치도 등록됨 ────────────────────────────────────────
        else:
            # 상단 툴바
            tb1, tb2, tb3, tb4 = st.columns([3, 1.1, 1.1, 1])
            with tb1:
                st.markdown(f"**🗺️ {fixed_img['label']}**")
            with tb2:
                add_mode = st.session_state.pos_add_mode
                if st.button(
                    "🔴 추가 중" if add_mode else "📍 핀 추가",
                    type="primary" if add_mode else "secondary",
                    use_container_width=True, key="toggle_add_mode",
                ):
                    st.session_state.pos_add_mode    = not add_mode
                    st.session_state.pos_edit_pin_id = None
                    st.rerun()
            with tb3:
                if st.button("🖼️ 이미지 변경", use_container_width=True, key="change_img"):
                    for _k2 in ("pos_fixed_image","pos_pins","pos_active_pin_id","pos_edit_pin_id","pos_add_mode"):
                        st.session_state[_k2] = None if "image" in _k2 or "id" in _k2 else ([] if "pins" in _k2 else False)
                    st.rerun()
            with tb4:
                st.markdown(
                    f"<div style='text-align:center;padding:6px 0;font-size:0.75rem;"
                    f"color:#1e3a5f;font-weight:700;'>핀 {len(st.session_state.pos_pins)}개</div>",
                    unsafe_allow_html=True
                )

            if st.session_state.pos_add_mode:
                st.markdown('<div class="add-banner">🎯 핀 추가 모드 — 아래 폼에서 포지션 이름과 좌표(%)를 입력하세요</div>', unsafe_allow_html=True)

            # ── 배치도 이미지 + 핀 오버레이 HTML ─────────────────
            pins      = st.session_state.pos_pins
            active_id = st.session_state.pos_active_pin_id

            pins_html = ""
            for pin in pins:
                assigned  = _is_assigned(pin["label"])
                is_active = active_id == pin["id"]
                cls = "active" if is_active else ("assigned" if assigned else "idle")
                short = pin["label"][:5]
                pins_html += f"""
                <div class="pin-outer" style="left:{pin['x']}%;top:{pin['y']}%;">
                    <div class="pin-circle {cls}">{short}</div>
                    <div class="pin-needle {cls}"></div>
                    <div class="pin-label">{pin['label']}</div>
                </div>"""

            map_html = f"""
            <div class="pos-root map-outer">
                <div class="map-stage">⛪ &nbsp; S T A G E &nbsp; ⛪</div>
                <div class="map-wrap">
                    <img src="{fixed_img['url']}" alt="{fixed_img['label']}" draggable="false">
                    {pins_html}
                </div>
                <div class="legend">
                    <div class="legend-item"><div class="legend-dot" style="background:#2563eb;"></div>포지션</div>
                    <div class="legend-item"><div class="legend-dot" style="background:#f59e0b;"></div>선택됨</div>
                    <div class="legend-item"><div class="legend-dot" style="background:#16a34a;"></div>배정완료</div>
                </div>
            </div>"""
            st.components.v1.html(map_html, height=500, scrolling=False)

            # ── 핀 버튼 그리드 (클릭 선택) ───────────────────────
            if pins:
                st.markdown("**📌 포지션 핀 선택**")
                _cols_n = 5
                _rows   = [pins[i:i+_cols_n] for i in range(0, len(pins), _cols_n)]
                for _row in _rows:
                    _rcols = st.columns(len(_row))
                    for _ci, _pin in enumerate(_row):
                        with _rcols[_ci]:
                            _assigned = _is_assigned(_pin["label"])
                            _active   = active_id == _pin["id"]
                            _icon     = "✅" if _assigned else ("🟠" if _active else "📍")
                            if st.button(
                                f"{_icon} {_pin['label']}",
                                key=f"pb_{_pin['id']}",
                                use_container_width=True,
                                type="primary" if _active else "secondary",
                            ):
                                st.session_state.pos_active_pin_id = (
                                    None if _active else _pin["id"]
                                )
                                st.session_state.pos_edit_pin_id = None
                                st.rerun()

            # ── 상세 패널 (토글) ──────────────────────────────────
            if active_id:
                ap = _get_pin(active_id)
                if ap:
                    assigned_name = next(
                        (a["name"] for a in st.session_state.pos_assignments
                         if a["position"] == ap["label"]), None
                    )
                    all_p = _all_posts()
                    linked = []
                    if not all_p.empty and ap.get("post_ids"):
                        for _pid in ap["post_ids"]:
                            _m = all_p[all_p["id"] == _pid]
                            if not _m.empty: linked.append(_m.iloc[0])

                    with st.container():
                        st.markdown('<div class="detail-panel">', unsafe_allow_html=True)

                        dh1, dh2 = st.columns([5, 1])
                        with dh1:
                            st.markdown(
                                f"<div class='detail-title'>📍 {ap['label']}</div>"
                                f"<div class='detail-tag'>위치 ({ap['x']:.1f}%, {ap['y']:.1f}%)</div>",
                                unsafe_allow_html=True
                            )
                        with dh2:
                            if st.button("✕", key="close_dp", use_container_width=True):
                                st.session_state.pos_active_pin_id = None
                                st.rerun()

                        if assigned_name:
                            st.success(f"✅ 현재 배정: **{assigned_name}**")

                        if ap.get("desc"):
                            st.markdown(f"<div class='detail-desc'>{ap['desc']}</div>", unsafe_allow_html=True)
                        else:
                            st.caption("설명 없음")

                        if ap.get("image_url"):
                            st.image(ap["image_url"], use_container_width=True)

                        if linked:
                            st.markdown("**🔗 연결된 게시글**")
                            for _lp in linked:
                                if st.button(f"📄 {_lp['title']}", key=f"lp_{_lp['id']}",
                                             use_container_width=True):
                                    st.session_state.page         = "🏛️ 팀 커뮤니티 게시판"
                                    st.session_state.view_post_id = _lp["id"]
                                    st.rerun()
                        else:
                            st.caption("연결된 게시글 없음")

                        de1, de2 = st.columns(2)
                        if de1.button("✏️ 핀 편집", key="edit_dp", use_container_width=True):
                            st.session_state.pos_edit_pin_id = active_id
                            st.rerun()
                        if de2.button("🗑️ 핀 삭제", key="del_dp",
                                      type="secondary", use_container_width=True):
                            _del_pin(active_id)
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

            # ── 핀 추가 폼 ───────────────────────────────────────
            if st.session_state.pos_add_mode:
                st.markdown("---")
                st.markdown("#### ➕ 새 핀 추가")
                st.caption("좌상단 (0%,0%) → 우하단 (100%,100%)")
                with st.form("add_pin_form", clear_on_submit=True):
                    af1, af2 = st.columns(2)
                    p_label  = af1.text_input("포지션 이름 *", placeholder="예) 4번 카메라")
                    p_x      = af2.number_input("X 위치 (%)", 0.0, 100.0, 50.0, 1.0)
                    af3, af4 = st.columns(2)
                    p_y      = af3.number_input("Y 위치 (%)", 0.0, 100.0, 50.0, 1.0)
                    p_desc   = af4.text_area("포지션 설명", placeholder="역할, 장비, 주의사항 등", height=78)
                    p_img_f  = st.file_uploader("포지션 사진 (선택)", type=["png","jpg","jpeg"], key="pin_img_up")

                    _ap2 = _all_posts()
                    _post_opts2 = list(_ap2["title"].values) if not _ap2.empty else []
                    p_posts = st.multiselect("🔗 관련 게시글 연결", _post_opts2, key="pin_post_link2")

                    if st.form_submit_button("📌 핀 등록", type="primary", use_container_width=True):
                        if not p_label.strip():
                            st.error("포지션 이름을 입력해 주세요.")
                        else:
                            _pu = None
                            if p_img_f:
                                _pu = upload_image_to_storage(p_img_f)
                                if not _pu:
                                    import base64 as _b64
                                    _pu = f"data:image/{p_img_f.name.rsplit('.',1)[-1].lower()};base64," + _b64.b64encode(p_img_f.getvalue()).decode()
                            _ids = []
                            if not _ap2.empty:
                                for _t in p_posts:
                                    _pm = _ap2[_ap2["title"] == _t]
                                    if not _pm.empty: _ids.append(_pm.iloc[0]["id"])
                            st.session_state.pos_pins.append({
                                "id": str(int(time.time()*1000)), "label": p_label.strip(),
                                "x": p_x, "y": p_y, "desc": p_desc.strip(),
                                "image_url": _pu, "post_ids": _ids,
                            })
                            st.session_state.pos_add_mode = False
                            st.success(f"✅ '{p_label.strip()}' 핀 등록 완료!")
                            st.rerun()

            # ── 핀 편집 폼 ───────────────────────────────────────
            epid = st.session_state.pos_edit_pin_id
            if epid:
                ep = _get_pin(epid)
                if ep:
                    st.markdown("---")
                    st.markdown(f"#### ✏️ 핀 편집 — {ep['label']}")
                    with st.form(f"edit_pin_{epid}", clear_on_submit=False):
                        ef1, ef2 = st.columns(2)
                        e_label  = ef1.text_input("포지션 이름", value=ep["label"])
                        e_x      = ef2.number_input("X (%)", 0.0, 100.0, float(ep["x"]), 1.0)
                        ef3, ef4 = st.columns(2)
                        e_y      = ef3.number_input("Y (%)", 0.0, 100.0, float(ep["y"]), 1.0)
                        e_desc   = ef4.text_area("설명", value=ep.get("desc",""), height=78)
                        e_img_f  = st.file_uploader("사진 변경", type=["png","jpg","jpeg"], key=f"epin_{epid}")

                        _eap = _all_posts()
                        _ep_opts = list(_eap["title"].values) if not _eap.empty else []
                        _ep_def  = []
                        if not _eap.empty:
                            for _pid2 in ep.get("post_ids",[]):
                                _pm2 = _eap[_eap["id"] == _pid2]
                                if not _pm2.empty: _ep_def.append(_pm2.iloc[0]["title"])
                        e_posts = st.multiselect("🔗 연결 게시글", _ep_opts, default=_ep_def, key=f"eposts_{epid}")

                        ec1, ec2 = st.columns(2)
                        if ec1.form_submit_button("💾 저장", type="primary", use_container_width=True):
                            _nu = ep.get("image_url")
                            if e_img_f:
                                _nu = upload_image_to_storage(e_img_f)
                                if not _nu:
                                    import base64 as _b64
                                    _nu = f"data:image/{e_img_f.name.rsplit('.',1)[-1].lower()};base64," + _b64.b64encode(e_img_f.getvalue()).decode()
                            _nids = []
                            if not _eap.empty:
                                for _t2 in e_posts:
                                    _pm3 = _eap[_eap["title"] == _t2]
                                    if not _pm3.empty: _nids.append(_pm3.iloc[0]["id"])
                            _save_pin({**ep, "label": e_label.strip(), "x": e_x, "y": e_y,
                                       "desc": e_desc.strip(), "image_url": _nu, "post_ids": _nids})
                            st.session_state.pos_edit_pin_id   = None
                            st.session_state.pos_active_pin_id = None
                            st.success("저장 완료!")
                            st.rerun()
                        if ec2.form_submit_button("취소", use_container_width=True):
                            st.session_state.pos_edit_pin_id = None
                            st.rerun()

    # ════════════════════════════════════════════════════════════════
    # 우측: 날짜·포지션 배정 패널
    # ════════════════════════════════════════════════════════════════
    with col_right:
        st.markdown('<div class="pos-root assign-panel">', unsafe_allow_html=True)
        st.markdown('<div class="assign-title">📋 날짜 &amp; 포지션 배정</div>', unsafe_allow_html=True)

        assign_date = st.date_input("📅 예배 날짜", value=st.session_state.pos_assign_date, key="pos_date_right")
        if assign_date != st.session_state.pos_assign_date:
            st.session_state.pos_assign_date = assign_date
        _wd = ["월","화","수","목","금","토","일"][assign_date.weekday()]
        st.markdown(
            f"<div style='font-size:0.76rem;color:#64748b;margin:-4px 0 10px;'>"
            f"{assign_date.strftime('%Y년 %m월 %d일')} ({_wd}요일)</div>",
            unsafe_allow_html=True
        )

        _rc1, _rc2 = st.columns([2, 1])
        with _rc2:
            if st.button("🔄 명단 로드", key="right_reload", use_container_width=True):
                with st.spinner("..."):
                    load_members_only()
                st.rerun()

        st.markdown("---")

        # 배정 폼 — 활성 핀이 있으면 포지션 자동 선택
        _apfa = _get_pin(st.session_state.pos_active_pin_id) if st.session_state.pos_active_pin_id else None

        # 포지션 목록: 핀 라벨 + POSITIONS 합집합
        _pin_labels = [p["label"] for p in st.session_state.pos_pins]
        _pos_merged = list(dict.fromkeys(POSITIONS + _pin_labels))  # 순서 유지 중복 제거

        if st.session_state.members_loaded and not st.session_state.members_db.empty:
            _nlist = ["선택하세요"] + list(st.session_state.members_db["name"].values)
            if _apfa and _apfa["label"] in _pos_merged:
                _auto_idx = _pos_merged.index(_apfa["label"])
            else:
                _auto_idx = 0

            with st.form("right_assign_form", clear_on_submit=True):
                _sn = st.selectbox("👤 팀원", _nlist, key="r_name")
                _sp = st.selectbox("🎥 포지션", _pos_merged, index=_auto_idx, key="r_pos")
                if _apfa:
                    st.caption(f"📍 선택된 핀: **{_apfa['label']}**")
                if st.form_submit_button("➕ 배정", type="primary", use_container_width=True):
                    if _sn == "선택하세요":
                        st.error("팀원을 선택하세요.")
                    elif _sp == "선택 안 함":
                        st.error("포지션을 선택하세요.")
                    else:
                        _ex = [a for a in st.session_state.pos_assignments if a["name"] != _sn]
                        _ex.append({"name": _sn, "position": _sp})
                        st.session_state.pos_assignments = _ex
                        st.success(f"{_sn} → {_sp}")
                        st.rerun()
        else:
            st.info("👆 '명단 로드' 버튼을 눌러주세요.")

        # 배정 목록
        if st.session_state.pos_assignments:
            st.markdown("---")
            _sorted = sorted(
                st.session_state.pos_assignments,
                key=lambda x: _pos_merged.index(x["position"]) if x["position"] in _pos_merged else 999
            )
            st.markdown(f"**배정 현황 ({len(_sorted)}명)**")
            for _i, _a in enumerate(_sorted):
                _ac1, _ac2 = st.columns([4, 1])
                with _ac1:
                    st.markdown(
                        f"<div class='assign-card'>"
                        f"<div><div class='aname'>{_a['name']}</div>"
                        f"<div class='apos'>🎥 {_a['position']}</div></div>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                with _ac2:
                    st.write("")
                    if st.button("🗑️", key=f"rdel_{_i}", use_container_width=True):
                        st.session_state.pos_assignments = [
                            a for a in st.session_state.pos_assignments if a["name"] != _a["name"]
                        ]
                        st.rerun()

            st.markdown("---")
            _date_s   = assign_date.strftime("%Y년 %m월 %d일")
            _copy_txt = f"📅 {_date_s} ({_wd}요일) 예배 포지션 명단\n\n" + "\n".join(
                f"• {a['name']} — {a['position']}" for a in _sorted
            )
            st.text_area("복사용 텍스트", value=_copy_txt,
                         height=max(110, 36 + len(_sorted)*24), key="r_copy")
            _cjs = _copy_txt.replace("\\","\\\\").replace("`","\\`").replace("$","\\$")
            st.components.v1.html(f"""
            <button onclick="navigator.clipboard.writeText(`{_cjs}`).then(()=>{{
                this.textContent='✅ 복사됨!';setTimeout(()=>this.textContent='📋 복사',2000);
            }})"
            style="width:100%;background:#1e3a5f;color:#fff;border:none;padding:8px;
                   border-radius:8px;font-size:0.85rem;cursor:pointer;font-weight:700;">
            📋 복사</button>""", height=46)

            if st.button("🗑️ 전체 초기화", type="secondary", use_container_width=True, key="r_reset"):
                st.session_state.pos_assignments = []
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════════════
# 8. 팀 커뮤니티 게시판
# ══════════════════════════════════════════════════════════════════════
elif st.session_state.page == "🏛️ 팀 커뮤니티 게시판":

    st.markdown("""
    <style>
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child {
        background-color: #3f0e40;
        min-height: 80vh;
        padding: 8px 6px;
    }
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child .stMarkdown p,
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child h3 {
        color: #fff;
    }
    section[data-testid="stMain"] div[data-testid="stColumns"] > div:first-child h2 {
        color: #fff !important; font-size:12px !important;
        letter-spacing:1px; text-transform:uppercase;
        margin: 8px 4px 4px !important;
    }
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
    .post-title   { font-size:15px; font-weight:600; color:#1d1c1d; }
    .post-preview { font-size:13px; color:#616061; margin-top:2px; }
    .post-meta    { font-size:12px; color:#97979a; margin-top:6px; }
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
            # FIX #7: require_conn() 체크 추가
            if not require_conn():
                return False
            conn.update(
                spreadsheet=SHEET_URL, worksheet="categories",
                data=pd.DataFrame(new_cat_df, columns=["id","name","parent_id"]).astype(str),
            )
            st.session_state.cat_db = new_cat_df.reset_index(drop=True)
            st.session_state.force_refresh = True
            return True

        channels = get_channels(st.session_state.cat_db)
        ch_id = st.session_state.sel_channel_id
        sc_id = st.session_state.sel_sub_cat_id

        col_sidebar, col_main = st.columns([1, 3.5], gap="small")

        with col_sidebar:
            st.markdown(
                "<div style='color:#fff;font-size:18px;font-weight:700;padding:8px 8px 4px;'>⛪ RW 미디어팀</div>",
                unsafe_allow_html=True,
            )

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
                # FIX #5: 채널 전환 시 폴더 추가창 닫기
                st.session_state.show_add_sc     = False
                st.rerun()

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

                        if save_categories(new_cat_df):  # FIX #7: 반환값 확인
                            st.session_state.sel_channel_id  = new_sel_id
                            st.session_state.sel_sub_cat_id  = None
                            st.session_state.comm_write_mode = False
                            st.session_state.view_post_id    = None
                            # FIX #5
                            st.session_state.show_add_sc     = False
                            st.rerun()

                except ImportError:
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
                                # FIX #5
                                st.session_state.show_add_sc     = False
                                st.rerun()
                        with c_up:
                            if i > 0 and st.button("↑", key=f"up_{ch['id']}", use_container_width=True):
                                rows = [r.to_dict() for _, r in channels.iterrows()]
                                rows[i], rows[i-1] = rows[i-1], rows[i]
                                new_channels = pd.DataFrame(rows).reset_index(drop=True)
                                non_ch = st.session_state.cat_db[st.session_state.cat_db["parent_id"] != ""]
                                new_cat = pd.concat([new_channels, non_ch], ignore_index=True)
                                save_categories(new_cat)
                                st.rerun()
                        with c_dn:
                            if i < len(channels) - 1 and st.button("↓", key=f"dn_{ch['id']}", use_container_width=True):
                                rows = [r.to_dict() for _, r in channels.iterrows()]
                                rows[i], rows[i+1] = rows[i+1], rows[i]
                                new_channels = pd.DataFrame(rows).reset_index(drop=True)
                                non_ch = st.session_state.cat_db[st.session_state.cat_db["parent_id"] != ""]
                                new_cat = pd.concat([new_channels, non_ch], ignore_index=True)
                                save_categories(new_cat)
                                st.rerun()

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
                    if new_ch_name.strip():
                        new_ch  = pd.DataFrame([{"id": str(int(time.time()*1000)),
                                                 "name": new_ch_name.strip(),
                                                 "parent_id": ""}])
                        new_cat = pd.concat([st.session_state.cat_db, new_ch], ignore_index=True)
                        if save_categories(new_cat):  # FIX #7
                            st.session_state.show_add_ch = False
                            st.rerun()
                if ca2.button("취소", key="cancel_add_ch"):
                    st.session_state.show_add_ch = False
                    st.rerun()

        with col_main:
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
                total_cells = num_folders + 2
                btn_cols = st.columns(max(total_cells, 4))

                is_all_sc = sc_id is None
                if btn_cols[0].button(
                    ("📁 " if is_all_sc else "📂 ") + "전체",
                    key="sc_pill_all",
                    use_container_width=True,
                    type="primary" if is_all_sc else "secondary",
                ):
                    st.session_state.sel_sub_cat_id  = None
                    # FIX #3: 폴더 전환 시 글쓰기 모드 리셋
                    st.session_state.comm_write_mode = False
                    st.rerun()

                for i, (_, sc) in enumerate(sub_cats.iterrows()):
                    is_active = sc_id == sc["id"]
                    if btn_cols[i + 1].button(
                        ("📁 " if is_active else "📂 ") + sc["name"],
                        key=f"sc_pill_{sc['id']}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                    ):
                        st.session_state.sel_sub_cat_id  = sc["id"]
                        # FIX #3: 폴더 전환 시 글쓰기 모드 리셋
                        st.session_state.comm_write_mode = False
                        st.rerun()

                if btn_cols[num_folders + 1].button(
                    "➕ 폴더",
                    key="sc_pill_add",
                    use_container_width=True,
                ):
                    st.session_state.show_add_sc = not st.session_state.show_add_sc
                    st.rerun()

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
                            if new_sc_name.strip():
                                new_sc  = pd.DataFrame([{
                                    "id": str(int(time.time()*1000)),
                                    "name": new_sc_name.strip(),
                                    "parent_id": ch_id,
                                }])
                                new_cat = pd.concat([st.session_state.cat_db, new_sc], ignore_index=True)
                                if save_categories(new_cat):  # FIX #7
                                    st.session_state.show_add_sc = False
                                    st.rerun()
                    with cf3:
                        if st.button("취소", key="cancel_sc", use_container_width=True):
                            st.session_state.show_add_sc = False
                            st.rerun()

                if sc_id is not None:
                    if st.button("🗑️ 현재 폴더 삭제", key="del_sc_main", type="secondary"):
                        new_cat = st.session_state.cat_db[st.session_state.cat_db["id"] != sc_id].reset_index(drop=True)
                        if save_categories(new_cat):  # FIX #7
                            st.session_state.sel_sub_cat_id = None
                            st.rerun()

                st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)

            # ── 글쓰기 모드 ─────────────────────────────────────────
            if st.session_state.comm_write_mode:
                if st.button("⬅️ 목록으로", key="back_from_write"):
                    st.session_state.comm_write_mode = False
                    st.rerun()

                st.subheader("✏️ 새 게시글 작성")

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
                        ch_row2  = st.session_state.cat_db[st.session_state.cat_db["id"] == ch_id]
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
                        cat_labels    = [label for _, label in cat_options]
                        chosen_label  = st.selectbox("게시 위치 (폴더) 선택", cat_labels, index=default_cat_idx)
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
                                    st.session_state.post_db         = updated_p
                                    st.session_state.force_refresh   = True
                                    st.session_state.comm_write_mode = False
                                    st.success("🎉 게시글이 등록되었습니다!")
                                    time.sleep(0.8)
                                    st.rerun()

            # ── 게시글 상세 ─────────────────────────────────────────
            elif st.session_state.view_post_id is not None:
                # FIX #4: view_post_id를 clean_id로 정규화해서 비교
                pid = clean_id(str(st.session_state.view_post_id))

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
                        par      = st.session_state.cat_db[st.session_state.cat_db["id"] == p_cat_row["parent_id"]]
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
                # FIX #6: clean_id 한 번만 적용 (로드 시 이미 처리됨)
                current_post_id = pid  # 이미 위에서 clean_id 처리됨

                if not comm_db.empty:
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
                                par      = st.session_state.cat_db[st.session_state.cat_db["id"] == p_cat_row["parent_id"]]
                                par_name = par["name"].values[0] if not par.empty else ""
                                cat_label = f"{par_name} / 📁 {p_cat_row['name']}"
                            else:
                                cat_label = p_cat_row["name"]
                        else:
                            cat_label = "미분류"

                        comm_db_tmp = st.session_state.comm_db.copy()
                        if not comm_db_tmp.empty:
                            post_id_clean = clean_id(str(post["id"]))
                            c_cnt = len(comm_db_tmp[comm_db_tmp["post_id"] == post_id_clean])
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
                                    # FIX #4: 저장 시 clean_id 적용
                                    st.session_state.view_post_id    = clean_id(str(post["id"]))
                                    st.session_state.comm_write_mode = False
                                    st.rerun()
