import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.graph_objects as go

st.set_page_config(page_title="학생수 감소 조기진단", layout="wide")

THREE = ["대전", "대구", "부산"]
SIDO_FULL = {"대전": "대전광역시", "대구": "대구광역시", "부산": "부산광역시"}
GRADE_COLORS = {1: "#7f1d1d", 2: "#dc2626", 3: "#f97316", 4: "#fbbf24", 5: "#7dd3fc"}


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

st.title("🏫 학생수 감소 조기진단")
st.caption("학교명을 검색하거나, 지도 위 점을 클릭하면 오른쪽에 상세정보가 뜹니다")

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

# ── 화면을 좌(지도) : 우(카드) = 7 : 3 비율로 분할 ──
map_col, info_col = st.columns([7, 3])

with map_col:
    fig = go.Figure()

    fig.add_trace(go.Choroplethmap(
        geojson=geojson, locations=sgg3.index, z=[0] * len(sgg3),
        colorscale=[[0, "white"], [1, "white"]], showscale=False,
        marker=dict(opacity=0.3, line=dict(width=1, color="#9ca3af")),
    ))

    trace_refs = [None]

    for g, color in GRADE_COLORS.items():
        sub = df_map[df_map["등급"] == g].reset_index(drop=True)
        trace_refs.append(sub)
        fig.add_trace(go.Scattermap(
            lat=sub["위도"], lon=sub["경도"], mode="markers",
            marker=dict(size=10 if g <= 2 else 6, color=color, opacity=0.9 if g <= 2 else 0.4),
            text=sub["학교명"],
            hoverinfo="text", name=f"{g}등급",
        ))

    if len(matched) > 0:
        trace_refs.append(matched)
        fig.add_trace(go.Scattermap(
            lat=matched["위도"], lon=matched["경도"], mode="markers",
            marker=dict(size=22, color="#000000", opacity=0.9),
            text=matched["학교명"] + " (검색됨)",
            hoverinfo="text", name="검색 결과",
        ))

    fig.update_layout(
        map=dict(style="carto-positron", center=dict(lat=center_lat, lon=center_lon), zoom=zoom_level),
        height=650, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,  # 옆에 카드가 있으니 범례는 공간 절약을 위해 생략 (원하면 True로 되돌리기)
    )

    event = st.plotly_chart(
        fig, use_container_width=True, on_select="rerun",
        selection_mode="points", key="risk_map",
    )

with info_col:
    clicked_row = None
    if event and event.selection and event.selection["points"]:
        point = event.selection["points"][0]
        curve_idx = point["curve_number"]
        point_idx = point["point_index"]
        ref_df = trace_refs[curve_idx]
        if ref_df is not None and point_idx < len(ref_df):
            clicked_row = ref_df.iloc[point_idx]

    display_row = clicked_row if clicked_row is not None else (matched.iloc[0] if len(matched) > 0 else None)

    if display_row is not None:
        r = display_row
        st.subheader(f"📍 {r['학교명']}")
        color = "🔴" if r["등급"] <= 2 else "🟡" if r["등급"] == 3 else "🔵"
        st.metric("위험등급", f"{color} {int(r['등급'])}등급")
        st.write(f"**위치**: {r['시도']} {r['행정구']}")
        st.write(f"**학교급**: {r['학교급']}")
        st.write(f"**유형**: {r['유형']}")
        st.write(f"**학생수**: {int(r['n0'])}명")
        st.write(f"**예측 변화**: {r['y']*100:.1f}%")
    else:
        st.info("지도 위 점을 클릭하거나\n학교명을 검색해보세요")
        st.write(f"전체 등록 학교 수(3개 시): {len(df_map):,}개교")
