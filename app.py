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

# --- 구글 시트 데이터 로드 및 전처리 함수 ---
@st.cache_data(ttl=10)
def load_cleaned_data(sheet_name):
    try:
        encoded_sheet_name = urllib.parse.quote(sheet_name)
        cache_buster = int(time.time())
        csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&sheet={encoded_sheet_name}&cb={cache_buster}"
        
        df_raw = pd.read_csv(csv_url, dtype=str, header=None)
        df_raw = df_raw.dropna(how='all', axis=0).dropna(how='all', axis=1)
        
        if df_raw.empty:
            return pd.DataFrame()
            
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
            if c_str == "" or "Unnamed" in c_str or c_str == "nan":
                c_str = f"공란_{j}"
            
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
        st.error(f"'{sheet_name}' 데이터를 가져오는 중 에러가 발생했습니다: {e}")
        return pd.DataFrame()

# --- 데이터 가져오기 ---
df_simple = load_cleaned_data("simple")
df_detail = load_cleaned_data("상세")

# --- 화면 탭 구성 ---
tab1, tab2 = st.tabs(["📑 요약 버전 (Simple)", "📄 상세 버전 (상세)"])

def render_tab_content(df, tab_name):
    if df.empty:
        st.info("시트에 데이터가 없거나 로드되지 않았습니다.")
        return

    date_col = df.columns[0] 
    df[date_col] = df[date_col].astype(str).str.strip()
    
    # -----------------------------------------------------------------
    # [수정] 1. 2016년 이후 데이터 필터링 및 2. 최신순(내림차순) 정렬 적용
    # -----------------------------------------------------------------
    # 연도를 안전하게 추출하기 위해 정규표현식(첫 4자리 숫자) 사용
    df['_year'] = df[date_col].str.extract(r'^(\d{4})').astype(float)
    
    # 2016년 이후 데이터만 필터링
    df = df[df['_year'] >= 2016].copy()
    
    # '2016.7.' 와 같은 형태에서 정확한 정렬을 위해 임시 datetime 컬럼 생성 (끝에 붙은 마침표 제거)
    df['_date_sort'] = pd.to_datetime(df[date_col].str.replace(r'\.$', '', regex=True), format='mixed', errors='coerce')
    
    # 최신순(내림차순) 정렬 진행
    df = df.sort_values(by=['_date_sort', date_col], ascending=[False, False])
    
    # 임시로 만든 컬럼 제거
    df = df.drop(columns=['_year', '_date_sort'])
    # -----------------------------------------------------------------
    
    # 정렬된 DataFrame을 기반으로 고유 일자 목록 생성 (순서 유지)
    unique_dates = [d for d in df[date_col].unique() if d and d != "nan" and not d.startswith("공란_")]

    selected_date = st.selectbox(
        f"📅 조회할 {date_col if not date_col.startswith('공란_') else '일자'} 선택 ({tab_name})", 
        ["전체 보기"] + unique_dates, 
        key=f"select_{tab_name}"
    )
    
    filtered_df = df.copy()
    if selected_date != "전체 보기":
        filtered_df = filtered_df[filtered_df[date_col] == selected_date]

    filtered_df = filtered_df.reset_index(drop=True)

    st.markdown(f"##### 📊 개정 이력 목록")
    if not filtered_df.empty:
        display_df = filtered_df.copy()
        
        valid_display_cols = [col for col in display_df.columns if not col.startswith("공란_")]
        display_df = display_df[valid_display_cols]
        display_df.index = range(1, len(display_df) + 1)
        
        # --- 표 너비 100% 확장 및 특정 컬럼 너비 강제 할당 (안전한 CSS 적용) ---
        css = "<style>\n"
        css += '[data-testid="stTable"] table { width: 100% !important; }\n'
        
        for i, col in enumerate(display_df.columns):
            if "내용" in col:
                css += f'[data-testid="stTable"] th:nth-child({i+2}), [data-testid="stTable"] td:nth-child({i+2}) {{ width: 50% !important; }}\n'
            elif "사유" in col:
                css += f'[data-testid="stTable"] th:nth-child({i+2}), [data-testid="stTable"] td:nth-child({i+2}) {{ width: 25% !important; }}\n'

        css += "</style>"
        st.markdown(css, unsafe_allow_html=True)
        # -----------------------------------------------------------------
        
        st.table(display_df)
    else:
        st.write("선택한 조건의 데이터가 없습니다.")
    
    st.divider()
    
    # --- 하단부: 항목 상세내용 + PDF 뷰어 ---
    if not filtered_df.empty:
        st.subheader("🔍 항목별 상세 내용 및 원문 대조")
        
        row_options = []
        for idx, row in filtered_df.iterrows():
            hint = f"[{row[date_col]}] "
            valid_cols_for_hint = [c for c in df.columns if not c.startswith("공란_")]
            second_col = valid_cols_for_hint[1] if len(valid_cols_for_hint) > 1 else date_col
            hint += f"{str(row[second_col])[:30]}..."
            row_options.append((idx, hint))
            
        selected_idx = st.selectbox(
            "자세히 볼 항목을 선택하세요:",
            options=[opt[0] for opt in row_options],
            format_func=lambda x: next(opt[1] for opt in row_options if opt[0] == x),
            key=f"row_box_{tab_name}"
        )
        
        chosen_row = filtered_df.loc[selected_idx]
        
        valid_cols = [c for c in df.columns if not c.startswith("공란_")]
        num_valid_cols = len(valid_cols)
        
        if num_valid_cols > 0:
            cols = st.columns(num_valid_cols)
            for i, col_name in enumerate(valid_cols):
                with cols[i]:
                    st.markdown(f"**📍 {col_name}**")
                    st.info(str(chosen_row[col_name]))
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        target_date_str = str(chosen_row[date_col])
        matched_year_key = None
        
        for y_key in FILE_MAP.keys():
            if y_key in target_date_str:
                matched_year_key = y_key
                break
        
        if matched_year_key:
            st.markdown(f"### 📄 {matched_year_key}년 공급규정 전문")
            with st.expander(f"🔍 {FILE_MAP[matched_year_key]} 원문 텍스트 펼치기", expanded=True):
                with st.spinner("PDF 문서 읽어오는 중..."):
                    pdf_text = extract_text_from_pdf(FILE_MAP[matched_year_key])
                    st.text_area(label="전체 파일 본문", value=pdf_text, height=450, key=f"pdf_area_{tab_name}_{selected_idx}")
        else:
            st.warning(f"⚠️ 선택한 일자({target_date_str})에 매칭되는 PDF 파일을 찾을 수 없습니다. (연도 확인 필요)")

with tab1:
    render_tab_content(df_simple, "Simple")

with tab2:
    render_tab_content(df_detail, "상세")
