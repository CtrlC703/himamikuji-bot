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
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 数字 → 絵文字 ---
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

# --- 結果列マップ（I列～S列） ---
RESULT_COL_MAP = {
    "大大吉": 9,  "大吉": 10, "吉": 11, "中吉": 12,
    "小吉": 13, "末吉": 14, "凶": 15, "大凶": 16,
    "大大凶": 17, "ひま吉": 18, "C賞": 19
}

# --- 起動時処理 ---
@bot.event
async def on_ready():
    global data_cache
    print(f"ログイン完了：{bot.user}")
    data_cache = load_data_file()
    print("data.json → キャッシュ復元完了")

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

# --- シート更新ユーティリティ ---
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
    prev_date = None
    if prev_date_str:
        try:
            prev_date = datetime.strptime(prev_date_str, "%Y-%m-%d").date()
        except:
            pass

    if prev_date == today:
        streak = prev_streak
        total = prev_total
    elif prev_date == today - timedelta(days=1):
        streak = prev_streak + 1
        total = prev_total + 1
    else:
        streak = 1
        total = prev_total + 1

    best = max(prev_best, streak)

    result_col = RESULT_COL_MAP.get(result)
    result_counts = [safe_int(existing[i]) for i in range(8,19)]
    if result_col and prev_date != today:
        idx = result_col - 9
        result_counts[idx] += 1

    new_row = [""]*19
    new_row[0] = str(user_id)
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
    new_row[0] = str(user_id)
    new_row[1] = username
    new_row[2] = date_str
    new_row[3] = time_str
    new_row[4] = result
    new_row[5] = str(streak)
    new_row[6] = str(total)
    new_row[7] = str(best)
    for i in range(11):
        new_row[8+i] = "0"
    idx = RESULT_COL_MAP.get(result) - 9
    new_row[8+idx] = "1"
    sheet.append_row(new_row)

# --- スラッシュコマンド ---
@bot.tree.command(name="ひまみくじ", description="1日1回 ひまみくじを引けます！")
async def himamikuji(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    today = datetime.now(JST).date()
    today_str = today.strftime("%Y-%m-%d")
    time_str = datetime.now(JST).strftime("%H:%M")

    if user_id not in data_cache:
        data_cache[user_id] = {"last_date": None, "result": None, "streak": 0, "time": "不明"}

    user = data_cache[user_id]

    # 同日チェック
    if user["last_date"] == str(today):
        await interaction.response.send_message(
            f"{username}は今日はもうひまみくじを引きました！\n"
            f"結果：【{user['result']}】［ひまみくじ継続中！！！ {number_to_emoji(user['streak'])}日目！！！］（{user['time']} に引きました）"
        )
        return

    # 抽選
    results = [r[0] for r in omikuji_results]
    weights = [r[1] for r in omikuji_results]
    result = random.choices(results, weights)[0]

    # Google Sheets 更新
    try:
        row = find_user_row(user_id)
        if row:
            update_existing_row(row, user_id, username, today_str, time_str, result)
        else:
            create_new_row(user_id, username, today_str, time_str, result)
    except Exception as e:
        print("Google Sheets 書き込み失敗:", e)

    # キャッシュ更新
    if user["last_date"] == str(today - timedelta(days=1)):
        streak = user["streak"] + 1
    else:
        streak = 1
    data_cache[user_id] = {"last_date": str(today), "result": result, "streak": streak, "time": time_str}
    save_data_file(data_cache)

    await interaction.response.send_message(
        f"{username} の今日の運勢は【{result}】です！\n"
        f"［ひまみくじ継続中！！！ {number_to_emoji(streak)}日目！！！］"
    )

# --- 実行 ---
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise Exception("DISCORD_TOKEN が設定されていません")

bot.run(TOKEN)

