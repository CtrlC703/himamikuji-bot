import json
import os
from datetime import datetime, timedelta
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- JST設定 ---
JST = pytz.timezone("Asia/Tokyo")

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

# --- ユーティリティ ---
RESULT_COL_MAP = {
    "大大吉": 9,  "大吉": 10, "吉": 11, "中吉": 12,
    "小吉": 13, "末吉": 14, "凶": 15, "大凶": 16,
    "大大凶": 17, "ひま吉": 18, "C賞": 19
}

def safe_int(val):
    try:
        return int(val)
    except:
        return 0

def find_user_row(user_id):
    try:
        cell = sheet.find(str(user_id), in_column=1)
        return cell.row
    except gspread.exceptions.CellNotFound:
        return None

# --- data.json 読み込み ---
with open("data.json", "r", encoding="utf-8") as f:
    data_cache = json.load(f)

# --- 同期処理 ---
for user_id, user_data in data_cache.items():
    username = "不明"
    today_str = user_data.get("last_date", "")
    time_str = user_data.get("time", "不明")
    result = user_data.get("result", "吉")
    streak = user_data.get("streak", 1)

    row = find_user_row(user_id)
    if row:
        # 既存行を上書き
        existing = sheet.row_values(row)
        while len(existing) < 19:
            existing.append("")

        prev_total = safe_int(existing[6])
        prev_best = safe_int(existing[7])
        total = max(prev_total, streak)
        best = max(prev_best, streak)

        # 結果カウントを調整（Google Sheets の結果列に反映）
        result_counts = [safe_int(existing[i]) for i in range(8,19)]
        idx = RESULT_COL_MAP.get(result, 11) - 9
        result_counts[idx] = max(result_counts[idx], 1)  # 最低1回はカウント

        new_row = [""]*19
        new_row[0] = str(user_id)
        new_row[1] = username
        new_row[2] = today_str
        new_row[3] = time_str
        new_row[4] = result
        new_row[5] = str(streak)
        new_row[6] = str(total)
        new_row[7] = str(best)
        for i in range(11):
            new_row[8+i] = str(result_counts[i])

        sheet.update(f"A{row}:S{row}", [new_row])
    else:
        # 新規ユーザーは追加
        new_row = [""]*19
        new_row[0] = str(user_id)
        new_row[1] = username
        new_row[2] = today_str
        new_row[3] = time_str
        new_row[4] = result
        new_row[5] = str(streak)
        new_row[6] = str(streak)
        new_row[7] = str(streak)
        for i in range(11):
            new_row[8+i] = "0"
        idx = RESULT_COL_MAP.get(result, 11) - 9
        new_row[8+idx] = "1"
        sheet.append_row(new_row)

print("data.json と Google Sheets の同期が完了しました！")
