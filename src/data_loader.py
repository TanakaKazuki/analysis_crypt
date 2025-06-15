import os
import pandas as pd
from datetime import datetime
import json
from typing import Dict
import glob


class DataLoader:
    def __init__(self, resource_dir='resource'):
        self.resource_dir = resource_dir
        self.checkpoint_dir = os.path.join('src', 'checkpoints')
        
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)
            
        self.checkpoint_file = os.path.join(self.checkpoint_dir, 'price_history.json')
        self.transaction_data = None
        
    def load_transaction_data(self) -> pd.DataFrame:
        """resource配下のすべての取引データを読み込む"""
        if self.transaction_data is None:
            # 利用可能なCSVファイルを検索
            csv_files = []
            
            # resourceディレクトリ内のすべてのCSVファイルを再帰的に検索
            if os.path.exists(self.resource_dir):
                csv_files = glob.glob(os.path.join(self.resource_dir, '**', '*.csv'), recursive=True)
                
            if not csv_files:
                self.transaction_data = pd.DataFrame()
                return self.transaction_data
            
            # 各ファイルを読み込んで結合
            dfs = []
            for file in csv_files:
                try:
                    df = pd.read_csv(file)
                    # ファイルの出所情報を追加
                    source_path = os.path.relpath(file, self.resource_dir)
                    source_dir = os.path.dirname(source_path)
                    df['データ元'] = source_dir if source_dir else 'root'
                    dfs.append(df)
                except Exception as e:
                    print(f"データ読み込みエラー: {e} - ファイル: {file}")
            
            if not dfs:
                self.transaction_data = pd.DataFrame()
                return self.transaction_data
            
            # データを結合
            self.transaction_data = pd.concat(dfs, ignore_index=True)
            
            # 日時をdatetime型に変換
            if '日時' in self.transaction_data.columns:
                self.transaction_data['日時'] = pd.to_datetime(self.transaction_data['日時'], format='%Y/%m/%d %H:%M', errors='coerce')
            
            # 数値カラムをfloat型に変換
            numeric_columns = ['約定数量', '約定レート', '約定金額', '注文手数料', 'レバレッジ手数料', '入出金金額', '数量', '送付手数料']
            for col in numeric_columns:
                if col in self.transaction_data.columns:
                    self.transaction_data[col] = pd.to_numeric(self.transaction_data[col], errors='coerce')
        
        return self.transaction_data

    def filter_data_by_year(self, year: int) -> pd.DataFrame:
        """指定された年のデータをフィルタリングする"""
        data = self.load_transaction_data()
        
        # 'all' の場合は全データを返す
        if year == 'all' or data.empty or '日時' not in data.columns:
            return data.copy() if not data.empty else pd.DataFrame()
        else:
            # 年でフィルタリング
            return data[data['日時'].dt.year == year]
        
    def get_years(self):
        """利用可能な年のリストを返す"""
        years = set()
        
        # データから年を抽出
        data = self.load_transaction_data()
        if not data.empty and '日時' in data.columns:
            years.update(data['日時'].dt.year.unique())
        
        years = sorted(list(years))
        years.append('all')  # 全期間のオプション
        return years
    
    def get_coins(self):
        """取引されたコインの一覧を返す"""
        coins = set()
        
        # データからコイン一覧を抽出
        data = self.load_transaction_data()
        if not data.empty and '銘柄名' in data.columns:
            coins.update(data['銘柄名'].unique())
                
        # JPYを除外（円での入出金記録）
        if 'JPY' in coins:
            coins.remove('JPY')
            
        return list(coins)
    
    def save_checkpoint(self, prices, metrics):
        """現在の価格とメトリクスをチェックポイントとして保存"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 既存のチェックポイントを読み込む
        checkpoints = []
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                try:
                    checkpoints = json.load(f)
                except json.JSONDecodeError:
                    checkpoints = []
        
        # 新しいチェックポイントを追加
        checkpoint = {
            'timestamp': timestamp,
            'prices': prices,
            'metrics': metrics
        }
        checkpoints.append(checkpoint)
        
        # チェックポイントを保存
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoints, f, ensure_ascii=False, indent=2)
            
        return timestamp
    
    def load_checkpoints(self):
        """保存されたチェックポイントを読み込む"""
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return []
        return [] 