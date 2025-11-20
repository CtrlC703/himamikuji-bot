import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# --- JST ---
JST = pytz.timezone('Asia/Tokyo')

# --- Google Sheets 認証 ---
service_key_json = os.environ.get("GOOGLE_SERVICE_KEY")
if not service_key_json:
    raise Exception("GOOGLE_SERVICE_KEY が設定されていません")
SERVICE_ACCOUNT_INFO = json.loads(service_key_json)

scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_INFO, scope)
gc = gspread.authorize(credentials)

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise Exception("SPREADSHEET_ID が設定されていません")

sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("ひまみくじデータ")

# --- 結果列マップ（I列～S列） ---
RESULT_COL_MAP = {
    "大大吉": 9, "大吉": 10, "吉": 11, "中吉": 12,
    "小吉": 13, "末吉": 14, "凶": 15, "大凶": 16,
    "大大凶": 17, "ひま吉": 18, "C賞": 19
}

# --- data.json 読み込み ---
with open("data.json", "r", encoding="utf-8") as f:
    data_cache = json.load(f)

# --- ユーザー検索 ---
def find_user_row(user_id):
    for i, row in enumerate(sheet.get_all_values(), start=1):
        if row and row[0] == user_id:
            return i
    return None

def safe_int(val):
    try:
        return int(val)
    except:
        return 0

def update_existing_row(row, user_id, username, info):
    existing = sheet.row_values(row)
    while len(existing) < 19:
        existing.append("")

    today_str = info["last_date"]
    time_str = info.get("time", "不明")
    streak = info.get("streak", 1)
    total = safe_int(existing[6])
    total = max(total, info.get("streak", 1) + total - 1)
    best = max(safe_int(existing[7]), streak)
    result = info.get("result", "")

    # 結果の集計
    result_counts = [safe_int(existing[i]) for i in range(8,19)]
    result_col = RESULT_COL_MAP.get(result)
    if result_col:
        idx = result_col - 9
        # 過去の値を置き換えて1にする（data.json 優先）
        result_counts[idx] = 1

    new_row = [""]*19
    new_row[0] = user_id
    new_row[1] = username or "Unknown"
    new_row[2] = today_str
    new_row[3] = time_str
    new_row[4] = result
    new_row[5] = str(streak)
    new_row[6] = str(total)
    new_row[7] = str(best)
    for i in range(11):
        new_row[8+i] = str(result_counts[i])

    sheet.update(f"A{row}:S{row}", [new_row])
    print(f"ユーザー {username} を更新しました")

def create_new_row(user_id, username, info):
    streak = info.get("streak", 1)
    total = streak
    best = streak
    time_str = info.get("time", "不明")
    result = info.get("result", "")

    new_row = [""]*19
    new_row[0] = user_id
    new_row[1] = username or "Unknown"
    new_row[2] = info.get("last_date", "")
    new_row[3] = time_str
    new_row[4] = result
    new_row[5] = str(streak)
    new_row[6] = str(total)
    new_row[7] = str(best)
    for i in range(11):
        new_row[8+i] = "0"

    result_col = RESULT_COL_MAP.get(result)
    if result_col:
        idx = result_col - 9
        new_row[8+idx] = "1"

    sheet.append_row(new_row)
    print(f"ユーザー {username} を新規追加しました")

# --- 同期 ---
for user_id, info in data_cache.items():
    username = info.get("username", "")  # data.json に username を追加しておくこと
    row = find_user_row(user_id)
    if row:
        update_existing_row(row, user_id, username, info)
    else:
        create_new_row(user_id, username, info)

print("Google Sheets と data.json の完全同期が完了しました！")
