import streamlit as st
import pandas as pd
import pdfplumber
import os
import urllib.parse

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="도시가스 공급규정 개정 이력 관리 시스템", layout="wide")
st.title("📖 도시가스 공급규정 통합 관리 시스템")
st.markdown("구글 스프레드시트(요약)와 깃허브 PDF(규정 전문)를 실시간 연동한 대시보드입니다.")

# --- 구글 시트 및 PDF 파일 매핑 설정 ---
SHEET_ID = "1sFagZeEQlp2UMxUCCT96QPQm2bqG_YVMRXU0cgErteA"
FILE_MAP = {
    "2023년": "1. 2023년_도시가스 공급규정 변경..pdf",
    "2024년": "1. 2024년_도시가스 공급규정 변경..pdf",
    "2025년": "1. 2025년_도시가스 공급규정 변경..pdf"
}

# --- PDF 전문 텍스트 추출 함수 ---
@st.cache_data
def extract_text_from_pdf(file_name):
    # 루트 폴더 혹은 data/ 폴더 모두 탐색 가능하도록 설정
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
@st.cache_data(ttl=300)  # 5분 캐시
def load_cleaned_data(sheet_name):
    try:
        encoded_sheet_name = urllib.parse.quote(sheet_name)
        csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
        df = pd.read_csv(csv_url)
        
        # 1. Unnamed로 시작하는 유령 컬럼 차단 및 제거
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
        
        # 2. 빈 셀 처리 및 데이터 정제
        df = df.fillna("")
        df.columns = [col.strip() for col in df.columns]
        return df
    except Exception as e:
        st.error(f"'{sheet_name}' 데이터를 가져오는 중 에러가 발생했습니다.")
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

    # 연도 기준 컬럼 자동 탐색 (연도 혹은 개정 문구가 들어간 컬럼)
    year_col = None
    for col in df.columns:
        if "연도" in col or "개정" in col or "구분" in col:
            year_col = col
            break
    if not year_col:
        year_col = df.columns[0]

    # 데이터 정렬 및 고유 연도 목록 생성
    df[year_col] = df[year_col].astype(str)
    unique_years = sorted(list(df[year_col].unique()), reverse=True)

    # 기능 1: 상단 개정연도 클릭 필터
    selected_year = st.selectbox(f"📅 조회할 개정연도 선택 ({tab_name})", ["전체 보기"] + unique_years, key=f"select_{tab_name}")
    
    filtered_df = df.copy()
    if selected_year != "전체 보기":
        filtered_df = filtered_df[filtered_df[year_col] == selected_year]

    # 테이블 뷰 출력 (중요 열 너비 확장 설정)
    st.markdown("##### 📊 개정 이력 목록")
    st.dataframe(
        filtered_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "개정사유": st.column_config.TextColumn("개정사유", width="large"),
            "개정내용": st.column_config.TextColumn("개정내용", width="large")
        }
    )
    
    st.divider()
    
    # 기능 2 & 3: 클릭/선택 시 글자 잘림 없는 상세조회 및 PDF 전문 연동
    if not filtered_df.empty:
        st.subheader("🔍 선택 이력 상세 정보 및 전문 확인")
        
        # 사용자가 쉽게 고를 수 있도록 셀렉트박스 생성
        row_options = []
        for idx, row in filtered_df.iterrows():
            # 사용 가능한 컬럼 조합하여 힌트 문구 생성
            hint = f"[{row[year_col]}] "
            for c in filtered_df.columns:
                if c != year_col and row[c]:
                    hint += f"{str(row[c])[:25]}..."
                    break
            row_options.append((idx, hint))
            
        selected_idx = st.selectbox(
            "자세히 보고 싶은 이력 항목을 선택하세요:",
            options=[opt[0] for opt in row_options],
            format_func=lambda x: next(opt[1] for opt in row_options if opt[0] == x),
            key=f"row_box_{tab_name}"
        )
        
        chosen_row = filtered_df.loc[selected_idx]
        
        # 내용 잘림 현상 완벽 방지: 마크다운으로 전체 텍스트 바인딩
        st.info("💡 아래 영역에서는 긴 문장도 잘림 없이 전체 내용이 자동 줄바꿈되어 표시됩니다.")
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("### 📝 개정 요약 상세")
            for col in filtered_df.columns:
                st.markdown(f"**• {col}**")
                st.caption(str(chosen_row[col]))
        
        with col_right:
            # 선택된 데이터의 연도를 파악하여 PDF 매칭
            target_year_str = str(chosen_row[year_col])
            matched_year_key = None
            for y_key in FILE_MAP.keys():
                if y_key[:4] in target_year_str:
                    matched_year_key = y_key
                    break
            
            if matched_year_key:
                st.markdown(f"### 📄 {matched_year_key} 공급규정 전문")
                with st.expander(f"🔍 {FILE_MAP[matched_year_key]} 원문 텍스트 펼치기", expanded=True):
                    with st.spinner("PDF 문서 읽어오는 중..."):
                        pdf_text = extract_text_from_pdf(FILE_MAP[matched_year_key])
                        st.text_area(label="전체 파일 본문", value=pdf_text, height=450, key=f"pdf_area_{tab_name}_{selected_idx}")
            else:
                st.warning("⚠️ 선택한 내역의 연도와 일치하는 PDF 원문 파일을 구조에서 찾을 수 없습니다. (FILE_MAP 설정을 확인해 주세요)")

with tab1:
    render_tab_content(df_simple, "Simple")

with tab2:
    render_tab_content(df_detail, "상세")
