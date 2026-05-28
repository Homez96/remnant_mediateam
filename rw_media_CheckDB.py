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
    with b_tab_admin:
        st.subheader("⚙️ 카테고리 설정 (최대 10개)")
        if not cat_df.empty:
            cat_list_str = " | ".join([f"📁 {name}" for name in cat_df["name"].values])
            st.markdown(f"**현재 생성된 카테고리:** \n`{cat_list_str}`")
        else:
            st.info("현재 생성된 카테고리가 없습니다.")
        st.write("")
        
        c1, c2 = st.columns(2)
        with c1:
            new_cat_name = st.text_input("새 카테고리 이름")
            if st.button("카테고리 추가"):
                if len(cat_df) >= 10: 
                    st.error("카테고리는 최대 10개까지만 생성할 수 있습니다.")
                elif not new_cat_name.strip():
                    st.error("카테고리 이름을 입력해 주세요.")
                # ✨ [개선] 카테고리 이름 중복 검증 로직 추가
                elif new_cat_name.strip() in cat_df["name"].values:
                    st.warning("⚠️ 중복된 카테고리 이름입니다. 다른 이름을 사용해 주세요.")
                else:
                    new_cat = pd.concat([cat_df, pd.DataFrame([{"id":str(int(time.time())), "name":str(new_cat_name.strip())}])], ignore_index=True)
                    upload_df = pd.DataFrame(new_cat, columns=["id", "name"]).astype(str)
                    conn.update(spreadsheet=clean_url, worksheet="categories", data=upload_df)
                    st.session_state.force_refresh = True
                    st.rerun()
        with c2:
            if not cat_df.empty:
                # 선택 박스에 고유 표시를 위해 카테고리 리스트 제공 (내부적 고유 매칭 보장)
                del_cat = st.selectbox("삭제/수정할 카테고리 선택", cat_df["name"].values)
                c_rename = st.text_input("카테고리 이름 변경(원할 때만 입력)")
                
                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("이름 변경 실행"):
                    if c_rename.strip():
                        if c_rename.strip() in cat_df["name"].values:
                            st.warning("⚠️ 이미 존재하는 카테고리 이름입니다.")
                        else:
                            updated_cat = cat_df.copy()
                            updated_cat.loc[updated_cat["name"] == del_cat, "name"] = str(c_rename.strip())
                            upload_df = pd.DataFrame(updated_cat, columns=["id", "name"]).astype(str)
                            conn.update(spreadsheet=clean_url, worksheet="categories", data=upload_df)
                            st.session_state.force_refresh = True
                            st.rerun()
                # 🗑️ 이름이 같더라도 유저가 상단 드롭다운에서 명확히 타겟팅한 카테고리의 첫번째 행만 매칭 삭제 처리
                if col_btn2.button("카테고리 삭제", type="secondary"):
                    tgt_id = cat_df[cat_df["name"] == del_cat]["id"].values[0]
                    updated_cat = cat_df[cat_df["id"] != tgt_id]
                    upload_df = pd.DataFrame(updated_cat, columns=["id", "name"]).astype(str)
                    conn.update(spreadsheet=clean_url, worksheet="categories", data=upload_df)
                    st.session_state.force_refresh = True
                    st.rerun()

    # 6-2. 글쓰기
    with b_tab_write:
        if cat_df.empty: st.warning("카테고리를 먼저 만들어주세요.")
        else:
            with st.form("write_post", clear_on_submit=True):
                p_cat = st.selectbox("카테고리 선택", cat_df["name"].values)
                p_title = st.text_input("제목 *")
                p_content = st.text_area("내용 *", height=200)
                p_links = st.text_input("링크 첨부 (쉼표 구분)")
                p_files = st.file_uploader("🖼️ 사진 업로드", type=['png','jpg','jpeg'], accept_multiple_files=True)
                
                if st.form_submit_button("게시글 등록"):
                    c_id = str(cat_df[cat_df["name"]==p_cat]["id"].values[0])
                    
                    if not p_title.strip() or not p_content.strip(): 
                        st.error("제목과 내용을 입력해주세요.")
                    # ✨ [개선] 같은 카테고리 내에서 동일한 제목의 게시글 생성 중복 방지 로직 추가
                    elif p_title.strip() in st.session_state.post_db[st.session_state.post_db["category_id"] == c_id]["title"].values:
                        st.warning("⚠️ 중복된 게시글 제목입니다. 해당 카테고리에 이미 같은 제목의 글이 있습니다.")
                    else:
                        with st.spinner("⏳ 등록 중..."):
                            p_id = str(int(time.time()))
                            
                            uploaded_urls = []
                            for f in p_files:
                                url_result = upload_image_to_storage(f)
                                if url_result: uploaded_urls.append(url_result)
                            
                            new_p = pd.DataFrame([{
                                "id": p_id, "category_id": c_id, "title": str(p_title.strip()), "content": str(p_content),
                                "links": str(p_links) if p_links else "", "image_urls": ",".join(uploaded_urls) if uploaded_urls else "",
                                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                            }])
                            
                            updated_p = pd.concat([st.session_state.post_db, new_p], ignore_index=True)
                            upload_df = pd.DataFrame(updated_p, columns=["id", "category_id", "title", "content", "links", "image_urls", "created_at"]).astype(str)
                            conn.update(spreadsheet=clean_url, worksheet="posts", data=upload_df)
                            st.session_state.force_refresh = True
                            st.success("🎉 등록되었습니다!")
                            time.sleep(1)
                            st.rerun()

    # 6-3. 게시글 보기 및 댓글 CRUD
    with b_tab_view:
        if cat_df.empty: st.info("생성된 카테고리가 없습니다.")
        else:
            sel_cat_name = st.selectbox("📂 카테고리 필터링", ["전체 보기"] + list(cat_df["name"].values))
            p_db = st.session_state.post_db.copy()
            
            if sel_cat_name != "전체 보기":
                sel_c_id = cat_df[cat_df["name"]==sel_cat_name]["id"].values[0]
                display_posts = p_db[p_db["category_id"] == sel_c_id]
            else: 
                display_posts = p_db
            
            if display_posts.empty:
                st.info("등록된 글이 없습니다.")
            
            # 고유한 ID 매칭 방식을 사용하므로 제목이 같아도 개별 expander 박스에 독립 배정되어 선택 삭제 가능
            for _, post in display_posts[::-1].iterrows():
                c_row = cat_df[cat_df["id"] == post["category_id"]]
                c_name = c_row["name"].values[0] if not c_row.empty else "미분류"
                
                with st.expander(f"[{c_name}] {post['title']} ({post['created_at']})"):
                    edit_mode = st.checkbox("✏️ 이 글 수정하기", key=f"e_mode_{post['id']}")
                    if edit_mode:
                        with st.form(f"form_ed_{post['id']}"):
                            ed_title = st.text_input("제목 변경", value=post['title'])
                            ed_content = st.text_area("내용 변경", value=post['content'], height=150)
                            ed_links = st.text_input("링크 변경", value=post['links'])
                            if st.form_submit_button("수정 완료 저장"):
                                p_db.loc[p_db["id"] == post["id"],
