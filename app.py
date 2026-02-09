## [PMS Revision History]
## 버전: Rev. 0.6.3 (API Stability & Bug Fix)
## 업데이트 요약:
## 1. 🚀 API 호출 안정화: 데이터 업데이트 후 짧은 대기(0.5초) 추가로 API 충돌 방지
## 2. 🛡️ 에러 핸들링: hist_ws.get_all_records() 호출 시 예외 처리를 추가하여 서버 오류 시에도 앱 유지
## 3. 📂 리소스 관리: 시트 연결 및 데이터 취합 시 불필요한 호출 최소화

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.6.3", page_icon="🏗️", layout="wide")

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
    
    # 관리용 시트 제외 리스트업
    all_ws = [ws for ws in sh.worksheets() if not ws.title.startswith('weekly_history')]
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
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu, index=menu.index(st.session_state["selected_menu"]), key="nav_menu")
    st.session_state["selected_menu"] = selected

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드 (API 에러 방어 로직 적용)
    # ---------------------------------------------------------
    if st.session_state["selected_menu"] == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        
        # [수정] API 호출 실패 시 빈 데이터프레임으로 대체하여 중단 방지
        try:
            hist_data = pd.DataFrame(hist_ws.get_all_records())
        except Exception as e:
            hist_data = pd.DataFrame(columns=["날짜", "프로젝트명", "주요현황", "작성자"])
            st.warning("⚠️ 히스토리 데이터를 불러오는 중 일시적인 API 지연이 발생했습니다. 잠시 후 새로고침 해주세요.")
        
        summary = []
        for ws in all_ws:
            try:
                p_df = pd.DataFrame(ws.get_all_records())
                prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if not p_df.empty else 0
                
                note = "최신 브리핑 데이터가 없습니다."
                if not hist_data.empty:
                    latest_p_hist = hist_data[hist_data['프로젝트명'] == ws.title].tail(1)
                    if not latest_p_hist.empty:
                        note = latest_p_hist.iloc[0]['주요현황']
                
                summary.append({"프로젝트명": ws.title, "진척률": prog, "최신현황": note})
            except: continue
        
        if summary:
            st.divider()
            for idx, row in enumerate(summary):
                with st.container():
                    col1, col2, col3 = st.columns([2.5, 2, 5.5])
                    if col1.button(f"📂 {row['프로젝트명']}", key=f"btn_{idx}", use_container_width=True):
                        st.session_state["selected_menu"] = row['프로젝트명']
                        st.rerun()
                    col2.write(f"**진척률: {row['진척률']}%**")
                    col2.progress(row['진척률'] / 100)
                    col3.info(f"{row['최신현황']}")
                st.write("")
            
            st.divider()
            sum_df = pd.DataFrame(summary)
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True), use_container_width=True)

    # ---------------------------------------------------------
    # CASE 2: 상세 관리
    # ---------------------------------------------------------
    else:
        p_name = st.session_state["selected_menu"]
        target_ws = sh.worksheet(p_name)
        # 상세 페이지 로딩 시에도 API 보호를 위한 지연 시도
        try:
            data_raw = target_ws.get_all_records()
            df_raw = pd.DataFrame(data_raw)
        except:
            st.error("데이터를 불러오는데 실패했습니다. 잠시 후 다시 시도해 주세요.")
            st.stop()
        
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

        with t3:
            st.subheader("📢 주간 현황 누적 업데이트")
            curr_note = df_raw.iloc[0]['비고'] if not df_raw.empty else ""
            with st.form("up_form"):
                new_status = st.text_area("이번 주 주요 현황 및 이슈 작성", value=curr_note)
                if st.form_submit_button("기록 저장 및 대시보드 반영"):
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    hist_ws.append_row([now, p_name, new_status, st.session_state['user_id']])
                    time.sleep(0.5) # API 충돌 방지 대기
                    target_ws.update_acell("F2", new_status)
                    st.success("기록되었습니다."); time.sleep(1); st.rerun()

            st.divider()

            st.subheader("🛠️ 개별 공정 현황 수정")
            if not df_raw.empty:
                df_raw['sel'] = df_raw['구분'] + " (" + df_raw['시작일'].astype(str) + ")"
                target_task = st.selectbox("수정할 공정 선택", df_raw['sel'].tolist())
                idx = df_raw[df_raw['sel'] == target_task].index[0]
                row = df_raw.iloc[idx]
                
                with st.form("edit_task"):
                    c1, c2 = st.columns(2)
                    ns = c1.selectbox("상태", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
                    np = c2.number_input("진행률(%)", 0, 100, int(row['진행률']))
                    nm = st.text_area("공정별 세부 비고", value=row['비고'])
                    if st.form_submit_button("공정 정보 업데이트"):
                        # 업데이트 전 짧은 대기 후 전송
                        time.sleep(0.2)
                        target_ws.update(f"E{idx+2}:G{idx+2}", [[ns, nm, np]])
                        st.success("수정 완료!"); time.sleep(1); st.rerun()
