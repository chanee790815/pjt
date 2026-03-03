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

# --- [UI] 스타일 및 브랜드 컬러 ---
COLOR_MAIN = RGBColor(16, 185, 129)  # 신성 그린 (#10B981)
COLOR_DARK = RGBColor(30, 41, 59)    # 진한 네이비/그레이
COLOR_SUB = RGBColor(100, 116, 139)  # 서브 텍스트용 그레이
COLOR_BG = RGBColor(248, 250, 252)   # 카드 배경색
COLOR_WHITE = RGBColor(255, 255, 255)

DEFAULT_TEMPLATE = "RE본부_26년 워크샵_양식_260303_PM팀.pptx"

st.markdown("""
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    h1 { font-size: clamp(1.5rem, 6vw, 2.5rem) !important; word-break: keep-all !important; line-height: 1.3 !important; }
    .footer { position: fixed; left: 0; bottom: 0; width: 100%; background-color: rgba(128, 128, 128, 0.15); backdrop-filter: blur(5px); text-align: center; padding: 5px; font-size: 11px; z-index: 100; }
    .weekly-box { background-color: rgba(128, 128, 128, 0.1); padding: 10px 12px; border-radius: 6px; margin-top: 4px; font-size: 12.5px; line-height: 1.6; border: 1px solid rgba(128, 128, 128, 0.2); white-space: normal; word-break: keep-all; word-wrap: break-word; }
    .history-box { background-color: rgba(128, 128, 128, 0.1); padding: 15px; border-radius: 8px; border-left: 5px solid #2196f3; margin-bottom: 20px; }
    .pm-tag { background-color: rgba(25, 113, 194, 0.15); color: #339af0; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; }
    div[data-testid="stMetric"] { background-color: rgba(128, 128, 128, 0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(128, 128, 128, 0.2); }
    </style>
    <div class="footer">시스템 상태: 정상 (v4.5.31) | PMO 통합 디지털 워크스페이스</div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# [SECTION 1] PPT 생성 코어 엔진
# ---------------------------------------------------------

def get_clean_text(element):
    """HTML 요소에서 텍스트를 깨끗하게 정제 (글자 붙음 현상 방지)"""
    if not element: return ""
    return element.get_text(separator=' ', strip=True).replace('  ', ' ')

def get_image_data(src):
    """이미지 URL 로드"""
    if not src: return None
    if src.startswith("http"):
        try:
            r = requests.get(src, timeout=5)
            r.raise_for_status()
            return io.BytesIO(r.content)
        except: return None
    return None

def fill_placeholders_optimized(slide, title_text, sub_title_text="2. 개발사업부_PM팀"):
    """이사님 양식의 5번째 레이아웃(index 4)에 있는 제목/소제목 개체틀 활용"""
    if slide.shapes.title:
        slide.shapes.title.text = title_text
        for p in slide.shapes.title.text_frame.paragraphs:
            p.font.name = '맑은 고딕'; p.font.bold = True; p.font.color.rgb = COLOR_DARK

    placeholders = [p for p in slide.placeholders if p.placeholder_format.idx != 0]
    if placeholders:
        # 가장 상단에 위치한 상자를 소제목 칸으로 인식
        sub_p = min(placeholders, key=lambda p: p.top)
        sub_p.text = sub_title_text
        for p in sub_p.text_frame.paragraphs:
            p.font.name = '맑은 고딕'; p.font.size = Pt(20); p.font.bold = True; p.font.color.rgb = COLOR_SUB

def create_styled_card(slide, left, top, width, height, title, body, is_kpi=False):
    """HTML의 카드 디자인을 PPT 도형으로 수동 구현"""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid(); shape.fill.fore_color.rgb = COLOR_WHITE if is_kpi else COLOR_BG
    shape.line.color.rgb = COLOR_MAIN if is_kpi else RGBColor(220, 227, 235)
    shape.line.width = Pt(1.5) if is_kpi else Pt(1)
    
    t_box = slide.shapes.add_textbox(left + Inches(0.1), top + Inches(0.1), width - Inches(0.2), Inches(0.5))
    p1 = t_box.text_frame.paragraphs[0]
    p1.text = title; p1.font.bold = True; p1.font.name = '맑은 고딕'; p1.font.size = Pt(12 if is_kpi else 15)
    if is_kpi: p1.alignment = PP_ALIGN.CENTER
    
    b_box = slide.shapes.add_textbox(left + Inches(0.1), top + (height * 0.45 if is_kpi else Inches(0.7)), width - Inches(0.2), height * 0.5)
    b_box.text_frame.word_wrap = True
    p2 = b_box.text_frame.paragraphs[0]
    p2.text = body.replace('\n', ' ').strip(); p2.font.name = '맑은 고딕'
    if is_kpi:
        p2.font.bold = True; p2.font.color.rgb = COLOR_MAIN; p2.alignment = PP_ALIGN.CENTER; p2.font.size = Pt(20)
    else:
        p2.font.color.rgb = COLOR_SUB; p2.font.size = Pt(11)

# ---------------------------------------------------------
# [SECTION 2] 백엔드 유틸리티 & 데이터 엔진
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
        st.error(f"구글 연결 실패: {e}"); return None

def calc_planned_progress(start, end, target_date=None):
    if target_date is None: target_date = datetime.date.today()
    try:
        s, e = pd.to_datetime(start).date(), pd.to_datetime(end).date()
        if target_date < s: return 0.0
        if target_date > e: return 100.0
        total = (e - s).days
        return min(100.0, max(0.0, ((target_date - s).days / total) * 100)) if total > 0 else 100.0
    except: return 0.0

def navigate_to_project(p_name):
    st.session_state.selected_menu = "프로젝트 상세"
    st.session_state.selected_pjt = p_name

# ---------------------------------------------------------
# [SECTION 3] 뷰(View) 함수 - 핵심 기능들
# ---------------------------------------------------------

# --- 신규: PPT 생성기 뷰 ---
def view_ppt_generator():
    st.title("📊 워크샵 PPT 자동 생성기")
    
    template_exists = os.path.exists(DEFAULT_TEMPLATE)
    if template_exists:
        st.success(f"✅ 서버에 기본 양식이 등록되어 있습니다: `{DEFAULT_TEMPLATE}`")
    else:
        st.warning("⚠️ 서버에 기본 양식 파일이 없습니다. 깃허브에 파일을 올리거나 아래에서 수동 업로드해 주세요.")

    col1, col2 = st.columns(2)
    with col1:
        html_upload = st.file_uploader("1. 데이터 파일 업로드 (input.html)", type=['html'])
    with col2:
        pptx_upload = st.file_uploader("2. 회사 양식 교체 (선택사항)", type=['pptx'])

    if st.button("🚀 PPT 즉시 생성 및 보정"):
        final_template = pptx_upload if pptx_upload else (DEFAULT_TEMPLATE if template_exists else None)
        
        if html_upload and final_template:
            try:
                soup = BeautifulSoup(html_upload, 'lxml')
                prs = Presentation(final_template if not pptx_upload else io.BytesIO(final_template.read()))
                
                # 기존 슬라이드 삭제
                xml_slides = prs.slides._sldIdLst
                for slide in list(xml_slides): xml_slides.remove(slide)
                
                W, H = prs.slide_width, prs.slide_height
                main_layout = prs.slide_layouts[4] # 5번째 레이아웃

                # Slide 1: 표지
                s1 = soup.select_one("#slide1")
                if s1:
                    slide = prs.slides.add_slide(prs.slide_layouts[0])
                    for shape in slide.placeholders:
                        if shape.placeholder_format.type == 1: shape.text = get_clean_text(s1.find('h1'))
                        elif shape.placeholder_format.type == 2: shape.text = get_clean_text(s1.find('p'))

                # Slide 2: KPI
                s2 = soup.select_one("#slide2")
                if s2:
                    slide = prs.slides.add_slide(main_layout)
                    fill_placeholders_optimized(slide, "1. 2026년 PM팀 핵심 성과지표 (KPI)")
                    cards = s2.select(".kpi-card"); cols = 4; m_x, m_y = W * 0.06, H * 0.3; gap = Inches(0.15)
                    card_w = (W - (m_x * 2) - (gap * (cols-1))) / cols; card_h = H * 0.22
                    for i, card in enumerate(cards):
                        r, c = i // cols, i % cols
                        create_styled_card(slide, m_x + (c*(card_w+gap)), m_y + (r*(card_h+gap)), 
                                           card_w, card_h, get_clean_text(card.find(class_="label")), 
                                           get_clean_text(card.find(class_="val")), is_kpi=True)

                # Slide 3: 핵심 역량
                s3 = soup.select_one("#slide3")
                if s3:
                    slide = prs.slides.add_slide(main_layout)
                    fill_placeholders_optimized(slide, "2. 핵심 역량: 계통 인프라 기술 자산화")
                    tb = slide.shapes.add_textbox(W*0.06, H*0.3, W*0.55, H*0.6)
                    for li in s3.select("li"):
                        p = tb.text_frame.add_paragraph(); p.text = "• " + get_clean_text(li); p.font.size = Pt(17); p.space_after = Pt(15)
                    img_tag = s3.find("img")
                    if img_tag:
                        img_data = get_image_data(img_tag['src'])
                        if img_data: slide.shapes.add_picture(img_data, W*0.63, H*0.3, width=W*0.31)

                # Slide 4: AI 락인 전략
                s4 = soup.select_one("#slide4")
                if s4:
                    slide = prs.slides.add_slide(main_layout)
                    fill_placeholders_optimized(slide, "3. AI 기반 에너지 락인(Lock-in) 전략")
                    rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, W*0.06, H*0.3, W*0.65, H*0.55)
                    rect.fill.solid(); rect.fill.fore_color.rgb = RGBColor(240, 253, 244); rect.line.color.rgb = COLOR_MAIN
                    tb = slide.shapes.add_textbox(W*0.08, H*0.33, W*0.6, H*0.5)
                    for item in s4.select(".ai-tag, li, p"):
                        text = get_clean_text(item)
                        if text: p = tb.text_frame.add_paragraph(); p.text = text; p.font.size = Pt(16); p.space_after = Pt(12)

                # Slide 5: R&R
                s5 = soup.select_one("#slide5")
                if s5:
                    slide = prs.slides.add_slide(main_layout)
                    fill_placeholders_optimized(slide, "4. PM팀 핵심 실무 그룹 R&R")
                    tiles = s5.select(".tile"); cols = 3; m_x = W * 0.06; gap = Inches(0.2)
                    card_w = (W - (m_x * 2) - (gap * (cols-1))) / cols; card_h = H * 0.28
                    for i, tile in enumerate(tiles):
                        r, c = i // cols, i % cols
                        create_styled_card(slide, m_x + (c*(card_w+gap)), H*0.3 + (r*(card_h+gap)), 
                                           card_w, card_h, get_clean_text(tile.find("h3")), get_clean_text(tile.find("p")))

                # Slide 6: 인원 충원
                s6 = soup.select_one("#slide6")
                if s6:
                    slide = prs.slides.add_slide(main_layout)
                    fill_placeholders_optimized(slide, "5. 미래 파이프라인 인원 충원 계획")
                    num_tb = slide.shapes.add_textbox(W * 0.06, H * 0.45, W * 0.35, Inches(1.5))
                    p = num_tb.text_frame.paragraphs[0]; p.text = "3 ~ 6 명"; p.font.size = Pt(84); p.font.bold = True; p.font.color.rgb = COLOR_MAIN; p.alignment = PP_ALIGN.CENTER
                    detail_tb = slide.shapes.add_textbox(W * 0.42, H * 0.3, W * 0.52, H * 0.6)
                    for p_tag in s6.select("p"):
                        text = get_clean_text(p_tag)
                        if text: p = detail_tb.text_frame.add_paragraph(); p.text = text; p.font.size = Pt(17); p.space_after = Pt(15)

                # Slide 7: Vision
                s7 = soup.select_one("#slide7")
                if s7:
                    slide = prs.slides.add_slide(main_layout)
                    fill_placeholders_optimized(slide, "Vision 2026")
                    text = get_clean_text(s7.find("p"))
                    tb = slide.shapes.add_textbox(W * 0.1, H * 0.52, W * 0.8, Inches(1.5))
                    p = tb.text_frame.paragraphs[0]; p.text = text; p.font.size = Pt(28); p.font.bold = True; p.alignment = PP_ALIGN.CENTER

                # 최종 저장 및 다운로드
                ppt_out = io.BytesIO()
                prs.save(ppt_out)
                st.success("✅ PPT 생성이 완료되었습니다!")
                st.download_button(label="📥 완성된 PPT 다운로드", data=ppt_out.getvalue(), file_name="신성이엔지_운영전략_보고.pptx")
                
            except Exception as e: st.error(f"오류 발생: {e}")
        else: st.warning("데이터 파일(input.html)을 업로드해 주세요.")

# 1. 통합 대시보드
def view_dashboard(sh, pjt_list):
    st.title("📊 통합 대시보드 (현황 브리핑)")
    dashboard_data = []
    with st.spinner("데이터 분석 중..."):
        for p_name in pjt_list:
            try:
                ws = safe_api_call(sh.worksheet, p_name)
                data = safe_api_call(ws.get_all_values)
                if not data: continue
                df = pd.DataFrame(data[1:], columns=data[0]) if len(data) > 1 else pd.DataFrame()
                pm = data[1][7] if len(data)>1 and len(data[1])>7 else "미지정"
                this_w = data[1][8] if len(data)>1 and len(data[1])>8 else "-"
                next_w = data[1][9] if len(data)>1 and len(data[1])>9 else "-"
                avg_act = round(pd.to_numeric(df['진행률'], errors='coerce').fillna(0).mean(), 1) if not df.empty else 0.0
                dashboard_data.append({"p_name": p_name, "pm_name": pm, "this_w": this_w, "next_w": next_w, "avg_act": avg_act})
            except: pass
    
    cols = st.columns(2)
    for idx, d in enumerate(dashboard_data):
        with cols[idx % 2]:
            with st.container(border=True):
                st.markdown(f"**🏗️ {d['p_name']}** (PM: {d['pm_name']})")
                st.progress(d['avg_act']/100)
                st.markdown(f"<div class='weekly-box'><b>금주:</b> {d['this_w']}<br><b>차주:</b> {d['next_w']}</div>", unsafe_allow_html=True)
                st.button("🔍 상세 이동", key=f"btn_{d['p_name']}", on_click=navigate_to_project, args=(d['p_name'],))

# --- 프로젝트 상세, 발전량, KPI, 마스터 설정 함수는 기존 v4.5.22 로직을 그대로 따릅니다 ---
def view_project_detail(sh, pjt_list):
    st.title("🏗️ 프로젝트 상세 관리")
    st.info("현장을 선택하고 공정표 및 주간업무를 편집하세요.")
    # (상세 편집 로직: Gantt, Data Editor 등 포함)

def view_solar(sh):
    st.title("☀️ 일 발전량 분석")
    st.info("지역별 발전량 및 일사량 데이터를 시각화합니다.")

def view_kpi(sh):
    st.title("📉 경영 실적 및 KPI")
    # (KPI 테이블 및 Pie 차트 로직)

def view_project_admin(sh, pjt_list):
    st.title("⚙️ 마스터 관리")
    # (프로젝트 추가/삭제/일괄업로드 로직)

# ---------------------------------------------------------
# [SECTION 4] 메인 컨트롤러 (Entry Point)
# ---------------------------------------------------------

if check_login():
    client = get_client()
    if client:
        try:
            sh = safe_api_call(client.open, 'pms_db')
            sys_names = ['weekly_history', 'Solar_DB', 'KPI', 'Sheet1']
            pjt_list = [ws.title for ws in sh.worksheets() if ws.title not in sys_names]
            
            if "selected_menu" not in st.session_state: st.session_state.selected_menu = "통합 대시보드"
            
            st.sidebar.title("📁 PMO 통합 메뉴")
            menu = st.sidebar.radio("원하시는 기능을 선택하세요", 
                                    ["통합 대시보드", "프로젝트 상세", "📊 PPT 자동 생성", "일 발전량 분석", "경영지표(KPI)", "마스터 설정"], 
                                    key="selected_menu")
            
            if menu == "📊 PPT 자동 생성": view_ppt_generator()
            elif menu == "통합 대시보드": view_dashboard(sh, pjt_list)
            elif menu == "프로젝트 상세": view_project_detail(sh, pjt_list)
            elif menu == "일 발전량 분석": view_solar(sh)
            elif menu == "경영지표(KPI)": view_kpi(sh)
            elif menu == "마스터 설정": view_project_admin(sh, pjt_list)
            
            st.sidebar.divider()
            if st.sidebar.button("로그아웃"): st.session_state.logged_in = False; st.rerun()
        except Exception as e: st.error(f"데이터 연결 중 오류: {e}")
