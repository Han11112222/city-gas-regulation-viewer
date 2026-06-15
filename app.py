import streamlit as st
import pandas as pd
import pdfplumber
import os
import urllib.parse
import numpy as np
import time
import re  # [신규] 조항 번호(제X조) 추출을 위해 추가

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

# --- [신규] PDF 텍스트에서 특정 조항(예: 제4조)만 추출하는 함수 ---
def get_clause_text(pdf_text, clause_name):
    if not clause_name:
        return "조항 정보가 식별되지 않아 전체 본문을 하단에서 확인하세요."
        
    # '제4조' 형태에서 숫자만 추출하거나 정확한 패턴 검색
    # 예: 제4조(용어의 정의) 또는 제4조 준하는 텍스트 매칭
    pattern = rf"({clause_name}\s*\(.*?\)|{clause_name})"
    matches = list(re.finditer(pattern, pdf_text))
    
    if not matches:
        return f"💡 PDF 전문에서 '{clause_name}' 텍스트 영역을 직접 매칭하지 못했습니다. 아래의 전체 본문에서 직접 찾으실 수 있습니다."
        
    # 첫 번째 매칭된 지점부터 텍스트 추출 시작
    start_idx = matches[0].start()
    
    # 다음 조항(예: 제5조, 제15조 등 숫자가 커지는 다음 제N조) 위치 탐색을 위한 패턴
    # 현재 조항 번호에서 숫자 추출
    num_match = re.search(r'\d+', clause_name)
    if num_match:
        current_num = int(num_match.group())
        next_clause_pattern = rf"(제\s*{current_num + 1}\s*조|제\s*{current_num + 2}\s*조)"
        next_match = re.search(next_clause_pattern, pdf_text[start_idx + 10:])
        
        if next_match:
            end_idx = start_idx + 10 + next_match.start()
            return pdf_text[start_idx:end_idx].strip()
            
    # 다음 조항을 못 찾으면 해당 위치부터 약 1500자(안전하게 해당 조 내용이 다 들어갈 분량) 출력
    return pdf_text[start_idx:start_idx + 1500].strip() + "\n\n...(이하 생략 - 하단 전체 전문을 참조하세요)..."

# --- 1. Simple(요약) 탭 데이터 로드 함수 ---
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

# --- 2. 상세(신구조문) 탭 전용 데이터 로드 함수 ---
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
                
            found_year = False
            for v in vals:
                if v.isdigit() and len(v) == 4:
                    current_year = v
                    found_year = True
                    break
            if found_year: continue
                
            if '현행' in vals or '개정(안)' in vals: continue
                
            if len(vals) >= 3:
                current_text = vals[1]
                revised_text = vals[2]
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

# --- 1. 요약 버전 (Simple) 탭 렌더링 함수 (기존 로직 완전 유지) ---
def render_simple_tab(df, tab_name="Simple"):
    if df.empty:
        st.info("시트에 데이터가 없거나 로드되지 않았습니다.")
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
        
        css = "<style>\n"
        css += '[data-testid="stTable"] table { width: 100% !important; }\n'
        for i, col in enumerate(display_df.columns):
            if "내용" in col:
                css += f'[data-testid="stTable"] th:nth-child({i+2}), [data-testid="stTable"] td:nth-child({i+2}) {{ width: 50% !important; }}\n'
            elif "사유" in col:
                css += f'[data-testid="stTable"] th:nth-child({i+2}), [data-testid="stTable"] td:nth-child({i+2}) {{ width: 25% !important; }}\n'
        css += "</style>"
        st.markdown(css, unsafe_allow_html=True)
        
        st.table(display_df)
    else:
        st.write("선택한 조건의 데이터가 없습니다.")
    
    st.divider()
    
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
            st.warning(f"⚠️ 선택한 일자({target_date_str})에 매칭되는 PDF 파일을 찾을 수 없습니다.")

# --- 2. [수정 및 고도화] 상세 버전 (신구조문 대비표) 탭 렌더링 함수 ---
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
        
        # [수정] 조문별 클릭(라디오 선택)을 위한 선택 데이터 구성
        row_options = []
        for idx, row in y_df.iterrows():
            # 텍스트에서 '제X조' 추출 시도
            clause_match = re.search(r'(제\s*\d+\s*조)', row['현행'] + row['개정(안)'])
            clause_name = clause_match.group(1).replace(" ", "") if clause_match else f"항목 {idx+1}"
            row_options.append((idx, clause_name))
            
        # 형님이 직관적으로 조항을 클릭하여 원문을 대조할 수 있도록 라디오 컨트롤 배치
        selected_idx = st.radio(
            f"🔍 전문 조회를 원하시는 조항을 클릭하세요 ({y}년):",
            options=[opt[0] for opt in row_options],
            format_func=lambda x: next(opt[1] for opt in row_options if opt[0] == x),
            key=f"radio_detail_{y}",
            horizontal=True
        )
        
        # 3단 구조문 배치 출력
        for idx, row in y_df.iterrows():
            # 사용자가 상단 라디오에서 선택한 조항은 하이라이트(또는 테두리) 효과를 간접적으로 주기 위해 배경 색상을 다르게 적용
            is_selected = (idx == selected_idx)
            
            with st.container():
                if is_selected:
                    st.markdown("<div style='background-color: #f0f4f8; padding: 10px; border-radius: 5px; border-left: 5px solid #2b5c8f;'>", unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([4, 4, 3])
                with col1:
                    st.markdown("##### ⬅️ 현행")
                    st.info(row['현행'] if row['현행'] else "(내용 없음)")
                with col2:
                    st.markdown("##### ➡️ 개정(안)")
                    st.success(row['개정(안)'] if row['개정(안)'] else "(내용 없음)")
                with col3:
                    st.markdown("##### 📝 개정 사유")
                    st.warning(row['개정 사유'] if row['개정 사유'] else "(내용 없음)")
                    
                if is_selected:
                    st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        # [핵심 신규 기능] 선택된 항목의 '제X조' 명칭을 기반으로 PDF에서 해당 전문만 파싱하여 즉시 바인딩
        chosen_row = y_df.loc[selected_idx]
        chosen_clause_name = next(opt[1] for opt in row_options if opt[0] == selected_idx)
        
        matched_year_key = next((k for k in FILE_MAP.keys() if k in y), None)
        if matched_year_key:
            st.markdown(f"### 📑 [전문 매칭] {y}년 공급규정 {chosen_clause_name} 전문")
            pdf_text = extract_text_from_pdf(FILE_MAP[matched_year_key])
            
            # 조항별 매칭 텍스트 추출
            target_clause_text = get_clause_text(pdf_text, chosen_clause_name)
            
            st.text_area(
                label=f"선택한 {chosen_clause_name}의 PDF 원문 구역", 
                value=target_clause_text, 
                height=250, 
                key=f"clause_area_{y}_{selected_idx}"
            )
            
            with st.expander(f"📁 {FILE_MAP[matched_year_key]} 전체 전문 텍스트 펼치기", expanded=False):
                st.text_area(label=f"{y}년 전체 원문", value=pdf_text, height=300, key=f"pdf_area_detail_{y}")

# --- 탭 실행 ---
with tab1:
    render_simple_tab(df_simple)

with tab2:
    render_detail_tab(df_detail)
