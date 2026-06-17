import sqlite3
import pandas as pd
import os

DB_PATH = "data.db"
TABLE_NAME = "数譜データ分析用"

def fix_database():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return

    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Read existing data
    df_raw = pd.read_sql_query(f'SELECT * FROM "{TABLE_NAME}"', conn)
    print(f"Original shape: {df_raw.shape}")
    
    if df_raw.empty:
        print("Table is empty. Nothing to do.")
        conn.close()
        return
        
    # 2. Extract first row to use as headers
    headers = df_raw.iloc[0].tolist()
    
    # Process headers to ensure they are unique and valid strings
    unique_headers = []
    for i, h in enumerate(headers):
        if pd.isna(h) or str(h).strip() == "":
            unique_headers.append(f"Column_{i+1}")
        else:
            h_str = str(h).strip()
            if h_str in unique_headers:
                unique_headers.append(f"{h_str}_{i+1}")
            else:
                unique_headers.append(h_str)
                
    # 3. Create new clean DataFrame
    df_clean = df_raw.iloc[1:].copy()
    df_clean.columns = unique_headers
    df_clean = df_clean.reset_index(drop=True)
    
    print(f"New shape: {df_clean.shape}")
    print("New columns:", list(df_clean.columns)[:10], "... (showing first 10)")
    
    # 4. Backup original DB (safety first!)
    backup_path = DB_PATH + ".bak"
    if not os.path.exists(backup_path):
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"Created database backup at {backup_path}")
    
    # 5. Overwrite the table with the clean version
    print(f"Overwriting table '{TABLE_NAME}' in database...")
    df_clean.to_sql(TABLE_NAME, conn, if_exists='replace', index=False)
    
    # Verify the save
    verify_df = pd.read_sql_query(f'SELECT * FROM "{TABLE_NAME}" LIMIT 5', conn)
    print("Verification - New table columns in DB:", list(verify_df.columns)[:5])
    
    conn.close()
    print("Database conversion complete successfully!")

if __name__ == "__main__":
    fix_database()
