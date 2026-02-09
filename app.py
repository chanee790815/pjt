## [PMS Revision History]
## 버전: Rev. 0.8.5 (KPI Layout Synchronization)
## 업데이트 요약:
## 1. 🎯 KPI 레이아웃 동기화: 제공된 이미지의 컬럼 순서 및 7대 지표 항목(매출, 이익, 설계, 공정, 안전, 기술, 채권) 완벽 반영
## 2. 📊 실적 시각화: KPI 항목별 목표 대비 달성률을 시각화하는 바 차트 추가
## 3. 🛡️ 안정성 유지: API Quota 에러 방지를 위한 리소스 캐싱 및 데이터 로드 실패 대응 로직 유지
## 4. 📱 모바일 최적화: 반응형 UI 및 차트 고정 설정(Static Mode) 유지

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.8.5", page_icon="🏗️", layout="wide")

# --- [UI] 모바일 대응 커스텀 CSS ---
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
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
        }
        .stButton button {
            height: 48px !important;
            font-size: 15px !important;
            font-weight: 600 !important;
        }
    }
    .stButton button {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
        background-color: white;
    }
    .stButton button:hover {
        border-color: #ff4b4b;
        color: #ff4b4b;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- [보안] 로그인 및 로그아웃 체크 ---
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
            user_db = st.secrets["passwords"]
            if user_id in user_db and password == user_db[user_id]:
                st.session_state["password_correct"] = True
                st.session_state["user_id"] = user_id
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
    return False

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

if not check_password():
    st.stop()

# --- 구글 시트 연결 및 리소스 캐싱 ---
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
        st.error(f"🚨 구글 API 인증 오류: {e}"); return None

@st.cache_resource
def get_spreadsheet(_client):
    try:
        return _client.open('pms_db')
    except Exception as e:
        raise e

@st.cache_data(ttl=300)
def fetch_dashboard_summary(_spreadsheet_id, _client_email):
    """프로젝트 목록, 요약 정보 및 KPI 데이터를 일괄 로드"""
    try:
        temp_client = get_client()
        sh = temp_client.open('pms_db')
        forbidden = ['weekly_history', 'conflict', 'Sheet1', 'KPI']
        all_worksheets = sh.worksheets()
        
        pjt_sheets = [ws for ws in all_worksheets if not any(k in ws.title for k in forbidden)]
        pjt_names = [ws.title for ws in pjt_sheets]
        
        # 1. 히스토리 로드
        try:
            hist_ws = sh.worksheet('weekly_history')
            hist_data = pd.DataFrame(hist_ws.get_all_records())
        except:
            hist_data = pd.DataFrame(columns=["날짜", "프로젝트명", "주요현황", "작성자"])

        # 2. KPI 데이터 로드
        try:
            kpi_ws = sh.worksheet('KPI')
            kpi_data = pd.DataFrame(kpi_ws.get_all_records())
        except:
            kpi_data = pd.DataFrame()

        # 3. 프로젝트 요약 생성
        summary = []
        for ws in pjt_sheets:
            try:
                time.sleep(0.05)
                data = ws.get_all_records()
                p_df = pd.DataFrame(data)
                prog = 0
                if not p_df.empty and '진행률' in p_df.columns:
                    prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1)
                
                note = "최신 브리핑 데이터가 없습니다."
                if not hist_data.empty:
                    latest = hist_data[hist_data['프로젝트명'] == ws.title].tail(1)
                    if not latest.empty: note = latest.iloc[0]['주요현황']
                
                summary.append({"프로젝트명": ws.title, "진척률": prog, "최신현황": note})
            except: 
                summary.append({"프로젝트명": ws.title, "진척률": 0, "최신현황": "데이터 로딩 지연 중..."})
            
        return pjt_names, summary, hist_data, kpi_data
    except Exception as e:
        raise e

@st.cache_data(ttl=60)
def get_ws_data(_client_email, pjt_name):
    temp_client = get_client()
    sh = temp_client.open('pms_db')
    ws = sh.worksheet(pjt_name)
    return ws.get_all_records()

client = get_client()

