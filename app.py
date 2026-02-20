import streamlit as st
import pandas as pd
import datetime
import gspread
from gspread.exceptions import APIError, WorksheetNotFound
from google.oauth2.service_account import Credentials
import requests
import time
import plotly.express as px
import plotly.graph_objects as go
import io

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.4.8 Final", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .weekly-box { background-color: #f8f9fa; padding: 12px; border-radius: 6px; margin-top: 10px; font-size: 13px; line-height: 1.6; color: #333; border: 1px solid #edf0f2; white-space: pre-wrap; }
    .history-box { background-color: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; }
    .pm-tag { background-color: #f1f3f5; color: #495057; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-left: 10px; }
    .risk-high { border-left: 5px solid #ff4b4b !important; }
    .risk-normal { border-left: 5px solid #1f77b4 !important; }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.4.8 Final) | 웹페이지 최종 통합 버전 활성화</div>
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
    except Exception as e:
        st.error(f"구글 클라우드 연결 실패: {e}")
        return None

def calc_planned_progress(start, end, target_date=None):
    if target_date is None: target_date = datetime.date.today()
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
# [SECTION 2] 뷰(View) 함수
# ---------------------------------------------------------

# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드 (현황 브리핑)")
    try:
        hist_df = pd.DataFrame(sh.worksheet('weekly_history').get_all_records())
        if not hist_df.empty:
            hist_df.columns = [c.strip() for c in hist_df.columns]
            hist_df['프로젝트명'] = hist_df['프로젝트명'].astype(str).str.strip()
    except: hist_df = pd.DataFrame()
        
    cols = st.columns(2)
    for idx, p_name in enumerate(pjt_list):
        with cols[idx % 2]:
            try:
                ws = sh.worksheet(p_name)
                df = pd.DataFrame(ws.get_all_records())
                
                # 담당 PM 정보 가져오기 (J1 셀)
                pm_name = ws.acell('J1').value or "미지정"
                
                if not df.empty and '진행률' in df.columns:
                    avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1)
                    avg_plan = round(df.apply(lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')), axis=1).mean(), 1)
                else:
                    avg_act = 0.0
                    avg_plan = 0.0
                
                status_ui = "🟢 정상"
                c_style = "pjt-card risk-normal"
                if (avg_plan - avg_act) >= 10:
                    status_ui = "🔴 지연"
                    c_style = "pjt-card risk-high"
                elif avg_act >= 100: status_ui = "🔵 완료"
                
                weekly_content = "등록된 주간업무가 없습니다."
                if not hist_df.empty:
                    p_match = hist_df[hist_df['프로젝트명'] == p_name.strip()]
                    if not p_match.empty:
                        latest = p_match.iloc[-1]
                        this_w = str(latest.get('금주업무', latest.get('주요현황', ''))).strip()
                        next_w = str(latest.get('차주업무', '')).strip()
                        summary = []
                        if this_w and this_w != 'nan': summary.append(f"<b>[금주]</b> {this_w[:70]}")
                        if next_w and next_w != 'nan' and next_w != "": summary.append(f"<b>[차주]</b> {next_w[:70]}")
                        if summary: weekly_content = "<br>".join(summary)
                
                st.markdown(f'''
                    <div class="{c_style}">
                        <h4>🏗️ {p_name} <span class="pm-tag">PM: {pm_name}</span> <span style="font-size:14px; float:right;">{status_ui}</span></h4>
                        <p style="font-size:13px; color:#666;">계획: {avg_plan}% | 실적: {avg_act}%</p>
                        <div class="weekly-box">{weekly_content}</div>
                    </div>
                ''', unsafe_allow_html=True)
                st.progress(min(1.0, max(0.0, avg_act/100)))
            except: pass

# 2. 프로젝트 상세 관리
def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list)
    if selected_pjt != "선택":
        ws = sh.worksheet(selected_pjt)
        
        # 데이터 로드 및 타입 보정 (진행률 수정 활성화를 위한 필수 단계)
        df = pd.DataFrame(ws.get_all_records())
        if '진행률' in df.columns:
            df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
            
        # 담당 PM 정보 가져오기 (J1 셀 사용)
        current_pm = ws.acell('J1').value or ""
        
        # 프로젝트 메타 정보 영역
        col_pm1, col_pm2 = st.columns([3, 1])
        with col_pm1:
            new_pm = st.text_input("프로젝트 담당 PM", value=current_pm, placeholder="담당 PM 이름을 입력하세요")
        with col_pm2:
            st.write(" ") # 수직 맞춤용
            if st.button("PM 정보 저장"):
                ws.update('J1', [[new_pm]])
                st.success("PM 정보가 업데이트되었습니다!")
        
        st.divider()

        tab1, tab2, tab3 = st.tabs(["📊 간트 차트", "📈 S-Curve 분석", "📝 주간 업무 보고"])
        
        with tab1:
            st.subheader(f"📅 {selected_pjt} 타임라인")
            try:
                cdf = df.copy()
                cdf['시작일'] = pd.to_datetime(cdf['시작일'], errors='coerce')
                cdf['종료일'] = pd.to_datetime(cdf['종료일'], errors='coerce')
                cdf = cdf.dropna(subset=['시작일', '종료일'])
                if not cdf.empty:
                    y_axis = '구분' if '구분' in cdf.columns else '대분류'
                    fig = px.timeline(cdf, x_start="시작일", x_end="종료일", y=y_axis, color="진행률", 
                                     color_continuous_scale='RdYlGn', range_color=[0, 100])
                    fig.update_yaxes(autorange="reversed")
                    st.plotly_chart(fig, use_container_width=True)
                else: st.warning("표시할 날짜 데이터가 없습니다.")
            except Exception as e: st.error(f"간트차트 로드 실패: {e}")

        with tab2:
            try:
                sdf = df.copy()
                sdf['시작일'] = pd.to_datetime(sdf['시작일'], errors='coerce').dt.date
                sdf['종료일'] = pd.to_datetime(sdf['종료일'], errors='coerce').dt.date
                sdf = sdf.dropna(subset=['시작일', '종료일'])
                if not sdf.empty:
                    min_d, max_d = sdf['시작일'].min(), sdf['종료일'].max()
                    d_range = pd.date_range(min_d, max_d, freq='W-MON').date.tolist()
                    p_trend = [sdf.apply(lambda r: calc_planned_progress(r['시작일'], r['종료일'], d), axis=1).mean() for d in d_range]
                    a_prog = pd.to_numeric(sdf['진행률'], errors='coerce').fillna(0).mean()
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(x=[d.strftime("%Y-%m-%d") for d in d_range], y=p_trend, mode='lines+markers', name='계획'))
                    fig_s.add_trace(go.Scatter(x=[datetime.date.today().strftime("%Y-%m-%d")], y=[a_prog], mode='markers', name='현재 실적', marker=dict(size=12, color='red', symbol='star')))
                    fig_s.update_layout(title="진척률 추이 (S-Curve)", yaxis_title="진척률(%)")
                    st.plotly_chart(fig_s, use_container_width=True)
            except: pass

        with tab3:
            st.subheader("📋 현재 저장된 주간 업무 현황")
            try:
                h_ws = sh.worksheet('weekly_history')
                h_df = pd.DataFrame(h_ws.get_all_records())
                if not h_df.empty:
                    h_df['프로젝트명'] = h_df['프로젝트명'].astype(str).str.strip()
                    p_match = h_df[h_df['프로젝트명'] == selected_pjt.strip()]
                    if not p_match.empty:
                        latest = p_match.iloc[-1]
                        st.markdown(f"""
                        <div class="history-box">
                            <p style="font-size:14px; color:#555; margin-bottom:10px;">📅 <b>최종 보고일:</b> {latest.get('날짜', '-')}</p>
                            <p style="margin-bottom:12px;"><b>✔️ 금주 주요 업무:</b><br>{latest.get('금주업무', latest.get('주요현황', '-'))}</p>
                            <p style="margin-bottom:0;"><b>🔜 차주 주요 업무:</b><br>{latest.get('차주업무', '-')}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else: st.info("아직 등록된 주간 업무 기록이 없습니다.")
            except: st.warning("데이터를 불러오는 중 오류가 발생했습니다.")

            st.divider()
            st.subheader("📝 신규 주간 업무 보고 작성")
            with st.form("weekly_entry_form"):
                in_this = st.text_area("✔️ 금주 주요 업무 입력", height=120)
                in_next = st.text_area("🔜 차주 주요 업무 입력", height=120)
                if st.form_submit_button("저장 및 시스템 반영"):
                    h_ws.append_row([datetime.date.today().strftime("%Y-%m-%d"), selected_pjt, in_this, in_next, st.session_state.user_id])
                    st.success("로그가 저장되었습니다!"); time.sleep(1); st.rerun()
        
        st.write("---")
        st.subheader("📝 상세 공정표 편집")
        st.info("💡 진행률(%) 칸을 더블클릭하여 숫자를 직접 입력할 수 있습니다.")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 공정표 데이터 저장"):
            # 저장 전 데이터 타입 정리
            final_df = edited.copy()
            header = final_df.columns.values.tolist()
            rows = final_df.fillna("").astype(str).values.tolist()
            ws.update([header] + rows)
            # PM 정보 복구 (J1 셀)
            ws.update('J1', [[new_pm]])
            st.success("데이터가 성공적으로 저장되었습니다!"); time.sleep(1); st.rerun()

# 3. 일 발전량 분석
def view_solar(sh):
    st.title("☀️ 일 발전량 및 일조 분석")
    try:
        db_ws = sh.worksheet('Solar_DB')
        df_db = pd.DataFrame(db_ws.get_all_records())
        if not df_db.empty:
            df_db['날짜'] = pd.to_datetime(df_db['날짜'], errors='coerce')
            st.subheader("📊 월별 평균 발전 시간 (h)")
            m_avg = df_db.groupby(df_db['날짜'].dt.month)['발전시간'].mean().reset_index()
            st.plotly_chart(px.bar(m_avg, x='날짜', y='발전시간', labels={'날짜':'월'}, color_discrete_sequence=['#ffca28']), use_container_width=True)
            st.dataframe(df_db.tail(15), use_container_width=True)
    except: st.info("Solar_DB 시트를 찾을 수 없습니다.")

# 4. 경영지표 KPI
def view_kpi(sh):
    st.title("📉 경영 실적 및 KPI")
    try:
        df = pd.DataFrame(sh.worksheet('KPI').get_all_records())
        st.subheader("전사 주요 경영지표 현황")
        st.dataframe(df, use_container_width=True)
    except: st.warning("KPI 데이터 시트를 찾을 수 없습니다.")

# 5. 리스크 현황
def view_risk_dashboard(sh, pjt_list):
    st.title("🚨 리스크 공정 모니터링")
    all_issues = []
    for p_name in pjt_list:
        try:
            df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
            if not df.empty and '비고' in df.columns:
                df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                issues = df[(df['비고'].astype(str).str.strip() != "") & (df['진행률'] < 100)].copy()
                if not issues.empty:
                    issues.insert(0, '현장명', p_name)
                    all_issues.append(issues)
        except: pass
    if all_issues: st.dataframe(pd.concat(all_issues), use_container_width=True)
    else: st.success("🎉 현재 진행 중인 리스크 공정이 없습니다.")

# 6. 마스터 관리
def view_project_admin(sh, pjt_list):
    st.title("⚙️ 마스터 관리")
    t1, t2, t3, t4, t5 = st.tabs(["➕ 등록", "✏️ 수정", "🗑️ 삭제", "🔄 엑셀 업로드", "📥 마스터 다운로드"])
    
    with t1:
        st.subheader("➕ 신규 프로젝트 등록")
        new_name = st.text_input("새 프로젝트 명칭 입력")
        if st.button("프로젝트 생성", type="primary") and new_name:
            if new_name not in pjt_list:
                with st.spinner("생성 중..."):
                    new_ws = sh.add_worksheet(title=new_name, rows="100", cols="20")
                    headers = ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "담당자"]
                    new_ws.append_row(headers)
                    st.success(f"'{new_name}' 프로젝트가 성공적으로 생성되었습니다!"); time.sleep(1); st.rerun()
            else: st.error("이미 존재하는 프로젝트 명칭입니다.")
            
    with t4:
        st.subheader("🔄 엑셀 데이터 동기화")
        target_sync = st.selectbox("업데이트 프로젝트 선택", ["선택"] + pjt_list, key="sync_sel")
        file = st.file_uploader("엑셀 파일 선택", type=['xlsx', 'xlsm'])
        if target_sync != "선택" and file and st.button("데이터 덮어쓰기"):
            df_up = pd.read_excel(file).fillna("").astype(str)
            ws = sh.worksheet(target_sync); ws.clear(); ws.update([df_up.columns.values.tolist()] + df_up.values.tolist())
            st.success("동기화 완료!")

    with t5:
        st.subheader("📥 마스터 다운로드")
        if st.button("📚 전 프로젝트 통합 마스터 엑셀 생성", type="primary", use_container_width=True):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for p in pjt_list:
                    try: pd.DataFrame(sh.worksheet(p).get_all_records()).to_excel(writer, index=False, sheet_name=p[:31])
                    except: pass
                try: pd.DataFrame(sh.worksheet('weekly_history').get_all_records()).to_excel(writer, index=False, sheet_name='weekly_history')
                except: pass
            st.download_button("📥 통합 파일 받기", output.getvalue(), f"PMO_Total_Master_{datetime.date.today()}.xlsx")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = client.open('pms_db')
            pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'conflict']]
            
            st.sidebar.title("📁 PMO 메뉴")
            menu = st.sidebar.radio("메뉴 선택", ["통합 대시보드", "리스크 현황", "프로젝트 상세", "일 발전량 분석", "경영지표(KPI)", "프로젝트 설정"])
            
            if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
            elif menu == "리스크 현황": view_risk_dashboard(sh, pjt_list)
            elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석": view_solar(sh)
            elif menu == "경영지표(KPI)": view_kpi(sh)
            elif menu == "프로젝트 설정": view_project_admin(sh, pjt_list)
            
            if st.sidebar.button("로그아웃"): st.session_state.logged_in = False; st.rerun()
        except Exception as e: st.error(f"DB 연결 오류: {e}")


이게 현재까지의 소스야

보다보니 발전량 검색하는 기능이 많이 지워졌더라고 복원해줘
