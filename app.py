import streamlit as st
import pandas as pd
import pdfplumber
import os
import urllib.parse
import numpy as np
import time

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="도시가스 공급규정 개정 이력 관리 시스템", layout="wide")
st.title("📖 도시가스 공급규정 통합 관리 시스템")
st.markdown("구글 스프레드시트(요약)와 깃허브 PDF(규정 전문)를 실시간 연동한 대시보드입니다.")

# --- 구글 시트 및 PDF 파일 매핑 설정 ---
SHEET_ID = "1sFagZeEQlp2UMxUCCT96QPQm2bqG_YVMRXU0cgErteA"
FILE_MAP = {
    "2023": "1. 2023년_도시가스 공급규정 변경..pdf",
    "2024": "1. 2024년_도시가스 공급규정 변경..pdf",
    "2025": "1. 2025년_도시가스 공급규정 변경..pdf"
}

# --- PDF 전문 텍스트 추출 함수 ---
@st.cache_data
def extract_text_from_pdf(file_name):
    possible_paths = [file_name, os.path.join("data", file_name)]
    target_path = None
    for p in possible_paths:
        if os.path.exists(p):
            target_path = p
            break
            
    if not target_path:
        return f"⚠️ 깃허브에 {file_name} 파일이 존재하지 않거나 경로가 잘못되었습니다."
        
    text = ""
    try:
        with pdfplumber.open(target_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        return f"❌ PDF 읽기 오류: {e}"
    return text

# --- 1. Simple(요약) 탭 데이터 로드 ---
@st.cache_data(ttl=10)
def load_simple_data(sheet_name):
    try:
        encoded_sheet_name = urllib.parse.quote(sheet_name)
        cache_buster = int(time.time())
        csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&sheet={encoded_sheet_name}&cb={cache_buster}"
        
        df_raw = pd.read_csv(csv_url, dtype=str, header=None)
        df_raw = df_raw.dropna(how='all', axis=0).dropna(how='all', axis=1)
        
        if df_raw.empty: return pd.DataFrame()
            
        header_idx = 0
        for i in range(min(10, len(df_raw))):
            row_vals = df_raw.iloc[i].fillna("").astype(str).tolist()
            if any(keyword in val for val in row_vals for keyword in ["일자", "연도", "내용", "사유"]):
                header_idx = i
                break
                
        headers = df_raw.iloc[header_idx].fillna("").astype(str)
        new_cols = []
        for j, c in enumerate(headers):
            c_str = c.strip()
            if c_str == "" or "Unnamed" in c_str or c_str == "nan": c_str = f"공란_{j}"
            base_name = c_str
            suffix = 1
            while c_str in new_cols:
                c_str = f"{base_name}_{suffix}"
                suffix += 1
            new_cols.append(c_str)
            
        df = df_raw.iloc[header_idx + 1:].copy()
        df.columns = new_cols
        if not df.empty:
            df.iloc[:, 0] = df.iloc[:, 0].replace(r'^\s*$', np.nan, regex=True).ffill()
        df = df.fillna("")
        return df
    except Exception as e:
        st.error(f"'{sheet_name}' 에러: {e}")
        return pd.DataFrame()

# --- 2. [수정] 상세(신구조문) 탭 전용 데이터 로드 (4번째 열까지 파싱) ---
@st.cache_data(ttl=10)
def load_detail_data_by_gid(gid):
    try:
        cache_buster = int(time.time())
        csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}&cb={cache_buster}"
        
        df_raw = pd.read_csv(csv_url, dtype=str, header=None)
        
        records = []
        current_year = "알 수 없음"
        
        for index, row in df_raw.iterrows():
            vals = [str(x).strip() if str(x).strip() != 'nan' else '' for x in row.tolist()]
            if all(v == '' for v in vals): continue
                
            # 1. 연도 감지
            found_year = False
            for v in vals:
                if v.isdigit() and len(v) == 4:
                    current_year = v
                    found_year = True
                    break
            if found_year: continue
                
            # 2. 헤더 행 스킵
            if '현행' in vals or '개정(안)' in vals: continue
                
            # 3. [수정] 데이터 추출 (인덱스 1: 현행, 인덱스 2: 개정안, 인덱스 3: 개정 사유)
            if len(vals) >= 3:
                current_text = vals[1]
                revised_text = vals[2]
                # 네 번째 열(인덱스 3) 데이터가 존재하면 가져오고, 없으면 빈 문자열 처리
                reason_text = vals[3] if len(vals) >= 4 else ''
                
                if current_text or revised_text or reason_text:
                    records.append({
                        '연도': current_year,
                        '현행': current_text,
                        '개정(안)': revised_text,
                        '개정 사유': reason_text
                    })
        
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"상세 데이터를 가져오는 중 에러가 발생했습니다: {e}")
        return pd.DataFrame()