if client:
    try:
        sh = get_spreadsheet(client)
        
        with st.spinner('데이터를 불러오고 있습니다...'):
            pjt_names, summary_list, full_hist_data, kpi_df = fetch_dashboard_summary(sh.id, st.secrets["gcp_service_account"]["client_email"])
        
        menu_options = ["🏠 전체 대시보드"] + pjt_names
        
        if "selected_project" not in st.session_state:
            st.session_state["selected_project"] = "🏠 전체 대시보드"

        # 사이드바 구성
        st.sidebar.title("📁 PMO 센터")
        st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']}** 님")
        
        try:
            current_index = menu_options.index(st.session_state["selected_project"])
        except ValueError:
            current_index = 0

        selected_menu = st.sidebar.selectbox("🎯 메뉴 선택", menu_options, index=current_index)
        
        if selected_menu != st.session_state["selected_project"]:
            st.session_state["selected_project"] = selected_menu
            st.rerun()

        if st.sidebar.button("🔄 데이터 새로고침"):
            st.cache_data.clear()
            st.rerun()

        with st.sidebar.expander("➕ 프로젝트 추가"):
            new_name = st.text_input("새 프로젝트 명칭")
            if st.button("시트 생성"):
                if new_name and new_name not in pjt_names:
                    new_ws = sh.add_worksheet(title=new_name, rows="100", cols="20")
                    new_ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
                    st.cache_data.clear()
                    st.success(f"'{new_name}' 생성 완료!"); time.sleep(1); st.rerun()

        st.sidebar.markdown("---")
        if st.sidebar.button("🔓 로그아웃"):
            logout()

        # ---------------------------------------------------------
        # CASE 1: 전체 대시보드
        # ---------------------------------------------------------
        if st.session_state["selected_project"] == "🏠 전체 대시보드":
            st.title("📊 통합 대시보드 및 경영지표")
            
            main_t1, main_t2 = st.tabs(["🏗️ 프로젝트 현황", "🎯 경영지표(KPI)"])

            with main_t1:
                if summary_list:
                    st.write("")
                    for idx, row in enumerate(summary_list):
                        with st.container():
                            if st.button(f"📂 {row['프로젝트명']}", key=f"pjt_btn_{idx}", use_container_width=True):
                                st.session_state["selected_project"] = row['프로젝트명']
                                st.rerun()
                            c1, c2 = st.columns([4, 6])
                            c1.markdown(f"**진척률: {row['진척률']}%**")
                            c2.progress(float(row['진척률'] / 100))
                            st.info(f"{row['최신현황']}")
                        st.write("")
                    
                    st.divider()
                    sum_df = pd.DataFrame(summary_list)
                    fig_main = px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True, title="프로젝트별 진도율")
                    st.plotly_chart(fig_main, use_container_width=True, config={'staticPlot': True})
                else:
                    st.warning("표시할 프로젝트 데이터가 없습니다.")

            with main_t2:
                st.subheader("📈 PM팀 경영지표 (KPI)")
                if not kpi_df.empty:
                    # 이미지 순서대로 컬럼 정렬 및 출력
                    cols_order = ['KPI 구분', 'KPI 항목', '정의/산식', '평가기준', '목표치', '실적', '달성률(%)', '가중치(%)']
                    # 실제 존재하는 컬럼만 필터링
                    display_cols = [c for c in cols_order if c in kpi_df.columns]
                    st.dataframe(kpi_df[display_cols], use_container_width=True, hide_index=True)
                    
                    st.write("")
                    chart_col1, chart_col2 = st.columns(2)
                    
                    with chart_col1:
                        if 'KPI 항목' in kpi_df.columns and '가중치(%)' in kpi_df.columns:
                            fig_kpi_pie = px.pie(kpi_df, values='가중치(%)', names='KPI 항목', hole=.4, title="항목별 가중치 분포")
                            st.plotly_chart(fig_kpi_pie, use_container_width=True, config={'staticPlot': True})
                    
                    with chart_col2:
                        if 'KPI 항목' in kpi_df.columns and '달성률(%)' in kpi_df.columns:
                            # 달성률 숫자 변환
                            kpi_df['달성률_num'] = pd.to_numeric(kpi_df['달성률(%)'].astype(str).str.replace('%',''), errors='coerce').fillna(0)
                            fig_kpi_bar = px.bar(kpi_df, x='KPI 항목', y='달성률_num', text_auto=True, title="지표별 달성률(%)", color='달성률_num', color_continuous_scale='RdYlGn')
                            st.plotly_chart(fig_kpi_bar, use_container_width=True, config={'staticPlot': True})
                else:
                    st.info("💡 **KPI 데이터 연동 방법**")
                    st.write("""
                    구글 시트(`pms_db`)에 **KPI** 시트를 만들고 아래 순서대로 데이터를 입력하세요.
                    1. **KPI 구분**: EPC매출액, 실행이익률, 설계지원 등
                    2. **KPI 항목**: 연간 매출금액, 프로젝트 실행원가율 등
                    3. **정의/산식** / **평가기준** / **목표치** / **실적** / **달성률(%)** / **가중치(%)**
                    """)
                    
                    # 이미지 기반 샘플 데이터 구성
                    sample_data = {
                        "KPI 구분": ["EPC매출액", "실행이익률", "설계지원", "공정준수율", "안전환경관리점수", "기술표준화", "매출채권"],
                        "KPI 항목": ["연간 매출금액", "프로젝트 실행원가율", "프로젝트 설계지원", "준공율", "안전관리", "원가절감", "매출채권"],
                        "목표치": ["712.36억원", "88.00%이하", "60건", "100%", "0.00", "5건", "0.00"],
                        "가중치(%)": [40, 20, 10, 2.5, 10, 2.5, 5]
                    }
                    st.table(pd.DataFrame(sample_data))

        # ---------------------------------------------------------
        # CASE 2: 프로젝트 상세 관리
        # ---------------------------------------------------------
        else:
            p_name = st.session_state["selected_project"]
            data_all = get_ws_data(st.secrets["gcp_service_account"]["client_email"], p_name)
            df_raw = pd.DataFrame(data_all) if data_all else pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
            
            st.title(f"🏗️ {p_name} 관리")
            t1, t2, t3, t4 = st.tabs(["📊 공정표", "📝 등록", "📢 현황보고", "📜 히스토리"])

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
                    
                    st.subheader("📋 전체 공정 리스트")
                    st.dataframe(df_raw, use_container_width=True)
                    
                    with st.expander("🔍 특정 항목 빠르게 수정"):
                        edit_idx = st.selectbox("수정할 행 번호 선택", df_raw.index)
                        with st.form(f"quick_edit_{edit_idx}"):
                            row = df_raw.iloc[edit_idx]
                            col1, col2 = st.columns(2)
                            new_s = col1.selectbox("상태 변경", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
                            new_p = col2.number_input("진행률(%)", 0, 100, int(row['진행률']))
                            new_n = st.text_input("비고 수정", value=row['비고'])
                            if st.form_submit_button("시트에 반영"):
                                try:
                                    target_ws = sh.worksheet(p_name)
                                    target_ws.update(f"E{edit_idx+2}:G{edit_idx+2}", [[new_s, new_n, new_p]])
                                    st.cache_data.clear()
                                    st.toast("업데이트 성공!"); time.sleep(0.5); st.rerun()
                                except:
                                    st.error("데이터 업데이트 중 오류가 발생했습니다.")

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
                        try:
                            target_ws = sh.worksheet(p_name)
                            target_ws.append_row([str(sd), str(ed), cat, name, stat, "", pct, st.session_state['user_id']])
                            st.cache_data.clear()
                            st.success("새 일정이 추가되었습니다."); time.sleep(0.5); st.rerun()
                        except:
                            st.error("데이터 저장 중 오류가 발생했습니다.")

            with t3:
                st.subheader("📢 주간 현황 보고 업데이트")
                with st.form("update_report_form"):
                    new_status = st.text_area("이번 주 주요 활동 및 이슈 사항을 입력하세요.")
                    if st.form_submit_button("저장 및 대시보드 반영"):
                        try:
                            hist_ws = sh.worksheet('weekly_history')
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                            hist_ws.append_row([timestamp, p_name, new_status, st.session_state['user_id']])
                            st.cache_data.clear()
                            st.success("현황이 저장되었습니다."); time.sleep(0.5); st.rerun()
                        except:
                            st.error("히스토리 시트 연결 실패. 관리자에게 문의하세요.")

            with t4:
                st.subheader("📜 과거 기록 조회")
                if not full_hist_data.empty:
                    filtered_h = full_hist_data[full_hist_data['프로젝트명'] == p_name].iloc[::-1]
                    if filtered_h.empty:
                        st.info("아직 기록된 히스토리가 없습니다.")
                    else:
                        for _, hr in filtered_h.iterrows():
                            with st.expander(f"📅 {hr['날짜']} | 작성자: {hr['작성자']}"):
                                st.write(hr['주요현황'])
                                
    except Exception as e:
        st.error("🚨 시스템 초기화 중 오류가 발생했습니다.")
        st.info(f"""
        **해결 가이드:**
        1. 구글 스프레드시트 이름이 **pms_db** 인지 확인하세요.
        2. 아래 서비스 계정 이메일을 복사하여, 구글 시트 우측 상단 **[공유]** 버튼을 통해 **편집자**로 추가해 주세요.
        
        **서비스 계정 이메일:**
        `{st.secrets["gcp_service_account"]["client_email"]}`
        """)
        st.warning(f"상세 에러 내용: {e}")
