import streamlit as st
import pandas as pd
import pdfplumber
import os
import urllib.parse
import numpy as np
import time
import re

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="DSE_도시가스 공급규정 개정 이력 관리 시스템", layout="wide")
st.title("📖 DSE_도시가스 공급규정 통합 관리 시스템")
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

# --- 조항 추출 함수 (본문 추출 및 페이지 번호/빈 줄 압축) ---
def get_clause_text(pdf_text, clause_name):
    if not clause_name:
        return "조항 번호가 명확하지 않아 부분 추출이 어렵습니다. 하단에서 전체 본문을 확인해 주세요."
        
    num_match = re.search(r'\d+', clause_name)
    if not num_match:
        return f"💡 '{clause_name}'에서 조항 번호를 식별할 수 없습니다."
        
    num = num_match.group()
    pattern = rf"제\s*{num}\s*조(?!\s*의)"
    matches = list(re.finditer(pattern, pdf_text))
    
    if not matches:
        return f"💡 PDF 전문에서 '제{num}조' 텍스트 영역을 직접 매칭하지 못했습니다."
        
    start_idx = -1
    
    for i, match in enumerate(matches):
        idx = match.start()
        snippet = pdf_text[idx:min(len(pdf_text), idx + 300)]
        is_toc = False
        
        if i == 0 and len(matches) > 1 and idx < 3000:
            is_toc = True
            
        if re.search(r'(\.(?:\s*\.){3,})', snippet) or re.search(r'([·․…─\-_](?:\s*[·․…─\-_]){3,})', snippet):
            is_toc = True
            
        first_line = snippet.split('\n')[0]
        if re.search(r'\s{4,}\d+\s*$', first_line):
            is_toc = True
            
        if re.match(rf"제\s*{num}\s*조\s*별표", snippet):
            is_toc = True
            
        if is_toc:
            continue
            
        start_idx = idx
        break
        
    if start_idx == -1:
        start_idx = matches[1].start() if len(matches) > 1 else matches[0].start()
        
    current_num = int(num)
    search_area = pdf_text[start_idx + 10:]
    
    next_clause_pattern = rf"\n\s*제\s*({current_num + 1}|{current_num + 2})\s*조"
    next_clause_matches = list(re.finditer(next_clause_pattern, search_area))
    next_clause_idx = next_clause_matches[0].start() if next_clause_matches else 4000
    
    next_chapter_pattern = r"\n\s*\[?\s*제\s*\d+\s*장"
    next_chapter_matches = list(re.finditer(next_chapter_pattern, search_area))
    next_chapter_idx = next_chapter_matches[0].start() if next_chapter_matches else 4000
    
    cut_length = min(next_clause_idx, next_chapter_idx)
    end_idx = start_idx + 10 + cut_length
    
    extracted_text = pdf_text[start_idx:end_idx].strip()
    
    extracted_text = re.sub(r'-\s*\d+\s*-', '', extracted_text)
    extracted_text = re.sub(r'\n+', '\n', extracted_text).strip()
    
    return extracted_text

