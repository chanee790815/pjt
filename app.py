import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v1.1.1", page_icon="🏗️", layout="wide")

# --- [UI] 디자인 및 저작권 문구 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .metric-box { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 20px; }
    </style>
    <div class="footer">출처: 기상청 공공데이터포털 (ASOS 종관기상관측 일자료) | 본 데이터는 기상청에서 제공하는 공공데이터를 활용하였습니다.</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 및 가이드 준수 데이터 수집 로직
# ---------------------------------------------------------

@st.cache_resource
def get_client():
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(key_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

def sync_yearly_data_v111(sh, stn_id, stn_name, target_year):
    """가이드 표준 항목(sumGsr)을 사용하여 데이터 수집 및 시트 정화"""
    try:
        db_ws = sh.worksheet('Solar_DB')
        SERVICE_KEY = 'ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe'
        
        start_dt = f"{target_year}0101"
        end_dt = f"{target_year}1231" if int(target_year) < datetime.date.today().year else (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        
        # 가이드 문서 표준 API 호출
        url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey={SERVICE_KEY}&numOfRows=366&pageNo=1&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start_dt}&endDt={end_dt}'
        
        res = requests.get(url, timeout=15).json()
        if res['response']['header']['resultCode'] != '00':
            st.error(f"API 오류: {res['response']['header']['resultMsg']}")
            return 0
            
        items = res['response']['body']['items']['item']
        new_rows = []
        for i in items:
            # 가이드 표준: sumGsr(합계 일사량) 사용
            raw_gsr = i.get('sumGsr', '0')
            gsr = float(raw_gsr) if raw_gsr and str(raw_gsr).strip() != '' else 0.0
            gen_h = round(gsr / 3.6, 2)
            new_rows.append([i['tm'], stn_name, gen_h, gsr])
        
        if new_rows:
            # 데이터 정화: 해당 연도 기존 데이터 삭제 후 새 데이터 삽입
            all_data = db_ws.get_all_values()
            if len(all_data) > 1:
                df_all = pd.DataFrame(all_data[1:], columns=all_data[0])
                df_all['날짜'] = pd.to_datetime(df_all['날짜'], errors='coerce')
                df_filtered = df_all[df_all['날짜'].dt.year != int(target_year)].dropna(subset=['날짜'])
                db_ws.clear()
                db_ws.append_row(["날짜", "지점", "발전시간", "일사량합계"])
                if not df_filtered.empty:
                    df_filtered['날짜'] = df_filtered['날짜'].dt.strftime('%Y-%m-%d')
                    db_ws.append_rows(df_filtered.values.tolist())
            
            db_ws.append_rows(new_rows)
            return len(new_rows)
    except Exception as e:
        st.error(f"동기화 오류: {e}")
        return 0

# ---------------------------------------------------------
# [SECTION 2] 분석 화면 (그래프 출력 보정)
# ---------------------------------------------------------

def show_daily_solar(sh):
    st.title("📅 일 발전량 연간 통계 리포트")
    
    # 동기화 도구
    with st.expander("📥 연도별 데이터 정밀 동기화 (가이드 표준)"):
        c1, c2, c3 = st.columns([1, 1, 1])
        stn = c1.selectbox("지점", [127, 108, 131, 159], format_func=lambda x: {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[x])
        year = c2.selectbox("수집 연도", list(range(2026, 2019, -1)))
        if c3.button(f"🚀 {year}년 데이터 수집/정정", use_container_width=True):
            with st.spinner('기상청 데이터를 수집 중입니다...'):
                count = sync_yearly_data_v111(sh, stn, {127:"충주", 108:"서울", 131:"청주", 159:"부산"}[stn], year)
                if count > 0: st.success(f"✅ {year}년 {count}건 수집 완료!"); time.sleep(1); st.rerun()

    # 분석 연도 선택
    year_list = list(range(2026, 2019, -1))
    sel_year = st.selectbox("📊 분석할 연도를 선택하세요", year_list, index=year_list.index(2023))
    
    try:
        ws = sh.worksheet('Solar_DB')
        df = pd.DataFrame(ws.get_all_records())
        
        if not df.empty:
            # 날짜 형식 강제 변환 및 필터링
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
            df = df.dropna(subset=['날짜'])
            df['연도'] = df['날짜'].dt.year
            df['월'] = df['날짜'].dt.month
            
            y_df = df[df['연도'] == int(sel_year)]
            
            if not y_df.empty:
                # 1. 연평균 메트릭
                avg_val = round(pd.to_numeric(y_df['발전시간']).mean(), 2)
                st.markdown(f'<div class="metric-box"><h2 style="color:#555;">✨ {sel_year}년 전체 평균 발전시간</h2><h1 style="color:#f1c40f; font-size:50px;">{avg_val} h / 일</h1></div>', unsafe_allow_html=True)
                
                # 2. 월간 차트
                m_avg = y_df.groupby('월')['발전시간'].mean().reset_index()
                all_months = pd.DataFrame({'월': range(1, 13)})
                m_avg = pd.merge(all_months, m_avg, on='월', how='left').fillna(0)
                
                fig = px.bar(m_avg, x='월', y='발전시간', text_auto='.2f', color='발전시간', color_continuous_scale='YlOrRd', title=f"{sel_year}년 월별 평균 발전효율 추이")
                fig.update_layout(xaxis=dict(tickmode='linear', dtick=1), height=450)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"💡 {sel_year}년 데이터가 시트에 없습니다. 수집 도구를 이용해 주세요.")
    except: st.info("데이터를 동기화해 주세요.")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 및 사이드바
# ---------------------------------------------------------

def check_password():
    if "password_correct" not in st.session_state: st.session_state["password_correct"] = False
    if st.session_state["password_correct"]: return True
    st.title("🏗️ PM 통합 관리 시스템") 
    with st.form("login_form"):
        u_id, u_pw = st.text_input("아이디"), st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["password_correct"], st.session_state["user_id"] = True, u_id
                st.rerun()
            else: st.error("정보 불일치")
    return False

if check_password():
    client = get_client(); sh = client.open('pms_db')
    pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']]
    
    if "page" not in st.session_state: st.session_state["page"] = "home"
    
    # 사이드바 메뉴 (이사님 지정 순서)
    st.sidebar.title("📁 PMO 센터"); st.sidebar.write(f"👤 **{st.session_state['user_id']} 이사님**"); st.sidebar.markdown("---")
    if st.sidebar.button("🏠 1. 전체 대시보드", use_container_width=True): st.session_state["page"] = "home"; st.rerun()
    st.sidebar.markdown("### ☀️ 2. 태양광 분석")
    if st.sidebar.button("⏱️ 시간별 발전량 조회", use_container_width=True): st.session_state["page"] = "solar_hr"; st.rerun()
    if st.sidebar.button("📅 일 발전량 조회 (1년)", use_container_width=True): st.session_state["page"] = "solar_day"; st.rerun()
    if st.sidebar.button("📉 3. 경영지표 (KPI)", use_container_width=True): st.session_state["page"] = "kpi"; st.rerun()
    
    st.sidebar.markdown("---"); st.sidebar.markdown("### 🏗️ 4. 프로젝트 목록")
    pjt_choice = st.sidebar.selectbox("현장 선택 (팝업)", ["선택하세요"] + pjt_list)
    if pjt_choice != "선택하세요":
        st.session_state["page"], st.session_state["current_pjt"] = "detail", pjt_choice
    
    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    # 페이지 라우팅
    pg = st.session_state["page"]
    if pg == "home": st.title("📊 통합 대시보드")
    elif pg == "solar_day": show_daily_solar(sh)
    elif pg == "detail": st.title(f"🏗️ {st.session_state['current_pjt']} 상세 관리")
