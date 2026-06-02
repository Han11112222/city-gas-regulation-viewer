import streamlit as st
import pdfplumber
import difflib
import os

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="도시가스 공급규정 비교", layout="wide")
st.title("📖 도시가스 공급규정 개정 이력 비교")
st.markdown("연도별 공급규정 PDF 파일을 비교하여 변경된 내용을 확인합니다.")

# --- 데이터 폴더 및 파일 설정 ---
DATA_DIR = "data"
# 실제 올려주신 파일명에 맞게 매핑
FILE_MAP = {
    "2023년": "1. 2023년_도시가스 공급규정 변경..pdf",
    "2024년": "1. 2024년_도시가스 공급규정 변경..pdf",
    "2025년": "1. 2025년_도시가스 공급규정 변경..pdf"
}

# --- PDF 텍스트 추출 함수 ---
@st.cache_data
def extract_text_from_pdf(file_path):
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        return f"PDF 읽기 오류 발생: {e}"
    return text

# --- UI 레이아웃 ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("개정 전 (기준)")
    year1 = st.selectbox("기준 연도 선택", ["2023년", "2024년", "2025년"], index=0)
    
with col2:
    st.subheader("개정 후 (비교 대상)")
    year2 = st.selectbox("비교 연도 선택", ["2023년", "2024년", "2025년"], index=1)

st.divider()

# --- 비교 로직 실행 ---
if year1 == year2:
    st.warning("서로 다른 연도를 선택해 주세요.")
else:
    with st.spinner('PDF 텍스트를 추출하고 비교하는 중입니다...'):
        # 파일 경로 생성
        path1 = os.path.join(DATA_DIR, FILE_MAP[year1])
        path2 = os.path.join(DATA_DIR, FILE_MAP[year2])
        
        # 텍스트 추출
        text1 = extract_text_from_pdf(path1)
        text2 = extract_text_from_pdf(path2)
        
        # 줄 단위로 나누기
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        
        st.subheader(f"📝 {year1} vs {year2} 변경 내역")
        st.markdown("🟢 **추가된 내용(초록색)** / 🔴 **삭제된 내용(빨간색)**")
        
        # difflib을 이용한 텍스트 비교
        diff = difflib.ndiff(lines1, lines2)
        
        diff_html = "<div style='font-family: monospace; line-height: 1.6; font-size: 14px;'>"
        for line in diff:
            if line.startswith('+ '): # 추가된 부분
                clean_text = line[2:].replace('<', '&lt;').replace('>', '&gt;')
                diff_html += f"<div style='color: #155724; background-color: #d4edda; padding: 2px 4px; margin: 2px 0;'>+ {clean_text}</div>"
            elif line.startswith('- '): # 삭제된 부분
                clean_text = line[2:].replace('<', '&lt;').replace('>', '&gt;')
                diff_html += f"<div style='color: #721c24; background-color: #f8d7da; text-decoration: line-through; padding: 2px 4px; margin: 2px 0;'>- {clean_text}</div>"
            elif line.startswith('? '): # 변경점 상세 표시 (생략 가능)
                pass
            # 변경 없는 부분은 너무 길어지므로 생략하거나 필요시 아래 코드 활성화
            # else:
            #     diff_html += f"<div style='color: #495057; padding: 2px 4px;'>  {line[2:]}</div>"
        
        diff_html += "</div>"
        
        # HTML 렌더링
        st.markdown(diff_html, unsafe_allow_html=True)
