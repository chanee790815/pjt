## [PMS Revision History]
## 버전: Rev. 0.7.2 (Ultra Mobile UI Optimization)
## 업데이트 요약:
## 1. 📱 타이틀 미세 조정: 모바일에서 제목(h1)이 두 줄로 넘어가며 여백을 낭비하지 않도록 크기 추가 축소 (1.4rem -> 1.25rem)
## 2. 📏 여백 최적화: 모바일 상단 패딩을 줄여 첫 화면에서 더 많은 프로젝트 리스트가 보이도록 개선
## 3. 🧊 차트 고정 유지: Plotly 차트의 Static Mode를 유지하여 부드러운 스크롤 환경 제공
## 4. 🛡️ 보안 유지: 비공개 저장소 및 Secrets 연동 로직 완벽 유지

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.7.2", page_icon="🏗️", layout="wide")

# --- [UI] 모바일 대응 커스텀 CSS ---
st.markdown("""
    <style>
    /* 전체 기본 폰트 최적화 */
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }

    /* 모바일 글꼴 및 레이아웃 최적화 (v0.7.2 추가 수정) */
    @media (max-width: 640px) {
        .main .block-container {
            padding-top: 0.5rem !important; /* 상단 여백 대폭 축소 */
            padding-left: 0.7rem !important;
            padding-right: 0.7rem !important;
        }
        .main .block-container h1 {
            font-size: 1.25rem !important; /* 제목 크기 최적화 */
            line-height: 1.3 !important;
            margin-bottom: 0.8rem !important;
            letter-spacing: -0.02em;
        }
        .main .block-container h2 {
            font-size: 1.1rem !important;
        }
        /* 탭 메뉴 글자 크기 및 간격 최적화 */
        .stTabs [data-baseweb="tab"] {
            font-size: 12px !important;
            padding-left: 6px !important;
            padding-right: 6px !important;
            height: 35px !important;
        }
        /* 가젯 및 카드 내부 텍스트 크기 */
        .stAlert {
            padding: 0.5rem !important;
            font-size: 0.85rem !important;
        }
    }
    
    /* 버튼 스타일 및 여백 통일 */
    .stButton button {
        margin-bottom: 4px;
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* 사이드바 너비 최적화 */
    [data-testid="stSidebar"] {
        min-width: 200px !important;
        max-width: 250px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- [보안] 멀티 계정 로그인 체크 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    
    st.title("🏗️ PM 통합 관리") 
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
    
    forbidden = ['weekly_history', 'conflict', 'Sheet1']
    all_ws = [ws for ws in sh.worksheets() if not any(k in ws.title for k in forbidden)]
    pjt_names = [s.title for s in all_ws]
    
    try:
        hist_ws = sh.worksheet('weekly_history')
    except:
        hist_ws = sh.add_worksheet(title='weekly_history', rows="1000", cols="5")
        hist_ws.append_row(["날짜", "프로젝트명", "주요현황", "작성자"])

    if "selected_menu" not in st.session_state:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"

    # 사이드바 구성
    st.sidebar.title("📁 PMO 센터")
    st.sidebar.write(f"👤 **{st.session_state['user_id']}** 님")
    
    menu = ["🏠 전체 대시보드"] + pjt_names
    if st.session_state["selected_menu"] not in menu:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"
        
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu, index=menu.index(st.session_state["selected_menu"]), key="nav_menu")
    st.session_state["selected_menu"] = selected

    with st.sidebar.expander("➕ 프로젝트 추가"):
        new_name = st.text_input("명칭 입력")
        if st.button("생성"):
            if new_name and new_name not in pjt_names:
                new_ws = sh.add_worksheet(title=new_name, rows="100", cols="20")
                new_ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
                st.success("완료!"); time.sleep(1); st.rerun()

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드
    # ---------------------------------------------------------
    if st.session_state["selected_menu"] == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        
        try:
            hist_data = pd.DataFrame(hist_ws.get_all_records())
        except:
            hist_data = pd.DataFrame(columns=["날짜", "프로젝트명", "주요현황", "작성자"])

        summary = []
        for ws in all_ws:
            try:
                data = ws.get_all_records()
                p_df = pd.DataFrame(data)
                prog = 0
                if not p_df.empty and '진행률' in p_df.columns:
                    prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1)
                
                note = "최신 브리핑 없음"
                if not hist_data.empty:
                    latest = hist_data[hist_data['프로젝트명'] == ws.title].tail(1)
                    if not latest.empty: note = latest.iloc[0]['주요현황']
                
                summary.append({"프로젝트명": ws.title, "진척률": prog, "최신현황": note})
            except: continue
        
        if summary:
            st.divider()
            for idx, row in enumerate(summary):
                with st.container():
                    c1, c2 = st.columns([4, 6])
                    if c1.button(f"📂 {row['프로젝트명']}", key=f"btn_{idx}", use_container_width=True):
                        st.session_state["selected_menu"] = row['프로젝트명']; st.rerun()
                    c2.write(f"**진척률: {row['진척률']}%**")
                    c2.progress(float(row['진척률'] / 100))
                    st.info(f"{row['최신현황']}")
                st.write("")
            
            st.divider()
            sum_df = pd.DataFrame(summary)
            # 메인 차트: Static 모드 유지
            fig_main = px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True)
            st.plotly_chart(fig_main, use_container_width=True, config={'staticPlot': True})

    # ---------------------------------------------------------
    # CASE 2: 상세 관리
    # ---------------------------------------------------------
    else:
        p_name = st.session_state["selected_menu"]
        target_ws = sh.worksheet(p_name)
        data_all = target_ws.get_all_records()
        df_raw = pd.DataFrame(data_all) if data_all else pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        
        st.title(f"🏗️ {p_name}")
        t1, t2, t3, t4 = st.tabs(["📊 공정표", "📝 등록", "📢 업데이트", "📜 기록"])

        with t1:
            if not df_raw.empty:
                df = df_raw.copy()
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                df = df.sort_values(by='시작일', ascending=True)
                chart_df = df[df['대분류']!='MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    fig_detail = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                    fig_detail.update_yaxes(autorange="reversed")
                    fig_detail.update_xaxes(side="top", dtick="M1", tickformat="%Y-%m")
                    st.plotly_chart(fig_detail, use_container_width=True, config={'staticPlot': True})
                
                st.subheader("📋 빠른 수정")
                st.dataframe(df_raw, use_container_width=True)
                
                with st.expander("🔍 정보 수정하기"):
                    edit_idx = st.selectbox("수정 행 선택", df_raw.index)
                    with st.form(f"quick_edit_{edit_idx}"):
                        row = df_raw.iloc[edit_idx]
                        new_s = st.selectbox("상태", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
                        new_n = st.text_input("비고", value=row['비고'])
                        new_p = st.number_input("진행률", 0, 100, int(row['진행률']))
                        if st.form_submit_button("반영"):
                            target_ws.update(f"E{edit_idx+2}:G{edit_idx+2}", [[new_s, new_n, new_p]])
                            time.sleep(0.5); st.rerun()

        with t2:
            st.subheader("📝 일정 등록")
            with st.form("new_schedule"):
                sd=st.date_input("시작일")
                ed=st.date_input("종료일")
                cat=st.selectbox("대분류", ["인허가", "설계/조사", "토목공사", "기타"])
                name=st.text_input("공정명")
                stat=st.selectbox("상태", ["예정", "진행중", "완료"])
                pct=st.number_input("진행률", 0, 100, 0)
                if st.form_submit_button("추가"):
                    target_ws.append_row([str(sd), str(ed), cat, name, stat, "", pct, st.session_state['user_id']])
                    time.sleep(0.5); st.rerun()

        with t3:
            st.subheader("📢 현황 업데이트")
            with st.form("up_form"):
                new_status = st.text_area("주요 현황 및 이슈 작성")
                if st.form_submit_button("저장 및 반영"):
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    hist_ws.append_row([now, p_name, new_status, st.session_state['user_id']])
                    time.sleep(0.5); st.rerun()

        with t4:
            st.subheader("📜 과거 기록")
            h_data = pd.DataFrame(hist_ws.get_all_records())
            if not h_data.empty:
                p_h = h_data[h_data['프로젝트명'] == p_name].iloc[::-1]
                for _, hr in p_h.iterrows():
                    with st.expander(f"📅 {hr['날짜']} | {hr['작성자']}"):
                        st.write(hr['주요현황'])
