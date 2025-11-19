import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta
import pytz
import random
import os
from flask import Flask
from threading import Thread
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Flask keep-alive ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()

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

# --- Discord Bot ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- キャッシュ ---
data_cache = {}

def load_data_file():
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data_file(data):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- 絵文字変換 ---
def number_to_emoji(num):
    digits = {"0":"0️⃣","1":"1️⃣","2":"2️⃣","3":"3️⃣","4":"4️⃣",
              "5":"5️⃣","6":"6️⃣","7":"7️⃣","8":"8️⃣","9":"9️⃣"}
    return "".join(digits[d] for d in str(num))

# --- おみくじデータ ---
omikuji_results = [
    ("大大吉", 0.3), ("大吉", 15), ("吉", 20), ("中吉", 25),
    ("小吉", 35), ("末吉", 1), ("凶", 10), ("大凶", 5),
    ("大大凶", 0.1), ("ひま吉", 0.5), ("C賞", 0.5)
]

# --- 結果列マップ I..S ---
RESULT_COL_MAP = {
    "大大吉": 9,  # I
    "大吉": 10,   # J
    "吉": 11,     # K
    "中吉": 12,   # L
    "小吉": 13,   # M
    "末吉": 14,   # N
    "凶": 15,     # O
    "大凶": 16,   # P
    "大大凶": 17, # Q
    "ひま吉": 18, # R
    "C賞": 19     # S
}

# --- Bot起動時に Sheets から復元 ---
def restore_cache_from_sheet():
    global data_cache
    rows = sheet.get_all_values()
    for row in rows[1:]:  # ヘッダー行スキップ
        if len(row) < 6:
            continue
        user_id = row[0].strip()
        last_date = row[2].strip()
        last_time = row[3].strip()
        last_result = row[4].strip()
        streak = int(row[5]) if row[5].isdigit() else 0
        if user_id:
            data_cache[user_id] = {
                "last_date": last_date,
                "result": last_result,
                "streak": streak,
                "time": last_time
            }
    save_data_file(data_cache)
    print(f"Sheetsからキャッシュ復元完了: {len(data_cache)} 件")

# --- ユーティリティ ---
def find_user_row(user_id):
    try:
        cell = sheet.find(str(user_id), in_column=1)
        return cell.row
    except gspread.exceptions.CellNotFound:
        return None

def safe_int(val):
    try:
        return int(val)
    except:
        return 0

def update_existing_row(row, user_id, username, date_str, time_str, result):
    existing = sheet.row_values(row)
    while len(existing) < 19:
        existing.append("")
    prev_date_str = existing[2]
    prev_streak = safe_int(existing[5])
    prev_total = safe_int(existing[6])
    prev_best = safe_int(existing[7])
    today = datetime.now(JST).date()
    try:
        prev_date = datetime.strptime(prev_date_str, "%Y-%m-%d").date() if prev_date_str else None
    except:
        prev_date = None
    if prev_date is not None and today - prev_date == timedelta(days=1):
        streak = prev_streak + 1
    else:
        streak = 1
    total = prev_total + 1
    best = max(prev_best, streak)
    # 結果列
    result_col = RESULT_COL_MAP.get(result)
    result_counts = [safe_int(existing[i]) for i in range(8,19)]
    if result_col:
        idx = result_col - 9
        result_counts[idx] += 1
    new_row = [""]*19
    new_row[0] = user_id
    new_row[1] = username
    new_row[2] = date_str
    new_row[3] = time_str
    new_row[4] = result
    new_row[5] = str(streak)
    new_row[6] = str(total)
    new_row[7] = str(best)
    for i in range(11):
        new_row[8+i] = str(result_counts[i])
    sheet.update(f"A{row}:S{row}", [new_row])

def create_new_row(user_id, username, date_str, time_str, result):
    streak = 1
    total = 1
    best = 1
    new_row = [""]*19
    new_row[0] = user_id
    new_row[1] = username
    new_row[2] = date_str
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

# --- 起動イベント ---
@bot.event
async def on_ready():
    print(f"ログイン完了: {bot.user}")
    restore_cache_from_sheet()
    # スラッシュコマンド同期
    try:
        guild_id = int(os.environ.get("DISCORD_GUILD_ID", 0))
        if guild_id:
            guild = discord.Object(id=guild_id)
            synced = await bot.tree.sync(guild=guild)
            print(f"サーバー同期: {len(synced)}")
        else:
            synced = await bot.tree.sync()
            print(f"グローバル同期: {len(synced)}")
    except Exception as e:
        print("同期エラー:", e)
    print("BOT 起動完了！")

# --- /ひまみくじ ---
@bot.tree.command(name="ひまみくじ", description="1日1回 ひまみくじを引けます！")
async def himamikuji(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    today = datetime.now(JST).date()
    today_str = today.strftime("%Y-%m-%d")
    time_str = datetime.now(JST).strftime("%H:%M")

    # キャッシュ初期化
    if user_id not in data_cache:
        data_cache[user_id] = {
            "last_date": None,
            "result": None,
            "streak": 0,
            "time": "不明"
        }

    user = data_cache[user_id]
    last_date = user["last_date"]
    streak_cache = user["streak"]

    # 同日重複チェック
    if last_date == today_str:
        emoji_streak = number_to_emoji(streak_cache)
        await interaction.response.send_message(
            f"{username}は今日はもうひまみくじを引きました！\n"
            f"結果：【{user['result']}】 継続中 {emoji_streak}日目（{user['time']}に引きました）"
        )
        return

    # 抽選
    results = [r[0] for r in omikuji_results]
    weights = [r[1] for r in omikuji_results]
    result = random.choices(results, weights)[0]

    # キャッシュ更新
    if last_date == (today - timedelta(days=1)).strftime("%Y-%m-%d"):
        streak_cache += 1
    else:
        streak_cache = 1

    data_cache[user_id] = {
        "last_date": today_str,
        "result": result,
        "streak": streak_cache,
        "time": time_str
    }
    save_data_file(data_cache)

    # Sheets 更新
    try:
        row = find_user_row(user_id)
        if row:
            update_existing_row(row, user_id, username, today_str, time_str, result)
        else:
            create_new_row(user_id, username, today_str, time_str, result)
    except Exception as e:
        print("Google Sheets 書き込み失敗:", e)

    emoji_streak = number_to_emoji(streak_cache)
    await interaction.response.send_message(
        f"{username} の今日の運勢は【{result}】です！\n"
        f"継続中！！！ {emoji_streak}日目！！！"
    )

# --- 実行 ---
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise Exception("DISCORD_TOKEN が設定されていません")

bot.run(TOKEN)

