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

# ---------- Google Sheets ----------
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets 認証
creds_json = os.environ.get("GOOGLE_SHEETS_KEY_JSON")
if creds_json:
    creds = Credentials.from_service_account_info(json.loads(creds_json))
    gc = gspread.authorize(creds)
    sh = gc.open("ひまみくじデータ")
    ws = sh.sheet1
else:
    print("⚠️ Google Sheets の認証情報がありません。Render の環境変数 GOOGLE_SHEETS_KEY_JSON を設定してください。")

# ---------- Flask keep alive ----------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_flask).start()

# ---------- Discord Bot ----------
JST = pytz.timezone('Asia/Tokyo')
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

# 絵文字変換
def number_to_emoji(num):
    digits = {"0":"0️⃣","1":"1️⃣","2":"2️⃣","3":"3️⃣","4":"4️⃣",
              "5":"5️⃣","6":"6️⃣","7":"7️⃣","8":"8️⃣","9":"9️⃣"}
    return "".join(digits[d] for d in str(num))

# おみくじ確率
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

# ---------- Google Sheets 用：ユーザーデータ管理 ----------
def load_user(user_id):
    try:
        data = ws.get_all_records()
        for row in data:
            if str(row["user_id"]) == str(user_id):
                return row
        return None
    except:
        return None

def save_user(user_id, last_date, result, streak, time_str):
    try:
        data = ws.get_all_records()
        for i, row in enumerate(data, start=2):
            if str(row["user_id"]) == str(user_id):
                ws.update(f"A{i}:E{i}", [[user_id, last_date, result, streak, time_str]])
                return

        ws.append_row([user_id, last_date, result, streak, time_str])
    except Exception as e:
        print("Google Sheets 保存エラー:", e)

# ---------- Bot 起動時 ----------
@bot.event
async def on_ready():
    print(f"ログイン完了：{bot.user}")
    await bot.tree.sync()
    print("BOT は起動しました！")

# ---------- /ひまみくじ ----------
@bot.tree.command(name="ひまみくじ", description="1日1回 ひまみくじを引けます！")
async def himamikuji(interaction: discord.Interaction):

    user_id = str(interaction.user.id)
    username = interaction.user.display_name

    today = datetime.now(JST).date()

    # Google Sheets からロード
    user = load_user(user_id)

    if not user:
        last_date = None
        last_result = None
        streak = 0
        last_time = "不明"
    else:
        last_date = user["last_date"]
        last_result = user["result"]
        streak = int(user["streak"])
        last_time = user["time"]

    # 今日すでに引いた？
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

    # ストリーク
    if last_date == str(today - timedelta(days=1)):
        streak += 1
    else:
        streak = 1

    emoji_streak = number_to_emoji(streak)
    time_str = datetime.now(JST).strftime("%H:%M")

    # Google Sheets に保存
    save_user(user_id, str(today), result, streak, time_str)

    await interaction.response.send_message(
        f"## {username}の今日の運勢は【{result}】です！！！\n"
        f"## ［ひまみくじ継続中！！！{emoji_streak}日目！！！］"
    )

# ---------- TOKEN ----------
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("⚠️ DISCORD_TOKEN が設定されていません。Renderの環境変数に追加してください。")
else:
    bot.run(TOKEN)
