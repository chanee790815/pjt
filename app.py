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
st.set_page_config(page_title="PM 통합 공정 관리 v4.1.7", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .pjt-card { background-color: #ffffff; padding: 20px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: #f1f1f1; color: #555; text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .risk-high { border-left: 5px solid #ff4b4b !important; }
    .risk-normal { border-left: 5px solid #1f77b4 !important; }
    .weekly-box { background-color: #f8f9fa; padding: 12px; border-radius: 6px; margin-top: 10px; font-size: 13px; line-height: 1.6; color: #333; border: 1px solid #edf0f2; white-space: pre-wrap; }
    .status-header { background: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #e9ecef; border-left: 5px solid #007bff; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.1.7) | 통합 데이터 통합 관리 모드</div>
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
                df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').mean(), 1) if not df.empty else 0
                avg_plan = round(df.apply(lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')), axis=1).mean(), 1) if not df.empty else 0
                
                status_ui = "🟢 정상"
                c_style = "pjt-card risk-normal"
                if (avg_plan - avg_act) >= 10:
                    status_ui = "🔴 지연"
                    c_style = "pjt-card risk-high"
                
                weekly_content = "등록된 주간업무가 없습니다."
                if not hist_df.empty:
                    p_match = hist_df[hist_df['프로젝트명'] == p_name.strip()]
                    if not p_match.empty:
                        latest = p_match.iloc[-1]
                        this_w = str(latest.get('금주업무', '')).strip()
                        next_w = str(latest.get('차주업무', '')).strip()
                        summary = []
                        if this_w and this_w != 'nan': summary.append(f"<b>[금주]</b> {this_w[:70]}")
                        if next_w and next_w != 'nan': summary.append(f"<b>[차주]</b> {next_w[:70]}")
                        if summary: weekly_content = "<br>".join(summary)
                
                st.markdown(f'<div class="{c_style}"><h4>🏗️ {p_name} <span style="font-size:14px; float:right;">{status_ui}</span></h4><p style="font-size:13px; color:#666;">계획: {avg_plan}% | 실적: {avg_act}%</p><div class="weekly-box">{weekly_content}</div></div>', unsafe_allow_html=True)
                st.progress(min(1.0, max(0.0, avg_act/100)))
            except: pass

def view_risk_dashboard(sh, pjt_list):
    st.title("🚨 리스크 및 이슈 트래킹")
    st.markdown("전체 프로젝트 중 **'비고'란에 이슈가 작성되어 있고 완료되지 않은 공정**들을 모니터링합니다.")
    
    all_issues = []
    with st.spinner("리스크 데이터를 수집 중..."):
        for p_name in pjt_list:
            try:
                df = pd.DataFrame(sh.worksheet(p_name).get_all_records())
                if not df.empty and '비고' in df.columns:
                    df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
                    df['비고'] = df['비고'].astype(str).str.strip()
                    issues_df = df[(df['비고'] != "") & (df['비고'] != "-") & (df['진행률'] < 100)].copy()
                    if not issues_df.empty:
                        issues_df.insert(0, '현장명', p_name)
                        all_issues.append(issues_df)
            except: pass
                
    if all_issues:
        final_df = pd.concat(all_issues, ignore_index=True)
        st.error(f"⚠️ 현재 집중 관리가 필요한 이슈가 총 {len(final_df)}건 있습니다.")
        st.dataframe(final_df, use_container_width=True)
    else:
        st.success("🎉 현재 등록된 오픈 이슈가 없습니다.")

def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list)
    if selected_pjt != "선택":
        ws = sh.worksheet(selected_pjt)
        df = pd.DataFrame(ws.get_all_records())
        
        # 상단 최근 보고 요약
        try:
            h_ws = sh.worksheet('weekly_history')
            h_df = pd.DataFrame(h_ws.get_all_records())
            if not h_df.empty:
                h_df['프로젝트명'] = h_df['프로젝트명'].astype(str).str.strip()
                p_h = h_df[h_df['프로젝트명'] == selected_pjt.strip()]
                if not p_h.empty:
                    latest = p_h.iloc[-1]
                    st.markdown(f'<div class="status-header"><h5>📋 최근 주간 보고 ({latest.get("날짜", "-")})</h5>'
                                f'<p style="font-size:14px; margin-bottom:5px;"><b>금주:</b> {latest.get("금주업무", "-")}</p>'
                                f'<p style="font-size:14px; margin-bottom:0;"><b>차주:</b> {latest.get("차주업무", "-")}</p></div>', unsafe_allow_html=True)
        except: pass

        tab1, tab2, tab3 = st.tabs(["📊 간트 차트", "📈 S-Curve 분석", "📝 주간 업무 보고"])
        
        with tab1:
            try:
                cdf = df.copy()
                cdf['시작일'] = pd.to_datetime(cdf['시작일'], errors='coerce')
                cdf['종료일'] = pd.to_datetime(cdf['종료일'], errors='coerce')
                cdf = cdf.dropna(subset=['시작일', '종료일'])
                fig = px.timeline(cdf, x_start="시작일", x_end="종료일", y="대분류", color="진행률", color_continuous_scale='RdYlGn', range_color=[0, 100])
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            except: st.warning("차트를 그릴 수 있는 날짜 데이터가 부족합니다.")

        with tab2:
            try:
                sdf = df.copy()
                sdf['시작일'] = pd.to_datetime(sdf['시작일'], errors='coerce').dt.date
                sdf['종료일'] = pd.to_datetime(sdf['종료일'], errors='coerce').dt.date
                sdf = sdf.dropna(subset=['시작일', '종료일'])
                if not sdf.empty:
                    min_d, max_d = sdf['시작일'].min(), sdf['종료일'].max()
                    d_range = pd.date_range(min_d, max_d, freq='W-MON').date.tolist()
                    if max_d not in d_range: d_range.append(max_d)
                    p_trend = [sdf.apply(lambda r: calc_planned_progress(r['시작일'], r['종료일'], d), axis=1).mean() for d in d_range]
                    a_prog = pd.to_numeric(sdf['진행률'], errors='coerce').fillna(0).mean()
                    x_axis = [d.strftime("%Y-%m-%d") for d in d_range]
                    today_s = datetime.date.today().strftime("%Y-%m-%d")
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(x=x_axis, y=p_trend, mode='lines+markers', name='계획'))
                    fig_s.add_trace(go.Scatter(x=[today_s], y=[a_prog], mode='markers', name='현재 실적', marker=dict(size=12, symbol='star', color='red')))
                    fig_s.add_vline(x=today_s, line_dash="dash", line_color="red")
                    fig_s.update_layout(title="계획 대비 실적 S-Curve", yaxis_title="진척률(%)", yaxis=dict(range=[0, 105]))
                    st.plotly_chart(fig_s, use_container_width=True)
            except: pass

        with tab3:
            st.subheader("📝 주간 주요 업무 보고 작성")
            try: hws = sh.worksheet('weekly_history')
            except: hws = sh.add_worksheet('weekly_history', 1000, 10); hws.append_row(['날짜', '프로젝트명', '금주업무', '차주업무', '작성자'])
            with st.form("w_form"):
                in_this = st.text_area("✔️ 금주 주요 업무", height=150)
                in_next = st.text_area("🔜 차주 주요 업무", height=150)
                if st.form_submit_button("저장 및 시스템 반영"):
                    hws.append_row([datetime.date.today().strftime("%Y-%m-%d"), selected_pjt, in_this, in_next, st.session_state.user_id])
                    st.success("로그가 저장되었습니다!"); st.rerun()
        
        st.write("---")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 공정표 변경사항 저장"):
            ws.clear(); ws.update([edited.columns.values.tolist()] + edited.fillna("").astype(str).values.tolist())
            st.success("저장되었습니다!")

def view_solar(sh):
    st.title("📅 일 발전량 분석")
    with st.expander("📥 기상청 데이터 수집 도구", expanded=True):
        c1, c2, c3 = st.columns(3)
        stn_map = {129:"서산(당진)", 108:"서울", 112:"인천", 119:"수원", 127:"충주", 131:"청주", 159:"부산"}
        stn_id = c1.selectbox("수집 지점", list(stn_map.keys()), format_func=lambda x: stn_map[x], index=0)
        year = c2.selectbox("수집 연도", range(2026, 2019, -1), index=1)
        if c3.button("🚀 데이터 동기화 실행", use_container_width=True):
            with st.spinner("데이터 요청 중..."):
                try:
                    db_ws = sh.worksheet('Solar_DB')
                    start, end = f"{year}0101", f"{year}1231"
                    if int(year) >= datetime.date.today().year: end = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
                    url = f'http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList?serviceKey=ba10959184b37d5a2f94b2fe97ecb2f96589f7d8724ba17f85fdbc22d47fb7fe&numOfRows=366&dataType=JSON&dataCd=ASOS&dateCd=DAY&stnIds={stn_id}&startDt={start}&endDt={end}'
                    res = requests.get(url, timeout=30).json()
                    items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                    rows = [[i['tm'], stn_map[stn_id], round(get_safe_float(i.get('sumGsr', 0)) / 3.6, 2), get_safe_float(i.get('sumGsr', 0))] for i in items]
                    if rows:
                        all_val = db_ws.get_all_values()
                        if len(all_val) > 1:
                            df_s = pd.DataFrame(all_val[1:], columns=all_val[0])
                            df_s['날짜'] = pd.to_datetime(df_s['날짜'], errors='coerce')
                            df_s = df_s.loc[~((df_s['날짜'].dt.year == int(year)) & (df_s['지점'] == stn_map[stn_id]))].dropna(subset=['날짜'])
                            df_s['날짜'] = df_s['날짜'].dt.strftime('%Y-%m-%d')
                            db_ws.clear(); db_ws.append_row(all_val[0]); db_ws.append_rows(df_s.values.tolist())
                        db_ws.append_rows(rows); st.success("✅ 수집 완료!"); st.rerun()
                except Exception as e: st.error(f"오류: {e}")

    try:
        df_db = pd.DataFrame(sh.worksheet('Solar_DB').get_all_records())
        if not df_db.empty:
            df_db['날짜'] = pd.to_datetime(df_db['날짜'], errors='coerce')
            m_avg = df_db.groupby(df_db['날짜'].dt.month)['발전시간'].mean().reset_index()
            st.plotly_chart(px.bar(m_avg, x='날짜', y='발전시간', labels={'날짜':'월'}, title="월별 평균 발전시간"), use_container_width=True)
    except: pass

def view_kpi(sh):
    st.title("📉 전사 경영지표 (KPI)")
    try:
        df = pd.DataFrame(sh.worksheet('KPI').get_all_records())
        st.dataframe(df, use_container_width=True)
    except: st.warning("KPI 시트를 찾을 수 없습니다.")

def view_project_admin(sh, pjt_list):
    st.title("⚙️ 프로젝트 설정 (마스터 관리)")
    t1, t2, t3, t4, t5 = st.tabs(["➕ 신규 등록", "✏️ 이름 수정", "🗑️ 삭제", "🔄 엑셀 동기화", "📥 마스터 다운로드"])
    
    with t1:
        new_name = st.text_input("새 프로젝트 명칭")
        if st.button("생성하기", type="primary") and new_name:
            if new_name not in pjt_list:
                sh.add_worksheet(title=new_name, rows="100", cols="20")
                sh.worksheet(new_name).append_row(["대분류", "구분", "작업명", "시작일", "종료일", "진행상태", "비고", "진행률", "담당자"])
                st.success(f"'{new_name}' 생성 완료!"); st.rerun()
    
    with t2:
        target = st.selectbox("수정할 프로젝트", ["선택"] + pjt_list, key="ren_sel")
        new_ren = st.text_input("새 이름")
        if st.button("수정 실행") and target != "선택" and new_ren:
            sh.worksheet(target).update_title(new_ren)
            st.success("수정 완료!"); st.rerun()

    with t3:
        target_del = st.selectbox("삭제할 프로젝트", ["선택"] + pjt_list, key="del_sel")
        if st.button("영구 삭제", type="primary") and target_del != "선택":
            if st.checkbox("정말 삭제하시겠습니까?"):
                sh.del_worksheet(sh.worksheet(target_del))
                st.success("삭제 완료!"); st.rerun()

    with t4:
        st.markdown("#### 🔄 엑셀 파일 동기화")
        target_sync = st.selectbox("업데이트 프로젝트", ["선택"] + pjt_list, key="sync_p")
        file = st.file_uploader("엑셀 파일 선택", type=['xlsx', 'xlsm'])
        if target_sync != "선택" and file and st.button("동기화 실행"):
            df_up = pd.read_excel(file).fillna("").astype(str)
            ws_sync = sh.worksheet(target_sync); ws_sync.clear()
            ws_sync.update([df_up.columns.values.tolist()] + df_up.values.tolist())
            st.success("동기화 완료!")

    with t5:
        st.info("💡 모든 현장 데이터와 주간업무 이력을 포함한 통합 파일을 생성합니다.")
        if st.button("📚 통합 마스터 엑셀 일괄 생성", type="primary", use_container_width=True):
            with st.spinner("병합 중..."):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    for p in pjt_list:
                        try: pd.DataFrame(sh.worksheet(p).get_all_records()).to_excel(writer, index=False, sheet_name=p[:31])
                        except: pass
                    try: pd.DataFrame(sh.worksheet('weekly_history').get_all_records()).to_excel(writer, index=False, sheet_name='weekly_history')
                    except: pass
                st.download_button("📥 통합 파일 다운로드", output.getvalue(), f"PMO_Master_Report_{datetime.date.today()}.xlsx", use_container_width=True)

# ---------------------------------------------------------
# [SECTION 3] 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
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
