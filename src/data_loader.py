import os
import pandas as pd
from datetime import datetime
import json
from typing import Dict


class DataLoader:
    def __init__(self, resource_dir='resource'):
        self.resource_dir = resource_dir
        self.gmo_dir = os.path.join(resource_dir, 'gmo')
        self.mercari_dir = os.path.join(resource_dir, 'mercari')
        self.checkpoint_dir = os.path.join('src', 'checkpoints')
        
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)
            
        self.checkpoint_file = os.path.join(self.checkpoint_dir, 'price_history.json')
        self.gmo_data = None
        self.mercari_data = None
        
    def load_gmo_data(self) -> pd.DataFrame:
        """GMOの取引データを読み込む"""
        if self.gmo_data is None:
            # 利用可能なGMOデータファイルを検索
            gmo_files = []
            
            # resourceディレクトリ内のファイルを検索
            if os.path.exists(self.gmo_dir):
                gmo_files = [os.path.join(self.gmo_dir, f) for f in os.listdir(self.gmo_dir) if f.endswith('.csv')]
                
            if not gmo_files:
                self.gmo_data = pd.DataFrame()
                return self.gmo_data
            
            # 各ファイルを読み込んで結合
            dfs = []
            for file in gmo_files:
                try:
                    df = pd.read_csv(file)
                    dfs.append(df)
                except Exception as e:
                    print(f"GMOデータ読み込みエラー: {e}")
            
            if not dfs:
                self.gmo_data = pd.DataFrame()
                return self.gmo_data
            
            # データを結合
            self.gmo_data = pd.concat(dfs, ignore_index=True)
            
            # 日時をdatetime型に変換
            if '日時' in self.gmo_data.columns:
                self.gmo_data['日時'] = pd.to_datetime(self.gmo_data['日時'], format='%Y/%m/%d %H:%M', errors='coerce')
            
            # 数値カラムをfloat型に変換
            numeric_columns = ['約定数量', '約定レート', '約定金額', '注文手数料', 'レバレッジ手数料', '入出金金額', '数量', '送付手数料']
            for col in numeric_columns:
                if col in self.gmo_data.columns:
                    self.gmo_data[col] = pd.to_numeric(self.gmo_data[col], errors='coerce')
        
        return self.gmo_data

    def load_mercari_data(self) -> pd.DataFrame:
        """メルカリの取引データを読み込む"""
        if self.mercari_data is None:
            # 利用可能なメルカリデータファイルを検索
            mercari_files = []
            
            # resourceディレクトリ内のファイルを検索
            if os.path.exists(self.mercari_dir):
                mercari_files = [os.path.join(self.mercari_dir, f) for f in os.listdir(self.mercari_dir) if f.endswith('.csv')]
            
            # 開発用: srcディレクトリにあるファイルも使用
            src_mercari_file = os.path.join('src', 'transactions_mercari.csv')
            if os.path.exists(src_mercari_file):
                mercari_files.append(src_mercari_file)
            
            if not mercari_files:
                self.mercari_data = pd.DataFrame()
                return self.mercari_data
            
            # 各ファイルを読み込んで結合
            dfs = []
            for file in mercari_files:
                try:
                    df = pd.read_csv(file)
                    dfs.append(df)
                except Exception as e:
                    print(f"メルカリデータ読み込みエラー: {e}")
            
            if not dfs:
                self.mercari_data = pd.DataFrame()
                return self.mercari_data
            
            # データを結合
            self.mercari_data = pd.concat(dfs, ignore_index=True)
            
            # 日時をdatetime型に変換
            if '日時' in self.mercari_data.columns:
                self.mercari_data['日時'] = pd.to_datetime(self.mercari_data['日時'], format='%Y/%m/%d %H:%M', errors='coerce')
            
            # 数値カラムをfloat型に変換
            numeric_columns = ['数量', '価格', '手数料', '約定数量', '約定レート', '約定金額', '注文手数料', 'レバレッジ手数料']
            for col in numeric_columns:
                if col in self.mercari_data.columns:
                    self.mercari_data[col] = pd.to_numeric(self.mercari_data[col], errors='coerce')
        
        return self.mercari_data

    def filter_data_by_year(self, year: int) -> Dict[str, pd.DataFrame]:
        """指定された年のデータをフィルタリングする"""
        gmo_data = self.load_gmo_data()
        mercari_data = self.load_mercari_data()
        
        result = {
            'gmo': pd.DataFrame(),
            'mercari': pd.DataFrame()
        }
        
        # 'all' の場合は全データを返す
        if year == 'all':
            result = {
                'gmo': gmo_data.copy() if not gmo_data.empty else pd.DataFrame(),
                'mercari': mercari_data.copy() if not mercari_data.empty else pd.DataFrame()
            }
            return result
        else:
            # GMOデータのフィルタリング
            if not gmo_data.empty and '日時' in gmo_data.columns:
                result['gmo'] = gmo_data[gmo_data['日時'].dt.year == year]
            
            # メルカリデータのフィルタリング
            if not mercari_data.empty and '日時' in mercari_data.columns:
                result['mercari'] = mercari_data[mercari_data['日時'].dt.year == year]
        
        return result
        
    def get_years(self):
        """利用可能な年のリストを返す"""
        years = set()
        
        # GMOデータから年を抽出
        gmo_data = self.load_gmo_data()
        if not gmo_data.empty and '日時' in gmo_data.columns:
            years.update(gmo_data['日時'].dt.year.unique())
        
        # メルカリデータから年を抽出
        mercari_data = self.load_mercari_data()
        if not mercari_data.empty and '日時' in mercari_data.columns:
            years.update(mercari_data['日時'].dt.year.unique())
        
        years = sorted(list(years))
        years.append('all')  # 全期間のオプション
        return years
    
    def get_coins(self):
        """取引されたコインの一覧を返す"""
        coins = set()
        
        # GMOデータからコイン一覧を抽出
        gmo_data = self.load_gmo_data()
        if not gmo_data.empty and '銘柄名' in gmo_data.columns:
            coins.update(gmo_data['銘柄名'].unique())
        
        # メルカリデータからコイン一覧を抽出
        mercari_data = self.load_mercari_data()
        if not mercari_data.empty and '銘柄名' in mercari_data.columns:
            coins.update(mercari_data['銘柄名'].unique())
                
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