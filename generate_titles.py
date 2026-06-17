import sqlite3
import pandas as pd
import numpy as np
from collections import defaultdict
import json
import os

DB_PATH = "data.db"
TABLE_NAME = "数譜データ分析用"
OUTPUT_PATH = "player_titles.json"

def format_val(val, mkey):
    if mkey == 'win_rate':
        return f"{val:.1%}"
    if mkey in ('games_played', 'wins'):
        return f"{val}局" if mkey == 'games_played' else f"{val}回"
    if mkey in ('max_hand', 'penalty_cards', 'draws'):
        return f"{val}枚"
    if isinstance(val, (int, np.integer)):
        return f"{val}回"
    if isinstance(val, (float, np.floating)):
        if val.is_integer():
            return f"{int(val)}回"
        return f"{val:.1f}回"
    return f"{val}回"

def generate_player_titles():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database {DB_PATH} not found.")
        return False
        
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f'SELECT * FROM "{TABLE_NAME}"', conn)
    conn.close()

    print("Total rows:", len(df))
    
    # 1. Clean columns
    df['年度'] = df['年度'].astype(str).str.strip()
    df['大会ID'] = df['大会ID'].astype(str).str.strip()
    df['大会'] = df['大会'].astype(str).str.strip()
    df['ルール'] = df['ルール'].astype(str).str.strip()
    df['人数'] = df['人数'].astype(str).str.strip()
    df['期'] = df['期'].astype(str).str.strip()
    df['回'] = df['回'].astype(str).str.strip()
    df['no.'] = df['no.'].astype(str).str.strip()
    df['本'] = df['本'].astype(str).str.strip()
    df['プレーヤー'] = df['プレーヤー'].astype(str).str.strip()
    
    # Build unique game key
    df['game_key'] = df['年度'] + '_' + df['大会ID'] + '_' + df['期'] + '_' + df['回'] + '_' + df['no.'] + '_' + df['本']
    
    # Clean numeric fields
    df['枚数_num'] = pd.to_numeric(df['枚数'], errors='coerce').fillna(0).astype(int)
    df['P枚数_num'] = pd.to_numeric(df['P枚数'], errors='coerce').fillna(0).astype(int)
    df['合計手数_num'] = pd.to_numeric(df['合計手数'], errors='coerce').fillna(0).astype(int)
    
    # Flags & Counts
    df['pass_flag'] = df['パス'].notna().astype(int)
    df['penalty_flag'] = df['ペナルティ'].notna().astype(int)
    df['penalty_cards'] = df['ペナルティ'].apply(lambda x: len(str(x)) if pd.notna(x) else 0)
    df['joker_flag'] = df['ジョーカー'].notna().astype(int)
    df['draw_cards'] = df['ドロー'].apply(lambda x: len(str(x)) if pd.notna(x) else 0)
    df['gc_flag'] = (df['GC,RR,IN'] == 'GC').astype(int)
    df['rr_flag'] = (df['GC,RR,IN'] == 'RR').astype(int)
    df['in_flag'] = (df['GC,RR,IN'] == 'IN').astype(int)
    
    # Extract game-level metadata
    print("Extracting game metadata...")
    game_meta = {}
    grouped_games = df.groupby('game_key')
    
    for gkey, gdf in grouped_games:
        first_row = gdf.iloc[0]
        participants = set()
        for col in ['1', '2', '3', '4']:
            if col in gdf.columns:
                p_name = str(first_row[col]).strip()
                if p_name and p_name != 'nan' and p_name != 'None' and p_name != '':
                    participants.add(p_name)
                    
        winner_row = gdf[gdf['勝者'].notna() & (gdf['勝者'] != '')]
        winner = None
        if not winner_row.empty:
            winner = str(winner_row.iloc[0]['勝P']).strip()
            if winner == 'nan' or winner == 'None' or winner == '':
                winner = None
                
        game_meta[gkey] = {
            'year': first_row['年度'],
            'tournament': first_row['大会'],
            'rule': first_row['ルール'],
            'players': first_row['人数'],
            'participants': list(participants),
            'winner': winner
        }
    
    all_players = sorted(list(df['プレーヤー'].unique()))
    all_players = [p for p in all_players if p and p != 'nan' and p != 'None' and p != '']
    
    # Calculate debut year and games played for each player
    player_debut_year = {}
    player_games = defaultdict(list)
    for gkey, meta in game_meta.items():
        for p in meta['participants']:
            player_games[p].append(gkey)
            year_val = int(meta['year']) if meta['year'].isdigit() else 9999
            if p not in player_debut_year or year_val < player_debut_year[p]:
                player_debut_year[p] = year_val
                
    # Pre-aggregate player stats per game for performance
    print("Pre-aggregating player stats per game...")
    player_game_stats = defaultdict(lambda: {
        'moves': 0, 'passes': 0, 'penalties': 0, 'penalty_cards': 0,
        'jokers': 0, 'draws': 0, 'gc': 0, 'rr': 0, 'in': 0, 'max_hand_cards': 0
    })
    
    for _, row in df.iterrows():
        p = row['プレーヤー']
        gkey = row['game_key']
        if not p or p == 'nan' or p == 'None' or p == '':
            continue
        stats = player_game_stats[(p, gkey)]
        stats['moves'] += 1
        stats['passes'] += row['pass_flag']
        stats['penalties'] += row['penalty_flag']
        stats['penalty_cards'] += row['penalty_cards']
        stats['jokers'] += row['joker_flag']
        stats['draws'] += row['draw_cards']
        stats['gc'] += row['gc_flag']
        stats['rr'] += row['rr_flag']
        stats['in'] += row['in_flag']
        stats['max_hand_cards'] = max(stats['max_hand_cards'], row['枚数_num'])

    # Build search filters list
    filters = []
    # 1. Global
    filters.append(('global', {}, '全期間・全対局において、'))
    
    # 2. Years
    years = sorted(df['年度'].unique())
    for y in years:
        if y and y != 'nan':
            filters.append(('year', {'year': y}, f'{y}年度の間、'))
            
    # 3. Tournaments
    tournaments = sorted(df['大会'].unique())
    for t in tournaments:
        if t and t != 'nan':
            filters.append(('tournament', {'tournament': t}, f'{t}において、'))
            
    # 4. Year + Tournament
    year_tournaments = df.groupby(['年度', '大会']).size().index
    for y, t in year_tournaments:
        if y and y != 'nan' and t and t != 'nan':
            filters.append(('year_tournament', {'year': y, 'tournament': t}, f'{y}年度の{t}において、'))
            
    # 5. Rule
    rules = sorted(df['ルール'].unique())
    for r in rules:
        if r and r != 'nan':
            filters.append(('rule', {'rule': r}, f'ルール{r}において、'))
            
    # 6. Players count
    players_counts = sorted(df['人数'].unique())
    for pc in players_counts:
        if pc and pc != 'nan':
            filters.append(('players_count', {'players': pc}, f'{pc}人対戦において、'))
            
    # 7. Tournaments with single participation
    for t in tournaments:
        if t and t != 'nan':
            t_players = defaultdict(int)
            for gkey, meta in game_meta.items():
                if meta['tournament'] == t:
                    for p in meta['participants']:
                        t_players[p] += 1
            once_players = {p for p, c in t_players.items() if c == 1}
            if len(once_players) > 0:
                filters.append(('tournament_once', {'tournament': t, 'once_players': list(once_players)}, f'{t}への参加が1回のみの選手のうち、'))

    # 8. Total games limits
    filters.append(('low_participation', {'max_games': 3}, '総対局数が3局以下の選手のうち、'))
    filters.append(('low_participation', {'max_games': 5}, '総対局数が5局以下の選手のうち、'))
    filters.append(('high_participation', {'min_games': 10}, '総対局数が10局以上の選手のうち、'))
    filters.append(('high_participation_large', {'min_games': 30}, '総対局数が30局以上の選手のうち、'))

    # 9. Debut Year Filters
    for y in sorted(list(set(player_debut_year.values()))):
        if y != 9999:
            filters.append(('debut_year', {'debut_year': y}, f'{y}年度にデビューした選手の中で、'))

    # 10. Player-Specific Filters (games played by player P)
    for p in all_players:
        p_gkeys = player_games[p]
        if len(p_gkeys) >= 1:
            filters.append(('player_specific', {'target_player': p, 'gkeys': p_gkeys}, f'自身が出場した対局において、対戦相手を含めて'))

    print("Total filters to check:", len(filters))

    # Metrics definition
    metric_names = [
        ('games_played', '最も対局数が多い選手', '最も対局数が少ない選手', True, False),
        ('wins', '最も勝利数が多い選手', None, True, False),
        ('win_rate', '最も勝率が高い選手', '最も勝率が低い選手', True, True),
        ('moves', '最も多く手数をプレイした選手', '最も手数が少ない選手', True, False),
        ('passes', '最もパス of the year', '最もパスの回数が少ない選手', True, False), # Let's clean up descriptions
        ('passes', '最もパスの回数が多い選手', '最もパスの回数が少ない選手', True, False),
        ('penalties', '最も多くペナルティを受けた選手', '一度もペナルティを受けなかった選手', True, False),
        ('penalty_cards', 'ペナルティで最も多くのカードを引いた選手', None, True, False),
        ('jokers', '最も多くジョーカーを使用した選手', '最もジョーカーの使用が少ない選手', True, False),
        ('draws', '山札から最も多くのカードをドローした選手', None, True, False),
        ('gc', '最も多くグロタンディーク素数切り(GC)を行った選手', None, True, False),
        ('rr', '最も多くラマヌジャン革命(RR)を行った選手', None, True, False),
        ('in', '最も多くジョーカーの単独出し(IN)を行った選手', None, True, False),
        ('max_hand', '1手で最も多くの枚数のカードを出した選手', None, True, False)
    ]

    player_titles_found = defaultdict(list)
    
    print("Running search space...")
    for filt_type, params, filt_desc in filters:
        if filt_type == 'global':
            gkeys = list(game_meta.keys())
        elif filt_type == 'year':
            gkeys = [gk for gk, m in game_meta.items() if m['year'] == params['year']]
        elif filt_type == 'tournament':
            gkeys = [gk for gk, m in game_meta.items() if m['tournament'] == params['tournament']]
        elif filt_type == 'year_tournament':
            gkeys = [gk for gk, m in game_meta.items() if m['year'] == params['year'] and m['tournament'] == params['tournament']]
        elif filt_type == 'rule':
            gkeys = [gk for gk, m in game_meta.items() if m['rule'] == params['rule']]
        elif filt_type == 'players_count':
            gkeys = [gk for gk, m in game_meta.items() if m['players'] == params['players']]
        elif filt_type == 'tournament_once':
            gkeys = [gk for gk, m in game_meta.items() if m['tournament'] == params['tournament']]
        elif filt_type == 'low_participation':
            gkeys = list(game_meta.keys())
        elif filt_type == 'high_participation':
            gkeys = list(game_meta.keys())
        elif filt_type == 'high_participation_large':
            gkeys = list(game_meta.keys())
        elif filt_type == 'debut_year':
            gkeys = list(game_meta.keys())
        elif filt_type == 'player_specific':
            gkeys = params['gkeys']
        else:
            gkeys = []
            
        if not gkeys:
            continue
            
        # Determine valid players in this subset
        sub_player_games = defaultdict(int)
        sub_player_wins = defaultdict(int)
        for gk in gkeys:
            meta = game_meta[gk]
            for p in meta['participants']:
                sub_player_games[p] += 1
            if meta['winner'] and meta['winner'] in meta['participants']:
                sub_player_wins[meta['winner']] += 1
                
        valid_players = list(sub_player_games.keys())
        if filt_type == 'tournament_once':
            valid_players = [p for p in valid_players if p in params['once_players']]
        elif filt_type == 'low_participation':
            valid_players = [p for p in valid_players if len(player_games[p]) <= params['max_games']]
        elif filt_type == 'high_participation':
            valid_players = [p for p in valid_players if len(player_games[p]) >= params['min_games']]
        elif filt_type == 'high_participation_large':
            valid_players = [p for p in valid_players if len(player_games[p]) >= params['min_games']]
        elif filt_type == 'debut_year':
            valid_players = [p for p in valid_players if player_debut_year.get(p) == params['debut_year']]
            
        if len(valid_players) < 2:
            continue
            
        # Compute metrics
        player_metrics = {}
        for p in valid_players:
            p_gkeys = [gk for gk in gkeys if gk in player_games[p]]
            if not p_gkeys:
                continue
                
            p_moves = 0
            p_passes = 0
            p_penalties = 0
            p_penalty_cards = 0
            p_jokers = 0
            p_draws = 0
            p_gc = 0
            p_rr = 0
            p_in = 0
            p_max_hand = 0
            
            for gk in p_gkeys:
                s = player_game_stats[(p, gk)]
                p_moves += s['moves']
                p_passes += s['passes']
                p_penalties += s['penalties']
                p_penalty_cards += s['penalty_cards']
                p_jokers += s['jokers']
                p_draws += s['draws']
                p_gc += s['gc']
                p_rr += s['rr']
                p_in += s['in']
                p_max_hand = max(p_max_hand, s['max_hand_cards'])
                
            games_played = sub_player_games[p]
            wins = sub_player_wins[p]
            win_rate = wins / games_played if games_played > 0 else 0
            
            player_metrics[p] = {
                'games_played': games_played,
                'wins': wins,
                'win_rate': win_rate,
                'moves': p_moves,
                'passes': p_passes,
                'penalties': p_penalties,
                'penalty_cards': p_penalty_cards,
                'jokers': p_jokers,
                'draws': p_draws,
                'gc': p_gc,
                'rr': p_rr,
                'in': p_in,
                'max_hand': p_max_hand
            }
            
        for mkey, max_desc, min_desc, check_max, check_min in metric_names:
            vals = []
            for p, mdict in player_metrics.items():
                v = mdict[mkey]
                if mkey == 'win_rate':
                    if filt_type == 'player_specific':
                        if mdict['games_played'] < 1:
                            continue
                    else:
                        if mdict['games_played'] < 3:
                            continue
                            
                if mkey == 'penalties' and min_desc and v == 0:
                    req_games = 1 if filt_type == 'player_specific' else 3
                    if mdict['games_played'] >= req_games:
                        vals.append((p, 0))
                elif v > 0:
                    vals.append((p, v))
                    
            if not vals:
                continue
                
            # MAX check
            if check_max and max_desc:
                max_val = max(v for p, v in vals)
                winners = [p for p, v in vals if v == max_val]
                
                if filt_type == 'player_specific':
                    target_player = params['target_player']
                    if target_player in winners and len(winners) <= 3:
                        formatted = format_val(max_val, mkey)
                        title_text = f"{filt_desc}{max_desc} ({formatted})"
                        player_titles_found[target_player].append({
                            'title': title_text,
                            'filt_type': filt_type,
                            'params': params,
                            'filt_desc': filt_desc,
                            'metric': mkey,
                            'metric_desc': max_desc,
                            'val': max_val,
                            'direction': 'max',
                            'score': 40
                        })
                else:
                    if len(winners) <= 2:
                        for w in winners:
                            formatted = format_val(max_val, mkey)
                            title_text = f"{filt_desc}{max_desc} ({formatted})"
                            player_titles_found[w].append({
                                'title': title_text,
                                'filt_type': filt_type,
                                'params': params,
                                'filt_desc': filt_desc,
                                'metric': mkey,
                                'metric_desc': max_desc,
                                'val': max_val,
                                'direction': 'max',
                                'score': 100 if filt_type == 'global' else 80 if filt_type in ('year', 'tournament') else 60
                            })
                        
            # MIN check
            if check_min and min_desc:
                min_req = 1 if filt_type == 'player_specific' else 3
                min_vals = [(p, v) for p, v in vals if player_metrics[p]['games_played'] >= min_req]
                if min_vals:
                    min_val = min(v for p, v in min_vals)
                    winners = [p for p, v in min_vals if v == min_val]
                    
                    if filt_type == 'player_specific':
                        target_player = params['target_player']
                        if target_player in winners and len(winners) <= 3:
                            if mkey == 'penalties' and min_val == 0:
                                title_text = f"{filt_desc}{min_desc}"
                            else:
                                formatted = format_val(min_val, mkey)
                                title_text = f"{filt_desc}{min_desc} ({formatted})"
                            player_titles_found[target_player].append({
                                'title': title_text,
                                'filt_type': filt_type,
                                'params': params,
                                'filt_desc': filt_desc,
                                'metric': mkey,
                                'metric_desc': min_desc,
                                'val': min_val,
                                'direction': 'min',
                                'score': 35
                            })
                    else:
                        if len(winners) <= 2:
                            for w in winners:
                                if mkey == 'penalties' and min_val == 0:
                                    title_text = f"{filt_desc}{min_desc}"
                                else:
                                    formatted = format_val(min_val, mkey)
                                    title_text = f"{filt_desc}{min_desc} ({formatted})"
                                    
                                player_titles_found[w].append({
                                    'title': title_text,
                                    'filt_type': filt_type,
                                    'params': params,
                                    'filt_desc': filt_desc,
                                    'metric': mkey,
                                    'metric_desc': min_desc,
                                    'val': min_val,
                                    'direction': 'min',
                                    'score': 90 if filt_type == 'global' else 70 if filt_type in ('year', 'tournament') else 50
                                })
                            
    # Finalize titles and write JSON
    results = {}
    
    for p in all_players:
        p_titles = player_titles_found[p]
        seen = set()
        unique_titles = []
        for t in p_titles:
            # Clean display text formatting for opponent comparisons
            t_clean = t['title'].replace("自身が出場した対局において、対戦相手を含めて最も", "対戦相手を含めて最も")
            t_clean = t_clean.replace("自身が出場した対局において、対戦相手を含めて一度も", "対戦相手を含めて一度も")
            
            if t_clean not in seen:
                seen.add(t_clean)
                unique_titles.append({
                    'title': t_clean,
                    'filt_type': t['filt_type'],
                    'params': t['params'],
                    'filt_desc': t['filt_desc'],
                    'metric': t['metric'],
                    'metric_desc': t['metric_desc'],
                    'val': t['val'],
                    'direction': t['direction'],
                    'score': t['score']
                })
                
        # Sort by score descending
        unique_titles.sort(key=lambda x: x['score'], reverse=True)
        
        # If less than 3, add custom fallbacks
        p_all_games = len(player_games[p])
        p_all_moves = sum(player_game_stats[(p, gk)]['moves'] for gk in player_games[p])
        debut_yr = player_debut_year.get(p, 2020)
        
        while len(unique_titles) < 3:
            # Generate a custom fallback title object
            fallback_index = len(unique_titles)
            if fallback_index == 0:
                title_text = f"{debut_yr}年度にデビューした数譜データベースのメンバー (総対局数: {p_all_games}局)"
            elif fallback_index == 1:
                title_text = f"数譜データベースに刻まれたプレイヤー (総手数: {p_all_moves}手)"
            else:
                title_text = f"数譜データベースのプレイヤー (デビュー: {debut_yr}年度)"
                
            unique_titles.append({
                'title': title_text,
                'filt_type': 'fallback',
                'params': {},
                'filt_desc': '',
                'metric': 'fallback',
                'metric_desc': '実績',
                'val': 0,
                'direction': 'max',
                'score': 10
            })
            
        results[p] = unique_titles
        
    # Write to player_titles.json
    print(f"Writing output to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print("Generation complete!")
    return True

if __name__ == "__main__":
    generate_player_titles()
