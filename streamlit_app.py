import streamlit as st
import sqlite3
import pandas as pd
import os
from collections import defaultdict
import random

# Set page configuration for a premium look
st.set_page_config(
    page_title="数譜データベース 閲覧・分析アプリ",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern design and layout styling
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1 {
        color: #1E3A8A;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 700;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
    }
    .db-info-card {
        background-color: #f8fafc;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #3b82f6;
        margin-bottom: 20px;
    }
    .title-list-container {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
        margin-top: 20px;
    }
    .player-title-item {
        font-size: 1.1em;
        padding: 8px 0;
        border-bottom: 1px dashed #e2e8f0;
        display: flex;
        align-items: center;
    }
    .player-title-item:last-child {
        border-bottom: none;
    }
    .title-icon {
        margin-right: 10px;
        font-size: 1.2em;
        color: #3b82f6; /* Primary color for icons */
    }
    .title-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        padding: 18px 24px;
        border-radius: 12px;
        border-left: 6px solid #fbbf24;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        margin-bottom: 16px;
        border-top: 1px solid #f1f5f9;
        border-right: 1px solid #f1f5f9;
        border-bottom: 1px solid #f1f5f9;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .title-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
    }
    .title-card-header {
        display: flex;
        align-items: center;
    }
    .title-card-icon {
        font-size: 1.5em;
        margin-right: 14px;
    }
    .title-card-text {
        font-size: 1.15em;
        font-weight: 600;
        color: #1e293b;
        font-family: 'Outfit', 'Inter', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

DB_PATH = "data.db"
TABLE_NAME = "数譜データ分析用"

@st.cache_data(ttl=600)
def get_database_info():
    """Retrieve metadata about the SQLite database."""
    if not os.path.exists(DB_PATH):
        return None
    
    file_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    return {
        "file_size_mb": file_size_mb,
        "tables": tables
    }

def load_table_data(table_name):
    """Load all rows from a specific table."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
    conn.close()
    return df

@st.cache_data(ttl=600)
def get_player_ranking():
    """Generate player ranking based on tournament participation, match count and logs count."""
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
        
    conn = sqlite3.connect(DB_PATH)
    # Perform aggregation directly in SQLite for performance
    query = f"""
    SELECT 
        "プレーヤー" as "プレーヤー名",
        COUNT(DISTINCT "大会ID") as "大会参加数",
        COUNT(DISTINCT "ID") as "対局数",
        COUNT(*) as "総手数"
    FROM "{TABLE_NAME}"
    WHERE "プレーヤー" IS NOT NULL AND "プレーヤー" != ''
    GROUP BY "プレーヤー"
    ORDER BY "大会参加数" DESC, "対局数" DESC, "総手数" DESC
    """
    df_ranking = pd.read_sql_query(query, conn)
    conn.close()
    
    # Add Rank Column
    df_ranking.insert(0, '順位', range(1, len(df_ranking) + 1))
    return df_ranking

@st.cache_data(ttl=600)
def get_player_history(player_name):
    """Fetch all records for a specific player."""
    conn = sqlite3.connect(DB_PATH)
    # Find all distinct tournaments the player participated in
    query = f"""
    SELECT DISTINCT
        "年度", "大会ID", "大会", "期", "回",
        COUNT(DISTINCT "ID") as "対局数",
        COUNT(*) as "手数"
    FROM "{TABLE_NAME}"
    WHERE "プレーヤー" = ?
    GROUP BY "年度", "大会ID", "大会", "期", "回"
    ORDER BY "年度" DESC, "大会ID" DESC
    """
    df_history = pd.read_sql_query(query, conn, params=(player_name,))
    conn.close()
    return df_history

import json
from generate_titles import generate_player_titles, format_val

@st.cache_data(ttl=3600)
def load_player_titles():
    """Load player titles from precalculated JSON, generating it if missing."""
    json_path = "player_titles.json"
    if not os.path.exists(json_path):
        generate_player_titles()
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.error(f"肩書きデータのロード中にエラーが発生しました: {e}")
    return {}

@st.cache_data(ttl=600)
def get_ranking_data_for_title(filt_type, params, metric, direction):
    """Reconstruct ranking list for a specific title combination on-the-fly."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f'SELECT * FROM "{TABLE_NAME}"', conn)
    conn.close()
    
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
    
    # Calculate debut year and games list
    player_debut_year = {}
    player_games = defaultdict(list)
    for gkey, meta in game_meta.items():
        for p in meta['participants']:
            player_games[p].append(gkey)
            year_val = int(meta['year']) if meta['year'].isdigit() else 9999
            if p not in player_debut_year or year_val < player_debut_year[p]:
                player_debut_year[p] = year_val

    # Apply filter to game keys
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
        target_player = params['target_player']
        gkeys = player_games[target_player]
    else:
        gkeys = []

    if not gkeys:
        return pd.DataFrame()

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

    player_game_stats = defaultdict(lambda: {
        'moves': 0, 'passes': 0, 'penalties': 0, 'penalty_cards': 0,
        'jokers': 0, 'draws': 0, 'gc': 0, 'rr': 0, 'in': 0, 'max_hand_cards': 0
    })
    
    df_sub = df[df['game_key'].isin(gkeys)]
    
    for _, row in df_sub.iterrows():
        p = row['プレーヤー']
        gkey = row['game_key']
        if not p or p not in valid_players:
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

    rows = []
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
        
        val_map = {
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
        rows.append({
            'プレーヤー名': p,
            '数値': val_map[metric],
            '対局数': games_played,
            '勝利数': wins
        })
        
    df_res = pd.DataFrame(rows)
    if df_res.empty:
        return df_res
        
    if metric == 'win_rate':
        df_res = df_res[df_res['対局数'] >= (1 if filt_type == 'player_specific' else 3)]
    elif metric == 'penalties' and direction == 'min':
        pass
    else:
        df_res = df_res[df_res['数値'] > 0]
        
    ascending = (direction == 'min')
    df_res = df_res.sort_values(by='数値', ascending=ascending).reset_index(drop=True)
    df_res.insert(0, '順位', range(1, len(df_res) + 1))
    return df_res

# Header Section
st.title("📊 数譜データベース 閲覧・分析アプリ")
st.markdown("SQLite データベース (`data.db`) の中身の可視化・検索、およびプレーヤー実績の分析が行えます。")
st.markdown("---")

# Load DB Info
db_info = get_database_info()

if db_info is None:
    st.error(f"⚠️ データベースファイル `{DB_PATH}` が見つかりませんでした。同じディレクトリに配置されているか確認してください。")
else:
    # Sidebar
    st.sidebar.header("🛠️ 設定 & 情報")
    
    st.sidebar.markdown(f"""
    <div class="db-info-card">
        <strong>📁 データベース情報</strong><br>
        • ファイル名: <code>{DB_PATH}</code><br>
        • サイズ: <code>{db_info['file_size_mb']:.2f} MB</code><br>
        • テーブル数: <code>{len(db_info['tables'])}</code>
    </div>
    """, unsafe_allow_html=True)

    # Main Tabs
    tab1, tab2, tab3 = st.tabs(["📋 データテーブル閲覧", "🏆 プレーヤーランキング", "👑 肩書き"])

    # --- TAB 1: DATA BROWSER ---
    with tab1:
        selected_table = st.selectbox(
            "🗂️ 表示するテーブルを選択",
            options=db_info['tables'],
            index=0 if db_info['tables'] else None,
            key="tab1-table-select"
        )
        
        if selected_table:
            # Table-specific limit rows
            limit_rows = st.slider(
                "🔍 最大表示行数 (ローカルブラウザの負荷軽減用)",
                min_value=100,
                max_value=10000,
                value=1000,
                step=100,
                key="tab1-limit-slider"
            )
            
            # Load data (cached)
            with st.spinner("データベースからデータを読み込んでいます..."):
                df = load_table_data(selected_table)
                
            # Metrics Row
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("総行数 (Total Rows)", f"{len(df):,}")
            with col2:
                st.metric("総列数 (Total Columns)", f"{len(df.columns):,}")
            with col3:
                st.metric("表示中の行数 (Displayed)", f"{min(len(df), limit_rows):,}")
                
            # Search / Filtering
            st.subheader("🔍 データ検索 & 絞り込み")
            search_query = st.text_input("テーブル内のテキストで絞り込み", "", key="tab1-search-input")
            
            filtered_df = df.copy()
            if search_query:
                search_col = st.selectbox("検索対象の列", ["すべての列"] + list(df.columns), key="tab1-search-col")
                
                if search_col == "すべての列":
                    mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
                    filtered_df = df[mask]
                else:
                    mask = df[search_col].astype(str).str.contains(search_query, case=False, na=False)
                    filtered_df = df[mask]
                    
                st.info(f"検索結果: {len(filtered_df):,} 行が見つかりました。")
                
            display_df = filtered_df.head(limit_rows)
            
            # Display DataFrame
            st.subheader("📋 データテーブル")
            st.dataframe(
                display_df,
                use_container_width=True,
                height=500
            )
            
            # Download Action
            st.subheader("📥 データのダウンロード")
            csv_data = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="表示中のデータをCSVとしてダウンロード",
                data=csv_data,
                file_name=f"{selected_table}_data.csv",
                mime="text/csv",
                key="tab1-download-csv"
            )
        else:
            st.info("データベースにテーブルが存在しません。")

    # --- TAB 2: PLAYER RANKING ---
    with tab2:
        st.subheader("🏆 大会参加数 プレーヤーランキング")
        st.markdown("各プレーヤーが出場した **ユニークな大会ID（大会数）** に基づくランキングです。同数の場合は対局数、総手数の順に順位付けしています。")
        
        # Load Ranking Data
        with st.spinner("ランキングを集計しています..."):
            ranking_df = get_player_ranking()
            
        if ranking_df.empty:
            st.warning("ランキングを表示するデータが見つかりませんでした。")
        else:
            col_rank_settings, _ = st.columns([1, 2])
            with col_rank_settings:
                top_n = st.slider(
                    "📊 表示する上位プレーヤー数",
                    min_value=5,
                    max_value=min(100, len(ranking_df)),
                    value=15,
                    step=5,
                    key="tab2-topn-slider"
                )
            
            top_ranking = ranking_df.head(top_n)
            
            # Interactive Chart for Ranking visualization
            st.write(f"📈 大会参加数ランキング (Top {top_n})")
            
            # Format dataframe for charting
            chart_df = top_ranking.set_index("プレーヤー名")[["大会参加数"]]
            st.bar_chart(chart_df, y="大会参加数", color="#1E3A8A")
            
            # Display ranking table
            st.subheader("📋 ランキング詳細")
            st.dataframe(
                ranking_df.head(top_n),
                use_container_width=True,
                hide_index=True
            )
            
            # Download Action for Ranking
            csv_ranking = ranking_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="ランキング全データをCSVとしてダウンロード",
                data=csv_ranking,
                file_name="player_ranking.csv",
                mime="text/csv",
                key="tab2-download-csv"
            )
            
            # Player Search / History Section
            st.markdown("---")
            st.subheader("👤 プレーヤー別 出場履歴詳細")
            
            selected_player = st.selectbox(
                "検索するプレーヤーを選択してください",
                options=ranking_df["プレーヤー名"].unique(),
                index=0
            )
            
            if selected_player:
                player_history = get_player_history(selected_player)
                
                # Show personal stats
                player_info = ranking_df[ranking_df["プレーヤー名"] == selected_player].iloc[0]
                
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                with col_stat1:
                    st.metric("現在の順位", f"{player_info['順位']} 位")
                with col_stat2:
                    st.metric("総大会数", f"{player_info['大会参加数']} 回")
                with col_stat3:
                    st.metric("総対局数", f"{player_info['対局数']} 局")
                with col_stat4:
                    st.metric("総手数", f"{player_info['総手数']} 手")
                
                st.markdown(f"**{selected_player}** 選手の大会出場リスト：")
                st.dataframe(
                    player_history,
                    use_container_width=True,
                    hide_index=True
                )

    # --- TAB 3: PLAYER TITLES ---
    with tab3:
        st.subheader("👑 あなただけの肩書き (全プレーヤー日本一要素)")
        st.markdown("データベース上の全プレイヤーの中で、そのプレイヤーが**「日本一（No.1）」**になる要素を自動抽出しました！")
        st.markdown("複数要素の組み合わせ（年度・大会・ルール・対戦相手条件など）から、勝敗だけでなく手数やパス回数、特殊役の達成率など様々な視点で日本一を見つけ出します。")

        # Add manual refresh cache button in sidebar or tab header
        col_hdr, col_btn = st.columns([4, 1])
        with col_hdr:
            st.info("💡 タイトルをクリックすると、その実績における他プレイヤーとの比較ランキングとグラフがその場で展開されます！")
        with col_btn:
            if st.button("🔄 肩書きデータを再計算", key="refresh-titles-btn", use_container_width=True):
                with st.spinner("データベースから肩書きを再計算しています... (数秒かかります)"):
                    generate_player_titles()
                    st.cache_data.clear()
                st.success("再計算が完了しました！")
                st.rerun()

        # Load titles
        titles = load_player_titles()

        if not titles:
            st.warning("肩書きデータをロードまたは生成できませんでした。")
        else:
            # Player selector
            player_list = sorted(titles.keys())
            selected_player = st.selectbox(
                "👤 プレーヤーを選択してください",
                options=player_list,
                key="tab3-player-select"
            )

            if selected_player:
                player_titles_list = titles.get(selected_player, [])

                st.markdown(f"### 🏆 {selected_player} 選手の日本一の肩書き")
                
                # We display at least 3 titles per player
                for i, t_obj in enumerate(player_titles_list):
                    t_title = t_obj['title']
                    t_filt_type = t_obj['filt_type']
                    t_params = t_obj['params']
                    t_metric = t_obj['metric']
                    t_direction = t_obj['direction']
                    t_val = t_obj['val']
                    
                    # Custom Icons based on metrics
                    icon = "👑"
                    if "対局数" in t_title or "出場" in t_title:
                        icon = "⚔️"
                    elif "勝利数" in t_title or "勝率" in t_title:
                        icon = "🏆"
                    elif "パス" in t_title:
                        icon = "⏸️"
                    elif "ペナルティ" in t_title:
                        icon = "⚠️"
                    elif "ジョーカー" in t_title or "単独出し" in t_title:
                        icon = "🃏"
                    elif "グロタン" in t_title or "GC" in t_title:
                        icon = "⚡"
                    elif "ラマヌジャン" in t_title or "RR" in t_title:
                        icon = "🌀"
                    elif "デビュー" in t_title or "メンバー" in t_title:
                        icon = "✨"

                    # Render card in custom styled HTML
                    st.markdown(f"""
                    <div class="title-card">
                        <div class="title-card-header">
                            <span class="title-card-icon">{icon}</span>
                            <span class="title-card-text">{t_title}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Ranking Proof Expander
                    if t_filt_type != 'fallback':
                        with st.expander(f"📊 この肩書きのデータ裏付け・ランキングを表示", expanded=False):
                            with st.spinner("ランキングを読み込んでいます..."):
                                df_rank = get_ranking_data_for_title(t_filt_type, t_params, t_metric, t_direction)
                                
                            if df_rank.empty:
                                st.write("ランキングデータが見つかりませんでした。")
                            else:
                                # Highlight target player
                                df_chart = df_rank.head(10).copy() # show top 10
                                
                                # Make sure the selected player is included in the chart even if not top 10
                                if selected_player not in df_chart['プレーヤー名'].values:
                                    target_row = df_rank[df_rank['プレーヤー名'] == selected_player]
                                    if not target_row.empty:
                                        df_chart = pd.concat([df_chart, target_row]).drop_duplicates(subset=['プレーヤー名'])
                                
                                # Set bar color (highlight target)
                                df_chart['color'] = df_chart['プレーヤー名'].apply(
                                    lambda x: '#F59E0B' if x == selected_player else '#1E3A8A'
                                )
                                
                                # Formatting metric name for axis label
                                y_label = t_obj.get('metric_desc', '数値')
                                if t_metric == 'win_rate':
                                    y_label += " (%)"
                                elif t_metric in ('max_hand', 'penalty_cards', 'draws'):
                                    y_label += " (枚)"
                                else:
                                    y_label += " (回/局)"
                                    
                                # Plot
                                st.write(f"📈 比較ランキング (上位10名 + 該当プレイヤー) - 軸: {y_label}")
                                
                                # Display bar chart with highlight
                                chart_data = df_chart.set_index('プレーヤー名')[['数値']]
                                if t_metric == 'win_rate':
                                    # Multiply win rate by 100 for better chart display
                                    chart_data['数値'] = chart_data['数値'] * 100
                                    st.bar_chart(chart_data, y="数値", color='#F59E0B')
                                else:
                                    st.bar_chart(chart_data, y="数値", color='#1E3A8A')
                                
                                # Table
                                st.write("📋 ランキング一覧")
                                
                                # Format table display
                                df_disp = df_rank.copy()
                                if t_metric == 'win_rate':
                                    df_disp['数値'] = df_disp['数値'].apply(lambda x: f"{x:.1%}")
                                elif t_metric in ('max_hand', 'penalty_cards', 'draws'):
                                    df_disp['数値'] = df_disp['数値'].apply(lambda x: f"{int(x)}枚")
                                elif t_metric == 'games_played':
                                    df_disp['数値'] = df_disp['数値'].apply(lambda x: f"{int(x)}局")
                                else:
                                    df_disp['数値'] = df_disp['数値'].apply(lambda x: f"{int(x)}回")
                                    
                                # Rename columns for presentation
                                df_disp = df_disp.rename(columns={'数値': y_label})
                                
                                # Highlight the selected player's row in dataframe
                                def highlight_player(row):
                                    return ['background-color: #FEF3C7; font-weight: bold' if row['プレーヤー名'] == selected_player else '' for _ in row]
                                    
                                st.dataframe(
                                    df_disp.style.apply(highlight_player, axis=1),
                                    use_container_width=True,
                                    hide_index=True
                                )

                # Show some stats for context
                ranking_df = get_player_ranking()
                player_info = ranking_df[ranking_df["プレーヤー名"] == selected_player]
                if not player_info.empty:
                    info = player_info.iloc[0]
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("現在の総合順位", f"{info['順位']} 位")
                    with col2:
                        st.metric("総対局数", f"{info['対局数']} 局")
                    with col3:
                        st.metric("総手数", f"{info['総手数']} 手")

            # 全肩書き一覧
            st.markdown("---")
            st.subheader("📋 全プレイヤー肩書き一覧")
            
            all_titles_flat = []
            for player, player_titles_list in titles.items():
                for t_idx, t_obj in enumerate(player_titles_list[:3]): # Show top 3 titles per player
                    all_titles_flat.append({
                        "プレーヤー名": player,
                        f"肩書き {t_idx+1}": t_obj['title']
                    })
                    
            # Pivot or group to show them in a clean table (one row per player)
            player_rows = defaultdict(dict)
            for item in all_titles_flat:
                p = item["プレーヤー名"]
                for k, v in item.items():
                    if k != "プレーヤー名":
                        player_rows[p][k] = v
                        
            flat_rows = []
            for p, val in player_rows.items():
                flat_rows.append({
                    "プレーヤー名": p,
                    "第一肩書き": val.get("肩書き 1", ""),
                    "第二肩書き": val.get("肩書き 2", ""),
                    "第三肩書き": val.get("肩書き 3", "")
                })
                
            titles_df = pd.DataFrame(flat_rows)
            
            st.dataframe(
                titles_df,
                use_container_width=True,
                hide_index=True
            )

            # Download
            csv_titles = titles_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="全肩書きデータをCSVとしてダウンロード",
                data=csv_titles,
                file_name="player_titles.csv",
                mime="text/csv",
                key="tab3-download-csv"
            )