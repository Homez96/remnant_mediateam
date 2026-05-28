import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import requests

# ══════════════════════════════════════════════════════════════════════
# 0. 이미지 업로드 (ImgBB) — secrets.toml에 [imgbb] api_key = "..." 저장
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
st.set_page_config(page_title="RW 미디어팀 통합 관리", page_icon="⛪", layout="centered")

# ══════════════════════════════════════════════════════════════════════
# 2. 세션 상태 초기화
# ══════════════════════════════════════════════════════════════════════
_defaults = {
    "page":             "🏠 홈 (대시보드)",
    "members_db":       pd.DataFrame(columns=["id", "name", "position"]),
    "attend_db":        pd.DataFrame(columns=["date", "id", "status", "reason", "meal"]),
    "cat_db":           pd.DataFrame(columns=["id", "name"]),
    "post_db":          pd.DataFrame(columns=["id", "category_id", "title", "content", "links", "image_urls", "created_at"]),
    "comm_db":          pd.DataFrame(columns=["id", "post_id", "author", "content", "created_at"]),
    "att_loaded":       False,
    "board_loaded":     False,
    "force_refresh":    False,
    "current_filter":   "전체",
    "selected_date_val": date.today(),
    # 게시판 라우팅 — None: 목록, str: 해당 post id 상세
    "view_post_id":     None,
    # 게시판 카테고리 필터
    "board_cat_filter": "전체 보기",
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

MENU_OPTIONS = ["🏠 홈 (대시보드)", "⛪ 예배 출석 관리", "🏛️ 팀 커뮤니티 게시판"]
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
    """force_refresh 중이면 캐시 우회(ttl=1), 평상시 10분"""
    return 1 if st.session_state.force_refresh else 600

def clean_id(val) -> str:
    if pd.isna(val): return ""
    s = str(val).strip()
    return s[:-2] if s.endswith(".0") else s

def clean_df(df, schema: dict) -> pd.DataFrame:
    """schema = {col: 'str'|'bool'}  id 계열은 자동으로 clean_id 적용"""
    if df is None or df.empty:
        return pd.DataFrame(columns=schema.keys())
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    for col, dtype in schema.items():
        if col not in df.columns:
            continue
        if col in ("id", "post_id", "category_id"):
            df[col] = df[col].apply(clean_id)
        elif dtype == "str":
            df[col] = df[col].astype(str).replace({"nan": "", "None": ""}).str.strip()
        elif dtype == "bool":
            df[col] = df[col].apply(lambda x: str(x).lower() in ("true", "1", "1.0"))
    return df

# ── 데이터 로드 함수 ────────────────────────────────────────────────
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
            st.session_state.cat_db     = clean_df(df_c,  {"id":"str","name":"str"})
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
        # 게시판 밖으로 나가면 상세 상태 초기화
        st.session_state.view_post_id = None
        st.rerun()
    st.write("---")
    if st.button("🔄 앱 전체 강제 새로고침"):
        st.session_state.force_refresh  = True
        st.session_state.att_loaded     = False
        st.session_state.board_loaded   = False
        st.session_state.view_post_id   = None
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

        # 날짜가 바뀌면 필터 초기화
        if st.session_state.get("last_date") != date_key:
            st.session_state.last_date      = date_key
            st.session_state.selected_date_val = selected_date
            st.session_state.current_filter = "전체"

        tab_att, tab_mem = st.tabs(["📋 출석 체크", "👥 예배자 관리"])

        # ── 출석 체크 탭 ────────────────────────────────────────────
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

                # ── 상단 인원 통계 필터 버튼 ────────────────────────
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

                # ── 필터에 따른 이름 목록 구성 ──────────────────────
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

                        # ① 이름 선택 (필터 연동)
                        chosen_name = st.selectbox("👤 1. 이름 선택", member_names_list)

                        # 선택된 팀원의 기존 데이터 추출
                        user_row = merged[merged["name"] == chosen_name].iloc[0]

                        # ② 포지션 선택 (기존값 기본 선택)
                        base_pos = str(user_row["position"]).strip()
                        pos_idx  = POSITIONS.index(base_pos) if base_pos in POSITIONS else 0
                        chosen_position = st.selectbox("🎥 2. 오늘 담당 포지션 선택", POSITIONS, index=pos_idx)

                        # ③ 출석 상태 선택
                        STATUS_OPTIONS   = ["출석", "지각", "결석", "미체크"]
                        base_status      = str(user_row["status"]).strip()
                        status_idx       = STATUS_OPTIONS.index(base_status) if base_status in STATUS_OPTIONS else 3
                        chosen_status    = st.selectbox("📊 3. 출석 상태 변경", STATUS_OPTIONS, index=status_idx)

                        # ④ 사유 입력
                        chosen_reason = st.text_input(
                            "📝 4. 특이사항 / 사유 입력",
                            value=str(user_row["reason"]).strip(),
                            placeholder="지각 및 결석 사유 등을 자유롭게 입력하세요.",
                        )

                        # ⑤ 식사 신청 여부
                        chosen_meal = st.checkbox("🍴 5. 오늘 식사 신청 여부", value=bool(user_row["meal"]))

                        st.write("")
                        save_btn = st.form_submit_button("💾 현재 팀원 출석 저장", type="primary", use_container_width=True)

                        if save_btn:
                            if not require_conn(): st.stop()
                            target_id = user_row["id"]

                            # members 시트 포지션 업데이트
                            raw_members = st.session_state.members_db.copy()
                            raw_members["id"] = raw_members["id"].astype(str).apply(clean_id)
                            m_idx = raw_members[raw_members["id"] == target_id].index[0]
                            raw_members.at[m_idx, "position"] = chosen_position
                            conn.update(
                                spreadsheet=SHEET_URL, worksheet="members",
                                data=pd.DataFrame(raw_members, columns=["id","name","position"]).astype(str),
                            )
                            st.session_state.members_db = raw_members

                            # attendance 시트 해당 인원 해당 날짜 행 교체
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
                            new_db = pd.concat([remain, new_record], ignore_index=True)
                            upload_df = pd.DataFrame(new_db, columns=["date","id","status","reason","meal"])
                            conn.update(spreadsheet=SHEET_URL, worksheet="attendance", data=upload_df)

                            st.session_state.attend_db = upload_df
                            st.session_state.force_refresh = True
                            st.success(f"🎉 {chosen_name} 님 저장 완료! (포지션: {chosen_position} / 상태: {chosen_status})")
                            time.sleep(0.6)
                            st.rerun()

        # ── 예배자 관리 탭 ───────────────────────────────────────────
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
                            st.session_state.members_db = new_m
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
                            st.session_state.members_db = updated
                            st.session_state.force_refresh = True
                            st.rerun()

            with m_tab3:
                if not st.session_state.members_db.empty:
                    del_tgt = st.selectbox("삭제할 대상 선택", st.session_state.members_db["name"].values, key="del_t")
                    if st.button("❌ 선택한 예배자 최종 삭제", type="secondary"):
                        if not require_conn(): st.stop()
                        updated = st.session_state.members_db[st.session_state.members_db["name"] != del_tgt].sort_values("name").reset_index(drop=True)
                        conn.update(spreadsheet=SHEET_URL, worksheet="members", data=pd.DataFrame(updated, columns=["id","name","position"]))
                        st.session_state.members_db = updated
                        st.session_state.force_refresh = True
                        st.rerun()

# ══════════════════════════════════════════════════════════════════════
# 7. 팀 커뮤니티 게시판
# ══════════════════════════════════════════════════════════════════════
elif st.session_state.page == "🏛️ 팀 커뮤니티 게시판":
    st.header("🏛️ 팀 커뮤니티 게시판")

    if not st.session_state.board_loaded:
        st.warning("⚠️ 구글 시트에서 게시판 데이터를 가져오기 전입니다.")
        if st.button("🔄 게시판 데이터 불러오기", type="primary", use_container_width=True):
            load_community_data()
            st.rerun()

    else:
        cat_df   = st.session_state.cat_db
        full_p_db = st.session_state.post_db.copy()

        b_tab_view, b_tab_write, b_tab_admin = st.tabs(["📖 게시글 보기", "📝 글쓰기", "⚙️ 카테고리 관리"])

        # ══════════════════════════════════════════════════════════════
        # 7-1. 게시글 보기 (목록 ↔ 상세 라우팅)
        # ══════════════════════════════════════════════════════════════
        with b_tab_view:

            # ── 상세 페이지 ──────────────────────────────────────────
            if st.session_state.view_post_id is not None:
                pid = st.session_state.view_post_id

                # 뒤로 가기
                if st.button("⬅️ 목록으로 돌아가기"):
                    st.session_state.view_post_id = None
                    st.rerun()

                # 해당 게시글 존재 확인
                if full_p_db.empty or pid not in full_p_db["id"].values:
                    st.warning("게시글을 찾을 수 없습니다. 목록으로 돌아가세요.")
                    st.stop()

                post = full_p_db[full_p_db["id"] == pid].iloc[0]
                c_row  = cat_df[cat_df["id"] == post["category_id"]] if not cat_df.empty else pd.DataFrame()
                c_name = c_row["name"].values[0] if not c_row.empty else "미분류"

                # 제목 영역
                st.markdown(f"### [{c_name}] {post['title']}")
                st.caption(f"🕐 {post['created_at']}")
                st.markdown("---")

                # 수정 모드 토글
                edit_mode = st.checkbox("✏️ 이 글 수정하기", key=f"e_mode_{pid}")
                if edit_mode:
                    with st.form(f"form_ed_{pid}"):
                        ed_title   = st.text_input("제목 변경",  value=post["title"])
                        ed_content = st.text_area("내용 변경",  value=post["content"], height=200)
                        ed_links   = st.text_input("링크 변경", value=post["links"])
                        if st.form_submit_button("💾 수정 완료 저장"):
                            if not require_conn(): st.stop()
                            full_p_db.loc[full_p_db["id"] == pid, ["title","content","links"]] = [
                                str(ed_title), str(ed_content), str(ed_links)
                            ]
                            conn.update(spreadsheet=SHEET_URL, worksheet="posts",
                                        data=pd.DataFrame(full_p_db, columns=["id","category_id","title","content","links","image_urls","created_at"]).astype(str))
                            st.session_state.post_db = full_p_db
                            st.session_state.force_refresh = True
                            st.rerun()
                else:
                    # 본문
                    st.write(post["content"])

                    # 이미지
                    if isinstance(post["image_urls"], str) and post["image_urls"].strip():
                        for url in post["image_urls"].split(","):
                            if url.strip():
                                st.image(url.strip(), use_container_width=True)

                    # 링크
                    if isinstance(post["links"], str) and post["links"].strip():
                        for link in post["links"].split(","):
                            lnk = link.strip()
                            if not lnk: continue
                            if "youtube.com" in lnk or "youtu.be" in lnk or any(lnk.lower().endswith(e) for e in (".mp4",".mov",".avi",".webm")):
                                st.video(lnk)
                            else:
                                st.link_button("🔗 첨부 링크 열기", lnk)

                st.markdown("---")

                # ── 댓글 영역 ────────────────────────────────────────
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
                        c_col1, c_col2 = st.columns([5, 1])

                        with c_col1:
                            st.caption(f"**{citem['author']}** ({citem['created_at']})")
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
                            st.write("")
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
                                st.session_state.comm_db = updated_cm
                                st.session_state.force_refresh = True
                                time.sleep(0.3)
                                st.rerun()

                # 댓글 달기 폼
                st.markdown("---")
                with st.form(f"comm_{pid}", clear_on_submit=True):
                    st.markdown("**댓글 달기**")
                    member_names    = ["선택하세요"] + list(st.session_state.members_db["name"].values) + ["[직접 입력]"]
                    selected_author = st.selectbox("작성자 선택", member_names)
                    custom_auth     = ""
                    if selected_author == "[직접 입력]":
                        custom_auth = st.text_input("작성자명 직접 입력", placeholder="이름 입력")
                    c_txt = st.text_area("댓글 내용", height=70)

                    if st.form_submit_button("댓글 등록"):
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
                            st.session_state.comm_db = updated_cm
                            st.session_state.force_refresh = True
                            st.success("댓글이 등록되었습니다!")
                            time.sleep(0.3)
                            st.rerun()

                # 게시글 삭제
                st.markdown("---")
                if st.button("🗑️ 이 게시글 전체 삭제", type="secondary"):
                    if not require_conn(): st.stop()
                    updated_p = full_p_db[full_p_db["id"] != pid]
                    conn.update(spreadsheet=SHEET_URL, worksheet="posts",
                                data=pd.DataFrame(updated_p, columns=["id","category_id","title","content","links","image_urls","created_at"]).astype(str))
                    st.session_state.post_db = updated_p

                    # 관련 댓글도 함께 삭제
                    raw = st.session_state.comm_db.copy()
                    raw["post_id"] = raw["post_id"].apply(clean_id)
                    updated_cm = raw[raw["post_id"] != current_post_id]
                    conn.update(spreadsheet=SHEET_URL, worksheet="comments",
                                data=pd.DataFrame(updated_cm, columns=["id","post_id","author","content","created_at"]).astype(str))
                    st.session_state.comm_db    = updated_cm
                    st.session_state.view_post_id  = None   # 목록으로 복귀
                    st.session_state.force_refresh = True
                    st.success("게시글과 관련 댓글이 삭제되었습니다.")
                    time.sleep(0.8)
                    st.rerun()

            # ── 게시글 목록 페이지 ───────────────────────────────────
            else:
                # 카테고리 필터
                cat_options = ["전체 보기"] + list(cat_df["name"].values)
                sel_cat = st.selectbox("📂 카테고리", cat_options,
                                       index=cat_options.index(st.session_state.board_cat_filter)
                                       if st.session_state.board_cat_filter in cat_options else 0,
                                       key="cat_filter_sel")
                # 필터값 세션에 저장 (탭 전환 후 복원)
                if sel_cat != st.session_state.board_cat_filter:
                    st.session_state.board_cat_filter = sel_cat

                if sel_cat != "전체 보기" and not cat_df.empty and sel_cat in cat_df["name"].values:
                    sel_cid      = cat_df[cat_df["name"] == sel_cat]["id"].values[0]
                    display_posts = full_p_db[full_p_db["category_id"] == sel_cid]
                else:
                    display_posts = full_p_db

                st.markdown("---")

                if display_posts.empty:
                    st.info("등록된 게시글이 없습니다.")
                else:
                    for _, post in display_posts[::-1].iterrows():
                        c_row  = cat_df[cat_df["id"] == post["category_id"]] if not cat_df.empty else pd.DataFrame()
                        c_name = c_row["name"].values[0] if not c_row.empty else "미분류"

                        # 해당 게시글 댓글 수
                        comm_db = st.session_state.comm_db.copy()
                        if not comm_db.empty:
                            comm_db["post_id"] = comm_db["post_id"].apply(clean_id)
                            c_cnt = len(comm_db[comm_db["post_id"] == clean_id(str(post["id"]))])
                        else:
                            c_cnt = 0

                        col_btn, col_info = st.columns([3, 2])
                        with col_btn:
                            if st.button(f"📄 {post['title']}", key=f"goto_{post['id']}", use_container_width=True):
                                st.session_state.view_post_id = post["id"]
                                st.rerun()
                        with col_info:
                            st.caption(f"[{c_name}]  💬 {c_cnt}  · {post['created_at']}")

        # ══════════════════════════════════════════════════════════════
        # 7-2. 글쓰기
        # ══════════════════════════════════════════════════════════════
        with b_tab_write:
            if cat_df.empty:
                st.warning("⚠️ 카테고리를 먼저 만들어주세요. (카테고리 관리 탭)")
            else:
                with st.form("write_post", clear_on_submit=True):
                    p_cat     = st.selectbox("카테고리 선택", cat_df["name"].values)
                    p_title   = st.text_input("제목 *")
                    p_content = st.text_area("내용 *", height=200)
                    p_links   = st.text_input("링크 첨부 (쉼표 구분, 유튜브 링크 가능)")
                    p_files   = st.file_uploader("🖼️ 사진 업로드", type=["png","jpg","jpeg"], accept_multiple_files=True)

                    if st.form_submit_button("📝 게시글 등록"):
                        if not require_conn(): st.stop()
                        c_id = str(cat_df[cat_df["name"] == p_cat]["id"].values[0])
                        if not p_title.strip() or not p_content.strip():
                            st.error("제목과 내용을 모두 입력해 주세요.")
                        elif (not full_p_db.empty and
                              p_title.strip() in full_p_db[full_p_db["category_id"] == c_id]["title"].values):
                            st.warning("같은 카테고리에 동일한 제목의 게시글이 있습니다.")
                        else:
                            with st.spinner("⏳ 등록 중..."):
                                p_id = str(int(time.time()*1000))
                                uploaded_urls = [u for f in p_files if (u := upload_image_to_storage(f))]
                                new_p = pd.DataFrame([{
                                    "id": p_id, "category_id": c_id,
                                    "title": p_title.strip(), "content": p_content,
                                    "links": p_links or "",
                                    "image_urls": ",".join(uploaded_urls),
                                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                }])
                                updated_p = pd.concat([full_p_db, new_p], ignore_index=True)
                                conn.update(spreadsheet=SHEET_URL, worksheet="posts",
                                            data=pd.DataFrame(updated_p, columns=["id","category_id","title","content","links","image_urls","created_at"]).astype(str))
                                st.session_state.post_db = updated_p
                                st.session_state.force_refresh = True
                                st.success("🎉 등록되었습니다!")
                                time.sleep(0.8)
                                st.rerun()

        # ══════════════════════════════════════════════════════════════
        # 7-3. 카테고리 관리
        # ══════════════════════════════════════════════════════════════
        with b_tab_admin:
            st.subheader("⚙️ 카테고리 설정 (최대 10개)")
            if not cat_df.empty:
                st.markdown("**현재 카테고리:** " + "  |  ".join([f"📁 {n}" for n in cat_df["name"].values]))
            else:
                st.info("현재 생성된 카테고리가 없습니다.")
            st.write("")

            c1, c2 = st.columns(2)
            with c1:
                new_cat_name = st.text_input("새 카테고리 이름")
                if st.button("➕ 카테고리 추가"):
                    if not require_conn(): st.stop()
                    if len(cat_df) >= 10:
                        st.error("카테고리는 최대 10개까지 생성할 수 있습니다.")
                    elif not new_cat_name.strip():
                        st.error("카테고리 이름을 입력해 주세요.")
                    elif new_cat_name.strip() in cat_df["name"].values:
                        st.warning("중복된 카테고리 이름입니다.")
                    else:
                        new_cat = pd.concat([cat_df, pd.DataFrame([{"id": str(int(time.time()*1000)), "name": new_cat_name.strip()}])], ignore_index=True)
                        conn.update(spreadsheet=SHEET_URL, worksheet="categories",
                                    data=pd.DataFrame(new_cat, columns=["id","name"]).astype(str))
                        st.session_state.cat_db = new_cat
                        st.session_state.force_refresh = True
                        st.rerun()

            with c2:
                if not cat_df.empty:
                    del_cat   = st.selectbox("수정/삭제할 카테고리", cat_df["name"].values)
                    c_rename  = st.text_input("새 이름으로 변경 (선택)")
                    btn1, btn2 = st.columns(2)

                    if btn1.button("✏️ 이름 변경"):
                        if not require_conn(): st.stop()
                        if not c_rename.strip():
                            st.error("변경할 이름을 입력해 주세요.")
                        elif c_rename.strip() in cat_df["name"].values:
                            st.warning("중복된 이름입니다.")
                        else:
                            updated_cat = cat_df.copy()
                            updated_cat.loc[updated_cat["name"] == del_cat, "name"] = c_rename.strip()
                            conn.update(spreadsheet=SHEET_URL, worksheet="categories",
                                        data=pd.DataFrame(updated_cat, columns=["id","name"]).astype(str))
                            st.session_state.cat_db = updated_cat
                            st.session_state.force_refresh = True
                            st.rerun()

                    if btn2.button("🗑️ 삭제", type="secondary"):
                        if not require_conn(): st.stop()
                        tgt_id      = cat_df[cat_df["name"] == del_cat]["id"].values[0]
                        updated_cat = cat_df[cat_df["id"] != tgt_id]
                        conn.update(spreadsheet=SHEET_URL, worksheet="categories",
                                    data=pd.DataFrame(updated_cat, columns=["id","name"]).astype(str))
                        st.session_state.cat_db = updated_cat
                        st.session_state.force_refresh = True
                        st.rerun()
