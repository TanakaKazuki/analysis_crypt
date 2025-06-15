import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict


class CryptoAnalyzer:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.gmo_data = None
        self.mercari_data = None
        self.current_prices = {
            'BTC': 0,
            'ETH': 0,
            'SOL': 0,
            'XRP': 0,
            'DOGE': 0,
            'XLM': 0
        }
        
    def analyze_transactions(self, year, current_prices):
        """取引データを分析する"""
        # 現在の価格を設定
        self.set_current_prices(current_prices)
        
        # データを読み込む
        if self.gmo_data is None:
            self.gmo_data = self.data_loader.load_gmo_data()
        if self.mercari_data is None:
            self.mercari_data = self.data_loader.load_mercari_data()
        
        # 年でフィルタリング
        filtered_data = self.data_loader.filter_data_by_year(year)
        
        # GMOデータの分析
        gmo_results = self._analyze_gmo_data(filtered_data['gmo'], year)
        
        # メルカリデータの分析
        mercari_results = self._analyze_mercari_data(filtered_data['mercari'], year)
        
        # 結果をマージ
        results = {}
        for coin in set(list(gmo_results.keys()) + list(mercari_results.keys())):
            gmo_data = gmo_results.get(coin, {
                'principal': 0,
                'quantity': 0,
                'avg_price': 0,
                'current_value': 0,
                'unrealized_profit': 0,
                'realized_profit': 0
            })
            mercari_data = mercari_results.get(coin, {
                'principal': 0,
                'quantity': 0,
                'avg_price': 0,
                'current_value': 0,
                'unrealized_profit': 0,
                'realized_profit': 0
            })
            
            total_quantity = gmo_data['quantity'] + mercari_data['quantity']
            total_principal = gmo_data['principal'] + mercari_data['principal']
            
            results[coin] = {
                'principal': total_principal,
                'quantity': total_quantity,
                'avg_price': total_principal / total_quantity if total_quantity > 0 else 0,
                'current_value': gmo_data['current_value'] + mercari_data['current_value'],
                'unrealized_profit': gmo_data['unrealized_profit'] + mercari_data['unrealized_profit'],
                'realized_profit': gmo_data['realized_profit'] + mercari_data['realized_profit']
            }
        
        return results
    
    def calculate_yearly_profit(self):
        """年ごとの確定利益を計算"""
        yearly_profits = {}
        
        # 全データを取得
        all_data = self.data_loader.filter_data_by_year('all')
        
        # GMOデータの分析
        if not all_data['gmo'].empty:
            gmo_df = all_data['gmo'].copy()
            if '日時' in gmo_df.columns:
                gmo_df['年'] = pd.to_datetime(gmo_df['日時'], errors='coerce').dt.year
                
                # 売却による確定利益を抽出
                sell_transactions = gmo_df[
                    (gmo_df['売買区分'] == '売') & 
                    (gmo_df['取引区分'].fillna('').astype(str).str.contains('取引所現物取引|販売所取引', na=False))
                ]
                
                for year, group in sell_transactions.groupby('年'):
                    if year not in yearly_profits:
                        yearly_profits[year] = 0
                    yearly_profits[year] += group['日本円受渡金額'].sum()
        
        # メルカリデータの分析
        if not all_data['mercari'].empty:
            mercari_df = all_data['mercari'].copy()
            if '日時' in mercari_df.columns:
                mercari_df['年'] = pd.to_datetime(mercari_df['日時'], errors='coerce').dt.year
                
                # 売却による確定利益を抽出
                sell_transactions = mercari_df[(mercari_df['売買区分'] == '売')]
                
                for year, group in sell_transactions.groupby('年'):
                    if year not in yearly_profits:
                        yearly_profits[year] = 0
                    yearly_profits[year] += group['約定金額'].sum()
        
        return yearly_profits
    
    def _analyze_gmo_data(self, data: pd.DataFrame, year: int) -> Dict[str, Dict[str, float]]:
        results = {}
        current_prices = self._get_current_prices()
        
        for coin in ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'XLM']:
            coin_data = data[data['銘柄名'] == coin].copy()
            if coin_data.empty:
                continue
            
            total_quantity = 0
            total_principal = 0
            sold_quantity = 0
            realized_profit = 0
            
            for _, row in coin_data.iterrows():
                # ステーキング報酬の処理
                if row['精算区分'] == '暗号資産預入・送付' and row['授受区分'] == '預入':
                    if pd.notna(row['数量']) and row['数量'] > 0:
                        total_quantity += float(row['数量'])
                    # ステーキング報酬は元本に加算しない（0円で取得）
                    continue
                
                # ステーキング手数料の処理
                if row['精算区分'] == '暗号資産預入・送付' and row['授受区分'] == '送付':
                    if pd.notna(row['数量']) and row['数量'] > 0:
                        total_quantity -= float(row['数量'])
                    # ステーキング手数料は元本に影響しない
                    continue
                
                # 取引所現物取引手数料返金の処理
                if row['精算区分'] == '取引所現物 取引手数料返金':
                    # 手数料返金は元本を減らす（コスト減少）
                    if pd.notna(row['日本円受渡金額']) and row['日本円受渡金額'] > 0:
                        total_principal -= float(row['日本円受渡金額'])
                    continue
                
                # 販売所取引の処理
                if '販売所取引' in str(row['精算区分']):
                    # 販売所取引では日本円受渡金額から取得
                    if pd.notna(row['日本円受渡金額']):
                        amount = abs(float(row['日本円受渡金額']))
                        
                        if row['売買区分'] == '買':
                            if pd.notna(row['約定数量']):
                                quantity = float(row['約定数量'])
                            elif pd.notna(row['数量']):
                                quantity = float(row['数量'])
                            else:
                                # 数量が不明な場合はスキップ
                                continue
                                
                            # 販売所取引では手数料が含まれているため、別途計算しない
                            total_quantity += quantity
                            total_principal += amount
                        continue
                
                # 取引所現物取引の処理
                if '取引所現物取引' in str(row['精算区分']):
                    quantity = 0
                    price = 0
                    fee = 0
                    
                    if pd.notna(row['約定数量']):
                        quantity = float(row['約定数量'])
                    
                    if pd.notna(row['約定レート']):
                        price = float(row['約定レート'])
                    
                    if pd.notna(row['注文手数料']):
                        fee = float(row['注文手数料'])
                    
                    if row['売買区分'] == '買':
                        total_quantity += quantity
                        total_principal += (quantity * price) + fee
                    else:  # 売
                        sold_quantity += quantity
                        total_quantity -= quantity
                        
                        # 売却時の処理を修正
                        sale_amount = quantity * price
                        if pd.notna(row['日本円受渡金額']):
                            sale_amount = float(row['日本円受渡金額'])
                        
                        # 売却による実現利益の計算（手数料を考慮）
                        realized_profit += sale_amount
                        
                        # 元本の調整（売却分の元本を減らす）
                        if total_quantity > 0:
                            # 売却分の元本を減らす（平均取得単価で計算）
                            avg_cost = total_principal / (total_quantity + quantity) if (total_quantity + quantity) > 0 else 0
                            total_principal -= avg_cost * quantity
            
            # 現在の保有数量
            current_quantity = total_quantity
            
            # コインの現在価格を取得
            current_price = current_prices.get(coin, 0)
            
            # 現在の評価額
            current_value = current_quantity * current_price
            
            # 平均取得単価
            avg_price = total_principal / total_quantity if total_quantity > 0 else 0
            
            # 含み益
            unrealized_profit = current_value - total_principal
            
            results[coin] = {
                'principal': total_principal,
                'quantity': current_quantity,  # 丸めを行わない
                'avg_price': avg_price,
                'current_value': current_value,
                'unrealized_profit': unrealized_profit,
                'realized_profit': realized_profit
            }
        
        return results
    
    def _analyze_mercari_data(self, df, year):
        """メルカリデータの分析"""
        if df.empty:
            return {}
            
        results = {}
        current_prices = self._get_current_prices()
        
        # 各コインごとに分析
        for coin in df['銘柄名'].unique():
            if pd.isna(coin) or coin == 'JPY':
                continue  # 無効なコインや日本円は分析対象外
                
            coin_df = df[df['銘柄名'] == coin].copy()
            
            # 買いと売りのトランザクションを抽出
            buy_transactions = coin_df[(coin_df['売買区分'] == '買')]
            sell_transactions = coin_df[(coin_df['売買区分'] == '売')]
            
            # 買いトランザクションから投資元本と取得数量を計算
            total_quantity = 0
            total_principal = 0
            
            for _, row in buy_transactions.iterrows():
                quantity = row.get('約定数量', 0)
                if pd.notna(quantity) and quantity > 0:
                    total_quantity += quantity
                    
                    # 金額を取得
                    amount = 0
                    if pd.notna(row.get('約定金額')):
                        amount = row.get('約定金額')
                    
                    # 手数料を考慮
                    fee = 0
                    if pd.notna(row.get('注文手数料')):
                        fee = row.get('注文手数料')
                        
                    total_principal += amount + fee
            
            # 売りトランザクションから売却数量を計算
            sold_quantity = 0
            realized_profit = 0
            
            for _, row in sell_transactions.iterrows():
                quantity = row.get('約定数量', 0)
                if pd.notna(quantity) and quantity > 0:
                    sold_quantity += quantity
                    
                    # 売却金額
                    sale_amount = 0
                    if pd.notna(row.get('約定金額')):
                        sale_amount = row.get('約定金額')
                    
                    # 手数料を考慮
                    fee = 0
                    if pd.notna(row.get('注文手数料')):
                        fee = row.get('注文手数料')
                        
                    # 確定利益に追加
                    realized_profit += sale_amount - fee
                    
                    # 元本の調整（売却分の元本を減らす）
                    if total_quantity > 0:
                        # 売却分の元本を減らす（平均取得単価で計算）
                        avg_cost = total_principal / (total_quantity + quantity) if (total_quantity + quantity) > 0 else 0
                        total_principal -= avg_cost * quantity
                        total_quantity -= quantity
            
            # 現在の保有数量
            current_quantity = total_quantity
            
            # コインの現在価格を取得
            current_price = current_prices.get(coin, 0)
            
            # 現在の評価額
            current_value = current_quantity * current_price
            
            # 平均取得単価
            avg_price = total_principal / total_quantity if total_quantity > 0 else 0
            
            # 含み益
            unrealized_profit = current_value - total_principal
            
            results[coin] = {
                'principal': total_principal,
                'quantity': current_quantity,  # 丸めを行わない
                'avg_price': avg_price,
                'current_value': current_value,
                'unrealized_profit': unrealized_profit,
                'realized_profit': realized_profit
            }
            
        return results
        
    def get_distribution_data(self, coin, current_price):
        """価格分布データを取得"""
        # 全データを取得
        all_data = self.data_loader.filter_data_by_year('all')
        distribution_data = []
        
        # GMOデータの分析
        if not all_data['gmo'].empty:
            gmo_df = all_data['gmo'].copy()
            coin_df = gmo_df[gmo_df['銘柄名'] == coin]
            buy_transactions = coin_df[(coin_df['売買区分'] == '買')]
            
            for _, row in buy_transactions.iterrows():
                quantity = row.get('約定数量', 0)
                rate = row.get('約定レート', 0)
                
                if pd.notna(quantity) and pd.notna(rate) and quantity > 0 and rate > 0:
                    distribution_data.append({
                        'quantity': quantity,
                        'price': rate
                    })
        
        # メルカリデータの分析
        if not all_data['mercari'].empty:
            mercari_df = all_data['mercari'].copy()
            coin_df = mercari_df[mercari_df['銘柄名'] == coin]
            buy_transactions = coin_df[(coin_df['売買区分'] == '買')]
            
            for _, row in buy_transactions.iterrows():
                quantity = row.get('約定数量', 0)
                rate = row.get('約定レート', 0)
                
                if pd.notna(quantity) and pd.notna(rate) and quantity > 0 and rate > 0:
                    distribution_data.append({
                        'quantity': quantity,
                        'price': rate
                    })
        
        # 平均取得単価を計算
        total_quantity = sum(item['quantity'] for item in distribution_data)
        total_cost = sum(item['quantity'] * item['price'] for item in distribution_data)
        avg_price = total_cost / total_quantity if total_quantity > 0 else 0
        
        return {
            'distribution': distribution_data,
            'avg_price': avg_price,
            'current_price': current_price,
            'total_quantity': total_quantity,
            'current_value': total_quantity * current_price
        }
        
    def calculate_scenario(self, coin, current_price, additional_quantity):
        """追加購入シナリオの計算"""
        # 現在の状況を取得
        current_data = self.get_distribution_data(coin, current_price)
        
        # 現在のデータ
        current_quantity = current_data['total_quantity']
        current_avg_price = current_data['avg_price']
        current_total_cost = current_quantity * current_avg_price
        
        # 追加購入後のデータ
        new_quantity = current_quantity + additional_quantity
        new_total_cost = current_total_cost + (additional_quantity * current_price)
        new_avg_price = new_total_cost / new_quantity if new_quantity > 0 else 0
        new_value = new_quantity * current_price
        
        return {
            'current': {
                'quantity': current_quantity,
                'avg_price': current_avg_price,
                'total_cost': current_total_cost,
                'value': current_quantity * current_price
            },
            'new': {
                'quantity': new_quantity,
                'avg_price': new_avg_price,
                'total_cost': new_total_cost,
                'value': new_value
            },
            'change': {
                'quantity': additional_quantity,
                'avg_price': new_avg_price - current_avg_price,
                'total_cost': new_total_cost - current_total_cost,
                'value': new_value - (current_quantity * current_price)
            }
        }

    def _get_current_prices(self) -> Dict[str, float]:
        """現在の価格を取得する"""
        return self.current_prices

    def set_current_prices(self, prices: Dict[str, float]):
        """現在の価格を設定する"""
        self.current_prices = prices 