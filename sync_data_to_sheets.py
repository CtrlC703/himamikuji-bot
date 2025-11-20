import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# --- JSTタイムゾーン ---
JST = pytz.timezone('Asia/Tokyo')

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

# --- data.json 読み込み ---
def load_data_file():
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

data_cache = load_data_file()

# --- 結果列マップ ---
RESULT_COL_MAP = {
    "大大吉": 9,  "大吉": 10, "吉": 11, "中吉": 12,
    "小吉": 13,  "末吉": 14, "凶": 15, "大凶": 16,
    "大大凶": 17,"ひま吉": 18,"C賞": 19
}

def safe_int(val):
    try:
        return int(val)
    except:
        return 0

# --- ユーザー行取得 ---
def find_user_row(user_id):
    try:
        cell = sheet.find(str(user_id), in_column=1)
        if cell:
            return cell.row
        return None
    except Exception:
        return None

# --- 既存行更新 ---
def update_existing_row(row, user_id, username, user_data):
    existing = sheet.row_values(row)
    while len(existing) < 19:
        existing.append("")

    # 前回値
    prev_date_str = existing[2]
    prev_streak = safe_int(existing[5])
    prev_total = safe_int(existing[6])
    prev_best = safe_int(existing[7])
    result_counts = [safe_int(existing[i]) for i in range(8,19)]

    today_str = user_data["last_date"]
    result = user_data["result"]
    streak = user_data["streak"]

    # 結果カウント更新
    result_col = RESULT_COL_MAP.get(result)
    if result_col:
        idx = result_col - 9
        result_counts[idx] += 1

    # 新しい行データ作成
    new_row = [""]*19
    new_row[0] = str(user_id)
    new_row[1] = username or "Unknown"
    new_row[2] = today_str
    new_row[3] = user_data.get("time","不明")
    new_row[4] = result
    new_row[5] = str(streak)
    new_row[6] = str(prev_total + 1)  # 総合は1増
    new_row[7] = str(max(prev_best, streak))
    for i in range(11):
        new_row[8+i] = str(result_counts[i])

    sheet.update(f"A{row}:S{row}", [new_row])
    print(f"ユーザー {username} を復元しました")

# --- 新規行作成 ---
def create_new_row(user_id, username, user_data):
    streak = user_data["streak"]
    total = 1
    best = streak
    result_counts = ["0"]*11
    result = user_data["result"]
    idx = RESULT_COL_MAP.get(result) - 9
    result_counts[idx] = "1"

    new_row = [""]*19
    new_row[0] = str(user_id)
    new_row[1] = username or "Unknown"
    new_row[2] = user_data["last_date"]
    new_row[3] = user_data.get("time","不明")
    new_row[4] = result
    new_row[5] = str(streak)
    new_row[6] = str(total)
    new_row[7] = str(best)
    for i in range(11):
        new_row[8+i] = result_counts[i]

    sheet.append_row(new_row)
    print(f"ユーザー {username} を新規追加しました")

# --- メイン同期処理 ---
for user_id, user_data in data_cache.items():
    username = user_data.get("username") or "Unknown"
    row = find_user_row(user_id)
    if row:
        update_existing_row(row, user_id, username, user_data)
    else:
        create_new_row(user_id, username, user_data)
