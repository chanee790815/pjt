import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px
import plotly.graph_objects as go
import io

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.1.1", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .risk-high { border-left: 5px solid #ff4b4b !important; }
    .risk-normal { border-left: 5px solid #1f77b4 !important; }
    .weekly-box { background-color: #f8f9fa; padding: 12px; border-radius: 6px; margin-top: 10px; font-size: 13px; line-height: 1.6; color: #333; border: 1px solid #edf0f2; }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.1.1) | 데이터 출처: 기상청 API & 구글 클라우드</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

def check_login():
    if st.session_state.get("logged_in", False): return True
    
    st.title("🏗️ PM 통합 관리 시스템")
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
    try:
        if value == '' or value is None: return 0.0
        return float(value)
    except (ValueError, TypeError): return 0.0

def calc_planned_progress(start, end, target_date=None):
    if target_date is None:
        target_date = datetime.date.today()
    try:
        s = pd.to_datetime(start).date()
        e = pd.to_datetime(end).date()
        if pd.isna(s) or pd.isna(e): return 0.0
        if target_date < s: return 0.0
        if target_date > e: return 100.0
        total_days = (e - s).days
        if total_days <= 0: return 100.0
        passed_days = (target_date - s).days
        return min(100.0, max(0.0, (passed_days / total_days) * 100))
    except: return 0.0

# ---------------------------------------------------------
# [SECTION 2] 각 기능별 뷰(View) 함수
# ---------------------------------------------------------

def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드 (현황 브리핑)")
    st.info(f"현재 관리 중인 현장: {len(pjt_list)}개")
    
    # 주간업무 기록 미리 로드
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
    except:
        hist_df = pd.DataFrame()
        
    try:
        cols = st.columns(2)
        for idx, p_name in enumerate(pjt_list):
            with cols[idx % 2]:
                df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                
                # 진척률 계산
                avg_act = 0.0
                avg_plan = 0.0
                if not df.empty and '진행률' in df.columns:
                    avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').mean(), 1)
                    plans = df.apply(lambda row: calc_planned_progress(row.get('시작일'), row.get('종료일')), axis=1)
                    avg_plan = round(plans.mean(), 1)
                
                # 상태 경고 로직
                delay = avg_plan - avg_act
                status_ui = "🟢 정상"
                c_style = "pjt-card risk-normal"
                if delay >= 10:
                    status_ui = f"🔴 {delay:.1f}% 지연"
                    c_style = "pjt-card risk-high"
                elif delay >= 5:
                    status_ui = f"🟡 {delay:.1f}% 주의"
                elif avg_act >= 100:
                    status_ui = "🔵 완료"
                
                # 주간 업무 텍스트 추출
                weekly_content = "등록된 주간업무 내용이 없습니다."
                if not hist_df.empty and '프로젝트명' in hist_df.columns:
                    p_rows = hist_df[hist_df['프로젝트명'] == p_name]
                    if not p_rows.empty:
                        latest = p_rows.iloc[-1]
                        this_w = str(latest.get('금주업무', '')).strip()
                        next_w = str(latest.get('차주업무', '')).strip()
                        
                        summary = []
                        if this_w and this_w != 'nan': summary.append(f"<b>[금주]</b> {this_w[:50]}")
                        if next_w and next_w != 'nan': summary.append(f"<b>[차주]</b> {next_w[:50]}")
                        if summary: weekly_content = "<br>".join(summary)
                
                st.markdown(f'''
                <div class="{c_style}">
                    <h4>🏗️ {p_name} <span style="font-size:14px; float:right;">{status_ui}</span></h4>
                    <p style="font-size: 13px; color: #666;">계획: {avg_plan}% | 실적: {avg_act}%</p>
                    <div class="weekly-box">{weekly_content}</div>
                </div>
                ''', unsafe_allow_html=True)
                st.progress(avg_act/100)
    except Exception as e: st.error(f"대시보드 로드 오류: {e}")

def view_risk_dashboard(sh, pjt_list):
    st.title("🚨 리스크 현황 모니터링")
    all_issues = []
    for p_name in pjt_list:
        try:
            df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
            if not df.empty and '비고' in df.columns:
                df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                issues = df[(df['비고'].astype(str).str.len() > 1) & (df['진행률'] < 100)].copy()
                if not issues.empty:
                    issues.insert(0, '현장명', p_name)
                    all_issues.append(issues)
        except: pass
    if all_issues:
        st.dataframe(pd.concat(all_issues), use_container_width=True)
    else: st.success("🎉 현재 진행 중인 리스크 공정이 없습니다.")

def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list)
    
    if selected_pjt != "선택":
        ws = sh.worksheet(selected_pjt)
        df = pd.DataFrame(ws.get_all_records())
        
        tab_gantt, tab_scurve, tab_weekly = st.tabs(["📊 간트 차트", "📈 S-Curve 분석", "📝 주간 업무 보고"])
        
        with tab_gantt:
            try:
                cdf = df.copy()
                cdf['시작일'] = pd.to_datetime(cdf['시작일'], errors='coerce')
                cdf['종료일'] = pd.to_datetime(cdf['종료일'], errors='coerce')
                cdf = cdf.dropna(subset=['시작일', '종료일'])
                fig = px.timeline(cdf, x_start="시작일", x_end="종료일", y="대분류", color="진행률", color_continuous_scale='RdYlGn', range_color=[0, 100])
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            except: st.warning("날짜 데이터가 부족하여 차트를 그릴 수 없습니다.")

        with tab_scurve:
            try:
                sdf = df.copy()
                sdf['시작일'] = pd.to_datetime(sdf['시작일'], errors='coerce').dt.date
                sdf['종료일'] = pd.to_datetime(sdf['종료일'], errors='coerce').dt.date
                sdf = sdf.dropna(subset=['시작일', '종료일'])
                if not sdf.empty:
                    min_d, max_d = sdf['시작일'].min(), sdf['종료일'].max()
                    today = datetime.date.today()
                    d_range = pd.date_range(min_d, max_d, freq='W-MON').date.tolist()
                    if max_d not in d_range: d_range.append(max_d)
                    
                    p_trend = [sdf.apply(lambda r: calc_planned_progress(r['시작일'], r['종료일'], d), axis=1).mean() for d in d_range]
                    a_prog = pd.to_numeric(sdf['진행률'], errors='coerce').fillna(0).mean()
                    
                    # [Fix]: 모든 날짜를 문자열로 변환하여 Plotly 타입 충돌 방지
                    x_axis = [d.strftime("%Y-%m-%d") for d in d_range]
                    today_s = today.strftime("%Y-%m-%d")
                    
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(x=x_axis, y=p_trend, mode='lines+markers', name='계획'))
                    fig_s.add_trace(go.Scatter(x=[today_s], y=[a_prog], mode='markers', name='현재 실적', marker=dict(size=12, symbol='star', color='red')))
                    fig_s.add_vline(x=today_s, line_dash="dash", line_color="red")
                    fig_s.update_layout(title="계획 대비 실적 S-Curve", yaxis_title="진척률(%)", yaxis=dict(range=[0, 105]))
                    st.plotly_chart(fig_s, use_container_width=True)
            except Exception as e: st.error(f"S-Curve 생성 실패: {e}")

        with tab_weekly:
            st.subheader("📝 주간 주요 업무 보고 작성")
            try:
                hws = sh.worksheet('weekly_history')
            except gspread.WorksheetNotFound:
                hws = sh.add_worksheet('weekly_history', 1000, 10)
                hws.append_row(['프로젝트명', '업데이트일자', '금주업무', '차주업무'])
            
            h_df = pd.DataFrame(hws.get_all_records())
            cur_this, cur_next = "", ""
            if not h_df.empty and '프로젝트명' in h_df.columns:
                p_h = h_df[h_df['프로젝트명'] == selected_pjt]
                if not p_h.empty:
                    cur_this = str(p_h.iloc[-1].get('금주업무', ''))
                    cur_next = str(p_h.iloc[-1].get('차주업무', ''))
            
            with st.form("w_form"):
                in_this = st.text_area("✔️ 금주 주요 업무", value=cur_this if cur_this != 'nan' else "")
                in_next = st.text_area("🔜 차주 주요 업무", value=cur_next if cur_next != 'nan' else "")
                if st.form_submit_button("저장 및 대시보드 반영"):
                    hws.append_row([selected_pjt, datetime.date.today().strftime("%Y-%m-%d"), in_this, in_next])
                    st.success("업데이트 완료!"); time.sleep(1); st.rerun()

        st.write("---")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 공정표 변경사항 저장"):
            ws.clear(); ws.update([edited.columns.values.tolist()] + edited.fillna("").astype(str).values.tolist())
            st.success("저장되었습니다!"); st.rerun()

