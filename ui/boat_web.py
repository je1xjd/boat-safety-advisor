import sys
import os

# プロジェクトのルートディレクトリ（uiフォルダの一つ上の階層）をシステムパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- 以下の既存のインポートを記述 ---
import datetime
import pandas as pd
import streamlit as st

# --- サービス層 ---
from services.service import BoatDataService

# --- 新しいエンジン層から個別にインポート ---
from engine import AnalysisResult, AnalysisSummary
from engine import SafetyRule
from engine import BoatSafetyEngine
from engine import NavigationAnalyzer
from engine import StatusFormatter

# --- 表示整形クラス ---
from engine.formatter import (
    SafetyReportFormatter,
    StatusUIConfig,
    ReportFormatter,
    TideFormatter
)


# --- まだ移動が済んでいない共通関数/クラス ---
# これらは今後 engine/utils.py 等に移動予定ですが、
# 移動完了までは以下のインポートを一時的に使用します。
# from engine.utils import summarize_daytime_weather, SunCalculator 

# ※上記がまだない場合は、とりあえず以下のようにしておきます
from engine.utils import summarize_daytime_weather, SunCalculator


# ==========================================================
# Streamlit設定：アプリの基本情報を定義
# ==========================================================

st.set_page_config(
    page_title="相模川河口 海況安全判定",
    page_icon="🚤",
    layout="wide"
)

# ==========================================================
# キャッシュ：データ取得を高速化するためのキャッシュ処理
# ==========================================================

@st.cache_data(ttl=600)
def load_all_data(target_date):
    """
    サービス層を介して分析結果全体を取得する。
    """
    return BoatDataService.get_full_analysis(target_date)


# ==========================================================
# サマリーカード描画：判定結果をフロントエンドに表示
# ==========================================================

def render_summary_card(
    result_text,
    result_color,
    weather_text,
    temp_max,
    temp_min,
    max_window,
    before_str,
    after_str,
    tide_text,
    umi_info
):
    """安全判定結果を視覚的に強調して表示するHTMLパーツ"""

    # st.markdown("### 【 総合出港安全判定 】")

    # 判定結果（出港可/不可）の大きなラベル表示
    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:56px;
            font-weight:bold;
            color:{result_color};
            padding:10px;
        ">
        {result_text}
        </div>
        """,
        unsafe_allow_html=True
    )

    # 天気概要と気温情報の表示（気温を赤・青に色分け）
    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:22px;
            color:#0b4f84;
            font-weight:bold;
        ">
        {weather_text}
         | 
        【<span style="color: #e74c3c;">{temp_max:.0f}℃</span>
        /
        <span style="color: #3498db;">{temp_min:.0f}℃</span>】
        </div>
        """,
        unsafe_allow_html=True
    )

