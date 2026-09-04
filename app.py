import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go

st.set_page_config(page_title="학생수 감소 조기진단", layout="wide")

THREE = ["대전", "대구", "부산"]
SIDO_FULL = {"대전": "대전광역시", "대구": "대구광역시", "부산": "부산광역시"}
GRADE_COLORS = {1: "#7f1d1d", 2: "#dc2626", 3: "#f97316", 4: "#fbbf24", 5: "#7dd3fc"}

# 네이버 지도 기본 마커 규격(25~34px, 커스텀 최대 64px) 참고해 화면 픽셀 고정 크기로 설정.
# Scattermap의 marker.size는 화면 픽셀 단위라 확대·축소해도 이 크기 그대로 유지된다.
GRADE_SIZE = {1: 22, 2: 18, 3: 14, 4: 13, 5: 12}
GRADE_OPACITY = {1: 1.0, 2: 0.95, 3: 0.85, 4: 0.8, 5: 0.75}

# 검색 중일 때 3~5등급도 주변 맥락 파악하게 살짝 키움 (역시 픽셀 고정)
GRADE_SIZE_SEARCH = {1: 22, 2: 18, 3: 17, 4: 16, 5: 15}
GRADE_OPACITY_SEARCH = {1: 1.0, 2: 0.95, 3: 0.95, 4: 0.9, 5: 0.85}

# 검색된 학교 강조 크기 — 고정 40px (요청하신 값)
SEARCH_HIGHLIGHT_SIZE = 40

# 유형별 배지 색상
TYPE_STYLE = {
    "순전출형": {"bg": "#dbeafe", "fg": "#1e40af"},
    "인구감소형": {"bg": "#fee2e2", "fg": "#991b1b"},
    "비위험": {"bg": "#f3f4f6", "fg": "#374151"},
}


def type_badge(유형):
    style = TYPE_STYLE.get(유형, TYPE_STYLE["비위험"])
    return (
        f"<span style='background-color:{style['bg']}; color:{style['fg']}; "
        f"padding:8px 20px; border-radius:8px; font-weight:700; font-size:1.3rem;'>"
        f"{유형}</span>"
    )


@st.cache_data
def load_data():
    return pd.read_csv("school_dashboard.csv")


@st.cache_data
def load_boundary():
    sgg = gpd.read_parquet("assets/sgg.parquet").to_crs(epsg=4326)
    sgg3 = sgg[sgg["sidonm"].isin(SIDO_FULL.values())].reset_index(drop=True)
    return sgg3, sgg3.__geo_interface__


df = load_data()
sgg3, geojson = load_boundary()
df_map = df[df["시도"].isin(THREE)].dropna(subset=["위도", "경도"]).copy()

st.title("🏫 스쿨캐스터")
st.caption("학교명을 검색하거나, 지도 위 점을 클릭하면 오른쪽에 상세정보가 뜹니다.")

query = st.text_input("학교명 검색 (예: 대구명곡초)")

matched = pd.DataFrame()
center_lat, center_lon, zoom_level = 36.0, 128.3, 6.3

if query:
    matched = df_map[df_map["학교명"].str.contains(query, na=False)].reset_index(drop=True)
    if len(matched) == 0:
        st.warning("검색 결과 없음")
    else:
        center_lat = float(matched.iloc[0]["위도"])
        center_lon = float(matched.iloc[0]["경도"])
        zoom_level = 13

map_col, info_col = st.columns([7, 3])

with map_col:
    fig = go.Figure()

    fig.add_trace(go.Choroplethmap(
        geojson=geojson, locations=sgg3.index, z=[0] * len(sgg3),
        colorscale=[[0, "white"], [1, "white"]], showscale=False,
        marker=dict(opacity=0.3, line=dict(width=1, color="#9ca3af")),
    ))

    trace_refs = [None]

    is_searching = len(matched) > 0
    size_map = GRADE_SIZE_SEARCH if is_searching else GRADE_SIZE
    opacity_map = GRADE_OPACITY_SEARCH if is_searching else GRADE_OPACITY

    for g in sorted(GRADE_COLORS, reverse=True):
        color = GRADE_COLORS[g]
        sub = df_map[df_map["등급"] == g].reset_index(drop=True)
        trace_refs.append(sub)
        fig.add_trace(go.Scattermap(
            lat=sub["위도"], lon=sub["경도"], mode="markers",
            marker=dict(size=size_map[g], color=color, opacity=opacity_map[g]),
            text=sub["학교명"],
            hoverinfo="text", name=f"{g}등급",
        ))

    if len(matched) > 0:
        trace_refs.append(matched)
        fig.add_trace(go.Scattermap(
            lat=matched["위도"], lon=matched["경도"], mode="markers",
            marker=dict(size=SEARCH_HIGHLIGHT_SIZE + 6, color="#111827", opacity=1.0),  # 짙은 남색 테두리
            hoverinfo="skip", showlegend=False,
        ))
        trace_refs.append(matched)
        fig.add_trace(go.Scattermap(
            lat=matched["위도"], lon=matched["경도"], mode="markers",
            marker=dict(size=SEARCH_HIGHLIGHT_SIZE,
                        color=[GRADE_COLORS[int(g)] for g in matched["등급"]],
                        opacity=1.0),
            text=matched["학교명"] + " (검색됨)",
            hoverinfo="text", name="검색 결과",
        ))

    fig.update_layout(
        map=dict(style="carto-positron", center=dict(lat=center_lat, lon=center_lon), zoom=zoom_level),
        height=650, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
    )

    event = st.plotly_chart(
        fig, use_container_width=True, on_select="rerun",
        selection_mode="points", key="risk_map",
    )

with info_col:
    clicked_row = None
    if event and event.selection and event.selection["points"]:
        try:
            point = event.selection["points"][0]
            curve_idx = point["curve_number"]
            point_idx = point["point_index"]
            ref_df = trace_refs[curve_idx]
            if ref_df is not None and point_idx < len(ref_df):
                clicked_row = ref_df.iloc[point_idx]
        except (KeyError, IndexError):
            clicked_row = None

    display_row = clicked_row if clicked_row is not None else (matched.iloc[0] if len(matched) > 0 else None)

    if display_row is not None:
        r = display_row
        st.subheader(f"📍 {r['학교명']}")

        badge_col1, badge_col2 = st.columns(2)
        with badge_col1:
            color = "🔴" if r["등급"] <= 2 else "🟡" if r["등급"] == 3 else "🔵"
            st.metric("위험등급", f"{color} {int(r['등급'])}등급")
        with badge_col2:
            st.write("유형")
            st.markdown(type_badge(r["유형"]), unsafe_allow_html=True)

        st.markdown(f"<p style='font-size:1.5rem;'><b>위치</b>: {r['시도']} {r['행정구']}</p>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:1.5rem;'><b>학교급</b>: {r['학교급']}</p>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:1.5rem;'><b>학생수</b>: {int(r['n0'])}명</p>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size:1.5rem;'><b>예측 변화</b>: {r['y']*100:.1f}%</p>", unsafe_allow_html=True)
