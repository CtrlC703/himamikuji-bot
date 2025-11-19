import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz
import os

# --- JST設定 ---
JST = pytz.timezone('Asia/Tokyo')

# --- Google Sheets 認証 ---
service_key_json = os.environ.get("GOOGLE_SERVICE_KEY")
if not service_key_json:
    raise Exception("GOOGLE_SERVICE_KEY が設定されていません")

SERVICE_ACCOUNT_INFO = json.loads(service_key_json)

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_INFO, scope)
gc = gspread.authorize(credentials)

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise Exception("SPREADSHEET_ID が設定されていません")

sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("ひまみくじデータ")

# --- Google Sheets から data.json 作成 ---
data_cache = {}

rows = sheet.get_all_values()  # 全行取得
for row in rows[1:]:  # 1行目はヘッダーならスキップ
    if len(row) < 6:  # 必要な列が揃っていない行は無視
        continue

    user_id = row[0].strip()
    username = row[1].strip()
    last_date = row[2].strip()       # C列: 直近日付
    last_time = row[3].strip()       # D列: 直近時間
    last_result = row[4].strip()     # E列: 直近結果
    streak = row[5].strip()

    # streak は整数に変換
    try:
        streak = int(streak)
    except:
        streak = 0

    if user_id:
        data_cache[user_id] = {
            "last_date": last_date,
            "result": last_result,
            "streak": streak,
            "time": last_time
        }

# --- data.json に書き込む ---
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data_cache, f, ensure_ascii=False, indent=4)

print(f"復元完了！ {len(data_cache)} 件のユーザーを data.json に保存しました。")
