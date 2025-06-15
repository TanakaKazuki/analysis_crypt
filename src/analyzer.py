import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict


class CryptoAnalyzer:
    def __init__(self, data_loader):
        self.data_loader = data_loader
        self.transaction_data = None
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
        if self.transaction_data is None:
            self.transaction_data = self.data_loader.load_transaction_data()
        
        # 年でフィルタリング
        filtered_data = self.data_loader.filter_data_by_year(year)
        
        # データの分析
        results = self._analyze_data(filtered_data, year)
        
        return results
    
    def calculate_yearly_profit(self):
        """年ごとの確定利益を計算（移動平均法）"""
        yearly_profits = {}
        yearly_coin_profits = {}
        
        # 全データを取得
        all_data = self.data_loader.filter_data_by_year('all')
        
        if not all_data.empty and '日時' in all_data.columns:
            all_data['年'] = pd.to_datetime(all_data['日時'], errors='coerce').dt.year
            
            # 取引データを日時順にソート
            all_data = all_data.sort_values('日時')
            
            # コインごとの取得原価と平均単価を追跡
            coin_holdings = {}  # {coin: {'quantity': 総数量, 'total_cost': 総コスト}}
            
            # 移動平均法での利益計算
            for _, row in all_data.iterrows():
                coin = row['銘柄名']
                if coin == 'JPY':  # 日本円は除外
                    continue
                
                year = row['年']
                if year not in yearly_profits:
                    yearly_profits[year] = 0
                    yearly_coin_profits[year] = {}
                
                if coin not in yearly_coin_profits[year]:
                    yearly_coin_profits[year][coin] = 0
                
                # コインの保有状況を初期化
                if coin not in coin_holdings:
                    coin_holdings[coin] = {'quantity': 0, 'total_cost': 0}
                
                # ステーキング報酬の処理
                if row['精算区分'] == '暗号資産預入・送付' and row['授受区分'] == '預入':
                    if pd.notna(row['数量']) and row['数量'] > 0:
                        coin_holdings[coin]['quantity'] += float(row['数量'])
                    # ステーキング報酬は元本に加算しない（0円で取得）
                    continue
                
                # ステーキング手数料の処理
                if row['精算区分'] == '暗号資産預入・送付' and row['授受区分'] == '送付':
                    if pd.notna(row['数量']) and row['数量'] > 0:
                        coin_holdings[coin]['quantity'] -= float(row['数量'])
                    # ステーキング手数料は元本に影響しない
                    continue
                
                # 取引所現物取引手数料返金の処理
                if row['精算区分'] == '取引所現物 取引手数料返金':
                    # 手数料返金は元本を減らす（コスト減少）
                    if pd.notna(row['日本円受渡金額']) and row['日本円受渡金額'] > 0:
                        coin_holdings[coin]['total_cost'] -= float(row['日本円受渡金額'])
                    continue
                
                # 購入の処理
                if row['売買区分'] == '買':
                    quantity = 0
                    cost = 0
                    
                    # 販売所取引の処理
                    if '販売所取引' in str(row['精算区分']):
                        # 販売所取引では日本円受渡金額から取得
                        if pd.notna(row['日本円受渡金額']):
                            cost = abs(float(row['日本円受渡金額']))
                            
                            if pd.notna(row['約定数量']):
                                quantity = float(row['約定数量'])
                            elif pd.notna(row['数量']):
                                quantity = float(row['数量'])
                            else:
                                # 数量が不明な場合はスキップ
                                continue
                    
                    # 取引所現物取引の処理
                    elif '取引所現物取引' in str(row['精算区分']):
                        if pd.notna(row['約定数量']):
                            quantity = float(row['約定数量'])
                        
                        if pd.notna(row['約定レート']) and pd.notna(row['約定数量']):
                            price = float(row['約定レート'])
                            cost = quantity * price
                        
                        if pd.notna(row['注文手数料']):
                            cost += float(row['注文手数料'])
                    
                    # 保有数量と総コストを更新
                    if quantity > 0:
                        coin_holdings[coin]['quantity'] += quantity
                        coin_holdings[coin]['total_cost'] += cost
                
                # 売却の処理
                elif row['売買区分'] == '売' and ('取引所現物取引' in str(row['精算区分']) or '販売所取引' in str(row['精算区分'])):
                    quantity = 0
                    sale_amount = 0
                    
                    # 販売所取引の処理
                    if '販売所取引' in str(row['精算区分']):
                        if pd.notna(row['日本円受渡金額']):
                            sale_amount = float(row['日本円受渡金額'])
                            
                            if pd.notna(row['約定数量']):
                                quantity = float(row['約定数量'])
                            elif pd.notna(row['数量']):
                                quantity = float(row['数量'])
                            else:
                                # 数量が不明な場合はスキップ
                                continue
                    
                    # 取引所現物取引の処理
                    elif '取引所現物取引' in str(row['精算区分']):
                        if pd.notna(row['約定数量']):
                            quantity = float(row['約定数量'])
                        
                        if pd.notna(row['日本円受渡金額']):
                            sale_amount = float(row['日本円受渡金額'])
                        elif pd.notna(row['約定レート']) and pd.notna(row['約定数量']):
                            price = float(row['約定レート'])
                            sale_amount = quantity * price
                        
                        if pd.notna(row['注文手数料']):
                            sale_amount -= float(row['注文手数料'])
                    
                    # 移動平均法による利益計算
                    if quantity > 0 and coin_holdings[coin]['quantity'] > 0:
                        # 平均取得単価
                        avg_cost = coin_holdings[coin]['total_cost'] / coin_holdings[coin]['quantity'] if coin_holdings[coin]['quantity'] > 0 else 0
                        
                        # 売却分の原価
                        cost_of_sold = avg_cost * quantity
                        
                        # 利益計算
                        profit = sale_amount - cost_of_sold
                        
                        # 年間・コインごとの利益に加算
                        yearly_profits[year] += profit
                        yearly_coin_profits[year][coin] += profit
                        
                        # 保有数量と総コストを更新
                        coin_holdings[coin]['quantity'] -= quantity
                        coin_holdings[coin]['total_cost'] -= cost_of_sold
        
        return yearly_profits, yearly_coin_profits
    
    def _analyze_data(self, data: pd.DataFrame, year: int) -> Dict[str, Dict[str, float]]:
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
        
    def get_distribution_data(self, coin, current_price):
        """価格分布データを取得"""
        # 全データを取得
        all_data = self.data_loader.filter_data_by_year('all')
        distribution_data = []
        
        if not all_data.empty:
            coin_df = all_data[all_data['銘柄名'] == coin]
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
        
    def calculate_scenario_by_amount(self, coin, current_price, additional_amount):
        """金額ベースの追加購入シナリオの計算"""
        # 現在の状況を取得
        current_data = self.get_distribution_data(coin, current_price)
        
        # 現在のデータ
        current_quantity = current_data['total_quantity']
        current_avg_price = current_data['avg_price']
        current_total_cost = current_quantity * current_avg_price
        
        # 追加購入数量を計算（金額 ÷ 現在価格）
        additional_quantity = additional_amount / current_price if current_price > 0 else 0
        
        # 追加購入後のデータ
        new_quantity = current_quantity + additional_quantity
        new_total_cost = current_total_cost + additional_amount
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
                'total_cost': additional_amount,
                'value': new_value - (current_quantity * current_price)
            },
            'additional_amount': additional_amount
        }

    def _get_current_prices(self) -> Dict[str, float]:
        """現在の価格を取得する"""
        return self.current_prices

    def set_current_prices(self, prices: Dict[str, float]):
        """現在の価格を設定する"""
        self.current_prices = prices 