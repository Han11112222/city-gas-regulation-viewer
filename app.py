import streamlit as st
import pandas as pd
import pdfplumber
import os
import urllib.parse
import numpy as np

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
@st.cache_data(ttl=300)
def load_cleaned_data(sheet_name):
    try:
        encoded_sheet_name = urllib.parse.quote(sheet_name)
        csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&sheet={encoded_sheet_name}"
        
        df = pd.read_csv(csv_url, dtype=str)
        
        # 1. 완벽히 비어있는 행과 열 삭제
        df = df.dropna(how='all', axis=0).dropna(how='all', axis=1)
        
        if not df.empty and len(df.columns) > 0:
            # 2. 'Unnamed' 컬럼명 정리
            new_cols = []
            for c in df.columns:
                if "Unnamed" in str(c):
                    new_cols.append("")
                else:
                    new_cols.append(str(c).strip())
            df.columns = new_cols
            
            # 3. 셀 병합 빈칸을 이전 일자로 채우기
            df.iloc[:, 0] = df.iloc[:, 0].replace(r'^\s*$', np.nan, regex=True).ffill()
        
        # 4. 남은 빈 셀 처리
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

    # 드롭다운 필터용 일자 목록 생성
    df[date_col] = df[date_col].astype(str).str.strip()
    unique_dates = sorted([d for d in df[date_col].unique() if d and d != "nan"], reverse=True)

    selected_date = st.selectbox(
        f"📅 조회할 일자 선택 ({tab_name})", 
        ["전체 보기"] + unique_dates, 
        key=f"select_{tab_name}"
    )
    
    filtered_df = df.copy()
    if selected_date != "전체 보기":
        filtered_df = filtered_df[filtered_df[date_col] == selected_date]

    # [핵심 수정] 필터링 후 내부 인덱스를 무조건 0, 1, 2...로 초기화하여 KeyError 원천 차단
    filtered_df = filtered_df.reset_index(drop=True)

    st.markdown(f"##### 📊 개정 이력 목록")
    if not filtered_df.empty:
        # 화면 출력용 데이터프레임의 인덱스만 1부터 시작하는 숫자로 예쁘게 변경
        display_df = filtered_df.copy()
        display_df.index = range(1, len(display_df) + 1)
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
            second_col = df.columns[1] if len(df.columns) > 1 else date_col
            hint += f"{str(row[second_col])[:30]}..."
            row_options.append((idx, hint))
            
        selected_idx = st.selectbox(
            "자세히 볼 항목을 선택하세요:",
            options=[opt[0] for opt in row_options],
            format_func=lambda x: next(opt[1] for opt in row_options if opt[0] == x),
            key=f"row_box_{tab_name}"
        )
        
        chosen_row = filtered_df.loc[selected_idx]
        
        valid_cols = [c for c in df.columns if c != ""]
        num_valid_cols = len(valid_cols)
        
        if num_valid_cols > 0:
            cols = st.columns(num_valid_cols)
            for i, col_name in enumerate(valid_cols):
                with cols[i]:
                    st.markdown(f"**📍 {col_name if col_name else '항목'}**")
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
            st.warning(f"⚠️ 선택한 일자({target_date_str})에 매칭되는 PDF 파일을 찾을 수 없습니다.")

with tab1:
    render_tab_content(df_simple, "Simple")

with tab2:
    render_tab_content(df_detail, "상세")
