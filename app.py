import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v3.0.1", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    </style>
    <div class="footer">시스템 상태: 정상 (v3.0.1 Patch) | 데이터 출처: 기상청 API & 구글 클라우드</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

def check_login():
    if st.session_state.get("logged_in", False): return True
    
    st.title("🏗️ PM 통합 관리 시스템 (v3.0.1)")
    with st.form("login"):
        u_id = st.text_input("ID")
        u_pw = st.text_input("Password", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = u_id
                st.rerun()
            else: st.error("정보 불일치")
    return False

@st.cache_resource
def get_client():
    try:
        key_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
        return gspread.authorize(creds)
    except: return None

def get_safe_float(value):
    """빈 문자열이나 None을 0.0으로 안전하게 변환"""
    try:
        if value == '' or value is None:
            return 0.0
        return float(value)
    except (ValueError, TypeError):
        return 0.0

# ---------------------------------------------------------
# [SECTION 2] 각 기능별 뷰(View) 함수
# ---------------------------------------------------------

def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드")
    st.info(f"현재 관리 중인 현장: {len(pjt_list)}개")
    
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        cols = st.columns(2)
        for idx, p_name in enumerate(pjt_list):
            with cols[idx % 2]:
                p_df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                prog = round(pd.to_numeric(p_df['진행률'], errors='coerce').mean(), 1) if '진행률' in p_df.columns else 0
                
                last_status = "업데이트 대기 중"
                if not hist_df.empty:
                    row = hist_df[hist_df['프로젝트명'] == p_name]
                    if not row.empty: last_status = row.iloc[-1]['주요현황']

                st.markdown(f"""
                <div class="pjt-card">
                    <h4>🏗️ {p_name}</h4>
                    <p style="font-size:14px; color:#666;">{last_status}</p>
                </div>
                """, unsafe_allow_html=True)
                st.progress(prog/100, text=f"진척률: {prog}%")
    except Exception as e:
        st.error(f"대시보드 로드 오류: {e}")

def view_solar(sh):
    st.title("📅 일 발전량 분석")
    
    # 1. 데이터 동기화 섹션
    with st.expander("📥 기상청 데이터 수집 도구"):
        c1, c2, c3 = st.columns([1, 1, 1])
        stn_map = {127:"충주", 108:"서울", 131:"청주", 159:"부산"}
        stn_id = c1.selectbox("수집 지점", list(stn_map.keys()), format_func=lambda x: stn_map[x])
        year = c2.selectbox("수집 연도", list(range(2026, 2019, -1)))
        
        if c3.button("🚀 데이터 동기화 실행", use_container_width=True):
            with st.spinner("기상청 서버 통신 중..."):
                try:
                    db_ws = sh.worksheet('Solar_DB')
                    start, end = f"{year}0101", f"{year}1231"
                    if int(year) >= datetime.date.today().year:
                        end = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
                        
                    url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey=ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe&numOfRows=366&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start}&endDt={end}'
                    res = requests.get(url, timeout=10).json()
                    
                    items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                    
                    # [수정됨] 안전한 숫자 변환 로직 적용
                    rows = []
                    for i in items:
                        gsr_val = get_safe_float(i.get('sumGsr', 0)) # 빈값 처리
                        gen_val = round(gsr_val / 3.6, 2)
                        rows.append([i['tm'], stn_map[stn_id], gen_val, gsr_val])
                    
                    if rows:
                        all_val = db_ws.get_all_values()
                        if len(all_val) > 1:
                            df = pd.DataFrame(all_val[1:], columns=all_val[0])
                            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
                            # 중복 데이터 삭제 (해당 연도 & 해당 지점)
                            df = df.loc[~((df['날짜'].dt.year == int(year)) & (df['지점'] == stn_map[stn_id]))].dropna(subset=['날짜'])
                            df['날짜'] = df['날짜'].dt.strftime('%Y-%m-%d')
                            db_ws.clear(); db_ws.append_row(all_val[0]); db_ws.append_rows(df.values.tolist())
                        
                        db_ws.append_rows(rows)
                        st.success(f"✅ {year}년 {stn_map[stn_id]} 데이터 {len(rows)}건 수집 완료!"); time.sleep(1); st.rerun()
                    else:
                        st.warning("수집된 데이터가 없습니다 (기상청 응답 없음).")
                        
                except Exception as e: st.error(f"오류 발생: {e}")

    # 2. 차트 섹션
    st.subheader("📊 연간 발전 효율 차트")
    col1, col2 = st.columns(2)
    sel_stn = col1.selectbox("분석 지점", ["충주", "서울", "청주", "부산"])
    sel_year = col2.selectbox("분석 연도", list(range(2026, 2019, -1)), index=3) # 2023 기본값
    
    try:
        df = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            target = df.loc[(df['날짜'].dt.year == int(sel_year)) & (df['지점'] == sel_stn)].copy()
            
            if not target.empty:
                avg = round(pd.to_numeric(target['발전시간']).mean(), 2)
                st.metric(f"{sel_year}년 {sel_stn} 평균", f"{avg} h")
                target['월'] = target['날짜'].dt.month
                m_avg = target.groupby('월')['발전시간'].mean().reset_index()
                st.plotly_chart(px.bar(m_avg, x='월', y='발전시간', color_discrete_sequence=['#ffca28']), use_container_width=True)
            else: st.warning("해당 조건의 데이터가 없습니다.")
    except: st.warning("데이터베이스 로드 실패")

