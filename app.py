## [PMS Revision History]
## 버전: Rev. 0.6.8 (Main UI Recovery)
## 업데이트 요약:
## 1. 🛡️ 메인 화면 복구: 데이터가 없는 시트나 관리용 시트(conflict 등)를 대시보드에서 완벽 제외
## 2. 🔄 동기화 안정화: 데이터 추가/수정 후 0.5초 대기 로직을 통해 구글 API 충돌 방지
## 3. 📂 리스트 최적화: 시트 이름에 'history'나 'conflict'가 포함된 경우 리스트업 차단

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.6.8", page_icon="🏗️", layout="wide")

# --- [인증] 멀티 계정 체크 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    st.title("🏗️ PM 통합 공정 관리 시스템")
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)")
        password = st.text_input("비밀번호 (PW)", type="password")
        if st.form_submit_button("로그인"):
            user_db = st.secrets["passwords"]
            if user_id in user_db and password == user_db[user_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = user_id
                st.rerun()
            else:
                st.error("정보가 일치하지 않습니다.")
    return False

if not check_password():
    st.stop()

# --- 구글 시트 연결 ---
@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 연결 오류: {e}"); return None

client = get_client()
if client:
    sh = client.open('pms_db')
    
    # [수정] 관리용 시트 및 비정상 시트 필터링 강화
    forbidden_keywords = ['weekly_history', 'conflict', 'Sheet1']
    all_ws = [ws for ws in sh.worksheets() if not any(k in ws.title for k in forbidden_keywords)]
    pjt_names = [s.title for s in all_ws]
    
    try:
        hist_ws = sh.worksheet('weekly_history')
    except:
        hist_ws = sh.add_worksheet(title='weekly_history', rows="1000", cols="5")
        hist_ws.append_row(["날짜", "프로젝트명", "주요현황", "작성자"])

    if "selected_menu" not in st.session_state:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"

    st.sidebar.title("📁 PMO 프로젝트 센터")
    st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']}**")
    
    menu = ["🏠 전체 대시보드"] + pjt_names
    # 선택된 메뉴가 리스트에 없을 경우 대시보드로 강제 초기화 (오류 방지)
    if st.session_state["selected_menu"] not in menu:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"
        
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu, index=menu.index(st.session_state["selected_menu"]), key="nav_menu")
    st.session_state["selected_menu"] = selected

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드 (복구된 메인 화면)
    # ---------------------------------------------------------
    if st.session_state["selected_menu"] == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        
        # 히스토리 데이터 로드 에러 방어
        try:
            hist_data = pd.DataFrame(hist_ws.get_all_records())
        except:
            hist_data = pd.DataFrame(columns=["날짜", "프로젝트명", "주요현황", "작성자"])

        summary = []
        for ws in all_ws:
            try:
                # 빈 시트일 경우 기본값 설정
                data_list = ws.get_all_records()
                p_df = pd.DataFrame(data_list)
                
                prog = 0
                if not p_df.empty and '진행률' in p_df.columns:
                    prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1)
                
                note = "최신 브리핑이 없습니다."
                if not hist_data.empty:
                    latest_p_hist = hist_data[hist_data['프로젝트명'] == ws.title].tail(1)
                    if not latest_p_hist.empty:
                        note = latest_p_hist.iloc[0]['주요현황']
                
                summary.append({"프로젝트명": ws.title, "진척률": prog, "최신현황": note})
            except Exception as e:
                continue # 에러 발생 시 해당 프로젝트만 건너뛰고 메인 화면은 유지
        
        if summary:
            st.divider()
            for idx, row in enumerate(summary):
                with st.container():
                    col1, col2, col3 = st.columns([2.5, 2, 5.5])
                    if col1.button(f"📂 {row['프로젝트명']}", key=f"btn_{idx}", use_container_width=True):
                        st.session_state["selected_menu"] = row['프로젝트명']
                        st.rerun()
                    col2.write(f"**진척률: {row['진척률']}%**")
                    col2.progress(float(row['진척률'] / 100))
                    col3.info(f"{row['최신현황']}")
                st.write("")
            
            st.divider()
            sum_df = pd.DataFrame(summary)
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True), use_container_width=True)
        else:
            st.info("관리 중인 프로젝트가 없습니다.")

    # ---------------------------------------------------------
    # CASE 2: 상세 관리 (수정/등록 로직 유지)
    # ---------------------------------------------------------
    else:
        p_name = st.session_state["selected_menu"]
        target_ws = sh.worksheet(p_name)
        data_all = target_ws.get_all_records()
        df_raw = pd.DataFrame(data_all) if data_all else pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        
        st.title(f"🏗️ {p_name} 상세 관리")
        t1, t2, t3, t4 = st.tabs(["📊 통합 공정표", "📝 일정등록", "📢 현황업데이트", "📜 과거기록조회"])

        with t1:
            if not df_raw.empty:
                df = df_raw.copy()
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                df = df.sort_values(by='시작일', ascending=True)
                chart_df = df[df['대분류']!='MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                    fig.update_yaxes(autorange="reversed")
                    fig.update_xaxes(side="top", dtick="M1", tickformat="%Y-%m")
                    st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_raw, use_container_width=True)
                
                # 빠른 수정 (image_4d08e0.png의 기능)
                with st.expander("🔍 특정 공정 정보 빠르게 수정하기"):
                    edit_idx = st.selectbox("행 번호 선택", df_raw.index)
                    with st.form(f"quick_edit_{edit_idx}"):
                        c1, c2, c3 = st.columns([2, 5, 2])
                        new_s = c1.selectbox("상태", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(df_raw.iloc[edit_idx]['진행상태']))
                        new_n = c2.text_input("비고", value=df_raw.iloc[edit_idx]['비고'])
                        new_p = c3.number_input("진행률", 0, 100, int(df_raw.iloc[edit_idx]['진행률']))
                        if st.form_submit_button("반영"):
                            target_ws.update(f"E{edit_idx+2}:G{edit_idx+2}", [[new_s, new_n, new_p]])
                            time.sleep(0.5); st.rerun()

        with t2:
            st.subheader("📝 신규 일정 등록")
            with st.form("new_schedule"):
                c1, c2, c3 = st.columns(3)
                sd=c1.date_input("시작일"); ed=c2.date_input("종료일"); cat=c3.selectbox("대분류", ["인허가", "설계/조사", "토목공사", "기타"])
                name=st.text_input("공정명"); stat=st.selectbox("상태", ["예정", "진행중", "완료"]); pct=st.number_input("진행률", 0, 100, 0)
                if st.form_submit_button("추가"):
                    target_ws.append_row([str(sd), str(ed), cat, name, stat, "", pct, st.session_state['user_id']])
                    time.sleep(0.5); st.rerun()
