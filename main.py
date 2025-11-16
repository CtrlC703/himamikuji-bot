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

# --- Flask keep-alive（Render用） ---
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

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(SERVICE_ACCOUNT_INFO, scope)
gc = gspread.authorize(credentials)

SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise Exception("SPREADSHEET_ID が設定されていません")

sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("ひまみくじデータ")

# --- Discord Bot ---
JST = pytz.timezone('Asia/Tokyo')
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- キャッシュ（再起動しても復元するデータ） ---
data_cache = {}

def load_data_file():
    """data.json を読み込む"""
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data_file(data):
    """data.json に保存"""
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

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

# --- BOT 起動時に data.json をキャッシュにロード ---
@bot.event
async def on_ready():
    global data_cache

    print(f"ログイン完了：{bot.user}")

    # ←★ 追加：data.json の内容をキャッシュに復元
    data_cache = load_data_file()
    print("data.json → キャッシュ復元完了")

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

# --- スラッシュコマンド ---
@bot.tree.command(name="ひまみくじ", description="1日1回 ひまみくじを引けます！")
async def himamikuji(interaction: discord.Interaction):

    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    today = datetime.now(JST).date()

    # キャッシュになければ初期化
    if user_id not in data_cache:
        data_cache[user_id] = {
            "last_date": None,
            "result": None,
            "streak": 0,
            "time": "不明"
        }

    user = data_cache[user_id]
    last_date = user["last_date"]
    last_result = user["result"]
    last_time = user["time"]
    streak = user["streak"]

    # 今日すでに引いた？
    if last_date == str(today):
        emoji_streak = number_to_emoji(streak)
        await interaction.response.send_message(
            f"## {username}は今日はもうひまみくじを引きました！\n"
            f"## 結果：【{last_result}】［ひまみくじ継続中！！！ {emoji_streak}日目！！！］（{last_time} に引きました）"
        )
        return

    # おみくじ抽選
    results = [r[0] for r in omikuji_results]
    weights = [r[1] for r in omikuji_results]
    result = random.choices(results, weights)[0]

    # 連続判定
    if last_date == str(today - timedelta(days=1)):
        streak += 1
    else:
        streak = 1

    # 更新
    time_str = datetime.now(JST).strftime("%H:%M")
    data_cache[user_id] = {
        "last_date": str(today),
        "result": result,
        "streak": streak,
        "time": time_str
    }

    # data.json 保存（←再起動しても維持される）
    save_data_file(data_cache)

    # Sheets に保存（任意）
    try:
        sheet.append_row([user_id, username, str(today), result, streak, time_str])
    except Exception as e:
        print("Google Sheets 書き込み失敗:", e)

    emoji_streak = number_to_emoji(streak)
    await interaction.response.send_message(
        f"## {username} の今日の運勢は【{result}】です！\n"
        f"## ［ひまみくじ継続中！！！ {emoji_streak}日目！！！］"
    )

# --- 実行 ---
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise Exception("DISCORD_TOKEN が設定されていません")

bot.run(TOKEN)
