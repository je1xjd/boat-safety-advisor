"""
boat_web.py

Streamlitを用いたWeb版の出港判定アプリケーション。
"""
import sys
import os
import datetime
import pandas as pd
import streamlit as st
from dataclasses import asdict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.analysis import BoatDataService
from engine import AnalysisResult, AnalysisSummary, SafetyRule, BoatSafetyEngine, NavigationAnalyzer, StatusFormatter
from engine.formatter import (
    SafetyReportFormatter,
    StatusUIConfig,
    ReportFormatter,
    TideFormatter
)
from engine.utils import summarize_daytime_weather, SunCalculator

st.set_page_config(
    page_title="相模川河口 海況安全判定",
    page_icon="🚤",
    layout="wide"
)

@st.cache_data(ttl=600)
def load_all_data(target_date):
    """分析結果データを取得する。"""
    return BoatDataService.get_full_analysis(target_date)

def render_summary_card(
    result_text, result_color, weather_text, temp_max, temp_min,
    max_window, before_str, after_str, tide_text, umi_info
):
    """判定結果を視覚的に表示する。"""
    st.markdown(
        f"""
        <div style="text-align:center; font-size:56px; font-weight:bold; color:{result_color}; padding:10px;">
        {result_text}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div style="text-align:center; font-size:22px; color:#0b4f84; font-weight:bold;">
        {weather_text} | 
        【<span style="color: #e74c3c;">{temp_max:.0f}℃</span> / 
        <span style="color: #3498db;">{temp_min:.0f}℃</span>】
        </div>
        """,
        unsafe_allow_html=True
    )

    if int(max_window[2]) > 0:
        st.markdown(
            f"""
            <div style="text-align:center; font-size:18px; color:#2e8b57; font-weight:bold; margin-bottom:10px;">
            最大連続活動枠: {int(max_window[0]):02d}-{int(max_window[1]):02d}時 ({int(max_window[2])}h)
            <br>前半 {before_str} / 後半 {after_str}
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.error(f"連続して安全な時間帯が {SafetyRule.REQUIRED_SAFE_HOURS} 時間以上確保できません。")

    tide_html = BoatSafetyEngine.get_ui_tide_text(umi_info)
    st.markdown(
        f"""
        <div style="background:#e9ecef; border:1px solid #808080; padding:10px; text-align:center; font-size:15px; font-weight:bold; color:#333; margin-top:8px; border-radius:2px;">
            {tide_text}
        </div>
        """,
        unsafe_allow_html=True
    )

def highlight_status(row):
    """判定ステータスに応じた行の背景色を返す。"""
    status = row["判定"]
    bg_color = StatusFormatter.get_status_color(status)
    return [f'background-color: {bg_color}'] * len(row)

st.title("🚤 ボート出港判定")
st.caption("相模川河口の潮位・潮汐・風速・風向・波高・うねりを総合評価")

JST = datetime.timezone(datetime.timedelta(hours=9), 'JST')
today_jst = datetime.datetime.now(JST).date()

date_options = [today_jst + datetime.timedelta(days=i) for i in range(8)]
weekdays = ["月", "火", "水", "木", "金", "土", "日"]

target_date = st.selectbox(
    "判定日",
    date_options,
    format_func=lambda d: f"{d.strftime('%Y-%m-%d')}({weekdays[d.weekday()]})"
)

run = st.button("🔍 海況判定を実行", width="stretch")
if not run:
    st.stop()

with st.spinner("海況データ取得中..."):
    result = load_all_data(target_date)

if result is None or result.weather_info is None:
    st.error("気象データ取得失敗")
    st.stop()

weather_info = result.weather_info
umi_info = result.umi_info
hour_data = result.hour_data
summary = result.summary

daytime_summary = summarize_daytime_weather(
    weather_info.weather_code, 
    weather_info.precipitation_probability
)

sunrise_hour, sunset_hour = SunCalculator.get_sun_times(umi_info)

ui_data = SafetyReportFormatter.get_ui_summary_data(summary)
tide_text = TideFormatter.get_ui_tide_text(result.umi_info)

render_summary_card(
    result_text=ui_data["label"],
    result_color=ui_data["color"],
    weather_text=daytime_summary,
    temp_max=result.weather_info.temp_max,
    temp_min=result.weather_info.temp_min,
    max_window=summary.best_window,
    before_str=summary.before_str,
    after_str=summary.after_str,
    tide_text=tide_text,
    umi_info=result.umi_info
)

table_rows = SafetyReportFormatter.build_table_rows(hour_data, sunrise_hour, sunset_hour)
display_rows = ReportFormatter.build_display_rows(table_rows)
df = pd.DataFrame([asdict(row) for row in display_rows])
df = df.rename(columns={
    "time_range": "時間", "status": "判定", "direction": "風向",
    "wind": "風速", "wave": "波浪", "tide": "潮位"
})
df = df[["時間", "判定", "風向", "風速", "波浪", "潮位"]]

styled_df = df.style.apply(highlight_status, axis=1)

with st.expander("時間別詳細データ", expanded=False):
    st.table(styled_df)
