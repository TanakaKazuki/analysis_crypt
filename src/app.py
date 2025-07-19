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
from plotly.subplots import make_subplots
from decimal import Decimal, ROUND_HALF_UP
import re
import json
from pathlib import Path

# カレントディレクトリをsrcの親ディレクトリに設定
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 自作モジュールのインポート
from src.data_loader import DataLoader
from src.analyzer import CryptoAnalyzer

# ページ設定
st.set_page_config(page_title="クリプト取引分析ツール", page_icon="��", layout="wide")

# セッション状態の初期化
if 'data_loader' not in st.session_state:
    st.session_state.data_loader = DataLoader()
    
@st.cache_resource
def get_analyzer(_data_loader):
    return CryptoAnalyzer(_data_loader)

if 'analyzer' not in st.session_state:
    st.session_state.analyzer = get_analyzer(st.session_state.data_loader)

# 最新のチェックポイントから価格を読み込む
def get_latest_prices():
    # データローダーからコイン一覧を取得し、初期価格を0に設定
    default_prices = {}
    coins = st.session_state.data_loader.get_coins()
    for coin in coins:
        default_prices[coin] = 0.0
    
    checkpoints = st.session_state.data_loader.load_checkpoints()
    if checkpoints:
        latest_checkpoint = checkpoints[-1]
        return latest_checkpoint['prices']
    return default_prices

# サイドバーの設定
st.sidebar.title("設定")

# 年の選択
years = st.session_state.data_loader.get_years()
selected_year = st.sidebar.selectbox("分析する年を選択", years, index=years.index('all') if 'all' in years else 0)

# コインの選択
coins = st.session_state.data_loader.get_coins()

# 最新の価格を取得
latest_prices = get_latest_prices()

# 現在の価格入力フォーム
st.sidebar.subheader("現在の価格を入力")
current_prices = {}

for coin in coins:
    # 最新の価格があればそれを初期値とする
    default_value = latest_prices.get(coin, 0.0)
    current_prices[coin] = st.sidebar.number_input(f"{coin}の価格", min_value=0.0, value=default_value, format="%.2f")

# チェックポイント記録ボタン
if st.sidebar.button("チェックポイント記録"):
    # 現在の分析結果を取得
    analysis_results = st.session_state.analyzer.analyze_transactions(selected_year, current_prices)
    
    # チェックポイントとして保存
    timestamp = st.session_state.data_loader.save_checkpoint(current_prices, analysis_results)
    st.sidebar.success(f"チェックポイントを記録しました: {timestamp}")