# --- PDF 원문용 하이라이트 함수 (상세 버전 탭에서 사용) ---
def highlight_differences(pdf_text, current_text, revised_text):
    if not pdf_text: return pdf_text

    curr_str = str(current_text)
    rev_str = str(revised_text)

    parts = re.split(r'(\(신설\)|\(변경\)|\(삭제\))', rev_str)

    targets = []
    c_clean_for_match = re.sub(r'\s+', '', curr_str)

    current_text_buffer = ""
    for part in parts:
        if part in ['(신설)', '(변경)', '(삭제)']:
            tag = part
            text = current_text_buffer
            current_text_buffer = "" 
            
            p_clean = re.sub(r'([①-⑳\d]+\s*~\s*[①-⑳\d]+\s*)?\(?생략\)?', '', text)
            p_clean = re.sub(r'제\s*\d+\s*조\s*\([^)]*\)', '', p_clean)
            p_clean = re.sub(r'^[)\],.\s]+', '', p_clean).strip()
            
            if len(p_clean) >= 2:
                p_clean_no_space = re.sub(r'\s+', '', p_clean)
                if p_clean_no_space not in c_clean_for_match:
                    p_clean_no_space = re.sub(r'[\'\"收藏“”‘’]', '', p_clean_no_space)
                    if len(p_clean_no_space) > 2:
                        targets.append((p_clean_no_space, tag))
        else:
            current_text_buffer += part

    if current_text_buffer:
        text = current_text_buffer
        p_clean = re.sub(r'([①-⑳\d]+\s*~\s*[①-⑳\d]+\s*)?\(?생략\)?', '', text)
        p_clean = re.sub(r'제\s*\d+\s*조\s*\([^)]*\)', '', p_clean)
        p_clean = re.sub(r'^[)\],.\s]+', '', p_clean).strip()
        
        if len(p_clean) >= 2:
            p_clean_no_space = re.sub(r'\s+', '', p_clean)
            if p_clean_no_space not in c_clean_for_match:
                p_clean_no_space = re.sub(r'[\'\"收藏“”‘’]', '', p_clean_no_space)
                if len(p_clean_no_space) > 2:
                    targets.append((p_clean_no_space, ""))

    if not targets:
        return pdf_text

    stripped_pdf = ""
    mapping = []
    for i, char in enumerate(pdf_text):
        if not char.isspace() and char not in ['\'', '"', '“', '”', '‘', '’']:
            stripped_pdf += char
            mapping.append(i)

    spans_to_highlight = []
    for t_text, tag in targets:
        start_pos = 0
        while True:
            idx = stripped_pdf.find(t_text, start_pos)
            if idx == -1: break
            orig_start = mapping[idx]
            orig_end = mapping[idx + len(t_text) - 1]
            spans_to_highlight.append((orig_start, orig_end, tag))
            start_pos = idx + len(t_text)

    if not spans_to_highlight:
        return pdf_text

    spans_to_highlight.sort(key=lambda x: x[0])
    merged_spans = []
    for s in spans_to_highlight:
        if not merged_spans:
            merged_spans.append(s)
        else:
            last = merged_spans[-1]
            if s[0] <= last[1] + 1:
                merged_spans[-1] = (last[0], max(last[1], s[1]), last[2] or s[2])
            else:
                merged_spans.append(s)

    highlighted_text = pdf_text
    for start, end, tag in reversed(merged_spans):
        part1 = highlighted_text[:start]
        part2 = highlighted_text[start:end+1]
        part3 = highlighted_text[end+1:]
        
        tag_html = f' <span style="color: #d32f2f; font-weight: bold;">{tag}</span>' if tag else ''
        highlighted_text = part1 + f'<span style="color: #d32f2f; font-weight: bold; background-color: #ffebee;">{part2}</span>{tag_html}' + part3

    return highlighted_text

# --- UI 텍스트간 실시간 비교용 하이라이트 함수 (2026년 list 탭에서 사용) ---
def highlight_ui_differences(current_text, revised_text):
    if not revised_text: return revised_text

    curr_str = str(current_text)
    rev_str = str(revised_text)

    split_pattern = r'생략|\(신설\)|\(변경\)|\(삭제\)|\n'
    rev_parts = re.split(split_pattern, rev_str)

    targets = []
    c_clean_for_match = re.sub(r'\s+', '', curr_str)

    for part in rev_parts:
        p_clean = re.sub(r'[①-⑳\d]+\s*~\s*[①-⑳\d]+', '', part)
        p_clean = re.sub(r'제\s*\d+\s*조\s*\([^)]*\)', '', p_clean)
        p_clean = re.sub(r'^[)\],.\s]+', '', p_clean).strip()

        if len(p_clean) < 2: continue

        p_clean_no_space = re.sub(r'\s+', '', p_clean)
        if p_clean_no_space in c_clean_for_match: continue

        p_clean_no_space = re.sub(r'[\'\"“”‘’]', '', p_clean_no_space)
        if len(p_clean_no_space) > 2:
            targets.append(p_clean_no_space)

    if not targets:
        return rev_str

    stripped_rev = ""
    mapping = []
    for i, char in enumerate(rev_str):
        if not char.isspace() and char not in ['\'', '"', '“', '”', '‘', '’']:
            stripped_rev += char
            mapping.append(i)

    spans_to_highlight = []
    for t in targets:
        start_pos = 0
        while True:
            idx = stripped_rev.find(t, start_pos)
            if idx == -1: break
            orig_start = mapping[idx]
            orig_end = mapping[idx + len(t) - 1]
            spans_to_highlight.append((orig_start, orig_end))
            start_pos = idx + len(t)

    if not spans_to_highlight:
        return rev_str

    spans_to_highlight.sort(key=lambda x: x[0])
    merged_spans = []
    for s in spans_to_highlight:
        if not merged_spans:
            merged_spans.append(s)
        else:
            last = merged_spans[-1]
            if s[0] <= last[1] + 1:
                merged_spans[-1] = (last[0], max(last[1], s[1]))
            else:
                merged_spans.append(s)

    highlighted_text = rev_str
    for start, end in reversed(merged_spans):
        part1 = highlighted_text[:start]
        part2 = highlighted_text[start:end+1]
        part3 = highlighted_text[end+1:]
        highlighted_text = part1 + f'<span style="color: #d32f2f; font-weight: bold; background-color: #ffebee;">{part2}</span>' + part3

    return highlighted_text