def view_project_detail(sh, pjt_list):
    st.title("🏗️ 개별 프로젝트 상세 관리")
    
    # [수정] 라디오 버튼이라 상태 유지됨
    selected_pjt = st.selectbox("관리할 현장을 선택하세요", ["선택"] + pjt_list)
    
    if selected_pjt != "선택":
        ws = sh.worksheet(selected_pjt)
        df = pd.DataFrame(ws.get_all_records())
        
        # 1. Gantt Chart
        if not df.empty and '시작일' in df.columns:
            try:
                chart_df = df.copy()
                chart_df['시작일'] = pd.to_datetime(chart_df['시작일'], errors='coerce')
                chart_df['종료일'] = pd.to_datetime(chart_df['종료일'], errors='coerce')
                chart_df = chart_df.dropna(subset=['시작일', '종료일'])
                
                y_col = '대분류' if '대분류' in chart_df.columns else chart_df.columns[0]
                
                fig = px.timeline(chart_df, x_start="시작일", x_end="종료일", y=y_col, color="진행률",
                                  color_continuous_scale='RdYlGn', range_color=[0, 100])
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            except: st.caption("날짜 데이터가 충분하지 않아 차트를 건너뜁니다.")

        # 2. Data Editor
        st.write("📝 데이터 수정")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 저장하기", use_container_width=True):
            ws.clear()
            ws.update([edited.columns.values.tolist()] + edited.values.tolist())
            st.success("저장되었습니다!"); time.sleep(1); st.rerun()

def view_kpi(sh):
    st.title("📉 전사 경영지표 (KPI)")
    try:
        df = pd.DataFrame(sh.worksheet('KPI').get_all_records())
        st.dataframe(df, use_container_width=True)
    except: st.error("KPI 시트가 존재하지 않습니다.")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (Router)
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        sh = client.open('pms_db')
        # 관리용 시트 제외
        pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']]
        
        # 사이드바 (Radio 버튼 유지)
        st.sidebar.title("📁 PMO 메뉴")
        st.sidebar.info(f"사용자: {st.session_state['user_id']}")
        
        menu = st.sidebar.radio(
            "이동할 메뉴를 선택하세요",
            ["통합 대시보드", "일 발전량 분석", "프로젝트 관리", "경영지표(KPI)"],
            index=0
        )
        
        st.sidebar.markdown("---")
        if st.sidebar.button("로그아웃"):
            st.session_state["logged_in"] = False
            st.rerun()

        # 라우팅
        if menu == "통합 대시보드":
            view_dashboard(sh, pjt_list)
        elif menu == "일 발전량 분석":
            view_solar(sh)
        elif menu == "프로젝트 관리":
            view_project_detail(sh, pjt_list)
        elif menu == "경영지표(KPI)":
            view_kpi(sh)
