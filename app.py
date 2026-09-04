import streamlit as st
import pandas as pd

st.set_page_config(page_title="학생수 감소 조기진단", layout="centered")

@st.cache_data
def load_data():
    return pd.read_csv("school_dashboard.csv")   # 경로만 수정됨

df = load_data()

st.title("🏫 학생수 감소 조기진단")
st.caption("학교명을 검색하면 위험등급·유형·다음해 예측을 보여줍니다")

query = st.text_input("학교명 검색 (예: 대구명곡초)")

if query:
    result = df[df["학교명"].str.contains(query, na=False)]
    if len(result) == 0:
        st.warning("검색 결과 없음")
    else:
        for _, row in result.head(5).iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.subheader(row["학교명"])
                    st.write(f"{row['시도']} {row['행정구']} · {row['학교급']}")
                    st.write(f"학생수: {int(row['n0'])}명 → 예측 변화 {row['y']*100:.1f}%")
                with col2:
                    color = "🔴" if row["등급"] <= 2 else "🟡" if row["등급"] == 3 else "🔵"
                    st.metric("위험등급", f"{color} {int(row['등급'])}등급")
                    st.write(f"유형: **{row['유형']}**")

                st.map(pd.DataFrame({"lat": [row["위도"]], "lon": [row["경도"]]}), zoom=12)
else:
    st.info("👆 학교명을 입력해보세요")
    st.write(f"전체 등록 학교 수: {len(df):,}개교")
