print("main.py を読み込みました")

import os
import json
import random
from datetime import datetime, timedelta
import pytz
import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- Flask keep-alive (Renderでは無くてもOK) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()

# --- 必須 env のチェック ---
if "GOOGLE_CREDENTIALS" not in os.environ:
    raise Exception("GOOGLE_CREDENTIALS が設定されていません")
if "SPREADSHEET_ID" not in os.environ:
    raise Exception("SPREADSHEET_ID が設定されていません")
if "DISCORD_TOKEN" not in os.environ:
    raise Exception("DISCORD_TOKEN が設定されていません")

# --- Google Sheets 認証（環境変数には JSON をそのまま貼る） ---
service_key_json = os.environ["GOOGLE_CREDENTIALS"]
# service_key_json は Google から落とした JSON をそのまま貼る（改行含む）
SERVICE_ACCOUNT_INFO = json.loads(service_key_json)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_INFO, scope)
gc = gspread.authorize(credentials)
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("ひまみくじデータ")

# --- Discord Bot ---
JST = pytz.timezone("Asia/Tokyo")
intents = discord.Intents.default()
# スラッシュコマンドだけなら message_content は不要。ただし必要なら True にする
intents.message_content = False
bot = commands.Bot(command_prefix="!", intents=intents)

# 絵文字変換
def number_to_emoji(num):
    digits = {"0":"0️⃣","1":"1️⃣","2":"2️⃣","3":"3️⃣","4":"4️⃣",
              "5":"5️⃣","6":"6️⃣","7":"7️⃣","8":"8️⃣","9":"9️⃣"}
    return "".join(digits[d] for d in str(num))

omikuji_results = [
    ("大大吉", 0.3), ("大吉", 15), ("吉", 20), ("中吉", 25),
    ("小吉", 35), ("末吉", 1), ("凶", 10), ("大凶", 5),
    ("大大凶", 0.1), ("ひま吉", 0.5), ("C賞", 0.5)
]

def load_data():
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")
    await bot.tree.sync()
    print("BOT は起動しました！")

@bot.tree.command(name="ひまみくじ", description="1日1回 ひまみくじを引けます！")
async def himamikuji(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    data = load_data()
    today = datetime.now(JST).date()

    if user_id not in data:
        data[user_id] = {"last_date": None, "result": None, "streak": 0, "time": "不明"}

    last_date = data[user_id]["last_date"]
    last_result = data[user_id]["result"]
    last_time = data[user_id]["time"]
    streak = data[user_id]["streak"]

    # すでに今日引いている場合（2行表示）
    if last_date == str(today):
        emoji_streak = number_to_emoji(streak)
        await interaction.response.send_message(
            f"## {username}は今日はもうひまみくじを引きました！\n"
            f"## 結果：［ひまみくじ継続中！！！{emoji_streak}日目！！！］\n"
            f"（{last_time} に引きました！）"
        )
        return

    results = [r[0] for r in omikuji_results]
    weights = [r[1] for r in omikuji_results]
    result = random.choices(results, weights)[0]

    if last_date == str(today - timedelta(days=1)):
        streak += 1
    else:
        streak = 1
    emoji_streak = number_to_emoji(streak)

    time_str = datetime.now(JST).strftime("%H:%M")
    data[user_id].update({
        "last_date": str(today),
        "result": result,
        "streak": streak,
        "time": time_str
    })
    save_data(data)

    # Google Sheets に書き込み（失敗しても例外を吐かない）
    try:
        sheet.append_row([user_id, username, str(today), result, streak, time_str])
    except Exception as e:
        print("Google Sheets 書き込み失敗:", e)

    await interaction.response.send_message(
        f"## {username}の今日の運勢はです！！！\n"
        f"## ［ひまみくじ継続中！！！{emoji_streak}日目！！！］"
    )

# --- Bot 起動 ---
TOKEN = os.environ["DISCORD_TOKEN"]
bot.run(TOKEN)


