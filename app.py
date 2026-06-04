import streamlit as st
import pandas as pd
import urllib.parse

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="도시가스 공급규정 개정 이력", layout="wide")
st.title("📖 연도별 도시가스 공급규정 개정 이력")
st.markdown("구글 스프레드시트와 연동하여 연도별 개정 내용과 사유를 확인합니다.")

# --- 구글 시트 정보 ---
SHEET_ID = "1sFagZeEQlp2UMxUCCT96QPQm2bqG_YVMRXU0cgErteA"

# --- 데이터 불러오기 함수 (CSV API 활용으로 변경) ---
@st.cache_data(ttl=600)  # 10분 캐싱
def load_sheet_data(sheet_name):
    try:
        # 한글 시트 이름(예: '상세')이 주소창에서 깨지지 않도록 인코딩
        encoded_sheet_name = urllib.parse.quote(sheet_name)
        
        # 구글 시트에서 가장 에러가 적은 CSV 익스포트용 특수 주소 구성
        csv_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={encoded_sheet_name}"
        
        # pd.read_excel 대신 훨씬 안정적인 read_csv 사용
        df = pd.read_csv(csv_url)
        df = df.fillna("")  # 빈 칸 처리
        return df
    except Exception as e:
        st.error(f"'{sheet_name}' 데이터를 불러오지 못했습니다.")
        st.info("""
        💡 **연동 실패 시 체크리스트:**
        1. 회사 구글 계정인 경우, 보안 정책상 외부 서비스(Streamlit)로의 데이터 공유가 원천 차단되어 있을 수 있습니다. 이 경우 **개인 구글 계정**으로 시트를 복사한 뒤 해당 시트의 ID로 변경하시면 백발백중 해결됩니다.
        2. 구글 시트 하단의 탭 이름이 정확히 `simple`과 `상세`로 되어있는지 소문자/오타를 확인해 주세요.
        """)
        return pd.DataFrame()

# --- 화면 탭 구성 ---
tab1, tab2 = st.tabs(["📑 요약 버전 (Simple)", "📄 상세 버전 (상세)"])

with tab1:
    st.subheader("개정 내용 요약")
    df_simple = load_sheet_data("simple")
    if not df_simple.empty:
        st.dataframe(df_simple, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("개정 내용 상세")
    df_detail = load_sheet_data("상세")
    if not df_detail.empty:
        st.dataframe(df_detail, use_container_width=True, hide_index=True)
