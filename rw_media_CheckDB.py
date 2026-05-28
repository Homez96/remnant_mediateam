import streamlit as st
import pandas as pd
from datetime import date, datetime
import time
import requests

# ── 0. 외부 스토리지(ImgBB 또는 Freeimage) 설정 ──────────────────────
API_KEY = "6f1ec1ad61b9dc8ff1f25abda8fe4096"
UPLOAD_URL = "https://api.imgbb.com/1/upload"

def upload_image_to_storage(file_buffer):
    if not API_KEY or "여기에" in API_KEY:
        st.error("❌ 이미지 API Key 설정이 필요합니다. 코드를 확인해 주세요.")
        return None
    try:
        payload = {"key": API_KEY, "action": "upload"}
        files = {"image": (file_buffer.name, file_buffer.getvalue())}
        response = requests.post(UPLOAD_URL, data=payload, files=files, timeout=20)
        res_data = response.json()
        if response.status_code == 200:
            return res_data["data"]["url"]
        else:
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
if "page" not in st.session_state:
    st.session_state.page = "⛪ 예배 출석 관리"

# ── 3. 구글 시트 연결 및 데이터 로드 ────────────────────────────────
try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    clean_url = "https://docs.google.com/spreadsheets/d/1584S2jzLNFlSJHAgNOBo_w6HjwMwlJ7pUei4jVqeJrU"
    
    ttl = 0 if st.session_state.force_refresh else 300
    
    df_m = conn.read(spreadsheet=clean_url, worksheet="members", ttl=ttl)
    df_a = conn.read(spreadsheet=clean_url, worksheet="attendance", ttl=ttl)
    df_c = conn.read(spreadsheet=clean_url, worksheet="categories", ttl=ttl)
    df_p = conn.read(spreadsheet=clean_url, worksheet="posts", ttl=ttl)
    df_cm = conn.read(spreadsheet=clean_url, worksheet="comments", ttl=ttl)
    
    if st.session_state.force_refresh:
        st.session_state.force_refresh = False

    def clean_df(df, type_dict):
        if df is None or df.empty: return pd.DataFrame(columns=type_dict.keys())
        for col, dtype in type_dict.items():
            if col in df.columns:
                if dtype == "str": df[col] = df[col].astype(str).replace("nan", "").replace("None", "")
                elif dtype == "bool": df[col] = df[col].apply(lambda x: True if str(x).lower() in ['true','1','1.0'] else False)
        return df

    st.session_state.members_db = clean_df(df_m, {"id":"str", "name":"str", "position":"str"}).sort_values("name").reset_index(drop=True)
    st.session_state.attend_db = clean_df(df_a, {"date":"str", "id":"str", "status":"str", "meal":"bool", "reason":"str"})
    st.session_state.cat_db = clean_df(df_c, {"id":"str", "name":"str"})
    st.session_state.post_db = clean_df(df_p, {"id":"str", "category_id":"str", "title":"str", "content":"str", "links":"str", "image_urls":"str", "created_at":"str"})
    st.session_state.comm_db = clean_df(df_cm, {"id":"str", "post_id":"str", "author":"str", "content":"str", "created_at":"str"})

except Exception as e:
    st.error(f"데이터 로드 실패: {e}")

# ── 4. 사이드바 메뉴 ────────────────────────────────────────────────
with st.sidebar:
    st.title("⛪ RW Media")
    st.session_state.page = st.radio("메뉴 이동", ["⛪ 예배 출석 관리", "🏛️ 팀 커뮤니티 게시판"])
    st.write("---")
    if st.button("🔄 데이터 강제 새로고침"):
        st.session_state.force_refresh = True
        st.rerun()

# ── 5. [페이지 1] 예배 출석 관리 ────────────────────────────────────
POSITIONS = ["선택 안 함", "4번 카메라", "5번 카메라", "6번 카메라", "7번 카메라", "PD", "TD",
             "노출", "자막", "LED", "조명", "사진 촬영", "릴스", "FD", "음향"]