# --- UI 텍스트 자동 줄바꿈 포맷팅 ---
def format_ui_text(text):
    if not text: return ""
    t = str(text)
    t = re.sub(r'(?<!\n)(?<!~)(?<!-)\s+([①-⑳])', r'\n\n\1', t)
    t = re.sub(r'(?<!\n)\s+(\d{1,2}\.\s*[“"”\'A-Za-z가-힣])', r'\n\n\1', t)
    t = re.sub(r'\n+', r'\n\n', t)
    return t.strip()

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
        
        df_ret = pd.DataFrame(records)
        if not df_ret.empty:
            df_ret = df_ret.drop_duplicates().reset_index(drop=True)
        return df_ret
    except Exception as e:
        st.error(f"상세 데이터를 가져오는 중 에러가 발생했습니다: {e}")
        return pd.DataFrame()

# --- 3. 2026년 list(pending issue) 탭 전용 데이터 로드 ---
@st.cache_data(ttl=10)
def load_pending_data_by_gid(gid):
    try:
        cache_buster = int(time.time())
        csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}&cb={cache_buster}"
        df_raw = pd.read_csv(csv_url, dtype=str, header=None)
        
        records = []
        curr_idx, rev_idx, reason_idx = 1, 2, 3
        start_parsing = False
        
        for index, row in df_raw.iterrows():
            vals = [str(x).strip() if str(x).strip() != 'nan' else '' for x in row.tolist()]
            if all(v == '' for v in vals): continue
            
            if '현행' in vals and ('개정(안)' in vals or '개정 (안)' in vals):
                curr_idx = vals.index('현행')
                rev_idx = vals.index('개정(안)') if '개정(안)' in vals else vals.index('개정 (안)')
                reason_idx = vals.index('개정 사유') if '개정 사유' in vals else (rev_idx + 1)
                start_parsing = True
                continue
                
            if start_parsing:
                curr_text = vals[curr_idx] if len(vals) > curr_idx else ''
                rev_text = vals[rev_idx] if len(vals) > rev_idx else ''
                reason_text = vals[reason_idx] if len(vals) > reason_idx else ''
                
                if curr_text or rev_text or reason_text:
                    records.append({
                        '현행': curr_text,
                        '개정(안)': rev_text,
                        '개정 사유': reason_text
                    })
                    
        df_ret = pd.DataFrame(records)
        if not df_ret.empty:
            df_ret = df_ret.drop_duplicates().reset_index(drop=True)
        return df_ret
    except Exception as e:
        st.error(f"2026년 대기 항목 로드 중 에러가 발생했습니다: {e}")
        return pd.DataFrame()

# --- 데이터 가져오기 ---
df_simple = load_simple_data("simple")
df_detail = load_detail_data_by_gid("1205780686")
df_pending = load_pending_data_by_gid("1846159023")  

# --- 화면 탭 구성 ---
tab1, tab2, tab3 = st.tabs(["📑 요약 버전 (Simple)", "📄 상세 버전 (신구조문 대비표)", "📝 2026년 list(pending issue)"])

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

