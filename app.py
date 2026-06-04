import streamlit as st
import pandas as pd

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="도시가스 공급규정 개정 이력", layout="wide")
st.title("📖 연도별 도시가스 공급규정 개정 이력")
st.markdown("구글 스프레드시트와 연동하여 연도별 개정 내용과 사유를 확인합니다.")

# --- 구글 시트 정보 ---
# Han형님이 주신 구글 시트 URL에서 ID 부분만 추출
SHEET_ID = "1sFagZeEQlp2UMxUCCT96QPQm2bqG_YVMRXU0cgErteA"
EXCEL_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"

# --- 데이터 불러오기 함수 (캐싱 적용) ---
@st.cache_data(ttl=600)  # 10분마다 데이터를 새로고침 (시트 내용이 바뀌면 10분 뒤 반영)
def load_sheet_data(sheet_name):
    try:
        # pandas를 이용해 지정된 시트 이름의 데이터를 읽어옴
        df = pd.read_excel(EXCEL_URL, sheet_name=sheet_name)
        df = df.fillna("")  # 데이터가 없는 빈 칸을 깔끔하게 처리
        return df
    except Exception as e:
        st.error(f"'{sheet_name}' 시트 데이터를 불러오지 못했습니다. 구글 시트의 공유 설정이 '링크가 있는 모든 사용자'인지 확인해주세요.")
        return pd.DataFrame()

# --- 화면 탭 구성 ---
tab1, tab2 = st.tabs(["📑 요약 버전 (Simple)", "📄 상세 버전 (상세)"])

with tab1:
    st.subheader("개정 내용 요약")
    df_simple = load_sheet_data("simple")  # 'simple' 탭 데이터 로드
    if not df_simple.empty:
        st.dataframe(df_simple, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("개정 내용 상세")
    df_detail = load_sheet_data("상세")  # '상세' 탭 데이터 로드
    if not df_detail.empty:
        st.dataframe(df_detail, use_container_width=True, hide_index=True)
