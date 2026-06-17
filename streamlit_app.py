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

@st.cache_data(ttl=600)
def get_all_player_titles():
    """全プレーヤーにユニークな肩書きを付与する。"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f'SELECT * FROM "{TABLE_NAME}"', conn)
    conn.close()

    assigned = {}
    used_titles = set()

    def assign(player, title):
        if player not in assigned and title not in used_titles:
            assigned[player] = title
            used_titles.add(title)
            return True
        return False

    # 全プレーヤーリスト
    all_players = sorted(df['プレーヤー'].dropna().unique())
    all_players = [p for p in all_players if p != '']

    # 年度一覧
    years = sorted(df['年度'].dropna().unique())

    # 1. 年度×大会 最多出場
    for year in years:
        for tournament in sorted(df['大会'].dropna().unique()):
            subset = df[(df['年度'] == year) & (df['大会'] == tournament)]
            if subset.empty:
                continue
            counts = subset.groupby('プレーヤー').size()
            if len(counts) == 0:
                continue
            best = counts.idxmax()
            assign(best, f"{year}年度 {tournament} 最多出場")

    # 2. 年度×ルール 最多出場
    for year in years:
        for rule in sorted(df['ルール'].dropna().unique()):
            subset = df[(df['年度'] == year) & (df['ルール'] == rule)]
            if subset.empty:
                continue
            counts = subset.groupby('プレーヤー').size()
            if len(counts) == 0:
                continue
            best = counts.idxmax()
            assign(best, f"{year}年度 ルール{rule} 最多出場")

    # 3. 大会別 最多出場
    for tournament in sorted(df['大会'].dropna().unique()):
        subset = df[df['大会'] == tournament]
        if subset.empty:
            continue
        counts = subset.groupby('プレーヤー').size()
        if len(counts) == 0:
            continue
        best = counts.idxmax()
        assign(best, f"{tournament} 最多出場")

    # 4. 年度別 最多出場
    for year in years:
        subset = df[df['年度'] == year]
        counts = subset.groupby('プレーヤー').size()
        if len(counts) == 0:
            continue
        best = counts.idxmax()
        assign(best, f"{year}年度 最多出場")

    # 5. ルール別 最多出場
    for rule in sorted(df['ルール'].dropna().unique()):
        subset = df[df['ルール'] == rule]
        counts = subset.groupby('プレーヤー').size()
        if len(counts) == 0:
            continue
        best = counts.idxmax()
        assign(best, f"ルール{rule} 最多出場")

    # 6. 人数別 最多出場
    for ninzu in sorted(df['人数'].dropna().unique()):
        subset = df[df['人数'] == ninzu]
        counts = subset.groupby('プレーヤー').size()
        if len(counts) == 0:
            continue
        best = counts.idxmax()
        assign(best, f"{ninzu}人対戦 最多出場")

    # 7. 回別 最多出場
    for kai in sorted(df['回'].dropna().unique()):
        subset = df[df['回'] == kai]
        counts = subset.groupby('プレーヤー').size()
        if len(counts) == 0:
            continue
        best = counts.idxmax()
        assign(best, f"「{kai}」最多出場")

    # 8. 期別 最多出場
    for ki in sorted(df['期'].dropna().unique()):
        subset = df[df['期'] == ki]
        counts = subset.groupby('プレーヤー').size()
        if len(counts) == 0:
            continue
        best = counts.idxmax()
        assign(best, f"第{ki}期 最多出場")

    # 9. GC,RR,IN 別 最多
    for gcrrin in sorted(df['GC,RR,IN'].dropna().unique()):
        subset = df[df['GC,RR,IN'] == gcrrin]
        counts = subset.groupby('プレーヤー').size()
        if len(counts) == 0:
            continue
        best = counts.idxmax()
        assign(best, f"{gcrrin} 最多")

    # 10. 手番1(先手) 最多
    subset = df[df['手番'] == '1']
    if not subset.empty:
        counts = subset.groupby('プレーヤー').size()
        if len(counts) > 0:
            best = counts.idxmax()
            assign(best, "先手 最多")

    # 11. 手番2(後手) 最多
    subset = df[df['手番'] == '2']
    if not subset.empty:
        counts = subset.groupby('プレーヤー').size()
        if len(counts) > 0:
            best = counts.idxmax()
            assign(best, "後手 最多")

    # 12. ジョーカー使用 最多種類
    joker_df = df[df['ジョーカー'].notna() & (df['ジョーカー'] != '')]
    if not joker_df.empty:
        joker_variety = joker_df.groupby('プレーヤー')['ジョーカー'].apply(lambda x: x.nunique())
        if len(joker_variety) > 0:
            best = joker_variety.idxmax()
            assign(best, f"ジョーカー使い ({joker_variety[best]}種類)")

    # 13. パス最少
    pass_df = df[df['パス'].notna() & (df['パス'] != '')]
    if not pass_df.empty:
        pass_counts = pass_df.groupby('プレーヤー').size()
        # 全プレーヤーのパス回数を出して最少を探す
        all_pass = df.copy()
        all_pass['has_pass'] = df['パス'].notna() & (df['パス'] != '')
        all_pass_counts = all_pass.groupby('プレーヤー')['has_pass'].sum()
        if len(all_pass_counts) > 0:
            best = all_pass_counts.idxmin()
            assign(best, "最もパスが少ない")

    # 14. 合計手数 最多
    te_count = df.groupby('プレーヤー')['手数'].apply(lambda x: x.astype(int).max() if len(x) > 0 else 0)
    if len(te_count) > 0:
        best = te_count.idxmax()
        assign(best, f"合計手数 最多 ({int(te_count[best])}手)")

    # 15. 枚数クラス別 最多
    for mc in sorted(df['枚数クラス'].dropna().unique()):
        subset = df[df['枚数クラス'] == mc]
        counts = subset.groupby('プレーヤー').size()
        if len(counts) == 0:
            continue
        best = counts.idxmax()
        assign(best, f"枚数クラス{mc} 最多")

    # 16. 年度×人数 最多出場
    for year in years:
        for ninzu in sorted(df['人数'].dropna().unique()):
            subset = df[(df['年度'] == year) & (df['人数'] == ninzu)]
            if subset.empty:
                continue
            counts = subset.groupby('プレーヤー').size()
            if len(counts) == 0:
                continue
            best = counts.idxmax()
            assign(best, f"{year}年度 {ninzu}人対戦 最多出場")

    # 17. 本別 最多出場
    for hon in sorted(df['本'].dropna().unique()):
        subset = df[df['本'] == hon]
        counts = subset.groupby('プレーヤー').size()
        if len(counts) == 0:
            continue
        best = counts.idxmax()
        assign(best, f"本{hon} 最多")

    # 18. 勝者 最多
    winner_df = df[df['勝者'].notna() & (df['勝者'] != '')]
    if not winner_df.empty:
        # 勝者カラムにはプレーヤー番号(1,2,3,4)が入っている
        # 勝者=1のときは 1列目のプレーヤーが勝者
        for w in sorted(winner_df['勝者'].unique()):
            w_subset = winner_df[winner_df['勝者'] == w]
            # 勝者列に対応するプレーヤー列を特定
            player_col = str(w) if w != '0' else '1'
            if player_col in df.columns:
                counts = w_subset[player_col].value_counts()
                if len(counts) > 0:
                    best = counts.idxmax()
                    assign(best, f"最多勝利 (勝者{w})")

    # 19. 残りのプレーヤーに汎用肩書きを付与
    for player in all_players:
        if player in assigned:
            continue
        player_df = df[df['プレーヤー'] == player]
        if player_df.empty:
            continue
        # そのプレーヤーの特徴的な大会を探す
        top_tournament = player_df['大会'].value_counts().index[0] if len(player_df['大会'].value_counts()) > 0 else None
        top_year = player_df['年度'].value_counts().index[0] if len(player_df['年度'].value_counts()) > 0 else None
        distinct_tournaments = player_df['大会ID'].nunique()

        if top_year and top_tournament:
            title = f"{top_year}年度 {top_tournament} 出場"
        elif top_tournament:
            title = f"{top_tournament} 出場"
        else:
            title = f"{distinct_tournaments}大会出場"

        if title not in used_titles:
            assign(player, title)
        else:
            # ユニークになるよう調整
            for i in range(2, 100):
                alt = f"{title} (その{i})"
                if alt not in used_titles:
                    assign(player, alt)
                    break

    return assigned

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
        st.subheader("👑 あなただけの肩書き")
        st.markdown("データベース上の全61名のプレーヤーに、それぞれ**ユニークな「1位」の肩書き**を付与しました。勝敗に関わらず、誰もが何らかの日本一になれます！")

        # 肩書き用のCSS
        st.markdown("""
        <style>
        .title-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px;
            padding: 40px 30px;
            text-align: center;
            color: white;
            margin: 20px 0;
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
        }
        .title-card .player-name {
            font-size: 2.2em;
            font-weight: 800;
            letter-spacing: 0.05em;
            margin-bottom: 10px;
        }
        .title-card .title-label {
            font-size: 0.85em;
            letter-spacing: 0.2em;
            opacity: 0.8;
            margin-bottom: 15px;
        }
        .title-card .title-text {
            font-size: 1.6em;
            font-weight: 700;
            background: rgba(255,255,255,0.15);
            border-radius: 50px;
            padding: 15px 30px;
            display: inline-block;
            margin: 10px 0;
        }
        .title-card .crown {
            font-size: 3em;
            margin-bottom: 10px;
        }
        .title-card .detail-text {
            font-size: 0.9em;
            opacity: 0.7;
            margin-top: 15px;
        }
        </style>
        """, unsafe_allow_html=True)

        # Load titles
        with st.spinner("肩書きを生成中..."):
            titles = get_all_player_titles()

        if not titles:
            st.warning("肩書きデータを生成できませんでした。")
        else:
            # Player selector
            player_list = sorted(titles.keys())
            selected_player = st.selectbox(
                "👤 プレーヤーを選択してください",
                options=player_list,
                key="tab3-player-select"
            )

            if selected_player:
                player_title = titles.get(selected_player, "肩書きなし")

                # Display the title card
                st.markdown(f"""
                <div class="title-card">
                    <div class="crown">👑</div>
                    <div class="player-name">{selected_player}</div>
                    <div class="title-label">〜 あなたの肩書き 〜</div>
                    <div class="title-text">{player_title}</div>
                    <div class="detail-text">この肩書きはデータベース上の全プレーヤーの中で唯一無二です</div>
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
                        st.metric("大会参加数", f"{info['大会参加数']} 大会")
                    with col2:
                        st.metric("総対局数", f"{info['対局数']} 局")
                    with col3:
                        st.metric("総手数", f"{info['総手数']} 手")

            # 全肩書き一覧
            st.markdown("---")
            st.subheader("📋 全プレーヤー肩書き一覧")
            titles_df = pd.DataFrame(
                [{"プレーヤー名": p, "肩書き": t} for p, t in sorted(titles.items())]
            )
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
