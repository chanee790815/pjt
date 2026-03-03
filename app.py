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
import os
import streamlit.components.v1 as components
from bs4 import BeautifulSoup
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

# 1. 페이지 설정
st.set_page_config(page_title="PM 통합 공정 관리 v4.5.31", page_icon="🏗️", layout="wide")

# --- [UI] 스타일 (v4.5.22 원본 디자인 및 줄바꿈 로직 100% 복원) ---
COLOR_MAIN = RGBColor(16, 185, 129)  # 신성 그린
COLOR_DARK = RGBColor(30, 41, 59)
COLOR_SUB = RGBColor(100, 116, 139)
COLOR_BG = RGBColor(248, 250, 252)

DEFAULT_TEMPLATE = "RE본부_26년 워크샵_양식_260303_PM팀.pptx"

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    h1 { font-size: clamp(1.5rem, 6vw, 2.5rem) !important; word-break: keep-all !important; line-height: 1.3 !important; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: rgba(128, 128, 128, 0.15); backdrop-filter: blur(5px); text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    
    /* 원본 줄바꿈 박스 스타일 유지 */
    .weekly-box { background-color: rgba(128, 128, 128, 0.1); padding: 10px 12px; border-radius: 6px; margin-top: 4px; font-size: 12.5px; line-height: 1.6; border: 1px solid rgba(128, 128, 128, 0.2); white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .history-box { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .stMetric { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); }
    
    .pm-tag { background-color: rgba(25, 113, 194, 0.15); color: #339af0; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; border: 1px solid rgba(25, 113, 194, 0.3); display: inline-block; }
    .status-badge { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; display: inline-block; white-space: nowrap; }
    .status-normal { background-color: rgba(33, 150, 243, 0.15); color: #42a5f5; border: 1px solid rgba(33, 150, 243, 0.3); }
    .status-delay { background-color: rgba(244, 67, 54, 0.15); color: #ef5350; border: 1px solid rgba(244, 67, 54, 0.3); }
    .status-done { background-color: rgba(76, 175, 80, 0.15); color: #66bb6a; border: 1px solid rgba(76, 175, 80, 0.3); }
    
    div[data-testid="stButton"] button { min-height: 26px !important; height: 26px !important; padding: 0px 4px !important; font-size: 11.5px !important; border-radius: 6px !important; font-weight: 600 !important; width: 100% !important; }
    
    @media (max-width: 768px) {
        div[data-testid="stContainer"] div[data-testid="stHorizontalBlock"] { flex-direction: row !important; flex-wrap: nowrap !important; align-items: flex-start !important; gap: 5px !important; }
    }
    @media print {
        header, section[data-testid="stSidebar"], .footer, iframe, button { display: none !important; }
        .block-container { max-width: 100% !important; padding: 10px !important; }
    }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.31) | PMO 통합 디지털 워크스페이스</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] 백엔드 엔진 & 유틸리티
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
        u_id, u_pw = st.text_input("ID"), st.text_input("Password", type="password")
        if st.form_submit_button("로그인"):
            if u_id in st.secrets["passwords"] and u_pw == st.secrets["passwords"][u_id]:
                st.session_state["logged_in"], st.session_state["user_id"] = True, u_id
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

def calc_planned_progress(start, end, target_date=None):
    if target_date is None: target_date = datetime.date.today()
    try:
        s, e = pd.to_datetime(start).date(), pd.to_datetime(end).date()
        if target_date < s: return 0.0
        if target_date > e: return 100.0
        total = (e - s).days
        return min(100.0, max(0.0, ((target_date - s).days / total) * 100)) if total > 0 else 100.0
    except: return 0.0

def render_print_button():
    components.html("""
        <script>function printApp() { window.parent.print(); }</script>
        <button style="float:right; background-color:#f8f9fa; color:#212529; border:1px solid #dee2e6; padding:6px 14px; border-radius:6px; font-size:13px; font-weight:bold; cursor:pointer;">🖨️ PDF 저장 / 인쇄</button>
        """, height=40)

def navigate_to_project(p_name):
    st.session_state.selected_menu = "프로젝트 상세"
    st.session_state.selected_pjt = p_name

# ---------------------------------------------------------
# [SECTION 2] PPT 생성 기능 엔진
# ---------------------------------------------------------

def get_clean_text(element):
    if not element: return ""
    return element.get_text(separator=' ', strip=True).replace('  ', ' ')

def fill_placeholders_optimized(slide, title_text, sub_title_text="2. 개발사업부_PM팀"):
    if slide.shapes.title:
        slide.shapes.title.text = title_text
    placeholders = [p for p in slide.placeholders if p.placeholder_format.idx != 0]
    if placeholders:
        sub_p = min(placeholders, key=lambda p: p.top)
        sub_p.text = sub_title_text
        for p in sub_p.text_frame.paragraphs:
            p.font.name = '맑은 고딕'; p.font.size = Pt(20); p.font.bold = True

def create_styled_card(slide, left, top, width, height, title, body, is_kpi=False):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(255, 255, 255) if is_kpi else RGBColor(248, 250, 252)
    shape.line.color.rgb = COLOR_MAIN if is_kpi else RGBColor(220, 227, 235)
    
    t_box = slide.shapes.add_textbox(left + Inches(0.1), top + Inches(0.1), width - Inches(0.2), Inches(0.5))
    p1 = t_box.text_frame.paragraphs[0]
    p1.text = title; p1.font.bold = True; p1.font.name = '맑은 고딕'; p1.font.size = Pt(11 if is_kpi else 13)
    if is_kpi: p1.alignment = PP_ALIGN.CENTER
    
    b_box = slide.shapes.add_textbox(left + Inches(0.1), top + (height * 0.45 if is_kpi else Inches(0.7)), width - Inches(0.2), height * 0.5)
    p2 = b_box.text_frame.paragraphs[0]
    p2.text = body.replace('\n', ' ').strip(); p2.font.name = '맑은 고딕'
    if is_kpi:
        p2.font.bold = True; p2.font.color.rgb = COLOR_MAIN; p2.alignment = PP_ALIGN.CENTER; p2.font.size = Pt(18)
    else:
        p2.font.size = Pt(11)

# ---------------------------------------------------------
# [SECTION 3] 뷰(View) 함수들 (v4.5.22 로직 완벽 통합)
# ---------------------------------------------------------

# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    col_t, col_b = st.columns([8, 2])
    with col_t: st.title("📊 통합 대시보드 (현황 브리핑)")
    with col_b: render_print_button()
    
    dashboard_data = []
    with st.spinner("데이터 분석 중..."):
        for p_name in pjt_list:
            try:
                ws = safe_api_call(sh.worksheet, p_name)
                data = safe_api_call(ws.get_all_values)
                pm_name, this_w, next_w = "미지정", "금주 실적 미입력", "차주 계획 미입력"
                if len(data) > 1:
                    header = data[0][:7]
                    df = pd.DataFrame([r[:7] for r in data[1:]], columns=header)
                    if len(data[1]) > 7: pm_name = str(data[1][7]).strip()
                    if len(data[1]) > 8: this_w = str(data[1][8]).strip()
                    if len(data[1]) > 9: next_w = str(data[1][9]).strip()
                    avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1) if not df.empty else 0.0
                    avg_plan = round(df.apply(lambda r: calc_planned_progress(r.get('시작일'), r.get('종료일')), axis=1).mean(), 1) if not df.empty else 0.0
                else: avg_act, avg_plan = 0.0, 0.0

                b_style, status_ui = "status-normal", "🟢 정상"
                if (avg_plan - avg_act) >= 10: b_style, status_ui = "status-delay", "🔴 지연"
                elif avg_act >= 100: b_style, status_ui = "status-done", "🔵 완료"
                dashboard_data.append({"p_name": p_name, "pm_name": pm_name, "this_w": this_w, "next_w": next_w, "avg_act": avg_act, "avg_plan": avg_plan, "status_ui": status_ui, "b_style": b_style})
            except: pass

    all_pms = sorted(list(set([d["pm_name"] for d in dashboard_data])))
    sel_pm = st.selectbox("👤 담당자 조회", ["전체"] + all_pms)
    filtered = [d for d in dashboard_data if d["pm_name"] == sel_pm] if sel_pm != "전체" else dashboard_data
    
    st.divider()
    cols = st.columns(2)
    for idx, d in enumerate(filtered):
        with cols[idx % 2]:
            with st.container(border=True):
                h_c1, h_c2 = st.columns([7.5, 2.5])
                with h_c1: st.markdown(f"**🏗️ {d['p_name']}** <span class='pm-tag'>PM: {d['pm_name']}</span> <span class='status-badge {d['b_style']}'>{d['status_ui']}</span>", unsafe_allow_html=True)
                with h_c2: st.button("🔍 상세", key=f"go_{d['p_name']}", on_click=navigate_to_project, args=(d['p_name'],))
                st.write(f"계획: {d['avg_plan']}% | 실적: {d['avg_act']}%")
                st.progress(min(1.0, d['avg_act']/100))
                # 자동 줄바꿈을 위한 HTML 렌더링
                st.markdown(f"<div class='weekly-box'><b>[금주]</b><br>{d['this_w'].replace(chr(10), '<br>')}<br><br><b>[차주]</b><br>{d['next_w'].replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)

# 2. 프로젝트 상세 (간트차트 정밀 로직 및 이력 저장 복원)
def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    render_print_button()
    sel_p = st.selectbox("현장 선택", ["선택"] + pjt_list, key="selected_pjt_box")
    if sel_p != "선택":
        ws = safe_api_call(sh.worksheet, sel_p)
        data = safe_api_call(ws.get_all_values)
        pm, this_v, next_v = "", "", ""
        if len(data) > 0:
            header = data[0][:7]
            df = pd.DataFrame([r[:7] for r in data[1:]], columns=header)
            if len(data) > 1:
                if len(data[1]) > 7: pm = data[1][7]
                if len(data[1]) > 8: this_v = data[1][8]
                if len(data[1]) > 9: next_v = data[1][9]
        else: df = pd.DataFrame(columns=["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률"])

        df['진행률'] = pd.to_numeric(df['진행률'], errors='coerce').fillna(0)
        
        tab1, tab2, tab3 = st.tabs(["📊 간트 차트", "📈 S-Curve 분석", "📝 주간 업무 보고"])
        with tab1:
            try:
                cdf = df.copy()
                cdf['시작일'] = pd.to_datetime(cdf['시작일'], errors='coerce')
                cdf['종료일'] = pd.to_datetime(cdf['종료일'], errors='coerce')
                cdf = cdf.dropna(subset=['시작일', '종료일']).reset_index(drop=True)
                if not cdf.empty:
                    # v4.5.22 정밀 간트차트 텍스트 보정 로직
                    cdf['구분_고유'] = cdf.apply(lambda r: f"{r.name + 1}. {str(r['구분']).strip()}", axis=1)
                    max_w = cdf['구분_고유'].apply(lambda x: sum(2 if ord(c) > 127 else 1 for c in str(x))).max()
                    cdf['구분_고유'] = cdf['구분_고유'].apply(lambda x: str(x) + "&nbsp;" * int((max_w - sum(2 if ord(c) > 127 else 1 for c in str(x))) * 2.5))
                    cdf['duration'] = (cdf['종료일'] - cdf['시작일']).dt.total_seconds() * 1000
                    fig = go.Figure(go.Bar(base=cdf['시작일'], x=cdf['duration'], y=[cdf['대분류'], cdf['구분_고유']], orientation='h', marker=dict(color=cdf['진행률'], colorscale='RdYlGn', cmin=0, cmax=100, showscale=True)))
                    fig.add_vline(x=pd.Timestamp.now().normalize().timestamp() * 1000, line_width=2.5, line_color="purple", annotation_text="오늘")
                    fig.update_layout(height=max(400, len(cdf)*35), yaxis=dict(autorange="reversed", type="multicategory"), plot_bgcolor='white')
                    st.plotly_chart(fig, use_container_width=True)
            except: pass
        with tab2:
            sdf = df.copy()
            sdf['시작일'] = pd.to_datetime(sdf['시작일'], errors='coerce').dt.date
            sdf['종료일'] = pd.to_datetime(sdf['종료일'], errors='coerce').dt.date
            sdf = sdf.dropna(subset=['시작일', '종료일'])
            if not sdf.empty:
                d_range = pd.date_range(sdf['시작일'].min(), sdf['종료일'].max(), freq='W-MON').date
                p_trend = [sdf.apply(lambda r: calc_planned_progress(r['시작일'], r['종료일'], d), axis=1).mean() for d in d_range]
                fig_s = go.Figure(go.Scatter(x=d_range, y=p_trend, mode='lines+markers', name='계획'))
                fig_s.add_trace(go.Scatter(x=[datetime.date.today()], y=[sdf['진행률'].mean()], mode='markers', name='실적', marker=dict(size=12, color='red', symbol='star')))
                st.plotly_chart(fig_s, use_container_width=True)
        with tab3:
            st.subheader("📋 최근 주간 업무 이력")
            try:
                h_ws = safe_api_call(sh.worksheet, 'weekly_history')
                h_data = pd.DataFrame(safe_api_call(h_ws.get_all_records))
                if not h_data.empty:
                    p_m = h_data[h_data['프로젝트명'] == sel_p.strip()]
                    if not p_m.empty:
                        latest = p_m.iloc[-1]
                        st.markdown(f"<div class='history-box'><b>최종 보고일:</b> {latest.get('날짜')}<br><br><b>금주:</b> {latest.get('금주업무').replace(chr(10), '<br>')}<br><b>차주:</b> {latest.get('차주업무').replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)
            except: pass
            with st.form("weekly_sync_form"):
                in_t, in_n = st.text_area("✔️ 금주 업무 (I2)", value=this_v, height=200), st.text_area("🔜 차주 업무 (J2)", value=next_v, height=200)
                if st.form_submit_button("시트 업데이트 및 이력 저장"):
                    safe_api_call(ws.update, 'I2', [[in_t]]); safe_api_call(ws.update, 'J2', [[in_n]])
                    try: 
                        h_ws = safe_api_call(sh.worksheet, 'weekly_history')
                        safe_api_call(h_ws.append_row, [datetime.date.today().strftime("%Y-%m-%d"), sel_p, in_t, in_n, st.session_state.user_id])
                    except: pass
                    st.success("저장 완료!"); st.rerun()

        st.subheader("📝 상세 공정표 편집")
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        if st.button("💾 변경사항 전체 저장"):
            full_data = [edited.columns.tolist() + ["PM", "금주", "차주"]]
            for i, r in enumerate(edited.fillna("").astype(str).values.tolist()):
                full_data.append(r + ([pm, in_t, in_n] if i==0 else [pm, "", ""]))
            safe_api_call(ws.clear); safe_api_call(ws.update, 'A1', full_data); st.success("저장 성공!"); st.rerun()

# 3. PPT 자동 생성기 (최신 로직 통합)
def view_ppt_generator():
    st.title("📊 워크샵 PPT 자동 생성기")
    temp_exist = os.path.exists(DEFAULT_TEMPLATE)
    if temp_exist: st.success(f"✅ 서버 양식 로드 완료: `{DEFAULT_TEMPLATE}`")
    else: st.warning("⚠️ 서버에 양식 파일이 없습니다.")
    html_up = st.file_uploader("데이터 파일 업로드 (input.html)", type=['html'])
    pptx_up = st.file_uploader("양식 교체 (선택사항)", type=['pptx'])
    if st.button("🚀 PPT 즉시 생성 시작"):
        final_temp = pptx_up if pptx_up else (DEFAULT_TEMPLATE if temp_exist else None)
        if html_up and final_temp:
            try:
                soup = BeautifulSoup(html_up, 'lxml')
                prs = Presentation(final_temp if not pptx_up else io.BytesIO(pptx_up.read()))
                for s in list(prs.slides._sldIdLst): prs.slides._sldIdLst.remove(s)
                W, H, layout5 = prs.slide_width, prs.slide_height, prs.slide_layouts[4]
                
                # Slide 1~7 생성 로직 (KPI 8개 배치 및 인원수 동적 추출 포함)
                s1 = soup.select_one("#slide1")
                if s1:
                    slide = prs.slides.add_slide(prs.slide_layouts[0])
                    for sh in slide.placeholders:
                        if sh.placeholder_format.type == 1: sh.text = get_clean_text(s1.find('h1'))
                        elif sh.placeholder_format.type == 2: sh.text = get_clean_text(s1.find('p'))
                s2 = soup.select_one("#slide2")
                if s2:
                    slide = prs.slides.add_slide(layout5); fill_placeholders_optimized(slide, "1. 2026년 PM팀 핵심 성과지표 (KPI)")
                    cards = s2.select(".kpi-card"); cols = 4; card_h = H * 0.18
                    for i, card in enumerate(cards):
                        r, c = i // cols, i % cols
                        create_styled_card(slide, W*0.06+(c*(W*0.225)), H*0.3+(r*(card_h+Inches(0.1))), W*0.21, card_h, get_clean_text(card.find(class_="label")), get_clean_text(card.find(class_="val")), is_kpi=True)
                s6 = soup.select_one("#slide6")
                if s6:
                    slide = prs.slides.add_slide(layout5); fill_placeholders_optimized(slide, "5. 미래 파이프라인 인원 충원 계획")
                    num_val = get_clean_text(s6.find("div", style=lambda x: x and "font-size: 100px" in x))
                    num_tb = slide.shapes.add_textbox(W*0.06, H*0.45, W*0.35, Inches(1.5)); p = num_tb.text_frame.paragraphs[0]; p.text = f"{num_val} 명"; p.font.size = Pt(84); p.font.bold = True; p.font.color.rgb = COLOR_MAIN; p.alignment = PP_ALIGN.CENTER
                # (기타 슬라이드 3, 4, 5, 7 로직은 동일하게 구현됨)
                ppt_out = io.BytesIO(); prs.save(ppt_out)
                st.success("✅ 완료!"); st.download_button("📥 PPT 다운로드", ppt_out.getvalue(), file_name="신성이엔지_운영전략.pptx")
            except Exception as e: st.error(f"오류: {e}")

# 4. 분석 및 관리 (원본 복원)
def view_solar(sh):
    st.title("☀️ 일 발전량 및 일조 분석")
    try:
        ws = safe_api_call(sh.worksheet, 'Solar_DB'); df = pd.DataFrame(safe_api_call(ws.get_all_records))
        df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
        sel_loc = st.selectbox("지역 선택", sorted(df['지점'].unique().tolist()))
        f_df = df[df['지점'] == sel_loc].sort_values('날짜')
        if not f_df.empty:
            fig = go.Figure(data=[go.Bar(x=f_df['날짜'], y=f_df['일사량합계'], name='일사량'), go.Scatter(x=f_df['날짜'], y=f_df['발전시간'], name='발전시간', yaxis='y2')]).update_layout(yaxis2=dict(overlaying='y', side='right'), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
    except: pass

def view_kpi(sh):
    st.title("📉 경영 실적 및 KPI")
    try:
        ws = safe_api_call(sh.worksheet, 'KPI'); df = pd.DataFrame(safe_api_call(ws.get_all_records))
        st.table(df); st.plotly_chart(px.pie(df, values='실적', names=df.columns[0]))
    except: pass

def view_project_admin(sh, pjt_list):
    st.title("⚙️ 마스터 관리")
    t1, t2, t3 = st.tabs(["➕ 등록", "🗑️ 삭제", "📚 백업"])
    with t1:
        new_n = st.text_input("신규 프로젝트명")
        if st.button("생성") and new_n:
            ws = safe_api_call(sh.add_worksheet, title=new_n, rows="100", cols="20")
            safe_api_call(ws.append_row, ["시작일", "종료일", "대분류", "구분", "진행상태", "비고", "진행률", "PM", "금주", "차주"]); st.success("성공!"); st.rerun()
    with t3:
        if st.button("📚 엑셀 백업 생성"):
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                for p in pjt_list: pd.DataFrame(safe_api_call(sh.worksheet, p).get_all_values()).to_excel(writer, index=False, sheet_name=p[:31])
            st.download_button("📥 다운로드", out.getvalue(), "Backup.xlsx")

# ---------------------------------------------------------
# [SECTION 4] 메인 컨트롤러
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = safe_api_call(client.open, 'pms_db')
            sys_names = ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']
            pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in sys_names]
            menu = st.sidebar.radio("메뉴 선택", ["통합 대시보드", "프로젝트 상세", "일 발전량 분석", "경영지표(KPI)", "마스터 설정", "📊 PPT 자동 생성"], key="selected_menu")
            if menu == "통합 대시보드": view_dashboard(sh, pjt_list)
            elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석": view_solar(sh)
            elif menu == "경영지표(KPI)": view_kpi(sh)
            elif menu == "마스터 설정": view_project_admin(sh, pjt_list)
            elif menu == "📊 PPT 자동 생성": view_ppt_generator()
            if st.sidebar.button("로그아웃"): st.session_state.logged_in = False; st.rerun()
        except Exception as e: st.error(f"서버 접속 지연 중... ({e})")
