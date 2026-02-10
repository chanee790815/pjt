import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import time
import plotly.express as px
import plotly.graph_objects as go
import requests

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v0.9.2", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 커스텀 CSS ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
    }
    section[data-testid="stSidebar"] { background-color: #f0f2f6; }
    .main .block-container { padding-top: 0.8rem !important; }
    
    /* 카드형 버튼 디자인 */
    .stButton button {
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
        background-color: white;
        font-weight: 500;
    }
    
    /* KPI 및 태양광 전용 버튼 강조 (사이드바 하단) */
    div.stButton > button[key="kpi_nav_link"], div.stButton > button[key="solar_nav_link"] {
        border: 2px solid #ff4b4b !important;
        color: #ff4b4b !important;
        font-weight: 700 !important;
        margin-top: 5px !important;
    }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        background-color: #f1f3f5;
        border-radius: 5px 5px 0 0;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 데이터 및 보안 로직 (Backend)
# ---------------------------------------------------------

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
    return _client.open('pms_db')

@st.cache_data(ttl=300)
def fetch_dashboard_summary(_spreadsheet_id, _client_email):
    try:
        temp_client = get_client()
        sh = temp_client.open('pms_db')
        forbidden = ['weekly_history', 'conflict', 'Sheet1', 'KPI']
        all_ws = sh.worksheets()
        
        pjt_sheets = [ws for ws in all_ws if ws.title not in forbidden]
        pjt_names = [ws.title for ws in pjt_sheets]
        
        try:
            hist_data = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        except:
            hist_data = pd.DataFrame(columns=["날짜", "프로젝트명", "주요현황", "작성자"])

        try:
            kpi_data = pd.DataFrame(sh.worksheet('KPI').get_all_records())
        except:
            kpi_data = pd.DataFrame()

        summary = []
        for ws in pjt_sheets:
            try:
                data = ws.get_all_records()
                p_df = pd.DataFrame(data)
                prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if '진행률' in p_df.columns else 0
                note = "최신 브리핑이 없습니다."
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
    return sh.worksheet(pjt_name).get_all_records()

# ---------------------------------------------------------
# [SECTION 2] 개별 페이지 렌더링 함수 (Frontend Modules)
# ---------------------------------------------------------

def show_dashboard(summary_list):
    st.title("📊 프로젝트 통합 대시보드")
    if not summary_list:
        st.warning("현재 진행 중인 프로젝트 데이터가 없습니다.")
        return

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
    st.plotly_chart(fig_main, use_container_width=True)

def show_solar_analysis():
    """태양광 발전시간 실시간 분석 페이지 (Rev 0.9.2)"""
    st.title("☀️ 태양광 발전 환경 분석 (기상청 API 연동)")
    
    # 발급받으신 인증키 적용
    SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
    
    col1, col2 = st.columns(2)
    # 기본 조회 날짜를 어제로 설정 (실측 데이터 보정 시간 고려)
    target_date = col1.date_input("조회 날짜 선택", datetime.date.today() - datetime.timedelta(days=1))
    # 적서리 프로젝트 인근 충주(127) 지점을 기본값으로 추천
    stn_id = col2.selectbox("관측 지점 선택", [127, 108, 131, 159], 
                            format_func=lambda x: {127:"충주 (적서리 인근)", 108:"서울", 131:"청주", 159:"부산"}[x])

    if st.button("실시간 일사량 데이터 불러오기"):
        with st.spinner('기상청 API 통신 중...'):
            date_str = target_date.strftime("%Y%m%d")
            url = 'http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList'
            params = {
                'serviceKey': SERVICE_KEY,
                'pageNo': '1', 'numOfRows': '24', 'dataType': 'JSON',
                'dataCd': 'ASOS', 'dateCd': 'HR', 'stnIds': str(stn_id),
                'startDt': date_str, 'startHh': '01', 'endDt': date_str, 'endHh': '23'
            }
            
            try:
                res = requests.get(url, params=params)
                json_data = res.json()
                
                if json_data['response']['header']['resultCode'] == '00':
                    items = json_data['response']['body']['items']['item']
                    df_solar = pd.DataFrame(items)
                    
                    # 수치형 변환 및 전처리
                    df_solar['icsr'] = pd.to_numeric(df_solar['icsr'], errors='coerce').fillna(0)
                    df_solar['hour'] = pd.to_datetime(df_solar['tm']).dt.hour
                    
                    # 발전시간 계산 로직: 누적 일사량(MJ) / 3.6 = 발전시간(h)
                    total_mj = df_solar['icsr'].sum()
                    gen_hours = round(total_mj / 3.6, 2)
                    
                    # 대시보드 메트릭 표시
                    m1, m2, m3 = st.columns(3)
                    m1.metric("총 누적 일사량", f"{round(total_mj, 2)} MJ/㎡")
                    m2.metric("☀️ 실측 발전시간", f"{gen_hours} h", help="누적 일사량 / 3.6")
                    m3.metric("최대 일사 시점", f"{df_solar.loc[df_solar['icsr'].idxmax(), 'hour']}시")

                    # 시간대별 일사량 그래프
                    fig_solar = px.area(df_solar, x='hour', y='icsr', 
                                        title=f"📅 {target_date} 지점별 일사량 추이",
                                        labels={'hour': '시간(시)', 'icsr': '일사량(MJ/㎡)'},
                                        color_discrete_sequence=['#f1c40f'])
                    fig_solar.update_layout(plot_bgcolor='white', xaxis=dict(showgrid=True, gridcolor='#eee'))
                    st.plotly_chart(fig_solar, use_container_width=True)
                    
                    with st.expander("API 원본 데이터 확인"):
                        st.dataframe(df_solar[['tm', 'icsr', 'ts', 'rn']])
                else:
                    st.error(f"API 응답 에러: {json_data['response']['header']['resultMsg']}")
            except Exception as e:
                st.error(f"데이터 연동 실패: {e}")

def show_kpi_page(kpi_df):
    st.title("📈 PM팀 경영지표 (KPI)")
    if kpi_df.empty:
        st.error("구글 시트의 'KPI' 데이터를 읽어올 수 없습니다.")
        return

    cols_order = ['KPI 구분', 'KPI 항목', '정의/산식', '평가기준', '목표치', '실적', '달성률(%)', '가중치(%)']
    display_cols = [c for c in cols_order if c in kpi_df.columns]
    
    k_c1, k_c2 = st.columns(2)
    k_c1.metric("핵심 지표", f"{len(kpi_df)} 개")
    try:
        total_w = pd.to_numeric(kpi_df['가중치(%)'], errors='coerce').sum()
        k_c2.metric("전체 가중치", f"{total_w}%")
    except: pass
    
    st.subheader("📋 경영목표 및 달성 현황")
    st.dataframe(kpi_df[display_cols], use_container_width=True, hide_index=True)
    
    st.divider()
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        if 'KPI 항목' in kpi_df.columns and '가중치(%)' in kpi_df.columns:
            fig_pie = px.pie(kpi_df, values='가중치(%)', names='KPI 항목', hole=.4, title="항목별 성과 비중")
            st.plotly_chart(fig_pie, use_container_width=True)
    with chart_col2:
        if 'KPI 항목' in kpi_df.columns and '달성률(%)' in kpi_df.columns:
            kpi_df['v'] = pd.to_numeric(kpi_df['달성률(%)'].astype(str).str.replace('%',''), errors='coerce').fillna(0)
            fig_bar = px.bar(kpi_df, x='KPI 항목', y='v', text_auto=True, title="목표 달성률(%)", color='v', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

def show_project_detail(p_name, sh, full_hist_data):
    data_all = get_ws_data(st.secrets["gcp_service_account"]["client_email"], p_name)
    df_raw = pd.DataFrame(data_all) if data_all else pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
    
    st.title(f"🏗️ {p_name} 관리 시스템")
    t1, t2, t3, t4 = st.tabs(["📊 통합 공정표", "📝 일정등록", "📢 현황보고", "📜 히스토리"])

    with t1:
        if not df_raw.empty and '시작일' in df_raw.columns:
            df = df_raw.copy()
            df['시작일'] = pd.to_datetime(df['시작일'], errors='coerce')
            df['종료일'] = pd.to_datetime(df['종료일'], errors='coerce')
            df = df.dropna(subset=['시작일', '종료일'])
            
            df['기간'] = (df['종료일'] - df['시작일']).dt.days + 1
            df['label'] = df.apply(lambda r: f"{r['대분류']} | {r['구분']} ({r['기간']}일)", axis=1)
            df = df.sort_values(by='시작일', ascending=False)

            fig = px.timeline(
                df, x_start="시작일", x_end="종료일", y="label", color="진행상태",
                color_discrete_map={"완료": "#2c3e50", "진행중": "#3498db", "예정": "#bdc3c7", "지연": "#e74c3c"},
                hover_data=["진행률"]
            )
            
            fig.update_layout(
                plot_bgcolor='white', paper_bgcolor='white',
                xaxis=dict(showgrid=True, gridcolor='#e9ecef', tickformat="%m/%d", dtick="D7", side="top"),
                yaxis=dict(showgrid=True, gridcolor='#f1f3f5', title="", tickfont=dict(size=11)),
                height=400 + (len(df) * 30), margin=dict(l=10, r=10, t=50, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("📋 공정 상세 리스트")
            st.dataframe(df_raw, use_container_width=True)
            
            with st.expander("🔍 빠른 상태 업데이트"):
                edit_idx = st.selectbox("수정 행 선택", df_raw.index)
                with st.form(f"edit_{edit_idx}"):
                    row = df_raw.iloc[edit_idx]
                    c1, c2 = st.columns(2)
                    ns = c1.selectbox("상태", ["예정", "진행중", "완료", "지연"], index=["예정", "진행중", "완료", "지연"].index(row['진행상태']))
                    np = c2.number_input("진행률(%)", 0, 100, int(row['진행률']))
                    nn = st.text_input("비고", value=row['비고'])
                    if st.form_submit_button("반영"):
                        sh.worksheet(p_name).update(f"E{edit_idx+2}:G{edit_idx+2}", [[ns, nn, np]])
                        st.cache_data.clear(); st.toast("성공!"); time.sleep(0.5); st.rerun()
        else: st.info("공정 데이터가 없습니다. '일정등록' 탭에서 첫 공정을 등록해 주세요.")

    with t2:
        st.subheader("📝 신규 공정 일정 등록")
        with st.form("new_schedule"):
            c1, c2 = st.columns(2)
            sd, ed = c1.date_input("시작일"), c2.date_input("종료일")
            cat = st.selectbox("대분류", ["인허가", "설계/조사", "토목공사", "구매/자재", "설치공사", "시운전", "기타"])
            name = st.text_input("상세 공정명 (작업내용)")
            stat = st.selectbox("초기 상태", ["예정", "진행중", "완료"])
            pct = st.number_input("초기 진행률(%)", 0, 100, 0)
            if st.form_submit_button("공정표에 추가"):
                sh.worksheet(p_name).append_row([str(sd), str(ed), cat, name, stat, "", pct, st.session_state['user_id']])
                st.cache_data.clear(); st.success("공정이 등록되었습니다."); time.sleep(0.5); st.rerun()

    with t3:
        st.subheader("📢 현장 이슈 및 주요 현황 업데이트")
        with st.form("up_report"):
            txt = st.text_area("활동 및 이슈 사항을 상세히 작성하세요.")
            if st.form_submit_button("현황 저장"):
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                sh.worksheet('weekly_history').append_row([ts, p_name, txt, st.session_state['user_id']])
                st.cache_data.clear(); st.success("주간 현황이 반영되었습니다."); time.sleep(0.5); st.rerun()

    with t4:
        st.subheader("📜 과거 기록 조회")
        if not full_hist_data.empty:
            filtered = full_hist_data[full_hist_data['프로젝트명'] == p_name].iloc[::-1]
            if filtered.empty: st.info("기록된 히스토리가 없습니다.")
            for _, r in filtered.iterrows():
                with st.expander(f"📅 {r['날짜']} | 작성자: {r['작성자']}"): st.write(r['주요현황'])

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (Main Application Loop)
# ---------------------------------------------------------

if check_password():
    client = get_client()
    if client:
        try:
            sh = get_spreadsheet(client)
            with st.spinner('실시간 동기화 중...'):
                pjt_names, summary_list, full_hist_data, kpi_df = fetch_dashboard_summary(sh.id, st.secrets["gcp_service_account"]["client_email"])
            
            if "selected_project" not in st.session_state:
                st.session_state["selected_project"] = "🏠 전체 대시보드"

            st.sidebar.title("📁 PMO 프로젝트 센터")
            st.sidebar.write(f"👤 접속자: **{st.session_state['user_id']} 이사님**")
            
            dropdown_opts = ["🏠 전체 대시보드"] + pjt_names
            curr_idx = dropdown_opts.index(st.session_state["selected_project"]) if st.session_state["selected_project"] in dropdown_opts else 0
            
            selected_menu = st.sidebar.selectbox("🎯 프로젝트 선택", dropdown_opts, index=curr_idx)
            
            if selected_menu != st.session_state["selected_project"] and selected_menu not in ["🎯 경영지표(KPI)", "☀️ 태양광 분석"]:
                st.session_state["selected_project"] = selected_menu
                st.rerun()

            with st.sidebar.expander("➕ 프로젝트 신규 생성"):
                n_name = st.text_input("새 프로젝트 명칭")
                if st.button("시트 생성"):
                    if n_name and n_name not in pjt_names:
                        sh.add_worksheet(title=n_name, rows="100", cols="20").append_row(["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"])
                        st.cache_data.clear(); st.success("생성 완료!"); time.sleep(1); st.rerun()

            st.sidebar.markdown("---")
            st.sidebar.subheader("💎 전사 및 기상 관리")
            if st.sidebar.button("🎯 경영지표(KPI) 관리", key="kpi_nav_link", use_container_width=True):
                st.session_state["selected_project"] = "🎯 경영지표(KPI)"
                st.rerun()
                
            # [Rev 0.9.2 추가] 태양광 분석 버튼
            if st.sidebar.button("☀️ 태양광 발전 분석", key="solar_nav_link", use_container_width=True):
                st.session_state["selected_project"] = "☀️ 태양광 분석"
                st.rerun()

            st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
            c_ref, c_log = st.sidebar.columns(2)
            if c_ref.button("🔄 갱신"): st.cache_data.clear(); st.rerun()
            if c_log.button("🔓 로그아웃"): logout()

            # --- 페이지 라우팅 로직 (Router) ---
            if st.session_state["selected_project"] == "🏠 전체 대시보드":
                show_dashboard(summary_list)
            elif st.session_state["selected_project"] == "🎯 경영지표(KPI)":
                show_kpi_page(kpi_df)
            elif st.session_state["selected_project"] == "☀️ 태양광 분석":
                show_solar_analysis()
            else:
                show_project_detail(st.session_state["selected_project"], sh, full_hist_data)
                                    
        except Exception as e:
            st.error("🚨 시스템 초기화 중 에러가 발생했습니다.")
            st.warning(f"상세 에러 내용: {e}")
