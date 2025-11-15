import json
from datetime import datetime, timedelta

# 日本時間
import pytz
JST = pytz.timezone('Asia/Tokyo')

# data.json を読み込む関数
def load_data():
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# data.json を保存する関数
def save_data(data):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

data = load_data()
today = datetime.now(JST).date()
updated_users = 0

for user_id, user_data in data.items():
    # time が無ければ追加
    if "time" not in user_data:
        user_data["time"] = "不明"
    
    # streak を過去日から計算（過去に連続していた場合）
    last_date_str = user_data.get("last_date")
    if last_date_str:
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
        # 今日-1日 が最後に引いた日なら streak を維持
        if last_date == today - timedelta(days=1):
            user_data["streak"] = user_data.get("streak", 0) + 1
        # それ以外は streak 1
        else:
            user_data["streak"] = 1
    else:
        # last_date が無ければ初期化
        user_data["streak"] = 0

    updated_users += 1

save_data(data)
print(f"{updated_users} 人分のデータを修正しました。")
