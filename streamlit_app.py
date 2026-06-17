import streamlit as st
import sqlite3
import pandas as pd
import os

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
    tab1, tab2 = st.tabs(["📋 データテーブル閲覧", "🏆 プレーヤーランキング"])

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
