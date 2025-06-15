import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import matplotlib.pyplot as plt
import altair as alt
from datetime import datetime
import os
import sys

# カレントディレクトリをsrcの親ディレクトリに設定
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 自作モジュールのインポート
from src.data_loader import DataLoader
from src.analyzer import CryptoAnalyzer

# ページ設定
st.set_page_config(page_title="仮想通貨取引分析ツール", page_icon="💰", layout="wide")

# セッション状態の初期化
if 'data_loader' not in st.session_state:
    st.session_state.data_loader = DataLoader()
    
@st.cache_resource
def get_analyzer(_data_loader):
    return CryptoAnalyzer(_data_loader)

if 'analyzer' not in st.session_state:
    st.session_state.analyzer = get_analyzer(st.session_state.data_loader)

# サイドバーの設定
st.sidebar.title("設定")

# 年の選択
years = st.session_state.data_loader.get_years()
selected_year = st.sidebar.selectbox("分析する年を選択", years, index=years.index('all'))

# コインの選択
coins = st.session_state.data_loader.get_coins()

# 現在の価格入力フォーム
st.sidebar.subheader("現在の価格を入力")
current_prices = {}

for coin in coins:
    default_value = 0.0
    current_prices[coin] = st.sidebar.number_input(f"{coin}の価格", min_value=0.0, value=default_value, format="%.2f")

# チェックポイント記録ボタン
if st.sidebar.button("チェックポイント記録"):
    # 現在の分析結果を取得
    analysis_results = st.session_state.analyzer.analyze_transactions(selected_year, current_prices)
    
    # チェックポイントとして保存
    timestamp = st.session_state.data_loader.save_checkpoint(current_prices, analysis_results)
    st.sidebar.success(f"チェックポイントを記録しました: {timestamp}")

# メインコンテンツ
st.title("仮想通貨取引分析ツール")

# タブの設定
tab1, tab2, tab3, tab4 = st.tabs(["取引サマリー", "年間確定利益", "価格・資産推移", "取得単価シミュレーション"])

# 分析結果を取得
analysis_results = st.session_state.analyzer.analyze_transactions(selected_year, current_prices)

