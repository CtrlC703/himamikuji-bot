import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import pytz
from datetime import datetime

# --- Google Sheets 認証 ---
service_key_json = os.environ.get("GOOGLE_SERVICE_KEY")
if not service_key_json:
    raise Exception("GOOGLE_SERVICE_KEY が設定されていません")
SERVICE_ACCOUNT_INFO = json.loads(service_key_json)

scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_INFO, scope)
gc = gspread.authorize(credentials)

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise Exception("SPREADSHEET_ID が設定されていません")

sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("ひまみくじデータ")

# --- JST設定 ---
JST = pytz.timezone('Asia/Tokyo')

# --- Google Sheets から data.json 作成 ---
data_cache = {}

rows = sheet.get_all_values()  # 全行取得
for row in rows[1:]:  # 1行目はヘッダーならスキップ
    if len(row) < 6:
        continue
    user_id = row[0].strip()
    username = row[1].strip()
    last_date = row[2].strip()
    last_time = row[3].strip()
    last_result = row[4].strip()
    streak = int(row[5].strip()) if row[5].strip().isdigit() else 0

    if user_id:
        data_cache[user_id] = {
            "last_date": last_date,
            "result": last_result,
            "streak": streak,
            "time": last_time
        }

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data_cache, f, ensure_ascii=False, indent=4)

print(f"復元完了！ {len(data_cache)} 件のユーザーを data.json に保存しました。")
