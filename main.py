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

# --- Flask keep-alive 用 ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# Flaskを別スレッドで起動
Thread(target=run_flask).start()

# --- Discord Bot ---
JST = pytz.timezone('Asia/Tokyo')
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

# 絵文字変換
def number_to_emoji(num):
    digits = {"0":"0️⃣","1":"1️⃣","2":"2️⃣","3":"3️⃣","4":"4️⃣",
              "5":"5️⃣","6":"6️⃣","7":"7️⃣","8":"8️⃣","9":"9️⃣"}
    return "".join(digits[d] for d in str(num))

# おみくじと確率
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

# --- /ひまみくじ ---
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

    # ✅ 今日すでに引いた場合
    if last_date == str(today):
        emoji_streak = number_to_emoji(streak)
        await interaction.response.send_message(
            f"## {username}は今日はもうひまみくじを引きました！\n"
            f"## 結果：【{last_result}】［ひまみくじ継続中！！！{emoji_streak}日目！！！］（{last_time} に引きました！）"
        )
        return

    # おみくじ抽選
    results = [r[0] for r in omikuji_results]
    weights = [r[1] for r in omikuji_results]
    result = random.choices(results, weights)[0]

    # ストリーク計算
    if last_date == str(today - timedelta(days=1)):
        streak += 1
    else:
        streak = 1
    emoji_streak = number_to_emoji(streak)

    # 記録
    time_str = datetime.now(JST).strftime("%H:%M")
    data[user_id] = {"last_date": str(today), "result": result, "streak": streak, "time": time_str}
    save_data(data)

    # 結果送信
    await interaction.response.send_message(
        f"## {username}の今日の運勢は【{result}】です！！！\n"
        f"## ［ひまみくじ継続中！！！{emoji_streak}日目！！！］"
    )

# --- TOKEN は Render の Secret Environment Variable に登録 ---
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print("⚠️ DISCORD_TOKEN が設定されていません。Renderの環境変数に追加してください。")
else:
    bot.run(TOKEN)
