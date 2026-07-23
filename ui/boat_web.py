"""
boat_web.py

Streamlitを用いたWeb版の出港判定アプリケーション。
相模川河口の海況データを視覚的に確認するためのUIを提供する。
"""
import sys
import os
import datetime
import pandas as pd
import streamlit as st
import altair as alt

# 自作モジュールをインポートするため、親ディレクトリをパスに追加する
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dataclasses import asdict
from engine.loader import get_rule_content
from services.analysis import BoatDataService
from engine import AnalysisResult, AnalysisSummary, SafetyRule, BoatSafetyEngine, NavigationAnalyzer, StatusFormatter
from engine.formatter import (
    SafetyReportFormatter,
    StatusUIConfig,
    ReportFormatter,
    TideFormatter
)
from engine.utils import summarize_daytime_weather, SunCalculator
from ui.web_charts import extract_number, draw_fixed_chart

# アプリケーションの基本レイアウトとタイトルを設定する
st.set_page_config(
    page_title="相模川河口 海況安全判定",
    page_icon="🚤",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# セッション状態の初期化が行われていない場合、ホーム画面をデフォルトに設定する
if "current_page" not in st.session_state:
    st.session_state.current_page = "home"

def _create_menu():
    """
    アプリケーションのサイドバーメニューを描画・制御する。
    """
    with st.sidebar:
        st.header("≡ メニュー")
        if st.button("🚤 出港判定", width='stretch'):
            st.session_state.current_page = "home"
            st.rerun()

        if st.button("⚖ 判定基準", width='stretch'):
            st.session_state.current_page = "criteria"
            st.rerun()

        st.divider()
        st.subheader("🚀 出港前")
        if st.button("下架前チェック", width='stretch'):
            st.session_state.current_page = "pre_lower"
            st.rerun()
        if st.button("下架後チェック", width='stretch'):
            st.session_state.current_page = "post_lower"
            st.rerun()

        st.divider()
        st.subheader("⚓ 帰港後")
        if st.button("上架前チェック", width='stretch'):
            st.session_state.current_page = "pre_lift"
            st.rerun()
        if st.button("上架後チェック", width='stretch'):
            st.session_state.current_page = "post_lift"
            st.rerun()
            
        st.divider()
        if st.button("⚙ 設定", width='stretch'):
            st.session_state.current_page = "settings"
            st.rerun()

        st.divider()
        st.caption("相模川河口 海況安全判定アプリ")

# --- サイドバーメニュー描画の実行 ---
_create_menu()

# --- 関数定義 ---
@st.cache_data(ttl=600)
def load_all_data(target_date):
    """
    指定された日付の海況解析データを取得する（キャッシュ有効期間: 600秒）。
    """
    return BoatDataService.get_full_analysis(target_date)

def render_summary_card(
    result_text, result_color, weather_text, temp_max, temp_min,
    max_window, before_str, after_str, tide_text, umi_info
):
    """
    判定結果の総合サマリー情報を視覚的なカード形式で描画する。
    """
    st.markdown(f'<div style="text-align:center; font-size:56px; font-weight:bold; color:{result_color}; padding:10px;">{result_text}</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align:center; font-size:22px; color:#0b4f84; font-weight:bold;">{weather_text} | 【<span style="color: #e74c3c;">{temp_max:.0f}℃</span> / <span style="color: #3498db;">{temp_min:.0f}℃</span>】</div>', unsafe_allow_html=True)
    if int(max_window[2]) > 0:
        st.markdown(f'<div style="text-align:center; font-size:18px; color:#2e8b57; font-weight:bold; margin-bottom:10px;">最大連続活動枠: {int(max_window[0]):02d}-{int(max_window[1]):02d}時 ({int(max_window[2])}h)<br>前半 {before_str} / 後半 {after_str}</div>', unsafe_allow_html=True)
    else:
        st.error(f"連続して安全な時間帯が {SafetyRule.REQUIRED_SAFE_HOURS} 時間以上確保できません。")
    st.markdown(f'<div style="background:#e9ecef; border:1px solid #808080; padding:10px; text-align:center; font-size:15px; font-weight:bold; color:#333; margin-top:8px; border-radius:2px;">{tide_text}</div>', unsafe_allow_html=True)

def highlight_status(row):
    """
    データフレームの行ごとの判定ステータスに応じて背景色のスタイルを返す。
    """
    return [f'background-color: {StatusFormatter.get_status_color(row["判定"])}'] * len(row)


# --- ページ定義（データ構造） ---
CHECKLIST_CONFIG = {
    "pre_lower": ("PRE_LOWER", "下架前チェックリスト"),
    "post_lower": ("POST_LOWER", "下架後チェックリスト"),
    "pre_lift": ("PRE_LIFT", "上架前チェックリスト"),
    "post_lift": ("POST_LIFT", "上架後チェックリスト"),
    "criteria": ("SAFETY_CRITERIA", "ボート出港安全基準"),
}

# --- ページごとの表示制御 ---
if st.session_state.current_page in CHECKLIST_CONFIG:
    section_key, title = CHECKLIST_CONFIG[st.session_state.current_page]
    st.title(title)
    
    items = get_rule_content(section_key)
    
    if st.session_state.current_page == "criteria":
        if items:
            st.text("\n".join(items))
        else:
            st.error("データが空です。")
    elif items and "エラー" not in items[0]:
        for item in items:
            st.checkbox(item)
    else:
        st.error(items[0] if items else "データが空です。")
        
    if st.button("ホームに戻る"):
        st.session_state.current_page = "home"
        st.rerun()

elif st.session_state.current_page == "home":
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

    if st.button("🔍 海況判定を実行", width='stretch'):
        with st.spinner("データ取得中..."):
            st.session_state.analysis_result = load_all_data(target_date)

    if "analysis_result" in st.session_state and st.session_state.analysis_result:
        result = st.session_state.analysis_result
        
        ui_data = SafetyReportFormatter.get_ui_summary_data(result.summary)
        render_summary_card(
            ui_data["label"], ui_data["color"], 
            summarize_daytime_weather(result.weather_info.weather_code, result.weather_info.precipitation_probability),
            result.weather_info.temp_max, result.weather_info.temp_min,
            result.summary.best_window, result.summary.before_str, result.summary.after_str,
            TideFormatter.get_ui_tide_text(result.umi_info), result.umi_info
        )

        st.markdown("<br>", unsafe_allow_html=True)

        table_rows = SafetyReportFormatter.build_table_rows(result.hour_data, *SunCalculator.get_sun_times(result.umi_info))
        all_rows = ReportFormatter.build_display_rows(table_rows)
        display_rows_filtered = ReportFormatter.filter_display_rows(all_rows)
        
        df = pd.DataFrame([asdict(row) for row in display_rows_filtered])
        df = df.rename(columns={"time_range": "時間", "status": "判定", "direction": "風向", "wind": "風速", "wave": "波浪", "tide": "潮位"})
        
        graph_data_list = []
        for k, v in result.hour_data.items():
            if SafetyRule.ACTIVITY_START_HOUR <= int(k) <= SafetyRule.ACTIVITY_END_HOUR:
                graph_data_list.append({
                    "時間": int(k),
                    "風速": v.wind_speed if v.wind_speed is not None else 0.0,
                    "波高": extract_number(v.wave_height),
                    "潮位": extract_number(v.tide)
                })
        df_graph = pd.DataFrame(graph_data_list)

        tab1, tab_wind, tab_wave, tab_tide = st.tabs(["📊 判定結果", "🍃 風速グラフ", "🌊 波高グラフ", "🚢 潮位グラフ"])
        
        with tab1:
            st.table(df[["時間", "判定", "風向", "風速", "波浪", "潮位"]].style.apply(highlight_status, axis=1))

        # Streamlitの仕様によるグラフ操作を無効化するためのCSS設定
        st.markdown("""
        <style>
        [data-testid="stVegaLiteChart"] {
            pointer-events: none;
        }
        </style>
        """, unsafe_allow_html=True)

        with tab_wind:
            st.subheader("風速 (m/s)")
            st.altair_chart(
                draw_fixed_chart(
                    df_graph, "風速", SafetyRule.WIND_COLOR, 
                    limit_val=SafetyRule.WIND_LIMIT_NORMAL,
                    limit_label="制限風速",
                    y_max=SafetyRule.WIND_Y_LIMIT
                ), 
                width='stretch'
            )
        
        with tab_wave:
            st.subheader("波高 (m)")
            st.altair_chart(
                draw_fixed_chart(
                    df_graph, "波高", SafetyRule.WAVE_COLOR, 
                    limit_val=SafetyRule.MAX_WAVE_HEIGHT_NORMAL,
                    limit_label="制限波高",
                    y_max=SafetyRule.WAVE_Y_LIMIT
                ), 
                width='stretch'
            )
            
        with tab_tide:
            st.subheader("潮位 (cm)")
            st.altair_chart(
                draw_fixed_chart(
                    df_graph, "潮位", SafetyRule.TIDE_COLOR, 
                    limit_val=SafetyRule.MIN_TIDE_CM,
                    limit_label="最低潮位",
                    y_max=SafetyRule.TIDE_Y_LIMIT
                ), 
                width='stretch'
            )
