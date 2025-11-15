import json

# data.json の読み込み
with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for user_id, user_data in data.items():
    user_data["last_date"] = "2000-01-01"  # 過去の日付にリセット
    user_data["result"] = None              # 結果リセット
    user_data["streak"] = 0                 # 継続日数リセット
    user_data["time"] = "不明"              # 時刻リセット

# 保存
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print("全ユーザーの継続日数と今日の状態をリセットしました！")
