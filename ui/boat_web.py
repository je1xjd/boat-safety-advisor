"""
boat_web.py

Streamlitを用いたWeb版の出港判定アプリケーション。
海況タイムラインを削除し、元の構成に戻しました。
"""
import sys
import os
import datetime
import pandas as pd
import streamlit as st
import altair as alt

# --- パス操作をimportの後に行う ---
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

# ページ設定
st.set_page_config(
    page_title="相模川河口 海況安全判定",
    page_icon="🚤",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ページ状態の初期化
if "current_page" not in st.session_state:
    st.session_state.current_page = "home"

# --- サイドバーメニュー ---
with st.sidebar:
    st.header("≡ メニュー")
    if st.button("🚤 出港判定", width='stretch'):
        st.session_state.current_page = "home"
        st.rerun()

    # 判定基準確認ボタン（ページ遷移として定義）
    if st.button("⚖ 判定基準を確認", width='stretch'):
        st.session_state.current_page = "criteria"
        st.rerun()

    st.divider()
    st.subheader("🚀 出港準備")
    if st.button("下架前チェック", width='stretch'):
        st.session_state.current_page = "pre_lower"
        st.rerun()
    if st.button("下架後チェック", width='stretch'):
        st.session_state.current_page = "post_lower"
        st.rerun()

    st.divider()
    st.subheader("⚓ 帰港処理")
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

# --- 関数定義 ---
@st.cache_data(ttl=600)
def load_all_data(target_date):
    return BoatDataService.get_full_analysis(target_date)

def render_summary_card(
    result_text, result_color, weather_text, temp_max, temp_min,
    max_window, before_str, after_str, tide_text, umi_info
):
    st.markdown(f'<div style="text-align:center; font-size:56px; font-weight:bold; color:{result_color}; padding:10px;">{result_text}</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="text-align:center; font-size:22px; color:#0b4f84; font-weight:bold;">{weather_text} | 【<span style="color: #e74c3c;">{temp_max:.0f}℃</span> / <span style="color: #3498db;">{temp_min:.0f}℃</span>】</div>', unsafe_allow_html=True)
    if int(max_window[2]) > 0:
        st.markdown(f'<div style="text-align:center; font-size:18px; color:#2e8b57; font-weight:bold; margin-bottom:10px;">最大連続活動枠: {int(max_window[0]):02d}-{int(max_window[1]):02d}時 ({int(max_window[2])}h)<br>前半 {before_str} / 後半 {after_str}</div>', unsafe_allow_html=True)
    else:
        st.error(f"連続して安全な時間帯が {SafetyRule.REQUIRED_SAFE_HOURS} 時間以上確保できません。")
    st.markdown(f'<div style="background:#e9ecef; border:1px solid #808080; padding:10px; text-align:center; font-size:15px; font-weight:bold; color:#333; margin-top:8px; border-radius:2px;">{tide_text}</div>', unsafe_allow_html=True)

def highlight_status(row):
    return [f'background-color: {StatusFormatter.get_status_color(row["判定"])}'] * len(row)


# --- ページ定義（データ構造） ---
# ファイル名からセクションキーへの変更で、ファイルシステムへの依存を排除
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
    
    # 判定基準ページならチェックボックスなしでテキスト表示
    if st.session_state.current_page == "criteria":
        if items:
            st.text("\n".join(items))
        else:
            st.error("データが空です。")
    # チェックリストページならチェックボックスを表示
    elif items and "エラー" not in items[0]:
        for item in items:
            st.checkbox(item)
    else:
        st.error(items[0] if items else "データが空です。")
        
    if st.button("ホームに戻る"):
        st.session_state.current_page = "home"
        st.rerun()

elif st.session_state.current_page == "home":
    # (以下、既存のホーム画面処理)
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

    # 判定結果がある場合のみタブを表示する
    if "analysis_result" in st.session_state and st.session_state.analysis_result:
        result = st.session_state.analysis_result
        
        # 1. タブを直接指標別に並べる
        tab1, tab_wind, tab_wave, tab_tide = st.tabs(["📊 判定結果", "🍃 風速グラフ", "🌊 波高グラフ", "🚢 潮位グラフ"])
        
        # 2. 判定結果と詳細タブ
        with tab1:
            ui_data = SafetyReportFormatter.get_ui_summary_data(result.summary)
            render_summary_card(
                ui_data["label"], ui_data["color"], 
                summarize_daytime_weather(result.weather_info.weather_code, result.weather_info.precipitation_probability),
                result.weather_info.temp_max, result.weather_info.temp_min,
                result.summary.best_window, result.summary.before_str, result.summary.after_str,
                TideFormatter.get_ui_tide_text(result.umi_info), result.umi_info
            )

            # テーブル表示用のデータ構築
            # --- 修正箇所: テーブル表示用のデータ構築 ---
            table_rows = SafetyReportFormatter.build_table_rows(result.hour_data, *SunCalculator.get_sun_times(result.umi_info))

            # 1. 全データを生成（グラフ用に使用）
            all_rows = ReportFormatter.build_display_rows(table_rows)

            # 2. テーブル用: フィルタリングを適用
            display_rows_filtered = ReportFormatter.filter_display_rows(all_rows)
            df = pd.DataFrame([asdict(row) for row in display_rows_filtered])
            df = df.rename(columns={"time_range": "時間", "status": "判定", "direction": "風向", "wind": "風速", "wave": "波浪", "tide": "潮位"})
            st.table(df[["時間", "判定", "風向", "風速", "波浪", "潮位"]].style.apply(highlight_status, axis=1))

            # 3. グラフ用: 全データ(all_rows)から直接作成
            df_graph = pd.DataFrame([asdict(row) for row in all_rows])
            df_graph = df_graph.rename(columns={"time_range": "時間", "wind": "風速", "wave": "波浪", "tide": "潮位"})
        
        # 数値抽出関数（日本語名のエラーを防ぐため、単純な抽出を行う）
        def extract_number(val):
            import re
            m = re.search(r"(\d+\.?\d*)", str(val))
            return float(m.group(1)) if m else 0.0

        df_graph["時間"] = df_graph["時間"].apply(extract_number).astype(int)
        df_graph["風速"] = df_graph["風速"].apply(extract_number)
        df_graph["波浪"] = df_graph["波浪"].apply(extract_number)
        df_graph["潮位"] = df_graph["潮位"].apply(extract_number)
        
        # CSSでグラフへのマウス入力を完全に無効化
        st.markdown("""
        <style>
        [data-testid="stVegaLiteChart"] {
            pointer-events: none;
        }
        </style>
        """, unsafe_allow_html=True)

        # 4. 各指標ごとのタブ表示
        # 【重要】CSSでグラフ領域へのホイール・マウス操作を物理的に遮断する
        st.markdown("""
        <style>
        [data-testid="stVegaLiteChart"] {
            pointer-events: none;
        }
        </style>
        """, unsafe_allow_html=True)

        def draw_fixed_chart(df, y_col, color):
            # 18時までのデータのみに絞り込んだdf_graphを使用する前提
            chart = alt.Chart(df).mark_line(point=True).encode(
                x=alt.X("時間:Q", 
                        title="時刻", 
                        # 定数を利用して表示範囲を制御
                        scale=alt.Scale(domain=[SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR]),
                        axis=alt.Axis(
                            format="d", 
                            tickCount=SafetyRule.ACTIVITY_END_HOUR - SafetyRule.ACTIVITY_START_HOUR + 1,
                            values=list(range(SafetyRule.ACTIVITY_START_HOUR, SafetyRule.ACTIVITY_END_HOUR + 1))
                        )
                ), 
                y=alt.Y(f"{y_col}:Q", scale=alt.Scale(zero=True))
            ).properties(height=300).configure_line(color=color)
            
            # 補助線とスタイルを一括適用
            return chart.configure_axis(
                grid=True,
                gridColor="#E0E0E0",
                gridDash=[2, 2],
                gridWidth=0.5
            )

        with tab_wind:
            st.subheader("時刻別 風速 (m/s)") # サブヘッダーも「時刻」に変更
            st.altair_chart(draw_fixed_chart(df_graph, "風速", "#3498db"), width='stretch')
        
        with tab_wave:
            st.subheader("時刻別 波高 (m)")
            st.altair_chart(draw_fixed_chart(df_graph, "波浪", "#e74c3c"), width='stretch')
            
        with tab_tide:
            st.subheader("時刻別 潮位 (cm)")
            st.altair_chart(draw_fixed_chart(df_graph, "潮位", "#2ecc71"), width='stretch')
