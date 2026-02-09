

## [PMS Revision History]
## 버전: Rev. 0.5.5 (Final Navigation)
## 업데이트 요약:
## 1. 🚀 대시보드 인터랙션: 프로젝트 버튼 클릭 시 상세 관리 페이지로 즉시 전환
## 2. 🔐 멀티 계정 인증: 관리자 및 팀원별 ID/PW 로그인 연동
## 3. 📊 시각화 최적화: 간트 차트 상단 날짜축 및 시작일 순 공정 정렬
## 4. ⚙️ 데이터 관리: 주간 현황 브리핑 및 개별 공정 수정 기능 통합

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.5.5", page_icon="🏗️", layout="wide")

# --- [보안] 로그인 체크 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True

    st.title("🏗️ PM 통합 공정 관리 시스템")
    st.subheader("계정 정보를 입력해 주세요.")
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)")
        password = st.text_input("비밀번호 (PW)", type="password")
        if st.form_submit_button("로그인"):
            user_db = st.secrets["passwords"]
            if user_id in user_db and password == user_db[user_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = user_id
                st.success(f"{user_id}님 환영합니다!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
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
        creds = Credentials.from_service_account_info(
            key_dict, 
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"🚨 구글 연결 오류: {e}"); return None

# --- 메인 실행 ---
client = get_client()
if client:
    sh = client.open('pms_db')
    all_ws = sh.worksheets()
    pjt_names = [s.title for s in all_ws]
    
    # [사이드바]
    st.sidebar.title("📁 PMO 프로젝트 센터")
    st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']}**")
    if st.sidebar.button("🔓 로그아웃"):
        st.session_state["password_correct"] = False
        st.rerun()
    
    st.sidebar.divider()
    
    # [내비게이션 관리]
    menu = ["🏠 전체 대시보드"] + pjt_names
    if "selected_menu" not in st.session_state:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"

    # 사이드바 메뉴 선택 (세션 상태와 동기화)
    selected = st.sidebar.selectbox(
        "🎯 메뉴 선택", 
        menu, 
        index=menu.index(st.session_state["selected_menu"]),
        key="main_menu"
    )
    st.session_state["selected_menu"] = selected

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드 (클릭 시 이동 기능 핵심)
    # ---------------------------------------------------------
    if st.session_state["selected_menu"] == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        summary = []
        for ws in all_ws:
            try:
                data = ws.get_all_records()
                if not data: continue
                df = pd.DataFrame(data)
                df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                prog = round(df['진행률'].mean(), 1)
                note = df.iloc[0]['비고'] if '비고' in df.columns else "-"
                summary.append({"프로젝트명": ws.title, "진척률": prog, "주간현황": note})
            except: continue
        
        if summary:
            sum_df = pd.DataFrame(summary)
            st.subheader("📋 프로젝트별 주간 브리핑")
            st.write("🔍 **프로젝트명을 클릭하면 해당 상세 페이지로 이동합니다.**")

            # 헤더 구성
            h1, h2, h3 = st.columns([2, 1, 4])
            h1.write("**프로젝트명**")
            h2.write("**진척률**")
            h3.write("**주간 주요 현황**")
            st.divider()

            # 프로젝트별 이동 버튼 생성
            for idx, row in sum_df.iterrows():
                c1, c2, c3 = st.columns([2, 1, 4])
                # 버튼 클릭 시 세션 상태를 변경하여 화면 전환
                if c1.button(f"📂 {row['프로젝트명']}", key=f"pjt_{idx}", use_container_width=True):
                    st.session_state["selected_menu"] = row['프로젝트명']
                    st.rerun()
                c2.write(f"**{row['진척률']}%**")
                c3.info(row['주간현황'])

            st.divider()
            st.plotly_chart(px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True), use_container_width=True)

    # ---------------------------------------------------------
    # CASE 2: 개별 프로젝트 상세 관리 (Gantt 차트 화면)
    # ---------------------------------------------------------
    else:
        target_ws = sh.worksheet(st.session_state["selected_menu"])
        df_raw = pd.DataFrame(target_ws.get_all_records())
        
        st.title(f"🏗️ {st.session_state['selected_menu']} 상세 관리")
        t1, t2, t3 = st.tabs(["📊 통합 공정표", "📝 일정 등록", "⚙️ 현황 및 관리"])

        with t1:
            if not df_raw.empty:
                df = df_raw.copy()
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                df = df.sort_values(by='시작일', ascending=True)

                # 간트 차트 (이미지 2, 8번의 화면 구현)
                chart_df = df[df['대분류'] != 'MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                    fig.update_yaxes(autorange="reversed")
                    fig.update_xaxes(side="top", dtick="M1", tickformat="%Y-%m")
                    fig.update_layout(height=500, template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df_raw, use_container_width=True)
            else:
                st.info("💡 등록된 공정이 없습니다.")

        with t3:
            # 주간 현황 및 명칭 관리 (이미지 4번 화면 구현)
            st.subheader("📢 주간 주요 현황 업데이트")
            curr_note = df_raw.iloc[0]['비고'] if not df_raw.empty else ""
            with st.form("up_f"):
                new_t = st.text_input("이번 주 주요 이슈", value=curr_note)
                if st.form_submit_button("현황 반영"):
                    target_ws.update_acell("F2", new_t); st.success("반영 완료!"); time.sleep(1); st.rerun()
            
            st.divider()
            # 개별 공정 수정 기능 (이전 버전 유지)
            if not df_raw.empty:
                st.subheader("🛠️ 개별 공정 현황 수정")
                df_raw['sel'] = df_raw['구분'] + " (" + df_raw['시작일'].astype(str) + ")"
                task = st.selectbox("수정할 공정 선택", df_raw['sel'].tolist())
                idx = df_raw[df_raw['sel'] == task].index[0]
                with st.form("edit_f"):
                    c1, c2 = st.columns(2)
                    ns = c1.selectbox("상태", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(df_raw.iloc[idx]['진행상태']))
                    np = c2.number_input("진행률", 0, 100, int(df_raw.iloc[idx]['진행률']))
                    if st.form_submit_button("수정 완료"):
                        target_ws.update(f"E{idx+2}:G{idx+2}", [[ns, df_raw.iloc[idx]['비고'], np]])
                        st.success("수정 성공!"); time.sleep(1); st.rerun()
