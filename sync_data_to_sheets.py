import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
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

# --- data.json 読み込み ---
with open("data.json", "r", encoding="utf-8") as f:
    data_cache = json.load(f)

# --- おみくじ結果列マップ ---
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

def find_user_row(user_id):
    try:
        cell = sheet.find(str(user_id), in_column=1)
        if cell:
            return cell.row
        return None
    except gspread.exceptions.CellNotFound:
        return None

def update_or_create_row(user_id, user_info):
    username = user_info.get("name") or user_info.get("username") or "Unknown"
    last_date = user_info.get("last_date", "")
    result = user_info.get("result", "")
    streak = user_info.get("streak", 0)
    time = user_info.get("time", "")

    row = find_user_row(user_id)
    if row:
        existing = sheet.row_values(row)
        while len(existing) < 19:
            existing.append("")

        # 既存結果カウント保持
        result_counts = [safe_int(existing[i]) for i in range(8,19)]

        # 今日の結果だけカウント増やす
        result_col = RESULT_COL_MAP.get(result)
        if result_col:
            idx = result_col - 9
            result_counts[idx] = 1  # 1日1回のみ反映

        new_row = [""]*19
        new_row[0] = str(user_id)
        new_row[1] = username
        new_row[2] = last_date
        new_row[3] = time
        new_row[4] = result
        new_row[5] = str(streak)
        new_row[6] = str(streak)  # totalと同じでOK
        new_row[7] = str(streak)  # bestをとりあえず同じ
        for i in range(11):
            new_row[8+i] = str(result_counts[i])

        sheet.update(f"A{row}:S{row}", [new_row])
        print(f"ユーザー {username} を更新しました")
    else:
        # 新規行作成
        new_row = [""]*19
        new_row[0] = str(user_id)
        new_row[1] = username
        new_row[2] = last_date
        new_row[3] = time
        new_row[4] = result
        new_row[5] = str(streak)
        new_row[6] = str(streak)
        new_row[7] = str(streak)
        for i in range(11):
            new_row[8+i] = "0"
        result_col = RESULT_COL_MAP.get(result)
        if result_col:
            new_row[8 + (result_col - 9)] = "1"
        sheet.append_row(new_row)
        print(f"ユーザー {username} を新規作成しました")

# --- 全ユーザー同期 ---
for user_id, user_info in data_cache.items():
    update_or_create_row(user_id, user_info)

print("Google Sheets と data.json の完全同期が完了しました！")
