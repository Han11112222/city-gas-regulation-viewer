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
        csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
        df = pd.read_csv(csv_url)
        
        # 1. Unnamed 유령 컬럼 완벽 제거
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
        
        # 2. 모든 데이터가 비어있는 빈 행(Row) 삭제
        df = df.dropna(how='all')
        
        # 3. 빈 셀 처리 및 공백 정제
        df = df.fillna("")
        df.columns = [str(col).strip() for col in df.columns]
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

    # [수정] '일자', '연도', '날짜' 등 가장 첫 번째 열을 기준(필터)으로 고정
    # 스프레드시트의 A열이 '일자'라고 가정하고 필터 기준으로 삼습니다.
    date_col = df.columns[0] 
    for col in df.columns:
        if any(keyword in col for keyword in ["일자", "연도", "년도", "날짜"]):
            date_col = col
            break

    # 필터용 날짜/일자 목록 생성 (빈 값 제외)
    df[date_col] = df[date_col].astype(str).str.strip()
    unique_dates = sorted([d for d in df[date_col].unique() if d], reverse=True)

    # 드롭다운 필터
    selected_date = st.selectbox(
        f"📅 조회할 {date_col} 선택 ({tab_name})", 
        ["전체 보기"] + unique_dates, 
        key=f"select_{tab_name}"
    )
    
    filtered_df = df.copy()
    if selected_date != "전체 보기":
        filtered_df = filtered_df[filtered_df[date_col] == selected_date]

    # [수정] 스프레드시트 모양 그대로 출력
    st.markdown(f"##### 📊 개정 이력 목록 (원본 형태)")
    if not filtered_df.empty:
        # st.table을 사용하여 원본 컬럼 순서대로 가로형 표 출력
        st.table(filtered_df)
    else:
        st.write("선택한 조건의 데이터가 없습니다.")
    
    st.divider()
    
    # 하단부 클릭 시 상세 내역 및 PDF 연동 뷰어
    if not filtered_df.empty:
        st.subheader("🔍 이력 원문 대조 확인")
        
        row_options = []
        for idx, row in filtered_df.iterrows():
            hint = f"[{row[date_col]}] "
            # '개정내용'이나 2번째 컬럼의 텍스트를 일부 보여줌
            second_col = df.columns[1] if len(df.columns) > 1 else date_col
            hint += f"{str(row[second_col])[:30]}..."
            row_options.append((idx, hint))
            
        selected_idx = st.selectbox(
            "자세히 보고 원문을 대조할 항목을 선택하세요:",
            options=[opt[0] for opt in row_options],
            format_func=lambda x: next(opt[1] for opt in row_options if opt[0] == x),
            key=f"row_box_{tab_name}"
        )
        
        chosen_row = filtered_df.loc[selected_idx]
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("### 📝 항목별 상세 내용")
            # 시트의 모든 열(일자, 내용, 사유 등)을 순서대로 출력
            for col in filtered_df.columns:
                st.markdown(f"**• {col}**")
                st.write(str(chosen_row[col]))
        
        with col_right:
            # 일자(예: 2024.07.01)에서 연도 4자리만 추출하여 PDF 파일 매칭
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
                st.warning("⚠️ 선택한 일자의 연도와 일치하는 PDF 원문 파일을 찾을 수 없습니다.")

with tab1:
    render_tab_content(df_simple, "Simple")

with tab2:
    render_tab_content(df_detail, "상세")
