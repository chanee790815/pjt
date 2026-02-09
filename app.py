## [PMS Revision History]
## 버전: Rev. 0.8.9 (Dedicated KPI Navigation Link)
## 업데이트 요약:
## 1. 🏗️ 사이드바 레이아웃 최종안: 프로젝트 목록(드롭다운)과 KPI 링크(독립 버튼)를 완벽히 분리하여 전문적인 대시보드 구조 완성
## 2. 🎯 KPI 독립 접근성: '프로젝트 신규 생성' 아래에 별도의 KPI 전용 메뉴를 배치하여 접근성 향상
## 3. 🛡️ 데이터 필터링 강화: 대시보드 요약 및 프로젝트 목록에서 'KPI' 항목을 완전히 배제하여 혼선 차단
## 4. 📱 UI 유지: 모바일 최적화 및 차트 터치 간섭 방지(Static Mode) 설정 유지

import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px
import plotly.graph_objects as go

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.8.9", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 커스텀 CSS ---
st.markdown("""
    <style>
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    /* 사이드바 스타일링 */
    section[data-testid="stSidebar"] {
        background-color: #f0f2f6;
    }
    .main .block-container {
        padding-top: 0.8rem !important; 
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
    }
    /* 기본 버튼 스타일 */
    .stButton button {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
        background-color: white;
    }
    /* KPI 전용 버튼 강조 (강렬한 레드 테두리 포인트) */
    div.stButton > button[key="kpi_nav_link"] {
        background-color: #ffffff !important;
        border: 2px solid #ff4b4b !important;
        color: #ff4b4b !important;
        font-weight: 700 !important;
        margin-top: 10px !important;
    }
    div.stButton > button[key="kpi_nav_link"]:hover {
        background-color: #fff1f1 !important;
        box-shadow: 0 4px 8px rgba(255, 75, 75, 0.15) !important;
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
        # 숨김 처리할 시스템 시트들
        forbidden = ['weekly_history', 'conflict', 'Sheet1', 'KPI']
        all_worksheets = sh.worksheets()
        
        # 실제 프로젝트 시트만 필터링 (KPI 제외)
        pjt_sheets = [ws for ws in all_worksheets if ws.title not in forbidden]
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

        # 3. 프로젝트 요약 정보 생성
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
                summary.append({"프로젝트명": ws.title, "진척률": 0, "최신현황": "로딩 지연..."})
            
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
        
        with st.spinner('실시간 데이터를 동기화 중입니다...'):
            pjt_names, summary_list, full_hist_data, kpi_df = fetch_dashboard_summary(sh.id, st.secrets["gcp_service_account"]["client_email"])
        
        # 🎯 내비게이션 초기 설정
        if "selected_project" not in st.session_state:
            st.session_state["selected_project"] = "🏠 전체 대시보드"

        # --- 사이드바 구성 ---
        st.sidebar.title("📁 PMO 프로젝트 센터")
        st.sidebar.write(f"👤 **{st.session_state['user_id']}** 님")
        
        # 1. 메인 드롭다운 (프로젝트 중심)
        dropdown_options = ["🏠 전체 대시보드"] + pjt_names
        
        # 내비게이션 동기화 로직
        try:
            # 현재 페이지가 KPI인 경우 드롭다운은 '전체 대시보드'를 기본으로 보여줌
            if st.session_state["selected_project"] == "🎯 경영지표(KPI)":
                current_idx = 0
            else:
                current_idx = dropdown_options.index(st.session_state["selected_project"])
        except ValueError:
            current_idx = 0

        selected_menu = st.sidebar.selectbox("🎯 메뉴 선택", dropdown_options, index=current_idx)
        
        # 드롭다운에서 메뉴를 직접 바꿨을 때만 상태 업데이트
        if selected_menu != st.session_state["selected_project"] and selected_menu != "🏠 전체 대시보드":
             st.session_state["selected_project"] = selected_menu
             st.rerun()
        elif selected_menu == "🏠 전체 대시보드" and st.session_state["selected_project"] != "🏠 전체 대시보드" and st.session_state["selected_project"] != "🎯 경영지표(KPI)":
             st.session_state["selected_project"] = "🏠 전체 대시보드"
             st.rerun()

        # 2. 신규 생성 섹션
        with st.sidebar.expander("➕ 프로젝트 신규 생성"):
            new_name = st.text_input("새 프로젝트 명칭")
            if st.button("시트 생성"):
                if new_name and new_name not in pjt_names and new_name != "KPI":
                    new_ws = sh.add_worksheet(title=new_name, rows="100", cols="20")
                    new_ws.append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
                    st.cache_data.clear()
                    st.success(f"'{new_name}' 생성 완료!"); time.sleep(1); st.rerun()

        # 3. [사용자 요청] 신규 생성 아래 별도 링크 (KPI 전용 버튼)
        st.sidebar.markdown("---")
        st.sidebar.subheader("💎 전사 관리")
        if st.sidebar.button("🎯 경영지표(KPI) 관리", key="kpi_nav_link", use_container_width=True):
            st.session_state["selected_project"] = "🎯 경영지표(KPI)"
            st.rerun()

        # 사이드바 하단 유틸리티
        st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
        col_ref, col_log = st.sidebar.columns(2)
        if col_ref.button("🔄 갱신"):
            st.cache_data.clear(); st.rerun()
        if col_log.button("🔓 로그아웃"):
            logout()

        # ---------------------------------------------------------
        # CASE 1: 전체 대시보드
        # ---------------------------------------------------------
        if st.session_state["selected_project"] == "🏠 전체 대시보드":
            st.title("📊 프로젝트 통합 대시보드")
            
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
                fig_main = px.bar(sum_df, x="프로젝트명", y="진척률", color="진척률", text_auto=True, title="프로젝트별 실시간 진도율")
                st.plotly_chart(fig_main, use_container_width=True, config={'staticPlot': True})
            else:
                st.warning("현재 진행 중인 프로젝트 데이터가 없습니다.")

        # ---------------------------------------------------------
        # CASE 2: 경영지표(KPI) 독립 페이지 (전용 레이아웃)
        # ---------------------------------------------------------
        elif st.session_state["selected_project"] == "🎯 경영지표(KPI)":
            st.title("📈 PM팀 경영지표 (KPI)")
            
            if not kpi_df.empty:
                # 이미지와 동일한 컬럼 순서 고정
                cols_order = ['KPI 구분', 'KPI 항목', '정의/산식', '평가기준', '목표치', '실적', '달성률(%)', '가중치(%)']
                display_cols = [c for c in cols_order if c in kpi_df.columns]
                
                # 상단 메트릭스
                k_c1, k_c2, k_c3 = st.columns(3)
                k_c1.metric("지표 개수", f"{len(kpi_df)} 개")
                try:
                    total_w = pd.to_numeric(kpi_df['가중치(%)'], errors='coerce').sum()
                    k_c2.metric("전체 가중치", f"{total_w}%")
                except: pass
                
                # 메인 데이터 테이블
                st.subheader("📋 경영목표 및 달성 현황")
                st.dataframe(kpi_df[display_cols], use_container_width=True, hide_index=True)
                
                st.divider()
                # 시각화 리포트
                chart_col1, chart_col2 = st.columns(2)
                with chart_col1:
                    if 'KPI 항목' in kpi_df.columns and '가중치(%)' in kpi_df.columns:
                        fig_kpi_pie = px.pie(kpi_df, values='가중치(%)', names='KPI 항목', hole=.4, title="항목별 비중")
                        st.plotly_chart(fig_kpi_pie, use_container_width=True, config={'staticPlot': True})
                with chart_col2:
                    if 'KPI 항목' in kpi_df.columns and '달성률(%)' in kpi_df.columns:
                        kpi_df['달성률_val'] = pd.to_numeric(kpi_df['달성률(%)'].astype(str).str.replace('%',''), errors='coerce').fillna(0)
                        fig_kpi_bar = px.bar(kpi_df, x='KPI 항목', y='달성률_val', text_auto=True, title="목표 달성률(%)", 
                                           color='달성률_val', color_continuous_scale='RdYlGn')
                        st.plotly_chart(fig_kpi_bar, use_container_width=True, config={'staticPlot': True})
            else:
                st.error("구글 시트의 'KPI' 워크시트가 비어있거나 찾을 수 없습니다.")

        # ---------------------------------------------------------
        # CASE 3: 프로젝트 상세 관리
        # ---------------------------------------------------------
        else:
            p_name = st.session_state["selected_project"]
            data_all = get_ws_data(st.secrets["gcp_service_account"]["client_email"], p_name)
            df_raw = pd.DataFrame(data_all) if data_all else pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
            
            st.title(f"🏗️ {p_name} 상세 관리")
            t1, t2, t3, t4 = st.tabs(["📊 통합 공정표", "📝 일정등록", "📢 현황보고", "📜 히스토리"])

            with t1:
                if not df_raw.empty and '시작일' in df_raw.columns:
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
                            new_s = col1.selectbox("상태", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
                            new_p = col2.number_input("진행률(%)", 0, 100, int(row['진행률']))
                            new_n = st.text_input("비고", value=row['비고'])
                            if st.form_submit_button("시트에 반영"):
                                sh.worksheet(p_name).update(f"E{edit_idx+2}:G{edit_idx+2}", [[new_s, new_n, new_p]])
                                st.cache_data.clear(); st.toast("성공!"); time.sleep(0.5); st.rerun()
                else:
                    st.info("등록된 공정 데이터가 없거나 프로젝트 데이터가 아닙니다.")

            with t2:
                st.subheader("📝 신규 일정 등록")
                with st.form("new_schedule_form"):
                    c1, c2 = st.columns(2)
                    sd, ed = c1.date_input("시작일"), c2.date_input("종료일")
                    cat = st.selectbox("대분류", ["인허가", "설계/조사", "토목공사", "기타"])
                    name = st.text_input("상세 공정명")
                    stat = st.selectbox("초기 상태", ["예정", "진행중", "완료"])
                    pct = st.number_input("초기 진행률(%)", 0, 100, 0)
                    if st.form_submit_button("공정표에 추가"):
                        sh.worksheet(p_name).append_row([str(sd), str(ed), cat, name, stat, "", pct, st.session_state['user_id']])
                        st.cache_data.clear(); st.success("추가됨"); time.sleep(0.5); st.rerun()

            with t3:
                st.subheader("📢 현황 보고 업데이트")
                with st.form("up_report"):
                    new_status = st.text_area("주요 활동 및 이슈 사항")
                    if st.form_submit_button("저장 및 반영"):
                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        sh.worksheet('weekly_history').append_row([timestamp, p_name, new_status, st.session_state['user_id']])
                        st.cache_data.clear(); st.success("저장됨"); time.sleep(0.5); st.rerun()

            with t4:
                st.subheader("📜 과거 기록 조회")
                if not full_hist_data.empty:
                    filtered_h = full_hist_data[full_hist_data['프로젝트명'] == p_name].iloc[::-1]
                    for _, hr in filtered_h.iterrows():
                        with st.expander(f"📅 {hr['날짜']} | 작성자: {hr['작성자']}"):
                            st.write(hr['주요현황'])
                                
    except Exception as e:
        st.error("🚨 시스템 에러 발생")
        st.info(f"구글 시트의 'KPI' 시트나 프로젝트 시트 구성을 확인해 주세요.")
        st.warning(f"상세 내용: {e}")
