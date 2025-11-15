print("main.py を読み込みました")

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

# ==============================
# Google Sheets 接続設定
# ==============================
SHEET_NAME = "ひまみくじデータ"

# 環境変数 GOOGLE_SERVICE_KEY に入っている JSON を読む
service_json = os.environ.get("GOOGLE_SERVICE_KEY")
if service_json is None:
    raise Exception("GOOGLE_SERVICE_KEY が設定されていません")

service_info = json.loads(service_json)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_info, scope)
gc = gspread.authorize(credentials)

# スプレッドシートを開く
spreadsheet = gc.open_by_key("1LDx3y_j1CukwVtj0186z9kP6bspPkfsz_oVW79WNOCU")
worksheet = spreadsheet.worksheet(SHEET_NAME)

# 行検索して取得
def load_user_data(user_id):
    try:
        cell = worksheet.find(user_id)
        row = cell.row
        data = worksheet.row_values(row)

        return {
            "user_id": data[0],
            "last_date": data[1],
            "result": data[2],
            "streak": int(data[3]),
            "time": data[4]
        }
    except:
        return None

# 保存（行がない場合は追加）
def save_user_data(user_id, last_date, result, streak, time):
    existing = load_user_data(user_id)

    if existing:
        row = worksheet.find(user_id).row
        worksheet.update(f"A{row}:E{row}", [[user_id, last_date, result, streak, time]])
    else:
        worksheet.append_row([user_id, last_date, result, streak, time])


# ==============================
# Flask（Render keep-alive）
# ==============================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()


# ==============================
# Discord BOT
# ==============================
JST = pytz.timezone('Asia/Tokyo')
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

# 数字→絵文字
def number_to_emoji(num):
    digits = {"0":"0️⃣","1":"1️⃣","2":"2️⃣","3":"3️⃣","4":"4️⃣",
              "5":"5️⃣","6":"6️⃣","7":"7️⃣","8":"8️⃣","9":"9️⃣"}
    return "".join(digits[d] for d in str(num))

# おみくじ
omikuji_results = [
    ("大大吉", 0.3),
    ("大吉", 15),
    ("吉", 20),
    ("中吉", 25),
    ("小吉", 35),
    ("末吉", 1),
    ("凶", 10),
    ("大凶", 5),
    ("大大凶", 0.1),
    ("ひま吉", 0.5),
    ("C賞", 0.5)
]

@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")
    await bot.tree.sync()
    print("BOT は起動しました！")

# ==============================
# /ひまみくじ コマンド
# ==============================
@bot.tree.command(name="ひまみくじ", description="1日1回 ひまみくじを引けます！")
async def himamikuji(interaction: discord.Interaction):

    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    today = datetime.now(JST).date()

    data = load_user_data(user_id)

    # 初回
    if data is None:
        data = {
            "last_date": None,
            "result": None,
            "streak": 0,
            "time": "不明"
        }

    last_date = data["last_date"]
    last_result = data["result"]
    last_time = data["time"]
    streak = data["streak"]

    # 今日すでに引いたか？
    if last_date == str(today):
        emoji_streak = number_to_emoji(streak)
        await interaction.response.send_message(
            f"## {username}は今日はもうひまみくじを引きました！\n"
            f"## 結果：【{last_result}】［ひまみくじ継続中！！！{emoji_streak}日目！！！］（{last_time} に引きました！）"
        )
        return

    # 抽選
    results = [r[0] for r in omikuji_results]
    weights = [r[1] for r in omikuji_results]
    result = random.choices(results, weights)[0]

    # ストリーク判定
    if last_date == str(today - timedelta(days=1)):
        streak += 1
    else:
        streak = 1
    emoji_streak = number_to_emoji(streak)

    # 保存
    time_str = datetime.now(JST).strftime("%H:%M")
    save_user_data(user_id, str(today), result, streak, time_str)

    # 返信
    await interaction.response.send_message(
        f"## {username}の今日の運勢は【{result}】です！！！\n"
        f"## ［ひまみくじ継続中！！！{emoji_streak}日目！！！］"
    )


# ==============================
# TOKEN 読み込み
# ==============================
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("⚠️ DISCORD_TOKEN が設定されていません。")
else:
    bot.run(TOKEN)

