import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import pytz

# --- JST設定 ---
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

# --- ユーザー行検索 ---
def find_user_row(user_id):
    try:
        cell = sheet.find(str(user_id), in_column=1)
        if cell:
            return cell.row
    except gspread.exceptions.APIError:
        pass
    return None

def safe_int(val):
    try:
        return int(val)
    except:
        return 0

# --- 既存行更新 ---
def update_existing_row(row, user_id, user_data):
    existing = sheet.row_values(row)
    while len(existing) < 19:
        existing.append("")

    prev_date_str = existing[2]
    prev_streak = safe_int(existing[5])
    prev_total = safe_int(existing[6])
    prev_best = safe_int(existing[7])
    result_counts = [safe_int(existing[i]) for i in range(8,19)]

    # 結果カウント更新
    result = user_data["result"]
    result_col = RESULT_COL_MAP.get(result)
    today = datetime.now(JST).date()
    prev_date = None
    if prev_date_str:
        try:
            prev_date = datetime.strptime(prev_date_str, "%Y-%m-%d").date()
        except:
            pass
    if prev_date != today and result_col:
        idx = result_col - 9
        result_counts[idx] += 1

    new_row = [""]*19
    new_row[0] = str(user_id)
    new_row[1] = user_data.get("username", "Unknown")
    new_row[2] = user_data.get("last_date", "")  # 日付はdata.json準拠
    new_row[3] = user_data.get("time", "不明")   # 時間もdata.json準拠
    new_row[4] = user_data.get("result", "")
    new_row[5] = str(user_data.get("streak", 0))
    new_row[6] = str(user_data.get("total", 0))
    new_row[7] = str(user_data.get("best", 0))
    for i in range(11):
        new_row[8+i] = str(result_counts[i])

    sheet.update(f"A{row}:S{row}", [new_row])
    print(f"ユーザー {new_row[1]} を復元しました")

# --- 新規行作成 ---
def create_new_row(user_id, user_data):
    streak = user_data.get("streak", 1)
    total = user_data.get("total", 1)
    best = user_data.get("best", 1)
    result_counts = [0]*11
    result = user_data.get("result")
    idx = RESULT_COL_MAP.get(result) - 9 if result in RESULT_COL_MAP else None
    if idx is not None:
        result_counts[idx] = 1

    new_row = [""]*19
    new_row[0] = str(user_id)
    new_row[1] = user_data.get("username", "Unknown")
    new_row[2] = user_data.get("last_date", "")
    new_row[3] = user_data.get("time", "不明")
    new_row[4] = result or ""
    new_row[5] = str(streak)
    new_row[6] = str(total)
    new_row[7] = str(best)
    for i in range(11):
        new_row[8+i] = str(result_counts[i])

    sheet.append_row(new_row)
    print(f"新規ユーザー {new_row[1]} を追加しました")

# --- 同期 ---
for user_id, user_data in data_cache.items():
    row = find_user_row(user_id)
    if row:
        update_existing_row(row, user_id, user_data)
    else:
        create_new_row(user_id, user_data)

print("Google Sheets と data.json の同期完了！")