# メインコンテンツ
st.title("クリプト取引分析ツール")

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
    yearly_profits, yearly_coin_profits = st.session_state.analyzer.calculate_yearly_profit()
    
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
        
        # 積み上げバーチャート用のデータ準備
        stacked_data = []
        all_coins = set()
        
        for year, coin_profits in yearly_coin_profits.items():
            for coin, profit in coin_profits.items():
                all_coins.add(coin)
                stacked_data.append({
                    "年": year,
                    "コイン": coin,
                    "確定利益 (円)": profit
                })
        
        if stacked_data:
            # データフレームに変換
            stacked_df = pd.DataFrame(stacked_data)
            
            # 積み上げバーチャート表示
            fig = px.bar(
                stacked_df,
                x="年",
                y="確定利益 (円)",
                color="コイン",
                title="年間確定利益の推移（コイン別）",
                barmode="relative"
            )
            
            # X軸を年単位に設定
            fig.update_xaxes(
                tickmode='array',
                tickvals=list(yearly_profits.keys()),
                ticktext=[str(year) for year in yearly_profits.keys()]
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 損益がマイナスの場合も適切に表示されることを説明
            st.info("注: 確定損失（マイナスの値）がある場合は、バーが下方向に伸びて表示されます。")
        
        # コインごとの確定利益の内訳を表示
        st.subheader("コインごとの確定利益内訳")
        
        # 年の選択
        if yearly_coin_profits:
            available_years = list(yearly_coin_profits.keys())
            if available_years:
                selected_profit_year = st.selectbox(
                    "年を選択", 
                    available_years, 
                    format_func=lambda x: f"{x}年"
                )
                
                # 選択した年のコインごとの利益を表示
                if selected_profit_year in yearly_coin_profits:
                    coin_profits = yearly_coin_profits[selected_profit_year]
                    
                    if coin_profits:
                        coin_profit_data = []
                        
                        for coin, profit in coin_profits.items():
                            coin_profit_data.append({
                                "コイン": coin,
                                "確定利益 (円)": round(profit),
                                "計算方法": "売却価格 - 平均取得単価 × 売却数量"
                            })
                        
                        # 合計行を追加
                        total_profit = sum(profit for profit in coin_profits.values())
                        coin_profit_data.append({
                            "コイン": "合計",
                            "確定利益 (円)": round(total_profit),
                            "計算方法": "各コインの確定利益の合計"
                        })
                        
                        # データフレームに変換
                        coin_profit_df = pd.DataFrame(coin_profit_data)
                        st.dataframe(coin_profit_df, use_container_width=True)
                        
                        # 円グラフで表示
                        coin_profit_chart_data = [row for row in coin_profit_data if row["コイン"] != "合計"]
                        
                        if coin_profit_chart_data:
                            fig = px.pie(
                                pd.DataFrame(coin_profit_chart_data),
                                values="確定利益 (円)",
                                names="コイン",
                                title=f"{selected_profit_year}年 コイン別確定利益内訳",
                                hole=0.4
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info(f"{selected_profit_year}年のコインごとの確定利益データはありません。")
    else:
        st.info("確定利益のデータがありません。")

# タブ3: 価格・資産推移
with tab3:
    st.header("価格・資産推移")
    
    # チェックポイントデータの読み込み
    checkpoints = st.session_state.data_loader.load_checkpoints()
    
    if checkpoints:
        # コイン選択
        selected_coin_for_chart = st.selectbox("コインを選択", ["全体"] + coins, key="chart_coin_selector")
        
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
            
            # データ確認用のデバッグ情報
            st.write(f"データポイント数: {len(chart_df)}")
            
            # 日時を日付型に変換
            chart_df["日時"] = pd.to_datetime(chart_df["日時"])
            
            if selected_coin_for_chart == "全体":
                # 全体の資産推移
                st.subheader("全体の資産推移")
                
                # 元本と評価額のみのグラフを作成（含み益は塗りつぶしで表現）
                fig = go.Figure()
                
                                # 元本のライン
                fig.add_trace(
                    go.Scatter(
                        x=chart_df["日時"], 
                        y=chart_df["元本"], 
                        name="元本", 
                        line=dict(color="blue"),
                        hoverinfo="skip"  # このトレースのホバー情報を表示しない
                    )
                )
                
                # 評価額のライン
                fig.add_trace(
                    go.Scatter(
                        x=chart_df["日時"], 
                        y=chart_df["評価額"], 
                        name="評価額", 
                        line=dict(color="green"),
                        fill='tonexty',  # 前のトレースとの間を塗りつぶし
                        fillcolor='rgba(0, 255, 0, 0.1)',  # 薄い緑色で塗りつぶし
                        hoverinfo="skip"  # このトレースのホバー情報を表示しない
                    )
                )
                
                # 統合されたホバー情報を持つ透明なトレース
                fig.add_trace(
                    go.Scatter(
                        x=chart_df["日時"],
                        y=chart_df["評価額"],  # 評価額と同じY座標を使用
                        name="情報",
                        mode="lines",  # markersではなくlinesを使用
                        line=dict(width=0),  # 線を非表示に
                        hovertemplate='<b>%{x|%Y-%m-%d}</b><br>元本: %{customdata[0]:,.0f}円<br>評価額: %{customdata[1]:,.0f}円<br>含み益: %{customdata[2]:,.0f}円<extra></extra>',
                        customdata=np.column_stack((chart_df["元本"], chart_df["評価額"], chart_df["含み益"])),
                        showlegend=False
                    )
                )
                
                
                # レイアウト設定
                fig.update_layout(
                    title="全体の資産推移",
                    xaxis_title="日付",
                    yaxis_title="金額 (円)",
                    xaxis=dict(
                        type='date',
                        tickformat='%Y-%m-%d'
                    ),
                    hovermode="x unified"  # X軸上の全ポイントを同時に表示
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                # コインごとの詳細
                # データ確認用のデバッグ情報
                st.write(f"選択コイン: {selected_coin_for_chart}")
                st.write(f"価格データ: {chart_df['価格'].tolist()}")
                st.write(f"保有枚数データ: {chart_df['保有枚数'].tolist()}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader(f"{selected_coin_for_chart}の価格推移")
                    
                    # データが1ポイントしかない場合はバーチャートで表示
                    if len(chart_df) == 1:
                        fig = px.bar(
                            chart_df,
                            x="日時",
                            y="価格",
                            title=f"{selected_coin_for_chart}の価格推移"
                        )
                    else:
                        fig = px.line(
                            chart_df,
                            x="日時",
                            y="価格",
                            title=f"{selected_coin_for_chart}の価格推移"
                        )
                    # X軸を日付のみに設定
                    fig.update_xaxes(
                        type='date',
                        tickformat='%Y-%m-%d'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader(f"{selected_coin_for_chart}の保有枚数推移")
                    
                    # データが1ポイントしかない場合はバーチャートで表示
                    if len(chart_df) == 1:
                        fig = px.bar(
                            chart_df,
                            x="日時",
                            y="保有枚数",
                            title=f"{selected_coin_for_chart}の保有枚数推移"
                        )
                    else:
                        fig = px.line(
                            chart_df,
                            x="日時",
                            y="保有枚数",
                            title=f"{selected_coin_for_chart}の保有枚数推移"
                        )
                    # X軸を日付のみに設定
                    fig.update_xaxes(
                        type='date',
                        tickformat='%Y-%m-%d'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                st.subheader(f"{selected_coin_for_chart}の資産推移")
                
                # 元本と評価額のみのグラフを作成（含み益は塗りつぶしで表現）
                fig = go.Figure()
                
                                # 元本のライン
                fig.add_trace(
                    go.Scatter(
                        x=chart_df["日時"], 
                        y=chart_df["元本"], 
                        name="元本", 
                        line=dict(color="blue"),
                        hoverinfo="skip"  # このトレースのホバー情報を表示しない
                    )
                )
                
                # 評価額のライン
                fig.add_trace(
                    go.Scatter(
                        x=chart_df["日時"], 
                        y=chart_df["評価額"], 
                        name="評価額", 
                        line=dict(color="green"),
                        fill='tonexty',  # 前のトレースとの間を塗りつぶし
                        fillcolor='rgba(0, 255, 0, 0.1)',  # 薄い緑色で塗りつぶし
                        hoverinfo="skip"  # このトレースのホバー情報を表示しない
                    )
                )
                
                # 統合されたホバー情報を持つ透明なトレース
                fig.add_trace(
                    go.Scatter(
                        x=chart_df["日時"],
                        y=chart_df["評価額"],  # 評価額と同じY座標を使用
                        name="情報",
                        mode="lines",  # markersではなくlinesを使用
                        line=dict(width=0),  # 線を非表示に
                        hovertemplate='<b>%{x|%Y-%m-%d}</b><br>元本: %{customdata[0]:,.0f}円<br>評価額: %{customdata[1]:,.0f}円<br>含み益: %{customdata[2]:,.0f}円<extra></extra>',
                        customdata=np.column_stack((chart_df["元本"], chart_df["評価額"], chart_df["含み益"])),
                        showlegend=False
                    )
                )
                
                
                # レイアウト設定
                fig.update_layout(
                    title=f"{selected_coin_for_chart}の資産推移",
                    xaxis_title="日付",
                    yaxis_title="金額 (円)",
                    xaxis=dict(
                        type='date',
                        tickformat='%Y-%m-%d'
                    ),
                    hovermode="x unified"  # X軸上の全ポイントを同時に表示
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("表示するデータがありません。チェックポイントにデータが含まれていない可能性があります。")
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
        additional_amount = st.number_input("追加購入金額（円）", min_value=0, value=0, step=1000)
        
        if additional_amount > 0:
            # シミュレーション計算（金額ベース）
            scenario = st.session_state.analyzer.calculate_scenario_by_amount(selected_coin_for_sim, current_price, additional_amount)
            
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
                         
            # 追加情報
            st.info(f"{additional_amount:,}円で購入できる{selected_coin_for_sim}の数量: {scenario['change']['quantity']:.8f}")
    
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
            if additional_amount > 0:
                st.subheader("追加購入シミュレーション")
                
                # 追加購入数量を計算
                additional_quantity = scenario['change']['quantity']
                
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
st.caption("© 2023 クリプト取引分析ツール - プライバシー保護のためローカル環境で実行されます") 