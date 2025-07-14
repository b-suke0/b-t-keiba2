#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
競馬データ専用整理ツール
netkeiba等の競馬データを完璧に構造化・整理するツール
"""

import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime
import json

class KeibaDataOrganizer:
    """競馬データ専用の整理クラス"""
    
    def __init__(self):
        self.race_info = {}
        self.horses_data = []
        self.training_data = []
    
    def parse_keiba_data(self, text):
        """競馬データを詳細解析"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 調教データセクションを除外
        filtered_lines = self.filter_training_section(lines)
        
        # レース基本情報を抽出
        self.race_info = self.extract_race_info(filtered_lines)
        
        # 馬データを抽出
        self.horses_data = self.extract_horses_data(filtered_lines)
        
        # 調教データを抽出
        self.training_data = self.extract_training_data(lines)
        
        return {
            'race_info': self.race_info,
            'horses_data': self.horses_data,
            'training_data': self.training_data
        }
    
    def filter_training_section(self, lines):
        """調教データセクションを除外"""
        filtered_lines = []
        skip_training_data = False
        
        for i, line in enumerate(lines):
            # 調教タイムセクションヘッダーを検出
            if '調教タイム' in line:
                skip_training_data = True
                continue
            
            # 調教セクション内のヘッダー行を検出
            if (skip_training_data or 
                re.search(r'枠\s+馬\s*番.*馬名.*日付.*コース.*馬場.*乗り役', line)):
                skip_training_data = True
                continue
            
            # 調教データっぽい行をスキップ
            if skip_training_data:
                # 調教データのパターンをチェック
                training_patterns = [
                    r'前走.*\d{4}/\d{2}/\d{2}.*美[坂Ｗ]',  # 前走 日付 美坂/美W
                    r'美[坂Ｗ].*良.*[助手騎手杉原内田]',      # 美坂/美W 良 助手/騎手
                    r'^\d+\.\d+$',                        # タイム単体
                    r'^\(\d+\.\d+\)$',                    # ラップタイム
                    r'外.*強め.*併せ.*秒.*先着',            # 併せ馬コメント
                    r'^\d+\s+[ＧＢＣ]強\s+動き.*[ＢＣ]$',    # 評価行
                    r'提供：デイリースポーツ',               # 提供者情報
                    r'すべての最終調教を見る',               # リンク
                    r'^-$',                              # ハイフン単体
                    r'ラップ表示',                        # ラップ表示ヘッダー
                    r'位置\s+脚色\s+評価',                # 評価ヘッダー
                    r'まずまず|動き上々',                  # 評価コメント
                ]
                
                is_training_data = False
                for pattern in training_patterns:
                    if re.search(pattern, line):
                        is_training_data = True
                        break
                
                if is_training_data:
                    continue
                
                # セクション終了の判定
                # 新しいページセクション開始 or 他のセクション開始
                if (any(keyword in line for keyword in [
                    'いま競輪が熱い', 'netkeiba', '利用者数', 'カテゴリ', 
                    'ニュース', 'レース', 'お気に入り馬', '検索バー', 
                    'みんなで一緒に競馬', 'URL', '© NET DREAMERS'
                ])):
                    skip_training_data = False
                    # これらの行も除外
                    continue
                
                # 通常データの再開（次の馬のデータなど）
                if re.match(r'^\d+\s+\d+\s*$', line):
                    skip_training_data = False
                    filtered_lines.append(line)
                # レース情報の再開
                elif any(keyword in line for keyword in ['発走', 'R', '歳以上', 'クラス']):
                    skip_training_data = False
                    filtered_lines.append(line)
                else:
                    # 調教セクション内の不明な行は除外
                    continue
            else:
                filtered_lines.append(line)
        
        return filtered_lines
    
    def extract_race_info(self, lines):
        """レース基本情報を抽出"""
        race_info = {
            'race_number': '',
            'race_name': '',
            'date': '',
            'time': '',
            'venue': '',
            'course_type': '',
            'distance': '',
            'direction': '',
            'weather': '',
            'track_condition': '',
            'grade': '',
            'prize_money': '',
            'entry_count': ''
        }
        
        for line in lines:
            # レース番号
            if re.search(r'^\d+R$', line.strip()):
                race_info['race_number'] = line.strip()
            
            # レース名（特別レース名を優先、条件レースは補助的に）
            # レース名が未設定の場合のみ設定
            if not race_info['race_name']:
                # サイト関連用語の除外
                site_terms = [
                    'netkeiba', 'netkeibaTV', '馬名で検索', 'お気に入り馬', 'メモ', 'アカウント',
                    'LIVE競輪', 'トップ', 'ニュース', 'レース', 'A I', '予想', 'UMAIビルダー',
                    'コラム', '地方競馬', 'データベース', 'ショップ', '競馬新聞', '俺プロ',
                    '一口馬主', 'POG', 'まとめ', '前', '次', '福島', '小倉', '函館'
                ]
                
                if line.strip() in site_terms:
                    continue
                
                # 特別レース名（G1、G2、G3、OP、S、杯、賞、記念などを含むレース）
                if (re.search(r'[GSL]$', line.strip()) or 
                    (re.search(r'[杯記念]', line) and not re.search(r'本賞金|賞金', line)) or
                    (len(line.strip()) <= 10 and 
                     not re.search(r'[0-9:]|発走|天候|馬場|回|日目|頭|万円|takashi|さん', line))):
                    race_info['race_name'] = line.strip()
            
            # 条件レース（特別レース名がない場合のみ）
            elif not race_info['race_name'] and re.search(r'[3-9]歳以上.*クラス', line):
                race_info['race_name'] = line.strip()
            
            # 発走時刻・距離・コース・天候（1行にまとまっている）
            if '発走' in line and 'm' in line:
                # 発走時刻
                time_match = re.search(r'(\d{1,2}:\d{2})発走', line)
                if time_match:
                    race_info['time'] = time_match.group(1)
                
                # 距離・コース
                distance_match = re.search(r'([ダ芝])(\d+)m', line)
                if distance_match:
                    race_info['course_type'] = distance_match.group(1)
                    race_info['distance'] = distance_match.group(2) + 'm'
                
                # 方向（「右 B」のような場合でも「右」のみ抽出）
                direction_match = re.search(r'\(([右左])', line)
                if direction_match:
                    race_info['direction'] = direction_match.group(1)
                
                # 天候
                weather_match = re.search(r'天候:([^/]+)', line)
                if weather_match:
                    race_info['weather'] = weather_match.group(1).strip()
                
                # 馬場状態
                condition_match = re.search(r'馬場:(\S+)', line)
                if condition_match:
                    race_info['track_condition'] = condition_match.group(1).strip()
            
            # 開催情報（○回○○○日目）
            if re.search(r'\d+回.*\d+日目', line):
                race_info['venue'] = line.strip()
            
            # 頭数（15頭など）
            if re.search(r'\s+(\d+)頭$', line):
                entry_match = re.search(r'(\d+)頭', line)
                if entry_match:
                    race_info['entry_count'] = entry_match.group(1) + '頭'
            
            # 賞金
            if '本賞金:' in line:
                race_info['prize_money'] = line.strip()
        
        return race_info
    
    def extract_horses_data(self, lines):
        """馬データを詳細抽出"""
        horses = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 枠番・馬番の検出（"1    1" のような形式）
            frame_horse_match = re.match(r'^(\d+)\s+(\d+)\s*$', line.strip())
            if frame_horse_match:
                # 新しい馬のデータを開始
                horse_data = {
                    'frame_number': frame_horse_match.group(1),
                    'horse_number': frame_horse_match.group(2),
                    'horse_name': '',
                    'father': '',
                    'mother': '',
                    'mother_father': '',
                    'trainer': '',
                    'jockey': '',
                    'weight': '',
                    'age': '',
                    'sex': '',
                    'coat_color': '',
                    'odds': '',
                    'popularity': '',
                    'past_races': [],
                    'stable_type': '',
                    'recent_form': '',
                    'load_weight': ''
                }
                
                # 枠番・馬番の次の行から情報を順次抽出
                j = i + 1
                
                # 1. 父名（次の行）
                if j < len(lines) and lines[j].strip():
                    horse_data['father'] = lines[j].strip()
                    j += 1
                
                # 2. 馬名（その次の行、しばしば"B"が付く）
                if j < len(lines) and lines[j].strip():
                    horse_name = lines[j].strip()
                    # "B"を除去（ブリンカー等の記号）
                    horse_name = re.sub(r'B$', '', horse_name)
                    horse_data['horse_name'] = horse_name
                    j += 1
                
                # 3. 母名（その次の行）
                if j < len(lines) and lines[j].strip():
                    horse_data['mother'] = lines[j].strip()
                    j += 1
                
                # 4. 母父名（括弧内）
                if j < len(lines) and lines[j].strip():
                    mother_father_line = lines[j].strip()
                    mother_father_match = re.search(r'\(([^)]+)\)', mother_father_line)
                    if mother_father_match:
                        horse_data['mother_father'] = mother_father_match.group(1)
                    j += 1
                
                # 5. 厩舎情報（美浦・調教師名）
                if j < len(lines) and ('美浦' in lines[j] or '栗東' in lines[j]):
                    stable_line = lines[j].strip()
                    stable_match = re.search(r'(美浦|栗東)・(.+)', stable_line)
                    if stable_match:
                        horse_data['stable_type'] = stable_match.group(1)
                        horse_data['trainer'] = stable_match.group(2).strip()
                    j += 1
                
                # 次の数行で残りの情報を抽出（馬のデータが終わるまで）
                k = j
                while k < len(lines):
                    current_line = lines[k].strip()
                    
                    # 次の馬のデータ開始を検出したら停止
                    if re.match(r'^(\d+)\s+(\d+)\s*$', current_line):
                        break
                    
                    if not current_line:
                        k += 1
                        continue
                    
                    # 馬体重
                    weight_match = re.search(r'(\d+)kg\(([+-]?\d+)\)', current_line)
                    if weight_match and not horse_data['weight']:
                        horse_data['weight'] = f"{weight_match.group(1)}kg({weight_match.group(2)})"
                        k += 1
                        continue
                    
                    # オッズ・人気（"32.1 (9人気)"の形式）
                    odds_popularity_match = re.search(r'(\d+\.\d+)\s+\((\d+)人気\)', current_line)
                    if odds_popularity_match and not horse_data['odds']:
                        horse_data['odds'] = odds_popularity_match.group(1)
                        horse_data['popularity'] = odds_popularity_match.group(2) + '番人気'
                        k += 1
                        continue
                    
                    # 年齢・性別・毛色（"牡4栗"の形式）
                    age_sex_color_match = re.search(r'^([牡牝セ])(\d+)(.+)$', current_line)
                    if age_sex_color_match and not horse_data['age']:
                        horse_data['sex'] = age_sex_color_match.group(1)
                        horse_data['age'] = age_sex_color_match.group(2) + '歳'
                        horse_data['coat_color'] = age_sex_color_match.group(3)
                        
                        # 年齢・性別・毛色行の次の行が騎手名
                        if k + 1 < len(lines) and lines[k + 1].strip():
                            next_line = lines[k + 1].strip()
                            # その次の行が負担重量（数字.数字）かチェック
                            if k + 2 < len(lines) and re.search(r'^\d+\.\d+$', lines[k + 2].strip()):
                                horse_data['jockey'] = next_line
                        
                        k += 1
                        continue
                    
                    # 負担重量（"58.0"の単独行）
                    load_weight_match = re.search(r'^(\d+\.\d+)$', current_line)
                    if load_weight_match and not horse_data['load_weight']:
                        horse_data['load_weight'] = load_weight_match.group(1) + 'kg'
                        k += 1
                        continue
                    
                    # 過去のレース成績
                    if re.search(r'\d{4}\.\d{2}\.\d{2}', current_line):
                        # より多くの行を含めて勝ち馬名も確実に取得
                        race_result = self.parse_past_race(current_line, lines[k:k+8])
                        if race_result:
                            horse_data['past_races'].append(race_result)
                    
                    k += 1
                
                horses.append(horse_data)
                i = k  # 次の馬の開始位置に移動
            else:
                i += 1
        
        return horses
    
    def parse_past_race(self, race_line, context_lines):
        """過去のレース情報を解析"""
        # print(f"DEBUG: レース解析開始 - race_line='{race_line}'")
        # print(f"DEBUG: context_lines 数: {len(context_lines)}")
        # for i, line in enumerate(context_lines):
        #     print(f"DEBUG: context_lines[{i}]: '{line}'")
        race_result = {
            'date': '',
            'venue': '',
            'race_name': '',
            'course_info': '',
            'finish_position': '',
            'passage_position': '',
            'field_size': '',
            'popularity': '',
            'jockey': '',
            'weight': '',
            'time': '',
            'track_condition': '',
            'winner_name': '',
            'time_diff': ''
        }
        
        # 日付抽出
        date_match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})', race_line)
        if date_match:
            race_result['date'] = f"{date_match.group(1)}/{date_match.group(2)}/{date_match.group(3)}"
        
        # 競馬場の抽出（JRA競馬場 + 地方競馬場）
        jra_venues = ['東京', '中山', '阪神', '京都', '新潟', '福島', '小倉', '札幌', '函館', '中京']
        local_venues = ['佐賀', '笠松', '園田', '姫路', '高知', '金沢', '浦和', '船橋', '大井', '川崎', '盛岡', '水沢', '門別']
        all_venues = jra_venues + local_venues
        
        # 競馬場名を抽出（日付行から）
        # "2025.05.18 佐賀1" → 競馬場: 佐賀, レース: 1
        venue_match = re.search(r'\d{4}\.\d{2}\.\d{2}\s+(.+?)(\d+)', race_line)
        if venue_match:
            venue_name = venue_match.group(1).strip()
            # 完全一致する競馬場名を検索
            for venue in all_venues:
                if venue == venue_name:
                    race_result['venue'] = venue
                    break
            # 部分一致でも検索
            if not race_result['venue']:
                for venue in all_venues:
                    if venue in venue_name:
                        race_result['venue'] = venue
                        break
        
        # 競馬場名が見つからない場合の補完検索
        if not race_result['venue']:
            for venue in all_venues:
                if venue in race_line:
                    race_result['venue'] = venue
                    break
        
        # 全ての行を結合してコンテキストを作成
        all_text = race_line + ' ' + ' '.join(context_lines)
        
        # コース情報・タイム抽出
        course_match = re.search(r'([ダ芝])(\d+)', all_text)
        if course_match:
            race_result['course_info'] = course_match.group(1) + course_match.group(2)
        
        time_match = re.search(r'(\d+:\d+\.\d+)', all_text)
        if time_match:
            race_result['time'] = time_match.group(1)
        
        # 天候状態
        condition_match = re.search(r'(良|稍重|重|不良)', all_text)
        if condition_match:
            race_result['track_condition'] = condition_match.group(1)
        
        # 頭数・馬番・人気の抽出（"15頭 4番 4人"の形式）
        # パターン1: "15頭 4番 4人 菅原明良 58.0"
        basic_info_pattern = re.search(r'(\d+)頭\s+(\d+)番\s+(\d+)人', all_text)
        if basic_info_pattern:
            race_result['field_size'] = basic_info_pattern.group(1) + '頭'
            # 4番は馬番なので、着順は別途検索
            race_result['popularity'] = basic_info_pattern.group(3) + '番人気'
        
        # 着順の抽出（競馬場名+数字パターンが最優先）
        # パターン1: "中京1", "小倉3" のような競馬場名+着順
        for venue in all_venues:
            pattern = rf'{venue}(\d+)'
            venue_match = re.search(pattern, race_line)
            if venue_match:
                race_result['finish_position'] = venue_match.group(1) + '着'
                break
        
        # 通過順位の抽出（参考情報として）
        # パターン1: "3-3-3-2" のような詳細通過順位
        detailed_passage = re.search(r'(\d+)-(\d+)-(\d+)-(\d+)', all_text)
        if detailed_passage:
            race_result['passage_position'] = detailed_passage.group(0)
        else:
            # パターン2: "4-3" のような簡易通過順位
            simple_passage = re.search(r'(\d+)-(\d+)', all_text)
            if simple_passage:
                race_result['passage_position'] = simple_passage.group(0)
        
        # 明示的な着順がある場合の別パターン（バックアップ）
        if not race_result['finish_position']:
            # "4着 16頭10番" のような形式
            alt_pattern = re.search(r'(\d+)着.*?(\d+)頭.*?(\d+)番', all_text)
            if alt_pattern:
                race_result['finish_position'] = alt_pattern.group(1) + '着'
                race_result['field_size'] = alt_pattern.group(2) + '頭'
                # 人気は別途検索
                pop_match = re.search(r'(\d+)番人気', all_text)
                if pop_match:
                    race_result['popularity'] = pop_match.group(1) + '番人気'
        
        # レース名抽出（JRA + 地方競馬場対応）
        for line in context_lines:
            # JRA競馬場のパターン
            if ('クラス' in line or '未勝利' in line or '特別' in line or 'S' in line or 
                'G' in line and ('I' in line or 'II' in line or 'III' in line)):
                race_result['race_name'] = line.strip()
                break
            # 地方競馬場のパターン（UMATE、C2ー7組、出雲杯・春など）
            elif (re.search(r'^[A-Z]+$', line) or  # UMATE
                  re.search(r'^C\d', line) or      # C2ー7組
                  '杯' in line or '賞' in line or '記念' in line or  # 出雲杯・春
                  'JRA' in line or '交流' in line):  # JRA交流戦
                race_result['race_name'] = line.strip()
                break
        
        # 勝ち馬とタイム差の抽出
        for line in context_lines:
            # "勝ち馬名(タイム差)" のパターンを検索
            # 通過順位（数字-数字）を除外し、日本語を含む馬名のみ抽出
            winner_diff_match = re.search(r'([^(]+)\(([0-9.-]+)\)', line)
            if winner_diff_match:
                winner_name = winner_diff_match.group(1).strip()
                time_diff_str = winner_diff_match.group(2)
                
                # デバッグ用出力
                # print(f"DEBUG: 行='{line}', 勝ち馬='{winner_name}', タイム差='{time_diff_str}'")
                
                # 通過順位パターン（数字-数字）を除外
                if re.match(r'^[\d-]+$', winner_name):
                    continue
                
                # 勝ち馬名が日本語やアルファベットを含む場合のみ処理
                if re.search(r'[あ-んア-ンー一-龯a-zA-Z]', winner_name):
                    race_result['winner_name'] = winner_name
                    
                    # タイム差の処理
                    if time_diff_str == "-":
                        race_result['time_diff'] = "-"  # 自分が1着
                    elif time_diff_str == "0.0":
                        race_result['time_diff'] = "0.0"  # 同着
                    else:
                        try:
                            diff_value = float(time_diff_str)
                            # 負の値も含めて正しくフォーマット
                            race_result['time_diff'] = f"{diff_value:.1f}"
                        except ValueError:
                            race_result['time_diff'] = time_diff_str
                    
                    # デバッグ用出力
                    # print(f"DEBUG: 設定完了 - winner_name='{race_result['winner_name']}', time_diff='{race_result['time_diff']}'")
                    break
        
        return race_result
    
    def extract_training_data(self, lines):
        """調教データを抽出"""
        training_data = []
        
        in_training_section = False
        for line in lines:
            if '調教タイム' in line:
                in_training_section = True
                continue
            
            if in_training_section and re.search(r'\d+\.\d+', line):
                training_info = {
                    'horse_name': '',
                    'date': '',
                    'course': '',
                    'condition': '',
                    'jockey': '',
                    'time': '',
                    'evaluation': ''
                }
                
                # 調教データの詳細解析
                parts = line.split()
                for part in parts:
                    if re.search(r'\d{4}/\d{2}/\d{2}', part):
                        training_info['date'] = part
                    elif re.search(r'\d+\.\d+', part):
                        training_info['time'] = part
                
                training_data.append(training_info)
        
        return training_data
    
    def create_race_summary_csv(self):
        """レース概要CSVを作成"""
        if not self.race_info:
            return None
        
        race_summary = pd.DataFrame([self.race_info])
        
        csv_buffer = io.StringIO()
        race_summary.to_csv(csv_buffer, index=False, encoding='utf-8')
        return csv_buffer.getvalue()
    
    def create_horses_csv(self):
        """出走馬詳細CSVを作成"""
        if not self.horses_data:
            return None
        
        # 馬データを平坦化
        flattened_data = []
        for horse in self.horses_data:
            horse_row = horse.copy()
            
            # 過去レース情報を文字列に変換
            if horse_row['past_races']:
                past_races_str = []
                for race in horse_row['past_races'][:3]:  # 最新3走
                    race_str = f"{race['date']} {race['venue']} {race['finish_position']}"
                    past_races_str.append(race_str)
                horse_row['recent_3_races'] = ' | '.join(past_races_str)
            else:
                horse_row['recent_3_races'] = ''
            
            # past_racesは除去（重複するため）
            del horse_row['past_races']
            
            flattened_data.append(horse_row)
        
        horses_df = pd.DataFrame(flattened_data)
        
        csv_buffer = io.StringIO()
        horses_df.to_csv(csv_buffer, index=False, encoding='utf-8')
        return csv_buffer.getvalue()
    
    def create_detailed_race_results_csv(self):
        """詳細レース成績CSVを作成"""
        detailed_results = []
        
        for horse in self.horses_data:
            for race in horse['past_races']:
                result_row = {
                    'horse_name': horse['horse_name'],
                    'frame_number': horse['frame_number'],
                    'horse_number': horse['horse_number'],
                    'race_date': race['date'],
                    'venue': race['venue'],
                    'race_name': race['race_name'],
                    'course_info': race['course_info'],
                    'finish_position': race['finish_position'],
                    'field_size': race['field_size'],
                    'popularity': race['popularity'],
                    'time': race['time'],
                    'jockey': race['jockey'],
                    'weight': race['weight']
                }
                detailed_results.append(result_row)
        
        if not detailed_results:
            return None
        
        results_df = pd.DataFrame(detailed_results)
        
        csv_buffer = io.StringIO()
        results_df.to_csv(csv_buffer, index=False, encoding='utf-8')
        return csv_buffer.getvalue()
    
    def create_ai_readable_json(self):
        """AI向けの完全なJSON出力を作成（すべてのデータを含む）"""
        ai_data = {
            "race_info": self.race_info,
            "horses": [],
            "training_data": self.training_data if hasattr(self, 'training_data') else []
        }
        
        for horse in self.horses_data:
            # 馬の基本情報（データ構造に合わせてすべてのフィールドを含む）
            horse_data = {
                "frame_number": horse.get('frame_number', ''),
                "horse_number": horse.get('horse_number', ''),
                "horse_name": horse.get('horse_name', ''),
                "father": horse.get('father', ''),
                "mother": horse.get('mother', ''),
                "mother_father": horse.get('mother_father', ''),
                "jockey": horse.get('jockey', ''),
                "trainer": horse.get('trainer', ''),
                "age": horse.get('age', ''),
                "sex": horse.get('sex', ''),
                "coat_color": horse.get('coat_color', ''),
                "odds": horse.get('odds', ''),
                "popularity": horse.get('popularity', ''),
                "weight": horse.get('weight', ''),
                "load_weight": horse.get('load_weight', ''),
                "stable_type": horse.get('stable_type', ''),
                "recent_form": horse.get('recent_form', ''),
                "past_races": []
            }
            
            # 過去レース（実際の構造に合わせてすべてのデータを含む）
            for race in horse.get('past_races', []):
                race_data = {
                    "date": race.get('date', ''),
                    "venue": race.get('venue', ''),
                    "race_name": race.get('race_name', ''),
                    "course_info": race.get('course_info', ''),
                    "finish_position": race.get('finish_position', ''),
                    "passage_position": race.get('passage_position', ''),
                    "field_size": race.get('field_size', ''),
                    "popularity": race.get('popularity', ''),
                    "jockey": race.get('jockey', ''),
                    "weight": race.get('weight', ''),
                    "time": race.get('time', ''),
                    "track_condition": race.get('track_condition', ''),
                    "winner_name": race.get('winner_name', ''),
                    "time_diff": race.get('time_diff', '')
                }
                horse_data["past_races"].append(race_data)
            
            ai_data["horses"].append(horse_data)
        
        return json.dumps(ai_data, ensure_ascii=False, indent=2)

