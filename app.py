## [PMS Revision History]
## 버전: Rev. 0.7.3 (Navigation & Card UI Optimization)
## 업데이트 요약:
## 1. 📂 원클릭 이동: 대시보드의 프로젝트 버튼 클릭 시 상세 페이지로 즉시 이동하는 내비게이션 로직 강화
## 2. 📱 모바일 UI 완성: 제목 폰트(1.25rem) 및 상단 여백 최소화 로직 유지 및 버튼 터치 영역 최적화
## 3. 🧊 차트 인터랙션 차단: 모바일 스크롤 방해를 막기 위한 Plotly Static Mode 완벽 적용
## 4. 🛡️ 보안 및 연동: 기존 비밀번호 보안 및 구글 시트(pms_db) 연동 코드 유지

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.7.3", page_icon="🏗️", layout="wide")

# --- [UI] 모바일 대응 커스텀 CSS ---
st.markdown("""
    <style>
    /* 전체 폰트 및 배경 최적화 */
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }

    /* 모바일 기기별 맞춤 레이아웃 (v0.7.3) */
    @media (max-width: 640px) {
        .main .block-container {
            padding-top: 0.8rem !important; 
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }
        .main .block-container h1 {
            font-size: 1.25rem !important;
            line-height: 1.3 !important;
            margin-bottom: 1rem !important;
            letter-spacing: -0.02em;
        }
        /* 프로젝트 리스트 버튼 간격 및 크기 */
        .stButton button {
            height: 48px !important;
            font-size: 15px !important;
            margin-bottom: 8px !important;
            font-weight: 600 !important;
        }
        /* 탭 메뉴 슬림화 */
        .stTabs [data-baseweb="tab"] {
            font-size: 12px !important;
            padding-left: 5px !important;
            padding-right: 5px !important;
        }
    }
    
    /* 공통 버튼 디자인: 카드 느낌 부여 */
    .stButton button {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
        background-color: white;
        color: #31333F;
    }
    .stButton button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- [보안] 로그인 체크 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if st.session_state["password_correct"]:
        return True
    
    st.title("🏗️ PM 통합 관리 시스템") 
    with st.form("login_form"):
        user_id = st.text_input("아이디 (ID)")
        password = st.text_input("비밀번호 (PW)", type="password")
        if st.form_submit_button("로그인"):
            # st.secrets에 저장된 계정 정보 확인
            user_db = st.secrets["passwords"]
            if user_id in user_db and password == user_db[user_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = user_id
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
        st.error(f"🚨 구글 시트 연결 오류: {e}"); return None

client = get_client()
if client:
    sh = client.open('pms_db')
    
    # 시스템 시트 제외하고 프로젝트 리스트 추출
    forbidden = ['weekly_history', 'conflict', 'Sheet1']
    all_ws = [ws for ws in sh.worksheets() if not any(k in ws.title for k in forbidden)]
    pjt_names = [s.title for s in all_ws]
    
    # 주간 히스토리 시트 확인 또는 생성
    try:
        hist_ws = sh.worksheet('weekly_history')
    except:
        hist_ws = sh.add_worksheet(title='weekly_history', rows="1000", cols="5")
        hist_ws.append_row(["날짜", "프로젝트명", "주요현황", "작성자"])

    # 초기 메뉴 설정
    if "selected_menu" not in st.session_state:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"

    # 사이드바 구성
    st.sidebar.title("📁 PMO 센터")
    st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']}** 님")
    
    menu = ["🏠 전체 대시보드"] + pjt_names
    # 세션 상태가 메뉴 목록에 없으면 기본값으로 리셋
    if st.session_state["selected_menu"] not in menu:
        st.session_state["selected_menu"] = "🏠 전체 대시보드"
        
    selected = st.sidebar.selectbox("🎯 메뉴 선택", menu, index=menu.index(st.session_state["selected_menu"]), key="nav_menu")
    st.session_state["selected_menu"] = selected

    # 프로젝트 신규 생성 기능
    with st.sidebar.expander("➕ 프로젝트 추가"):
        new_name = st.text_input("새 프로젝트 명칭")
        if st.button("시트 생성"):
            if new_name and new_name not in pjt_names:
                new_ws = sh.add_worksheet(title=new_name, rows="100", cols="20")
                new_ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
                st.success(f"'{new_name}' 생성 완료!"); time.sleep(1); st.rerun()

    # ---------------------------------------------------------
    # CASE 1: 전체 대시보드 (메인 화면)
    # ---------------------------------------------------------
    if st.session_state["selected_menu"] == "🏠 전체 대시보드":
        st.title("📊 프로젝트 통합 대시보드")
        
        # 히스토리 데이터 로드
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
                    # 진행률 컬럼의 평균 계산
                    prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1)
                
                note = "최신 브리핑 데이터가 없습니다."
                if not hist_data.empty:
                    latest = hist_data[hist_data['프로젝트명'] == ws.title].tail(1)
                    if not latest.empty: note = latest.iloc[0]['주요현황']
                
                summary.append({"프로젝트명": ws.title, "진척률": prog, "최신현황": note})
            except: continue
        
        if summary:
            st.divider()
            for idx, row in enumerate(summary):
                # 개별 프로젝트 정보 카드
                with st.container():
                    # [사용자 요청 반영] 프로젝트 버튼 클릭 시 상세 페이지로 이동
                    if st.button(f"📂 {row['프로젝트명']}", key=f"btn_{idx}", use_container_width=True):
                        st.session_state["selected_menu"] = row['프로젝트명']
                        st.rerun() # 즉시 페이지 전환
                    
                    c1, c2 = st.columns([4, 6])
                    c1.markdown(f"**진척률: {row['진척률']}%**")
                    c2.progress(float(row['진척률'] / 100))
                    st.info(f"{row['최신현황']}")
                st.write("") # 카드 간 여백
            
            st.divider()
            sum_df = pd.DataFrame(summary)
            # 전체 막대 차트: 모바일 스크롤 간섭 방지를 위해 staticPlot 적용
            fig_main = px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True, title="프로젝트별 진도율 비교")
            st.plotly_chart(fig_main, use_container_width=True, config={'staticPlot': True})

    # ---------------------------------------------------------
    # CASE 2: 프로젝트 상세 관리 페이지
    # ---------------------------------------------------------
    else:
        p_name = st.session_state["selected_menu"]
        target_ws = sh.worksheet(p_name)
        data_all = target_ws.get_all_records()
        df_raw = pd.DataFrame(data_all) if data_all else pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
        
        st.title(f"🏗️ {p_name} 관리")
        t1, t2, t3, t4 = st.tabs(["📊 공정표", "📝 일정등록", "📢 현황보고", "📜 히스토리"])

        with t1:
            if not df_raw.empty:
                df = df_raw.copy()
                df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
                df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
                df = df.sort_values(by='시작일', ascending=True)
                
                # 간트 차트 생성 (마일스톤 제외)
                chart_df = df[df['대분류']!='MILESTONE'].dropna(subset=['시작일', '종료일'])
                if not chart_df.empty:
                    fig_detail = px.timeline(chart_df, x_start="시작일", x_end="종료일", y="구분", color="진행상태")
                    fig_detail.update_yaxes(autorange="reversed")
                    fig_detail.update_xaxes(side="top", dtick="M1", tickformat="%Y-%m")
                    st.plotly_chart(fig_detail, use_container_width=True, config={'staticPlot': True})
                
                st.subheader("📋 전체 공정 리스트")
                st.dataframe(df_raw, use_container_width=True)
                
                # 빠른 데이터 수정 폼
                with st.expander("🔍 특정 항목 빠르게 수정"):
                    edit_idx = st.selectbox("수정할 행 번호 선택", df_raw.index)
                    with st.form(f"quick_edit_{edit_idx}"):
                        row = df_raw.iloc[edit_idx]
                        col1, col2 = st.columns(2)
                        new_s = col1.selectbox("상태 변경", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
                        new_p = col2.number_input("진행률(%)", 0, 100, int(row['진행률']))
                        new_n = st.text_input("비고 수정", value=row['비고'])
                        if st.form_submit_button("시트에 반영"):
                            # E(상태), F(비고), G(진행률) 컬럼 업데이트
                            target_ws.update(f"E{edit_idx+2}:G{edit_idx+2}", [[new_s, new_n, new_p]])
                            st.toast("업데이트 성공!"); time.sleep(0.5); st.rerun()

        with t2:
            st.subheader("📝 신규 일정 등록")
            with st.form("new_schedule_form"):
                c1, c2 = st.columns(2)
                sd = c1.date_input("시작일")
                ed = c2.date_input("종료일")
                cat = st.selectbox("대분류", ["인허가", "설계/조사", "토목공사", "기타"])
                name = st.text_input("상세 공정명")
                stat = st.selectbox("초기 상태", ["예정", "진행중", "완료"])
                pct = st.number_input("초기 진행률(%)", 0, 100, 0)
                if st.form_submit_button("공정표에 추가"):
                    target_ws.append_row([str(sd), str(ed), cat, name, stat, "", pct, st.session_state['user_id']])
                    st.success("새 일정이 추가되었습니다."); time.sleep(0.5); st.rerun()

        with t3:
            st.subheader("📢 주간 현황 보고 업데이트")
            with st.form("update_report_form"):
                new_status = st.text_area("이번 주 주요 활동 및 이슈 사항을 입력하세요.")
                if st.form_submit_button("저장 및 대시보드 반영"):
                    # 현재 시간을 기록하여 히스토리 시트에 저장
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    hist_ws.append_row([timestamp, p_name, new_status, st.session_state['user_id']])
                    st.success("현황이 저장되었습니다."); time.sleep(0.5); st.rerun()

        with t4:
            st.subheader("📜 과거 기록 조회")
            # 전체 히스토리에서 현재 프로젝트에 해당하는 것만 필터링 (최신순)
            h_data = pd.DataFrame(hist_ws.get_all_records())
            if not h_data.empty:
                filtered_h = h_data[h_data['프로젝트명'] == p_name].iloc[::-1]
                if filtered_h.empty:
                    st.info("아직 기록된 히스토리가 없습니다.")
                else:
                    for _, hr in filtered_h.iterrows():
                        with st.expander(f"📅 {hr['날짜']} | 작성자: {hr['작성자']}"):
                            st.write(hr['주요현황'])
