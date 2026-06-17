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

                for i, t_obj in enumerate(player_titles_list):
                    t_title = t_obj['title']

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

                    st.markdown(f"""
                    <div class="title-card">
                        <div class="title-card-header">
                            <span class="title-card-icon">{icon}</span>
                            <span class="title-card-text">{t_title}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

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