def main():
    st.set_page_config(
        page_title="🏇 競馬データ専用整理ツール",
        page_icon="🏇",
        layout="wide"
    )
    
    st.title("🏇 競馬データ専用整理ツール")
    st.markdown("---")
    
    # サイドバー
    st.sidebar.header("📋 使い方")
    st.sidebar.markdown("""
    1. **競馬データ**をテキストエリアに貼り付け
    2. **「データ解析開始」**ボタンをクリック
    3. **構造化されたデータ**を確認・ダウンロード
    
    ### 📊 抽出される情報
    - **レース基本情報**: 日時、距離、馬場状態
    - **出走馬詳細**: 血統、騎手、調教師、重量
    - **過去成績**: 最新のレース結果
    - **調教情報**: 調教タイム、評価
    """)
    
    st.sidebar.markdown("---")
    
    # 出力オプション
    st.sidebar.subheader("📊 出力オプション")
    output_race_summary = st.sidebar.checkbox("レース概要", value=True)
    output_horses_detail = st.sidebar.checkbox("出走馬詳細", value=True)
    output_race_results = st.sidebar.checkbox("過去成績詳細", value=True)
    
    st.sidebar.info("💡 **netkeiba等の競馬サイト**のデータに最適化されています")
    
    # メイン画面
    st.header("📝 競馬データ入力")
    keiba_data = st.text_area(
        "競馬の出馬表データを貼り付けてください",
        height=500,
            placeholder="""例：
12R
3歳以上1勝クラス
16:30発走 / ダ1700m (右) / 天候:曇 / 馬場:良

1    1        
ダノンストラーダ
エピファネイア
...
""",
            help="netkeibaや競馬新聞の出馬表データをそのまま貼り付けてください"
    )
    
    analyze_button = st.button("🔍 データ解析開始", type="primary")
    
    # with col2:
    #     st.header("📈 解析状況")
    #     if keiba_data:
    #         lines = [line.strip() for line in keiba_data.split('\n') if line.strip()]
    #         st.metric("入力行数", len(lines))
    #         
    #         # 馬数の推定
    #         horse_count = len([line for line in lines if re.match(r'^\d+\s+\d+', line.strip())])
    #         st.metric("推定出走馬数", horse_count)
    #         
    #         # レース情報の検出
    #         has_race_info = any('発走' in line or 'R' in line for line in lines)
    #         st.metric("レース情報", "検出" if has_race_info else "未検出")
    #     else:
    #         st.info("データを入力してください")
    
    # データ解析実行
    if analyze_button and keiba_data:
        with st.spinner("🔍 競馬データ解析中..."):
            organizer = KeibaDataOrganizer()
            parsed_data = organizer.parse_keiba_data(keiba_data)
        
        if parsed_data['horses_data']:
            st.success(f"✅ {len(parsed_data['horses_data'])}頭の馬データを解析しました！")
            
            # 結果表示
            st.header("📊 解析結果")
            
            # タブで結果を分割表示
            tab1, tab2, tab3, tab4 = st.tabs(["🏁 レース概要", "🐎 出走馬一覧", "📈 過去５レース成績", "💾 データ出力"])
            
            with tab1:
                st.subheader("レース基本情報")
                race_info = parsed_data['race_info']
                
                if race_info:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("レース", race_info.get('race_number', ''))
                        st.metric("開催", race_info.get('venue', ''))
                        st.metric("距離", race_info.get('distance', ''))
                    
                    with col2:
                        st.metric("発走時刻", race_info.get('time', ''))
                        st.metric("コース", race_info.get('course_type', ''))
                        st.metric("天候", race_info.get('weather', ''))
                    
                    with col3:
                        st.metric("頭数", race_info.get('entry_count', ''))
                        st.metric("馬場状態", race_info.get('track_condition', ''))
                        st.metric("向き", race_info.get('direction', ''))
                    
                    # レース名・賞金
                    if race_info.get('race_name'):
                        st.write(f"**レース名:** {race_info['race_name']}")
                    if race_info.get('prize_money'):
                        st.write(f"**賞金:** {race_info['prize_money']}")
            
            with tab2:
                st.subheader("出走馬一覧")
                horses_data = parsed_data['horses_data']
                
                if horses_data:
                    # 出走馬の概要表示
                    summary_data = []
                    for horse in horses_data:
                        summary_data.append({
                            '枠': horse['frame_number'],
                            '馬番': horse['horse_number'],
                            '馬名': horse['horse_name'],
                            '騎手': horse['jockey'],
                            '調教師': horse['trainer'],
                            '年齢': horse['age'],
                            '性別': horse['sex'],
                            'オッズ': horse['odds'],
                            '人気': horse['popularity'],
                            '馬体重': horse['weight']
                        })
                    
                    summary_df = pd.DataFrame(summary_data)
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
            
            with tab3:
                st.subheader("過去５レース成績詳細")
                
                # 各馬の過去成績を表示
                for horse in horses_data:  # 全頭表示
                    if horse['past_races']:
                        st.write(f"**{horse['horse_name']}** の過去成績")
                        
                        past_races_data = []
                        for race in horse['past_races'][:5]:  # 最新5走
                            past_races_data.append({
                                '日付': race['date'],
                                '競馬場': race['venue'],
                                'コース': race['course_info'],
                                '着順': race['finish_position'],
                                '通過順位': race.get('passage_position', ''),
                                '頭数': race['field_size'],
                                '人気': race['popularity'],
                                'タイム': race['time'],
                                'タイム差': race.get('time_diff', '')
                            })
                        
                        if past_races_data:
                            past_df = pd.DataFrame(past_races_data)
                            st.dataframe(past_df, use_container_width=True, hide_index=True)
                        
                        st.markdown("---")
            
            with tab4:
                st.subheader("💾 データ出力・ダウンロード")
                
                # データ出力（CSV + AI向けJSON）
                col1, col2, col3, col4 = st.columns(4)
                
                if output_race_summary:
                    with col1:
                        st.subheader("🏁 レース概要CSV")
                        race_csv = organizer.create_race_summary_csv()
                        if race_csv:
                            st.download_button(
                                label="📄 レース概要CSV",
                                data=race_csv,
                                file_name=f"race_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                
                if output_horses_detail:
                    with col2:
                        st.subheader("🐎 出走馬詳細CSV")
                        horses_csv = organizer.create_horses_csv()
                        if horses_csv:
                            st.download_button(
                                label="📄 出走馬詳細CSV",
                                data=horses_csv,
                                file_name=f"horses_detail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                
                if output_race_results:
                    with col3:
                        st.subheader("📈 過去成績CSV")
                        results_csv = organizer.create_detailed_race_results_csv()
                        if results_csv:
                            st.download_button(
                                label="📄 過去成績CSV",
                                data=results_csv,
                                file_name=f"race_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                
                # AI向けJSON出力
                with col4:
                    st.subheader("🤖 AI向けJSON")
                    ai_json = organizer.create_ai_readable_json()
                    if ai_json:
                        st.download_button(
                            label="📄 AI向けJSON",
                            data=ai_json,
                            file_name=f"ai_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json"
                        )
                        
                        # プレビュー表示
                        with st.expander("JSONプレビュー"):
                            st.code(ai_json[:1000] + "..." if len(ai_json) > 1000 else ai_json, language="json")
                
                # Excel統合ファイル作成
                st.subheader("📗 Excel統合ファイル")
                if st.button("📊 全データExcel生成"):
                    try:
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            
                            # レース概要シート
                            if output_race_summary and race_info:
                                race_df = pd.DataFrame([race_info])
                                race_df.to_excel(writer, sheet_name='レース概要', index=False)
                            
                            # 出走馬詳細シート
                            if output_horses_detail and horses_data:
                                horses_df = pd.DataFrame(summary_data)
                                horses_df.to_excel(writer, sheet_name='出走馬一覧', index=False)
                            
                            # 過去成績シート
                            if output_race_results:
                                all_results = []
                                for horse in horses_data:
                                    for race in horse['past_races']:
                                        result_row = {
                                            '馬名': horse['horse_name'],
                                            '日付': race['date'],
                                            '競馬場': race['venue'],
                                            'コース': race['course_info'],
                                            '着順': race['finish_position'],
                                            '頭数': race['field_size'],
                                            '人気': race['popularity'],
                                            'タイム': race['time']
                                        }
                                        all_results.append(result_row)
                                
                                if all_results:
                                    results_df = pd.DataFrame(all_results)
                                    results_df.to_excel(writer, sheet_name='過去成績', index=False)
                        
                        excel_data = excel_buffer.getvalue()
                        
                        st.download_button(
                            label="📗 統合Excelダウンロード",
                            data=excel_data,
                            file_name=f"keiba_data_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        
                    except Exception as e:
                        st.error(f"Excel生成エラー: {e}")
                
                # データ説明
                st.subheader("📝 出力データについて")
                st.info("""
                **レース概要CSV**: レースの基本情報（日時、距離、馬場状態など）
                
                **出走馬詳細CSV**: 各馬の基本情報（血統、騎手、重量、オッズなど）
                
                **過去成績CSV**: 全出走馬の過去レース結果詳細
                
                **統合Excel**: 上記3つのデータを1つのExcelファイルにまとめたもの
                """)
        
        else:
            st.error("❌ 競馬データを解析できませんでした。データ形式を確認してください。")
    
    elif analyze_button:
        st.warning("⚠️ 競馬データを入力してください。")
    
    # 使用例
    with st.expander("📖 使用例・サンプルデータ"):
        st.markdown("""
        ### 対応データ形式
        - **netkeiba**: 出馬表ページのテキスト
        - **競馬新聞**: 馬柱データ
        - **JRA公式**: 出馬表データ
        
        ### 抽出される情報
        1. **レース情報**: レース名、日時、距離、馬場状態
        2. **馬情報**: 馬名、血統（父・母・母父）、年齢・性別
        3. **関係者**: 騎手、調教師、馬主
        4. **成績**: オッズ、人気、過去の着順・タイム
        5. **調教**: 調教タイム、評価
        
        ### 活用方法
        - **予想分析**: データを元にした予想
        - **成績管理**: レース結果の記録・分析
        - **統計分析**: 騎手・調教師の成績分析
        """)

if __name__ == "__main__":
    main()
