import streamlit as st
import pandas as pd
import pdfplumber
import os
import urllib.parse
import numpy as np
import time
import re

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

# --- [수정 및 고도화] 조항(예: 제4조) 추출 함수 (줄바꿈/변칙 목차 완벽 차단) ---
def get_clause_text(pdf_text, clause_name):
    if not clause_name:
        return "조항 번호가 명확하지 않아 부분 추출이 어렵습니다. 하단에서 전체 본문을 확인해 주세요."
        
    # '제4조'에서 숫자만 분리 추출 (예: '4')
    num_match = re.search(r'\d+', clause_name)
    if not num_match:
        return f"💡 '{clause_name}'에서 조항 번호를 식별할 수 없습니다."
        
    num = num_match.group()
    # PDF 본문 특성상 '제 4 조'처럼 사이에 공백이 있을 수 있으므로 공백 유연성(\s*) 부여
    pattern = rf"제\s*{num}\s*조"
    matches = list(re.finditer(pattern, pdf_text))
    
    if not matches:
        return f"💡 PDF 전문에서 '제{num}조' 텍스트 영역을 직접 매칭하지 못했습니다."
        
    start_idx = -1
    
    for match in matches:
        idx = match.start()
        
        # 매칭 지점부터 넉넉하게 뒤로 200글자 범위를 확보하여 컨텍스트 검사
        snippet = pdf_text[idx:min(len(pdf_text), idx + 200)]
        
        # [핵심 보완] 줄바꿈(\n)이 채 채워지기 전에 점(.), 가운뎃점(·), 대시(-) 등이 3개 이상 연속되거나
        # '제4조 ... 2' 와 같이 숫자가 바로 이어지는 목차 특유의 패턴이 감지되면 목차로 보고 패스
        if re.search(r'[\.·․…─\-_]{3,}', snippet) or re.search(rf"제\s*{num}\s*조[\s\n]*\.+", snippet):
            continue
            
        # 문서의 완전 앞부분(4000자 미만)에 위치하면서 뒤에 매칭이 더 남아있다면 높은 확률로 목차 페이지이므로 패스
        if idx < 4000 and len(matches) > 1:
            continue
            
        start_idx = idx
        break
        
    # 만약 정밀 필터링으로 인해 모두 목차로 분류되어 걸러졌다면, 안전장치로 가장 마지막 매칭 지점(진짜 본문)을 강제 지정
    if start_idx == -1:
        start_idx = matches[-1].start()
        
    # 다음 조항(제5조 또는 제6조)의 시작 부분을 찾아 거기까지만 깔끔하게 슬라이싱
    current_num = int(num)
    next_clause_pattern = rf"\n\s*제\s*({current_num + 1}|{current_num + 2})\s*조"
    next_match = re.search(next_clause_pattern, pdf_text[start_idx + 10:])
    
    if next_match:
        end_idx = start_idx + 10 + next_match.start()
        return pdf_text[start_idx:end_idx].strip()
        
    # 다음 조항을 찾지 못한 예외의 경우 넉넉하게 2500자 추출 후 생략 처리
    return pdf_text[start_idx:start_idx + 2500].strip() + "\n\n...(이하 생략 - 전체 본문 참조)..."

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

# --- 2. 상세(신구조문) 탭 데이터 로드 ---
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

# --- 1. 요약 버전 (Simple) 탭 렌더링 ---
def render_simple_tab(df, tab_name="Simple"):
    if df.empty:
        st.info("시트에 데이터가 없거나 로드되지 않았습니다.")
        return

    date_col = df.columns[0] 
    df[date_col] = df[date_col].astype(str).str.strip()
    
    df['_year'] = df[date_col].str.extract(r'^(\d{4})').astype(float)
    df = df[df['_year'] >= 2016].copy()
    
    df['_date_sort'] = pd.to_datetime(df[date_col].str.replace(r'\.$', '', regex=True), format='mixed', errors='coerce')
    df = df.sort_values(by=['_date_sort', date_col], ascending=[False, False]).reset_index(drop=True)
    df = df.drop(columns=['_year', '_date_sort'])
    
    st.markdown(f"### 🔍 항목별 상세 내용 및 원문 대조")
    
    row_options = []
    for idx, row in df.iterrows():
        hint = f"[{row[date_col]}] "
        valid_cols_for_hint = [c for c in df.columns if not c.startswith("공란_")]
        second_col = valid_cols_for_hint[1] if len(valid_cols_for_hint) > 1 else date_col
        hint += f"{str(row[second_col])[:45]}..."
        row_options.append((idx, hint))
        
    selected_idx = st.selectbox(
        "자세히 볼 항목을 선택하세요:",
        options=[opt[0] for opt in row_options],
        format_func=lambda x: next(opt[1] for opt in row_options if opt[0] == x),
        key=f"row_box_{tab_name}"
    )
    
    chosen_row = df.loc[selected_idx]
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
    matched_year_key = next((k for k in FILE_MAP.keys() if k in target_date_str), None)
    
    if matched_year_key:
        st.markdown(f"### 📄 {matched_year_key}년 공급규정 전문")
        with st.expander(f"🔍 {FILE_MAP[matched_year_key]} 원문 텍스트 펼치기", expanded=False):
            with st.spinner("PDF 문서 읽어오는 중..."):
                pdf_text = extract_text_from_pdf(FILE_MAP[matched_year_key])
                st.text_area(label="전체 파일 본문", value=pdf_text, height=450, key=f"pdf_area_{tab_name}_{selected_idx}")

# --- 2. 상세 버전 탭 렌더링 ---
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
        
        matched_year_key = next((k for k in FILE_MAP.keys() if k in y), None)
        pdf_text = ""
        if matched_year_key:
            pdf_text = extract_text_from_pdf(FILE_MAP[matched_year_key])
        
        for idx, row in y_df.iterrows():
            with st.container():
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
            
            clause_match = re.search(r'(제\s*\d+\s*조)', str(row['현행']) + str(row['개정(안)']))
            clause_name = clause_match.group(1).replace(" ", "") if clause_match else ""
            
            expander_title = f"🔍 {clause_name} 원문 대조하기" if clause_name else "🔍 관련 원문 대조하기"
            with st.expander(expander_title):
                if matched_year_key and pdf_text:
                    # 줄바꿈 무시 목차 패스 알고리즘 적용
                    target_clause_text = get_clause_text(pdf_text, clause_name)
                    st.text_area(
                        label="PDF 원문 발췌", 
                        value=target_clause_text, 
                        height=200, 
                        key=f"text_area_detail_{y}_{idx}"
                    )
                else:
                    st.warning("해당 연도의 PDF 문서가 연결되지 않았습니다.")
            
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

# --- 탭 실행 ---
with tab1:
    render_simple_tab(df_simple)

with tab2:
    render_detail_tab(df_detail)