# タブ1: 取引サマリー
with tab1:
    st.header(f"{selected_year}年の取引サマリー")
    
    # 結果をデータフレームに変換
    summary_data = []
    
    for coin, metrics in analysis_results.items():
        summary_data.append({
            "コイン": coin,
            "元本 (円)": round(metrics['principal']),
            "取得コイン数": metrics['quantity'],
            "平均取得単価 (円)": round(metrics['avg_price']),
            "評価額 (円)": round(metrics['current_value']),
            "含み損益 (円)": round(metrics['unrealized_profit']),
            "含み損益率 (%)": round(metrics['unrealized_profit'] / metrics['principal'] * 100, 2) if metrics['principal'] > 0 else 0,
        })
    
    # 全体の合計行を追加
    total_principal = sum(metrics['principal'] for metrics in analysis_results.values())
    total_current_value = sum(metrics['current_value'] for metrics in analysis_results.values())
    total_profit = total_current_value - total_principal
    
    summary_data.append({
        "コイン": "合計",
        "元本 (円)": round(total_principal),
        "取得コイン数": "-",
        "平均取得単価 (円)": "-",
        "評価額 (円)": round(total_current_value),
        "含み損益 (円)": round(total_profit),
        "含み損益率 (%)": round(total_profit / total_principal * 100, 2) if total_principal > 0 else 0,
    })
    
    # データフレームに変換して表示
    summary_df = pd.DataFrame(summary_data)
    
    # 数値型のカラムを適切に処理
    numeric_columns = ['元本 (円)', '取得コイン数', '平均取得単価 (円)', '評価額 (円)', '含み損益 (円)', '含み損益率 (%)']
    for col in numeric_columns:
        if col in summary_df.columns:
            summary_df[col] = pd.to_numeric(summary_df[col], errors='coerce')
    
    st.dataframe(summary_df, use_container_width=True)
    
    # グラフ表示
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("コイン別元本内訳")
        coin_data = summary_df[summary_df["コイン"] != "合計"].copy()
        
        fig = px.pie(
            coin_data,
            values="元本 (円)",
            names="コイン",
            title="コイン別元本内訳",
            hole=0.4
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("コイン別評価額内訳")
        
        fig = px.pie(
            coin_data,
            values="評価額 (円)",
            names="コイン",
            title="コイン別評価額内訳",
            hole=0.4
        )
        st.plotly_chart(fig, use_container_width=True)
        
# タブ2: 年間確定利益
with tab2:
    st.header("年間確定利益")
    
    # 確定利益の計算
    yearly_profits = st.session_state.analyzer.calculate_yearly_profit()
    
    if yearly_profits:
        # データフレームに変換
        profit_data = []
        
        for year, profit in yearly_profits.items():
            profit_data.append({
                "年": year,
                "確定利益 (円)": round(profit),
            })
        
        profit_df = pd.DataFrame(profit_data)
        st.dataframe(profit_df, use_container_width=True)
        
        # グラフ表示
        fig = px.bar(
            profit_df,
            x="年",
            y="確定利益 (円)",
            title="年間確定利益の推移"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("確定利益のデータがありません。")

# タブ3: 価格・資産推移
with tab3:
    st.header("価格・資産推移")
    
    # チェックポイントデータの読み込み
    checkpoints = st.session_state.data_loader.load_checkpoints()
    
    if checkpoints:
        # コイン選択
        selected_coin_for_chart = st.selectbox("コインを選択", ["全体"] + coins)
        
        # データ準備
        chart_data = []
        
        for checkpoint in checkpoints:
            timestamp = checkpoint['timestamp']
            prices = checkpoint['prices']
            metrics = checkpoint['metrics']
            
            if selected_coin_for_chart == "全体":
                # 全コインの合計
                total_value = sum(coin_metrics['current_value'] for coin, coin_metrics in metrics.items())
                total_principal = sum(coin_metrics['principal'] for coin, coin_metrics in metrics.items())
                total_profit = total_value - total_principal
                
                chart_data.append({
                    "日時": timestamp,
                    "評価額": total_value,
                    "元本": total_principal,
                    "含み益": total_profit
                })
            elif selected_coin_for_chart in metrics:
                coin_metrics = metrics[selected_coin_for_chart]
                chart_data.append({
                    "日時": timestamp,
                    "価格": prices.get(selected_coin_for_chart, 0),
                    "評価額": coin_metrics['current_value'],
                    "元本": coin_metrics['principal'],
                    "含み益": coin_metrics['unrealized_profit'],
                    "保有枚数": coin_metrics['quantity']
                })
        
        if chart_data:
            chart_df = pd.DataFrame(chart_data)
            
            # 日時を日付型に変換
            chart_df["日時"] = pd.to_datetime(chart_df["日時"])
            
            if selected_coin_for_chart == "全体":
                # 全体の資産推移
                st.subheader("全体の資産推移")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=chart_df["日時"], y=chart_df["評価額"], name="評価額", line=dict(color="green")))
                fig.add_trace(go.Scatter(x=chart_df["日時"], y=chart_df["元本"], name="元本", line=dict(color="blue")))
                fig.add_trace(go.Scatter(x=chart_df["日時"], y=chart_df["含み益"], name="含み益", line=dict(color="red")))
                
                fig.update_layout(
                    title="全体の資産推移",
                    xaxis_title="日時",
                    yaxis_title="金額 (円)"
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                # コインごとの詳細
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader(f"{selected_coin_for_chart}の価格推移")
                    
                    fig = px.line(
                        chart_df,
                        x="日時",
                        y="価格",
                        title=f"{selected_coin_for_chart}の価格推移"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader(f"{selected_coin_for_chart}の保有枚数推移")
                    
                    fig = px.line(
                        chart_df,
                        x="日時",
                        y="保有枚数",
                        title=f"{selected_coin_for_chart}の保有枚数推移"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                st.subheader(f"{selected_coin_for_chart}の資産推移")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=chart_df["日時"], y=chart_df["評価額"], name="評価額", line=dict(color="green")))
                fig.add_trace(go.Scatter(x=chart_df["日時"], y=chart_df["元本"], name="元本", line=dict(color="blue")))
                fig.add_trace(go.Scatter(x=chart_df["日時"], y=chart_df["含み益"], name="含み益", line=dict(color="red")))
                
                fig.update_layout(
                    title=f"{selected_coin_for_chart}の資産推移",
                    xaxis_title="日時",
                    yaxis_title="金額 (円)"
                )
                
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("チェックポイントのデータがありません。「チェックポイント記録」ボタンを押して記録を開始してください。")

# タブ4: 取得単価シミュレーション
with tab4:
    st.header("取得単価シミュレーション")
    
    # コイン選択
    selected_coin_for_sim = st.selectbox("シミュレーションするコインを選択", coins, key="sim_coin")
    
    # 現在の価格を取得
    current_price = current_prices.get(selected_coin_for_sim, 0)
    
    # 追加購入シミュレーション
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("追加購入シミュレーション")
        additional_quantity = st.number_input("追加購入枚数", min_value=0.0, value=0.0, step=0.1)
        
        if additional_quantity > 0:
            # シミュレーション計算
            scenario = st.session_state.analyzer.calculate_scenario(selected_coin_for_sim, current_price, additional_quantity)
            
            st.subheader("シミュレーション結果")
            
            # 表形式で表示
            col1a, col1b = st.columns(2)
            
            with col1a:
                st.metric("現在の平均取得単価", f"{round(scenario['current']['avg_price']):,}円")
            
            with col1b:
                st.metric("購入後の平均取得単価", f"{round(scenario['new']['avg_price']):,}円", 
                         delta=f"{round(scenario['change']['avg_price']):,}円")
            
            col2a, col2b = st.columns(2)
            
            with col2a:
                st.metric("現在の評価額", f"{round(scenario['current']['value']):,}円")
            
            with col2b:
                st.metric("購入後の評価額", f"{round(scenario['new']['value']):,}円", 
                         delta=f"{round(scenario['change']['value']):,}円")
    
    with col2:
        st.subheader("価格分布")
        
        # 価格分布データを取得
        distribution_data = st.session_state.analyzer.get_distribution_data(selected_coin_for_sim, current_price)
        
        if distribution_data['distribution']:
            # 価格分布をヒストグラムとして表示
            dist_df = pd.DataFrame(distribution_data['distribution'])
            
            # 平均取得単価と現在の価格を表示するための縦線
            avg_price = distribution_data['avg_price']
            
            # 買値分布の可視化
            price_chart = alt.Chart(dist_df).mark_bar().encode(
                x=alt.X('price:Q', bin=alt.Bin(maxbins=20), title='価格 (円)'),
                y=alt.Y('sum(quantity):Q', title='取得枚数'),
                tooltip=['price:Q', 'quantity:Q']
            ).properties(
                title=f"{selected_coin_for_sim}の価格分布"
            )
            
            # 平均取得単価を示す縦線
            avg_line = alt.Chart(pd.DataFrame({'price': [avg_price]})).mark_rule(color='red').encode(
                x='price:Q',
                tooltip=['price:Q']
            )
            
            # 現在価格を示す縦線
            current_line = alt.Chart(pd.DataFrame({'price': [current_price]})).mark_rule(color='green').encode(
                x='price:Q',
                tooltip=['price:Q']
            )
            
            # 凡例をカスタム
            legend = alt.Chart(pd.DataFrame({
                'color': ['red', 'green'],
                'label': ['平均取得単価', '現在価格']
            })).mark_point().encode(
                y=alt.Y('label:N', title=None),
                color=alt.Color('color:N', scale=None)
            )
            
            # チャートを結合
            final_chart = price_chart + avg_line + current_line
            
            # チャートを表示
            st.altair_chart(final_chart, use_container_width=True)
            
            # 統計情報
            st.subheader("統計情報")
            col2a, col2b, col2c = st.columns(3)
            
            with col2a:
                st.metric("合計取得枚数", f"{distribution_data['total_quantity']:.8f}")
            
            with col2b:
                st.metric("平均取得単価", f"{round(distribution_data['avg_price']):,}円")
            
            with col2c:
                st.metric("現在の評価額", f"{round(distribution_data['current_value']):,}円")
                
            # 追加購入のシミュレーションを表示（動的グラフ）
            if additional_quantity > 0:
                st.subheader("追加購入シミュレーション")
                
                # 元のデータと新しいデータを結合
                sim_data = distribution_data['distribution'].copy()
                sim_data.append({
                    'quantity': additional_quantity,
                    'price': current_price
                })
                
                sim_df = pd.DataFrame(sim_data)
                
                # 新しい平均取得単価
                new_avg_price = scenario['new']['avg_price']
                
                # シミュレーションチャート
                sim_chart = alt.Chart(sim_df).mark_bar().encode(
                    x=alt.X('price:Q', bin=alt.Bin(maxbins=20), title='価格 (円)'),
                    y=alt.Y('sum(quantity):Q', title='取得枚数'),
                    tooltip=['price:Q', 'quantity:Q']
                ).properties(
                    title=f"{selected_coin_for_sim}の価格分布（追加購入後）"
                )
                
                # 新しい平均取得単価を示す縦線
                new_avg_line = alt.Chart(pd.DataFrame({'price': [new_avg_price]})).mark_rule(color='orange').encode(
                    x='price:Q',
                    tooltip=['price:Q']
                )
                
                # 元の平均取得単価を示す縦線
                old_avg_line = alt.Chart(pd.DataFrame({'price': [avg_price]})).mark_rule(color='red', strokeDash=[4, 4]).encode(
                    x='price:Q',
                    tooltip=['price:Q']
                )
                
                # 現在価格を示す縦線
                current_line = alt.Chart(pd.DataFrame({'price': [current_price]})).mark_rule(color='green').encode(
                    x='price:Q',
                    tooltip=['price:Q']
                )
                
                # チャートを結合
                final_sim_chart = sim_chart + new_avg_line + old_avg_line + current_line
                
                # チャートを表示
                st.altair_chart(final_sim_chart, use_container_width=True)
        else:
            st.info(f"{selected_coin_for_sim}の取引データがありません。")

# フッター
st.markdown("---")
st.caption("© 2023 仮想通貨取引分析ツール - プライバシー保護のためローカル環境で実行されます") 