# --- 2. [디자인 통합] 상세 버전 탭 렌더링 ---
def render_detail_tab(df):
    if df.empty:
        st.info("상세 탭 데이터가 없습니다.")
        return
        
    unique_years = sorted([y for y in df['연도'].unique() if y != "알 수 없음"], reverse=True)
    selected_year = st.selectbox("📅 신구조문을 비교할 연도 선택", ["전체 보기"] + unique_years, key="select_detail_year")
    
    years_to_show = unique_years if selected_year == "전체 보기" else [selected_year]
    
    for y in years_to_show:
        st.markdown(f"### ⚖️ {y}년 신구조문 대비표")
        
        y_df = df[df['연도'] == y].drop_duplicates().reset_index(drop=True)
        
        matched_year_key = next((k for k in FILE_MAP.keys() if k in y), None)
        pdf_text = ""
        if matched_year_key:
            pdf_text = extract_text_from_pdf(FILE_MAP[matched_year_key])
        
        for idx, row in y_df.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([4, 4, 3])
                with col1:
                    st.markdown("##### ⬅️ 현행")
                    # 3번째 탭과 완전히 일치하는 청색 커스텀 HTML 컨테이너 적용
                    st.markdown(f"""
                        <div style="background-color: #f0f6fc; border-left: 5px solid #1f6feb; padding: 12px; border-radius: 6px; white-space: pre-wrap; font-family: inherit; font-size: 14px; line-height: 1.6;">{format_ui_text(row['현행']) if row['현행'] else '(내용 없음)'}</div>
                    """, unsafe_allow_html=True)
                with col2:
                    st.markdown("##### ➡️ 개정(안)")
                    # 3번째 탭과 완전히 일치하는 녹색 커스텀 HTML 컨테이너 적용
                    st.markdown(f"""
                        <div style="background-color: #dafbe1; border-left: 5px solid #2ea44f; padding: 12px; border-radius: 6px; white-space: pre-wrap; font-family: inherit; font-size: 14px; line-height: 1.6;">{format_ui_text(row['개정(안)']) if row['개정(안)'] else '(내용 없음)'}</div>
                    """, unsafe_allow_html=True)
                with col3:
                    st.markdown("##### 📝 개정 사유")
                    # 3번째 탭과 완전히 일치하는 황색 커스텀 HTML 컨테이너 적용
                    st.markdown(f"""
                        <div style="background-color: #fff8c5; border-left: 5px solid #9e6a03; padding: 12px; border-radius: 6px; white-space: pre-wrap; font-family: inherit; font-size: 14px; line-height: 1.6;">{format_ui_text(row['개정 사유']) if row['개정 사유'] else '(내용 없음)'}</div>
                    """, unsafe_allow_html=True)
            
            clause_match = re.search(r'(제\s*\d+\s*조)', str(row['현행']) + str(row['개정(안)']))
            clause_name = clause_match.group(1).replace(" ", "") if clause_match else ""
            
            expander_title = f"🔍 {clause_name} 원문 대조하기" if clause_name else "🔍 관련 원문 대조하기"
            with st.expander(expander_title):
                if matched_year_key and pdf_text:
                    target_clause_text = get_clause_text(pdf_text, clause_name)
                    highlighted_clause_text = highlight_differences(target_clause_text, row['현행'], row['개정(안)'])
                    
                    st.markdown(f"**PDF 원문 발췌**")
                    st.markdown(
                        f"""
                        <div style="
                            height: 250px; 
                            overflow-y: auto; 
                            border: 1px solid #d0d7de; 
                            padding: 15px; 
                            border-radius: 6px; 
                            background-color: #f6f8fa; 
                            white-space: pre-wrap; 
                            font-family: inherit;
                            font-size: 14px;
                            line-height: 1.6;
                        ">
                            {highlighted_clause_text}
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                else:
                    st.warning("해당 연도의 PDF 문서가 연결되지 않았습니다.")
            
            st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

# --- 3. 2026년 list(pending issue) 탭 렌더링 ---
def render_pending_tab(df):
    st.markdown("### 📝 2026년 개정 대기 항목 (Pending Issues)")
    st.caption("마케팅본부 팀에서 수합 중인 내년도 개정 검토안 목록입니다.")
    
    if df.empty:
        st.info("현재 수합된 2026년 개정 대기 항목이 없거나 데이터를 불러오지 못했습니다.")
        return
        
    for idx, row in df.iterrows():
        with st.container():
            col1, col2, col3 = st.columns([4, 4, 3])
            
            with col1:
                st.markdown("##### ⬅️ 현행")
                st.markdown(f"""
                    <div style="background-color: #f0f6fc; border-left: 5px solid #1f6feb; padding: 12px; border-radius: 6px; white-space: pre-wrap; font-family: inherit; font-size: 14px; line-height: 1.6;">{row['현행'] if row['현행'] else '(내용 없음)'}</div>
                """, unsafe_allow_html=True)
                
            with col2:
                st.markdown("##### ➡️ 개정(안) 후보")
                highlighted_rev = highlight_ui_differences(row['현행'], row['개정(안)'])
                st.markdown(f"""
                    <div style="background-color: #dafbe1; border-left: 5px solid #2ea44f; padding: 12px; border-radius: 6px; white-space: pre-wrap; font-family: inherit; font-size: 14px; line-height: 1.6;">{highlighted_rev if highlighted_rev else '(내용 없음)'}</div>
                """, unsafe_allow_html=True)
                
            with col3:
                st.markdown("##### 📝 검토 및 개정 사유")
                st.markdown(f"""
                    <div style="background-color: #fff8c5; border-left: 5px solid #9e6a03; padding: 12px; border-radius: 6px; white-space: pre-wrap; font-family: inherit; font-size: 14px; line-height: 1.6;">{row['개정 사유'] if row['개정 사유'] else '(내용 없음)'}</div>
                """, unsafe_allow_html=True)
                
        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

# --- 탭 실행 ---
with tab1:
    render_simple_tab(df_simple)

with tab2:
    render_detail_tab(df_detail)

with tab3:
    render_pending_tab(df_pending)