# --- 데이터 가져오기 ---
df_simple = load_simple_data("simple")
df_detail = load_detail_data_by_gid("1205780686")

# --- 화면 탭 구성 ---
tab1, tab2 = st.tabs(["📑 요약 버전 (Simple)", "📄 상세 버전 (신구조문 대비표)"])

# --- Simple 탭 렌더링 함수 ---
def render_simple_tab(df):
    if df.empty:
        st.info("Simple 데이터가 없습니다.")
        return

    date_col = df.columns[0] 
    df[date_col] = df[date_col].astype(str).str.strip()
    
    df['_year'] = df[date_col].str.extract(r'^(\d{4})').astype(float)
    df = df[df['_year'] >= 2016].copy()
    df['_date_sort'] = pd.to_datetime(df[date_col].str.replace(r'\.$', '', regex=True), format='mixed', errors='coerce')
    df = df.sort_values(by=['_date_sort', date_col], ascending=[False, False])
    df = df.drop(columns=['_year', '_date_sort'])
    
    unique_dates = [d for d in df[date_col].unique() if d and d != "nan" and not d.startswith("공란_")]

    selected_date = st.selectbox(
        f"📅 조회할 일자 선택 (Simple)", 
        ["전체 보기"] + unique_dates, 
        key="select_simple"
    )
    
    filtered_df = df.copy()
    if selected_date != "전체 보기":
        filtered_df = filtered_df[filtered_df[date_col] == selected_date]

    st.markdown(f"##### 📊 개정 이력 목록")
    if not filtered_df.empty:
        display_df = filtered_df.copy()
        valid_display_cols = [col for col in display_df.columns if not col.startswith("공란_")]
        display_df = display_df[valid_display_cols]
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.write("선택한 조건의 데이터가 없습니다.")
        
    st.divider()
    
    if not filtered_df.empty:
        st.subheader("🔍 항목별 상세 내용")
        row_options = [(idx, f"[{row[date_col]}] {str(row.iloc[1])[:30]}...") for idx, row in filtered_df.iterrows()]
            
        selected_idx = st.selectbox(
            "자세히 볼 항목을 선택하세요:",
            options=[opt[0] for opt in row_options],
            format_func=lambda x: next(opt[1] for opt in row_options if opt[0] == x),
            key="row_box_simple"
        )
        chosen_row = filtered_df.loc[selected_idx]
        
        valid_cols = [c for c in df.columns if not c.startswith("공란_")]
        cols = st.columns(len(valid_cols))
        for i, col_name in enumerate(valid_cols):
            with cols[i]:
                st.markdown(f"**📍 {col_name}**")
                st.info(str(chosen_row[col_name]))

# --- [수정] 상세(신구조문) 탭 렌더링 함수 (3단 레이아웃 구현) ---
def render_detail_tab(df):
    if df.empty:
        st.info("상세 탭 데이터가 없습니다.")
        return
        
    unique_years = sorted([y for y in df['연도'].unique() if y != "알 수 없음"], reverse=True)
    selected_year = st.selectbox("📅 신구조문을 비교할 연도 선택", ["전체 보기"] + unique_years, key="select_detail_year")
    
    years_to_show = unique_years if selected_year == "전체 보기" else [selected_year]
    
    for y in years_to_show:
        st.markdown(f"### ⚖️ {y}년 신구조문 대비표")
        
        y_df = df[df['연도'] == y].reset_index(drop=True)
        
        for idx, row in y_df.iterrows():
            with st.container():
                # [수정] 좌우 너비 비율 조정 (현행 4 : 개정안 4 : 개정사유 3)
                col1, col2, col3 = st.columns([4, 4, 3])
                with col1:
                    st.markdown("##### ⬅️ 현행")
                    st.info(row['text_현행'] if 'text_현행' in df.columns else row['현행'] if row['현행'] else "(내용 없음)")
                with col2:
                    st.markdown("##### ➡️ 개정(안)")
                    st.success(row['개정(안)'] if row['개정(안)'] else "(내용 없음)")
                with col3:
                    st.markdown("##### 📝 개정 사유")
                    # 개정 사유를 주황색 계열 박스(warning)로 시각적 분리
                    st.warning(row['개정 사유'] if row['개정 사유'] else "(내용 없음)")
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        matched_year_key = next((k for k in FILE_MAP.keys() if k in y), None)
        if matched_year_key:
            with st.expander(f"🔍 {FILE_MAP[matched_year_key]} 원문 텍스트 확인하기", expanded=False):
                pdf_text = extract_text_from_pdf(FILE_MAP[matched_year_key])
                st.text_area(label=f"{y}년 원문", value=pdf_text, height=300, key=f"pdf_area_detail_{y}")

# --- 탭 실행 ---
with tab1:
    render_simple_tab(df_simple)

with tab2:
    render_detail_tab(df_detail)
