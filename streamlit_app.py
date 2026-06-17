import streamlit as st
import sqlite3
import pandas as pd
import os

# Set page configuration for a premium look
st.set_page_config(
    page_title="数譜データベース 閲覧アプリ",
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

@st.cache_data
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
    # Read entire table
    df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
    conn.close()
    return df

# Header Section
st.title("📊 数譜データベース 閲覧アプリ")
st.markdown("SQLite データベース (`data.db`) の中身を可視化・検索できるテストアプリケーションです。")
st.markdown("---")

# Load DB Info
db_info = get_database_info()

if db_info is None:
    st.error(f"⚠️ データベースファイル `{DB_PATH}` が見つかりませんでした。同じディレクトリに配置されているか確認してください。")
else:
    # Sidebar
    st.sidebar.header("🛠️ 設定 & 情報")
    
    # DB Info in Sidebar
    st.sidebar.markdown(f"""
    <div class="db-info-card">
        <strong>📁 データベース情報</strong><br>
        • ファイル名: <code>{DB_PATH}</code><br>
        • サイズ: <code>{db_info['file_size_mb']:.2f} MB</code><br>
        • テーブル数: <code>{len(db_info['tables'])}</code>
    </div>
    """, unsafe_allow_html=True)
    
    # Table Selector
    selected_table = st.sidebar.selectbox(
        "🗂️ 表示するテーブルを選択",
        options=db_info['tables'],
        index=0 if db_info['tables'] else None
    )
    
    if selected_table:
        # Options
        st.sidebar.subheader("⚙️ 表示オプション")
        
        limit_rows = st.sidebar.slider(
            "🔍 最大表示行数 (ローカルブラウザの負荷軽減用)",
            min_value=100,
            max_value=10000,
            value=1000,
            step=100
        )
        
        # Load data (cached for performance)
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
        search_query = st.text_input("テーブル内のテキストで絞り込み (大文字小文字を区別しません)", "")
        
        filtered_df = df.copy()
        if search_query:
            # Dropdown to select column to search, or "All Columns"
            search_col = st.selectbox("検索対象の列", ["すべての列"] + list(df.columns))
            
            if search_col == "すべての列":
                # Search across all columns
                mask = df.astype(str).apply(lambda x: x.str.contains(search_query, case=False, na=False)).any(axis=1)
                filtered_df = df[mask]
            else:
                # Search in specific column
                mask = df[search_col].astype(str).str.contains(search_query, case=False, na=False)
                filtered_df = df[mask]
                
            st.info(f"検索結果: {len(filtered_df):,} 行が見つかりました。")
            
        # Limit the displayed data size for performance
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
            key="download-csv"
        )
        
    else:
        st.info("データベースにテーブルが存在しません。")