if st.session_state.page == "⛪ 예배 출석 관리":
    st.header("⛪ 예배 출석 관리")
    
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
            st.info("예배자를 먼저 등록해주세요.")
        else:
            curr_a = a_df[a_df["date"] == date_key]
            merged = pd.merge(m_df, curr_a, on="id", how="left")
            merged["status"] = merged["status"].fillna("미체크")
            merged["meal"] = merged["meal"].fillna(False)
            merged["reason"] = merged["reason"].fillna("")
            
            p_c, l_c, a_c, m_c = (merged["status"]=="출석").sum(), (merged["status"]=="지각").sum(), (merged["status"]=="결석").sum(), merged["meal"].sum()
            u_c = len(m_df) - (p_c + l_c + a_c)
            
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
            m_btn(cols[3], "식사", m_c, "b_m", "식사")
            m_btn(cols[4], "미체크", u_c, "b_u", "미체크")
            
            f_s = st.session_state.current_filter
            if f_s == "식사": filtered = merged[merged["meal"] == True]
            elif f_s != "전체": filtered = merged[merged["status"] == f_s]
            else: filtered = merged
            
            st.info(f"**{f_s} 명단** : {', '.join(filtered['name'].values) if not filtered.empty else '없음'}")
            
            display_edit = filtered[["id","name","position","status","meal","reason"]].rename(columns={"name":"이름","position":"포지션","status":"상태","meal":"식사","reason":"사유"})
            edit_df = st.data_editor(
                display_edit,
                column_config={"id":None, "상태":st.column_config.SelectboxColumn(options=["출석","지각","결석","미체크"])},
                key=f"ed_{date_key}_{f_s}", width="stretch"
            )
            
            if st.button("💾 출석 저장", type="primary", width="stretch"):
                patch = edit_df.rename(columns={"이름":"name","포지션":"position","상태":"status","식사":"meal","사유":"reason"})
                patch["date"] = date_key
                patch["id"] = patch["id"].astype(str)
                
                old_db = st.session_state.attend_db
                remain = old_db[~((old_db["date"]==date_key) & (old_db["id"].isin(patch["id"])))]
                new_db = pd.concat([remain, patch[["date","id","status","reason","meal"]]], ignore_index=True)
                
                upload_df = pd.DataFrame(new_db, columns=["date","id","status","reason","meal"])
                conn.update(spreadsheet=clean_url, worksheet="attendance", data=upload_df)
                st.session_state.force_refresh = True
                st.success("저장 완료!")
                time.sleep(1)
                st.rerun()

    with tab_mem:
        st.dataframe(st.session_state.members_db[["name","position"]], width="stretch", hide_index=True)
        m_tab1, m_tab2, m_tab3 = st.tabs(["➕ 추가", "✏️ 수정", "🗑️ 삭제"])
        
        with m_tab1:
            with st.form("add_m"):
                n_n = st.text_input("새로운 예배자 이름 *")
                n_p = st.selectbox("포지션 선택", POSITIONS)
                if st.form_submit_button("예배자 신규 등록"):
                    if n_n.strip():
                        new_m = pd.concat([st.session_state.members_db, pd.DataFrame([{"id":str(int(time.time()*1000)), "name":n_n, "position":n_p}])], ignore_index=True)
                        new_m = new_m.sort_values(by="name").reset_index(drop=True)
                        upload_df = pd.DataFrame(new_m, columns=["id","name","position"])
                        conn.update(spreadsheet=clean_url, worksheet="members", data=upload_df)
                        st.session_state.force_refresh = True
                        st.rerun()

        with m_tab2:
            if not st.session_state.members_db.empty:
                edit_tgt = st.selectbox("수정할 대상 선택", st.session_state.members_db["name"].values, key="ed_t")
                tgt_row = st.session_state.members_db[st.session_state.members_db["name"] == edit_tgt].iloc[0]
                with st.form("edit_m"):
                    e_n = st.text_input("이름 수정", value=tgt_row["name"])
                    e_p = st.selectbox("포지션 수정", POSITIONS, index=POSITIONS.index(tgt_row["position"]) if tgt_row["position"] in POSITIONS else 0)
                    if st.form_submit_button("정보 수정 완료"):
                        updated = st.session_state.members_db.copy()
                        idx = updated[updated["id"] == tgt_row["id"]].index[0]
                        updated.at[idx, "name"] = e_n
                        updated.at[idx, "position"] = e_p
                        updated = updated.sort_values(by="name").reset_index(drop=True)
                        upload_df = pd.DataFrame(updated, columns=["id","name","position"])
                        conn.update(spreadsheet=clean_url, worksheet="members", data=upload_df)
                        st.session_state.force_refresh = True
                        st.rerun()

        with m_tab3:
            if not st.session_state.members_db.empty:
                del_tgt = st.selectbox("삭제할 대상 선택", st.session_state.members_db["name"].values, key="del_t")
                if st.button("❌ 선택한 예배자 최종 삭제", type="secondary"):
                    updated = st.session_state.members_db[st.session_state.members_db["name"] != del_tgt]
                    updated = updated.sort_values(by="name").reset_index(drop=True)
                    upload_df = pd.DataFrame(updated, columns=["id","name","position"])
                    conn.update(spreadsheet=clean_url, worksheet="members", data=upload_df)
                    st.session_state.force_refresh = True
                    st.rerun()

# ── 6. [페이지 2] 팀 커뮤니티 게시판 ──────────────────────────────────
elif st.session_state.page == "🏛️ 팀 커뮤니티 게시판":
    st.header("🏛️ 팀 커뮤니티 게시판")
    
    b_tab_view, b_tab_write, b_tab_admin = st.tabs(["📖 게시글 보기", "📝 글쓰기", "⚙️ 카테고리 관리"])
    cat_df = st.session_state.cat_db
    
    # 6-1. 카테고리 관리
    with b_tab_