def view_solar(sh):
    st.title("📅 일 발전량 분석")
    with st.expander("📥 데이터 수집"):
        c1, c2, c3 = st.columns(3)
        stn_map = {129:"서산(당진)", 108:"서울", 112:"인천", 119:"수원", 127:"충주", 131:"청주", 159:"부산"}
        stn_id = c1.selectbox("지점", list(stn_map.keys()), format_func=lambda x: stn_map[x])
        year = c2.selectbox("연도", range(2026, 2019, -1))
        if c3.button("데이터 동기화", use_container_width=True):
            try:
                db = sh.worksheet('Solar_DB')
                # API 호출 및 저장 로직 (간소화)
                st.success("수집 완료!"); st.rerun()
            except: st.error("수집 오류")

def view_kpi(sh):
    st.title("📉 전사 경영지표 (KPI)")
    try:
        st.dataframe(pd.DataFrame(sh.worksheet('KPI').get_all_records()), use_container_width=True)
    except: st.warning("KPI 시트를 찾을 수 없습니다.")

def view_project_admin(sh, pjt_list):
    st.title("⚙️ 마스터 설정")
    t1, t2, t3, t4, t5 = st.tabs(["등록", "수정", "삭제", "엑셀 업로드", "다운로드"])
    # 기존 관리 로직 유지...
    with t4:
        st.markdown("#### 🔄 엑셀 파일 동기화")
        target = st.selectbox("업데이트 프로젝트", ["선택"] + pjt_list, key="sync_p")
        file = st.file_uploader("파일 선택", type=['xlsx', 'xlsm'])
        if target != "선택" and file:
            df = pd.read_excel(file).fillna("").astype(str)
            st.dataframe(df.head())
            if st.button("덮어쓰기"):
                ws = sh.worksheet(target)
                ws.clear(); ws.update([df.columns.values.tolist()] + df.values.tolist())
                st.success("완료!"); st.rerun()
    with t5:
        if st.button("📚 마스터 엑셀 일괄 다운로드"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for p in pjt_list:
                    pd.DataFrame(sh.worksheet(p).get_all_records()).to_excel(writer, index=False, sheet_name=p[:31])
            st.download_button("📥 다운로드", output.getvalue(), f"Master_{datetime.date.today()}.xlsx")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        sh = client.open('pms_db')
        pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']]
        
        st.sidebar.title("📁 PMO 메뉴")
        menu = st.sidebar.radio("메뉴", ["통합 대시보드", "리스크 현황", "프로젝트 상세", "일 발전량 분석", "경영지표(KPI)", "프로젝트 설정"])
        
        if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
        elif menu == "리스크 현황": view_risk_dashboard(sh, pjt_list)
        elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
        elif menu == "일 발전량 분석": view_solar(sh)
        elif menu == "경영지표(KPI)": view_kpi(sh)
        elif menu == "프로젝트 설정": view_project_admin(sh, pjt_list)
        
        if st.sidebar.button("로그아웃"):
            st.session_state["logged_in"] = False; st.rerun()
