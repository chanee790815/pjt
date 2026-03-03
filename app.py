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
import streamlit.components.v1 as components

# [추가] 별도로 만든 PPT 엔진을 불러옵니다.
import ppt_engine 

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.22", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 ---
st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    
    /* 메인 제목 반응형 최적화 */
    h1 {
        font-size: clamp(1.5rem, 6vw, 2.5rem) !important; 
        word-break: keep-all !important; 
        line-height: 1.3 !important;
    }
    
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: rgba(128, 128, 128, 0.15); backdrop-filter: blur(5px); text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    
    /* 박스 디자인 (반투명 회색 배경) 및 자동 줄바꿈 최적화 */
    .weekly-box { background-color: rgba(128, 128, 128, 0.1); padding: 10px 12px; border-radius: 6px; margin-top: 4px; font-size: 12.5px; line-height: 1.6; border: 1px solid rgba(128, 128, 128, 0.2); white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .history-box { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); }
    
    /* 태그 및 뱃지 */
    .pm-tag { background-color: rgba(25, 113, 194, 0.15); color: #339af0; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; border: 1px solid rgba(25, 113, 194, 0.3); display: inline-block; }
    .status-badge { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; display: inline-block; white-space: nowrap; }
    .status-normal { background-color: rgba(33, 150, 243, 0.15); color: #42a5f5; border: 1px solid rgba(33, 150, 243, 0.3); }
    .status-delay { background-color: rgba(244, 67, 54, 0.15); color: #ef5350; border: 1px solid rgba(244, 67, 54, 0.3); }
    .status-done { background-color: rgba(76, 175, 80, 0.15); color: #66bb6a; border: 1px solid rgba(76, 175, 80, 0.3); }
    
    /* 컴팩트 버튼 디자인 */
    div[data-testid="stButton"] button {
        min-height: 26px !important;
        height: 26px !important;
        padding: 0px 4px !important;
        font-size: 11.5px !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        line-height: 1 !important;
        margin: 0 !important;
        margin-top: 2px !important;
        width: 100% !important;
    }
    
    /* 진행바 마진 최적화 */
    div[data-testid="stProgressBar"] { margin-bottom: 0px !important; margin-top: 5px !important; }
    
    /* 모바일 세로 모드 최적화 */
    @media (max-width: 768px) {
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important; flex-wrap: nowrap !important; align-items: flex-start !important; gap: 5px !important;
        }
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child { width: calc(100% - 80px) !important; flex: 1 1 auto !important; min-width: 0 !important; }
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child { width: 75px !important; flex: 0 0 75px !important; min-width: 75px !important; }
    }

    @media print {
        header[data-testid="stHeader"], section[data-testid="stSidebar"], .footer, iframe, button { display: none !important; }
        .block-container { max-width: 100% !important; padding: 10px !important; margin: 0 !important; }
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        div[data-testid="stContainer"] { page-break-inside: avoid; }
    }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.22) | PDF/보고서 인쇄 기능 추가</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [원본 유지] 백엔드 엔진 & 유틸리티
# ---------------------------------------------------------

def safe_api_call(func, *args, **kwargs):
    retries = 5
    for i in range(retries):
        try: return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) and i < retries - 1: time.sleep(2 ** i); continue
            else: raise e

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
        st.error(f"구글 클라우드 연결 실패: {e}"); return None

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

def navigate_to_project(p_name):
    st.session_state.selected_menu = "프로젝트 상세"
    st.session_state.selected_pjt = p_name

def render_print_button():
    components.html("""
        <script>function printApp() { window.parent.print(); }</script>
        <style>
            body { margin: 0; padding: 0; background-color: transparent; }
            .print-btn { float: right; background-color: #f8f9fa; color: #212529; border: 1px solid #dee2e6; padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: bold; cursor: pointer; transition: all 0.2s; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
            .print-btn:hover { background-color: #e9ecef; border-color: #ced4da; }
        </style>
        <button class="print-btn" onclick="printApp()">🖨️ PDF 저장 / 인쇄</button>
        """, height=40)

# ---------------------------------------------------------
# [원본 유지] 뷰(View) 함수들
# ---------------------------------------------------------

# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    col_title, col_btn = st.columns([8, 2])
    with col_title: st.title("📊 통합 대시보드 (현황 브리핑)")
    with col_btn: st.write(""); render_print_button()
    dashboard_data = []
    with st.spinner("프로젝트 데이터를 분석 중입니다..."):
        for p_name in pjt_list:
            try:
                ws = safe_api_call(sh.worksheet, p_name)
                data = safe_api_call(ws.get_all_values)
                pm_name, this_w, next_w = "미지정", "금주 실적 미입력", "차주 계획 미입력"
                if len(data) > 0:
                    header = data[0][:7]
                    df = pd.DataFrame([r[:7] for r in data[1:]], columns=header) if len(data) > 1 else pd.DataFrame(columns=header)
                    if len(data) > 1 and len(data[1]) > 7 and str(data[1][7]).strip(): pm_name = str(data[1][7]).strip()
                    if len(data) > 1 and len(data[1]) > 8 and str(data[1][8]).strip(): this_w = str(data[1][8]).strip()
                    if len(data) > 1 and len(data[1]) > 9 and str(data[1][9]).strip(): next_w = str(data[1][9]).strip()
                else: df = pd.DataFrame()
                if not df.empty and '진행률' in df.columns:
                    avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1)
                    avg_plan = round(df.apply(lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')), axis=1).mean(), 1)
                else: avg_act, avg_plan = 0.0, 0.0
                status_ui, b_style = "🟢 정상", "status-normal"
                if (avg_plan - avg_act) >= 10: status_ui, b_style = "🔴 지연", "status-delay"
                elif avg_act >= 100: status_ui, b_style = "🔵 완료", "status-done"
                dashboard_data.append({"p_name": p_name, "pm_name": pm_name, "this_w": this_w, "next_w": next_w, "avg_act": avg_act, "avg_plan": avg_plan, "status_ui": status_ui, "b_style": b_style})
            except: pass
    all_pms = sorted(list(set([d["pm_name"] for d in dashboard_data])))
    f_col1, f_col2 = st.columns([1, 3])
    with f_col1: selected_pm = st.selectbox("👤 담당자 조회", ["전체"] + all_pms)
    filtered_data = [d for d in dashboard_data if d["pm_name"] == selected_pm] if selected_pm != "전체" else dashboard_data
    total_cnt = len(filtered_data)
    normal_cnt, delay_cnt, done_cnt = len([d for d in filtered_data if d['status_ui'] == "🟢 정상"]), len([d for d in filtered_data if d['status_ui'] == "🔴 지연"]), len([d for d in filtered_data if d['status_ui'] == "🔵 완료"])
    with f_col2: st.markdown(f'<div class="metric-container" style="display: flex; gap: 10px; align-items: center; height: 100%; padding-top: 28px;"><div style="background: rgba(128,128,128,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">📊 조회된 프로젝트: <span style="color: #2196f3; font-size: 15px;">{total_cnt}</span>건</div><div style="background: rgba(33,150,243,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px; color: #1976d2;">🟢 정상: {normal_cnt}건</div><div style="background: rgba(244,67,54,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px; color: #d32f2f;">🔴 지연: {delay_cnt}건</div><div style="background: rgba(76,175,80,0.1); padding: 7px 12px; border-radius: 6px; font-weight: bold; font-size: 13px; color: #388e3c;">🔵 완료: {done_cnt}건</div></div>', unsafe_allow_html=True)
    st.divider()
    if total_cnt == 0: st.info("선택된 담당자의 프로젝트가 없습니다.")
    else:
        cols = st.columns(2)
        for idx, d in enumerate(filtered_data):
            with cols[idx % 2]:
                with st.container(border=True):
                    h_col1, h_col2 = st.columns([7.5, 2.5], gap="small")
                    with h_col1: st.markdown(f'<div style="display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 2px;"><h4 style="font-weight:700; margin:0; font-size:clamp(13.5px, 3.5vw, 16px); word-break:keep-all; line-height:1.2;">🏗️ {d["p_name"]}</h4><span class="pm-tag" style="margin:0;">PM: {d["pm_name"]}</span><span class="status-badge {d["b_style"]}" style="margin:0;">{d["status_ui"]}</span></div>', unsafe_allow_html=True)
                    with h_col2: st.button("🔍 상세", key=f"btn_go_{d['p_name']}", on_click=navigate_to_project, args=(d['p_name'],), use_container_width=True)
                    st.markdown(f'<div style="margin-bottom:4px; margin-top:2px;"><p style="font-size:12.5px; opacity: 0.7; margin-top:0; margin-bottom:4px;">계획: {d["avg_plan"]}% | 실적: {d["avg_act"]}%</p><div class="weekly-box" style="margin-top:0;"><div style="margin-bottom: 8px;"><b>[금주]</b><br>{d["this_w"].replace(chr(10), "<br>")}</div><div><b>[차주]</b><br>{d["next_w"].replace(chr(10), "<br>")}</div></div></div>', unsafe_allow_html=True)
                    st.progress(min(1.0, max(0.0, d['avg_act']/100)))

# 2. 프로젝트 상세 관리
def view_project_detail(sh, pjt_list):
    col_title, col_btn = st.columns([8, 2])
    with col_title: st.title("🏗️ 프로젝트 상세 관리")
    with col_btn: st.write(""); render_print_button()
    selected_pjt = st.selectbox("현장 선택", ["선택"] + pjt_list, key="selected_pjt")
    if selected_pjt != "선택":
        ws = safe_api_call(sh.worksheet, selected_pjt)
        data = safe_api_call(ws.get_all_values)
        current_pm, this_val, next_val = "", "", ""
        if len(data) > 0:
            header = data[0][:7]
            df = pd.DataFrame([r[:7] for r in data[1:]], columns=header) if len(data) > 1 else pd.DataFrame(columns=header)
            if len(data) > 1 and len(data[1]) > 7: current_pm = str(data[1][7]).strip()
            if len(data) > 1 and len(data[1]) > 8: this_val = str(data[1][8]).strip()
            if len(data) > 1 and len(data[1]) > 9: next_val = str(data[1][9]).strip()
        else: df = pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률"])
        if '시작일' in df.columns: df['시작일'] = df['시작일'].astype(str).str.split().str[0].replace('nan', '')
        if '종료일' in df.columns: df['종료일'] = df['종료일'].astype(str).str.split().str[0].replace('nan', '')
        if '진행률' in df.columns: df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
        col_pm1, col_pm2 = st.columns([3, 1])
        with col_pm1: new_pm = st.text_input("프로젝트 담당 PM (H2 셀)", value=current_pm)
        with col_pm2: st.write(""); 
            if st.button("PM 성함 저장"): safe_api_call(ws.update, 'H2', [[new_pm]]); st.success("PM이 업데이트되었습니다!")
        st.divider()
        tab1, tab2, tab3 = st.tabs(["📊 간트 차트", "📈 S-Curve 분석", "📝 주간 업무 보고"])
        with tab1:
            try:
                cdf = df.copy(); cdf['시작일'] = pd.to_datetime(cdf['시작일'], errors='coerce'); cdf['종료일'] = pd.to_datetime(cdf['종료일'], errors='coerce')
                cdf = cdf.dropna(subset=['시작일', '종료일']).reset_index(drop=True)
                if not cdf.empty:
                    cdf['대분류'] = cdf['대분류'].astype(str).replace({'nan': '미지정', '': '미지정'})
                    cdf['구분_고유'] = cdf.apply(lambda r: f"{r.name + 1}. {str(r['구분']).strip()}", axis=1)
                    def calc_text_width(text): return sum(2 if ord(c) > 127 else 1 for c in str(text))
                    max_width = cdf['구분_고유'].apply(calc_text_width).max()
                    cdf['구분_고유'] = cdf['구분_고유'].apply(lambda x: str(x) + "&nbsp;" * int((max_width - calc_text_width(x)) * 2.5))
                    cdf['duration'] = (cdf['종료일'] - cdf['시작일']).dt.total_seconds() * 1000
                    fig = go.Figure()
                    fig.add_trace(go.Bar(base=cdf['시작일'], x=cdf['duration'], y=[cdf['대분류'].tolist(), cdf['구분_고유'].tolist()], orientation='h', marker=dict(color=cdf['진행률'], colorscale='RdYlGn', cmin=0, cmax=100, showscale=True, colorbar=dict(title="진행률(%)")), customdata=cdf[['시작일', '종료일', '대분류', '구분']].values, hovertemplate="<b>[%{customdata[2]}] %{customdata[3]}</b><br>시작일: %{customdata[0]|%Y-%m-%d}<br>종료일: %{customdata[1]|%Y-%m-%d}<br>진행률: %{marker.color}%<extra></extra>"))
                    fig.add_vline(x=pd.Timestamp.now().normalize().timestamp() * 1000, line_width=2.5, line_color="purple", annotation_text="오늘", annotation_position="top", annotation_font=dict(color="purple", size=13, weight="bold"))
                    fig.update_layout(height=max(400, len(cdf) * 35), plot_bgcolor='white', yaxis=dict(autorange="reversed", type="multicategory"))
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e: st.error(f"차트 오류: {e}")
        with tab2:
            try:
                sdf = df.copy(); sdf['시작일'] = pd.to_datetime(sdf['시작일'], errors='coerce').dt.date; sdf['종료일'] = pd.to_datetime(sdf['종료일'], errors='coerce').dt.date
                sdf = sdf.dropna(subset=['시작일', '종료일'])
                if not sdf.empty:
                    d_range = pd.date_range(sdf['시작일'].min(), sdf['종료일'].max(), freq='W-MON').date.tolist()
                    p_trend = [sdf.apply(lambda r: calc_planned_progress(r['시작일'], r['종료일'], d), axis=1).mean() for d in d_range]
                    fig_s = go.Figure()
                    fig_s.add_trace(go.Scatter(x=d_range, y=p_trend, mode='lines+markers', name='계획'))
                    fig_s.add_trace(go.Scatter(x=[datetime.date.today()], y=[sdf['진행률'].mean()], mode='markers', name='현재 실적', marker=dict(size=12, color='red', symbol='star')))
                    st.plotly_chart(fig_s.update_layout(title="진척률 추이 (S-Curve)"), use_container_width=True)
            except: pass
        with tab3:
            st.subheader("📋 최근 주간 업무 이력")
            try:
                h_ws = safe_api_call(sh.worksheet, 'weekly_history')
                h_data = safe_api_call(h_ws.get_all_records)
                h_df = pd.DataFrame(h_data)
                if not h_df.empty:
                    p_match = h_df[h_df['프로젝트명'].astype(str).str.strip() == selected_pjt.strip()]
                    if not p_match.empty:
                        latest = p_match.iloc[-1]
                        st.markdown(f'<div class="history-box"><p style="font-size:14px; opacity: 0.7; margin-bottom:10px;">📅 <b>최종 보고일:</b> {latest.get("날짜", "-")}</p><div style="margin-bottom:12px;"><b>✔️ 금주 주요 업무:</b><br>{str(latest.get("금주업무", "-")).replace(chr(10), "<br>")}</div><div><b>🔜 차주 주요 업무:</b><br>{str(latest.get("차주업무", "-")).replace(chr(10), "<br>")}</div></div>', unsafe_allow_html=True)
            except: pass
            st.divider(); st.subheader("📝 주간 업무 작성 및 동기화 (I2, J2 셀 & 히스토리)")
            with st.form("weekly_sync_form"):
                in_this = st.text_area("✔️ 금주 주요 업무 (I2)", value=this_val, height=250)
                in_next = st.text_area("🔜 차주 주요 업무 (J2)", value=next_val, height=250)
                if st.form_submit_button("시트 데이터 업데이트 및 이력 저장"):
                    safe_api_call(ws.update, 'I2', [[in_this]]); safe_api_call(ws.update, 'J2', [[in_next]])
                    try: safe_api_call(h_ws.append_row, [datetime.date.today().strftime("%Y-%m-%d"), selected_pjt, in_this, in_next, st.session_state.user_id])
                    except: pass
                    st.success("업데이트 및 저장이 완료되었습니다!"); time.sleep(1); st.rerun()
        st.write("---"); st.subheader("📝 상세 공정표 편집 (A~G열 전용)")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 변경사항 전체 저장"):
            f_data = [edited.columns.tolist()[:7] + ["PM", "금주", "차주"]]
            e_rows = edited.fillna("").astype(str).values.tolist()
            for i, r in enumerate(e_rows): f_data.append(r[:7] + ([new_pm, in_this, in_next] if i == 0 else [new_pm, "", ""]))
            safe_api_call(ws.clear); safe_api_call(ws.update, 'A1', f_data); st.success("데이터가 저장되었습니다!"); time.sleep(1); st.rerun()

# 3. 일 발전량 분석
def view_solar(sh):
    col_t, col_b = st.columns([8, 2])
    with col_t: st.title("☀️ 일 발전량 및 일조 분석")
    with col_b: st.write(""); render_print_button()
    try:
        db_ws = safe_api_call(sh.worksheet, 'Solar_DB'); raw = safe_api_call(db_ws.get_all_records)
        if not raw: st.info("데이터가 없습니다."); return
        df_db = pd.DataFrame(raw); df_db['날짜'] = pd.to_datetime(df_db['날짜'], errors='coerce')
        locs = sorted(df_db['지점'].unique().tolist()); sel_loc = st.selectbox("조회 지역 선택", locs)
        f_df = df_db[df_db['지점'] == sel_loc].sort_values('날짜')
        if not f_df.empty:
            m1, m2 = st.columns(2); m1.metric("평균 발전 시간", f"{f_df['발전시간'].mean():.2f} h"); m2.metric("평균 일사량", f"{f_df['일사량합계'].mean():.2f}")
            fig = go.Figure(data=[go.Bar(x=f_df['날짜'], y=f_df['일사량합계'], name='일사량', marker_color='orange'), go.Scatter(x=f_df['날짜'], y=f_df['발전시간'], name='발전시간', yaxis='y2', line=dict(color='blue'))]).update_layout(yaxis2=dict(overlaying='y', side='right'), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
    except: st.error("분석 데이터를 불러올 수 없습니다.")

# 4. 경영지표 KPI
def view_kpi(sh):
    st.title("📉 경영 실적 및 KPI")
    try:
        ws = safe_api_call(sh.worksheet, 'KPI'); df = pd.DataFrame(safe_api_call(ws.get_all_records))
        st.table(df); st.plotly_chart(px.pie(df, values='실적', names=df.columns[0], title="항목별 실적 비중"))
    except: st.warning("KPI 시트를 찾을 수 없습니다.")

# 5. 마스터 관리
def view_project_admin(sh, pjt_list):
    st.title("⚙️ 마스터 관리")
    t1, t2, t3, t4, t5 = st.tabs(["➕ 등록", "✏️ 수정", "🗑️ 삭제", "🔄 업로드", "📥 다운로드"])
    with t1:
        new_n = st.text_input("신규 프로젝트명")
        if st.button("생성") and new_n:
            nw = safe_api_call(sh.add_worksheet, title=new_n, rows="100", cols="20")
            safe_api_call(nw.append_row, ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "PM", "금주", "차주"])
            st.success("생성 완료!"); st.rerun()
    with t5:
        if st.button("📚 통합 백업 엑셀 생성"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                for p in pjt_list:
                    try: d = safe_api_call(sh.worksheet, p).get_all_values(); pd.DataFrame(d[1:], columns=d[0]).to_excel(writer, index=False, sheet_name=p[:31])
                    except: pass
            st.download_button("📥 통합 파일 받기", out.getvalue(), f"Backup_{datetime.date.today()}.xlsx")

# ---------------------------------------------------------
# [SECTION 3] 메인 컨트롤러 (메인 메뉴 연동)
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = safe_api_call(client.open, 'pms_db')
            sys_names = ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1', 'Control_Center', 'Dashboard_Control', '통합 대시보드']
            pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in sys_names]
            if "selected_menu" not in st.session_state: st.session_state.selected_menu = "통합 대시보드"
            if "selected_pjt" not in st.session_state: st.session_state.selected_pjt = "선택"
            
            st.sidebar.title("📁 PMO 메뉴")
            # [수정] 메뉴 목록에 PPT 자동 생성을 추가하고, 해당 로직은 ppt_engine에서 가져옵니다.
            menu = st.sidebar.radio("메뉴 선택", ["통합 대시보드", "프로젝트 상세", "일 발전량 분석", "경영지표(KPI)", "마스터 설정", "📊 PPT 자동 생성"], key="selected_menu")
            
            if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
            elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석": view_solar(sh)
            elif menu == "경영지표(KPI)": view_kpi(sh)
            elif menu == "마스터 설정": view_project_admin(sh, pjt_list)
            elif menu == "📊 PPT 자동 생성": ppt_engine.view_ppt_generator(DEFAULT_TEMPLATE) # 엔진 연결
            
            if st.sidebar.button("로그아웃"): st.session_state.logged_in = False; st.rerun()
        except Exception as e: st.error(f"서버 접속 오류: {e}")