# 活動可能時間と潮汐のタイミングの表示
    if int(max_window[2]) > 0:
        # 安全な時間枠がある場合：詳細情報を表示
        st.markdown(
            f"""
            <div style="text-align:center; font-size:18px; color:#2e8b57; font-weight:bold; margin-bottom:10px;">
            最大連続活動枠: {int(max_window[0]):02d}-{int(max_window[1]):02d}時 ({int(max_window[2])}h)
            <br>
            前半 {before_str} / 後半 {after_str}
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        # 安全な時間枠がない場合：警告メッセージのみを表示
        st.error(f"連続して安全な時間帯が {SafetyRule.REQUIRED_SAFE_HOURS} 時間以上確保できません。")


# エンジンから整形済みHTML断片を取得して表示
    tide_html = BoatSafetyEngine.get_ui_tide_text(umi_info)
    
    st.markdown(
        f"""
        <div style="background:#e9ecef; border:1px solid #808080; padding:10px; text-align:center; font-size:15px; font-weight:bold; color:#333; margin-top:8px; border-radius:2px;">
            {tide_text}

        </div>
        """,
        unsafe_allow_html=True
    )


# ==========================================================
# DataFrame色付け関数
# ==========================================================


def highlight_status(row):
    status = row["判定"]
    # StatusFormatter を使用するように変更
    bg_color = StatusFormatter.get_status_color(status)
    return [f'background-color: {bg_color}'] * len(row)



# ==========================================================
# ヘッダ表示
# ==========================================================

st.title("🚤 ボート出港判定")
st.caption("相模川河口の潮位・潮汐・風速・風向・波高・うねりを総合評価")

# ==========================================================
# 日付選択：8日間先まで判定可能
# ==========================================================

# 日本時間を指定して今日の日付を取得
JST = datetime.timezone(datetime.timedelta(hours=9), 'JST')
today_jst = datetime.datetime.now(JST).date()

date_options = [today_jst + datetime.timedelta(days=i) for i in range(8)]
weekdays = ["月", "火", "水", "木", "金", "土", "日"]

target_date = st.selectbox(
    "判定日",
    date_options,
    format_func=lambda d: f"{d.strftime('%Y-%m-%d')}({weekdays[d.weekday()]})"
)


# ==========================================================
# 判定開始ボタン
# ==========================================================

run = st.button("🔍 海況判定を実行", width="stretch")

if not run:
    st.stop() # ボタンが押されるまで処理を待機

# ==========================================================
# データ取得：スピナーを表示して処理待機
# ==========================================================

with st.spinner("海況データ取得中..."):
    result = load_all_data(target_date)

# ==========================================================
# エラーチェック：データが取得できなかった場合の処理
# ==========================================================

if result is None or result.weather_info is None:
    st.error("気象データ取得失敗")
    st.stop()

# ==========================================================
# 変数の展開：resultから各データを取り出す
# ==========================================================
weather_info = result.weather_info
umi_info = result.umi_info
hour_data = result.hour_data
summary = result.summary


# ==========================================================
# 天気サマリーと潮汐データの初期処理
# ==========================================================

daytime_summary = summarize_daytime_weather(
    weather_info.weather_code, 
    weather_info.precipitation_probability
)


# ==========================================================
# 日出日入時刻のパース処理
# ==========================================================

sunrise_hour, sunset_hour = (
    SunCalculator.get_sun_times(
        umi_info
    )
)


# ==========================================================
# 安全判定データとサマリーの取得
# ==========================================================
# サービス層で生成された result を活用
# 辞書変換や Factory の再呼び出しは不要です
hour_data = result.hour_data
summary = result.summary

# ==========================================================
# UI表示用データの準備
# ==========================================================

# 総合判定データの取得（Formatterへの受け渡し）
ui_data = SafetyReportFormatter.get_ui_summary_data(summary)

# 潮汐テキストの生成（Formatter層へ責務を移譲するため、TideFormatterを使用）
tide_text = TideFormatter.get_ui_tide_text(result.umi_info)

# 判定結果に基づいてサマリーカードをレンダリング
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

# ==========================================================
# 詳細表：時間別データテーブルの構築
# ==========================================================

# 1. formatter からデータを構築
table_rows = SafetyReportFormatter.build_table_rows(
    hour_data,
    sunrise_hour,
    sunset_hour
)

# ReportFormatterで直接DataFrame生成または変換を完結させるのが理想だが、
# ロジックを変えないため、辞書リストへの変換を整理
display_rows = ReportFormatter.build_display_rows(table_rows)
df = pd.DataFrame([asdict(row) for row in display_rows])

# 4. 列名を適切な日本語にマッピング
df = df.rename(columns={
    "time_range": "時間",
    "status": "判定",
    "direction": "風向",
    "wind": "風速",
    "wave": "波浪",
    "tide": "潮位"
})

# 5. 不要な列（tagなど）があればここで絞り込む
df = df[["時間", "判定", "風向", "風速", "波浪", "潮位"]]

# スタイリング
styled_df = df.style.apply(highlight_status, axis=1)


# ==========================================================
# エキスパンダー表示：詳細表
# ==========================================================

with st.expander("時間別詳細データ", expanded=False):
    st.table(styled_df)

# ==========================================================
# フッター：安全基準の説明
# ==========================================================

# st.caption(
#     "【出港判定基準】: 潮位・潮汐・風速・風向・波高・うねりを総合評価"
# )