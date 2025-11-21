import os
import random
from datetime import datetime
import asyncio
import discord
from discord.ext import commands
import asyncpg
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# --- dotenv 読み込み ---
load_dotenv()

# --- 環境変数 ---
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_SERVICE_KEY = json.loads(os.getenv("GOOGLE_SERVICE_KEY"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# --- Bot 初期化 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- おみくじ設定 ---
RESULTS = [
    ("大大吉", 0.5), ("大吉", 15), ("吉", 20), ("中吉", 25), ("小吉", 35),
    ("末吉", 1), ("凶", 10), ("大凶", 5), ("大大凶", 0.1), ("ひま吉", 0.5), ("C賞", 0.5)
]

def draw_lottery():
    r = random.uniform(0, 100)
    total = 0
    for name, prob in RESULTS:
        total += prob
        if r <= total:
            return name
    return RESULTS[-1][0]  # 万一のため最後を返す

# --- Google Sheet 初期化 ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_SERVICE_KEY, scope)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# --- DB 初期化 ---
async def init_db():
    bot.db = await asyncpg.connect(DATABASE_URL)
    await bot.db.execute("""
        CREATE TABLE IF NOT EXISTS himamikuji (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            last_date TEXT,
            result TEXT,
            streak INTEGER,
            time TEXT
        );
    """)

async def read_user(user_id: str):
    row = await bot.db.fetchrow("SELECT * FROM himamikuji WHERE user_id=$1", user_id)
    return dict(row) if row else None

async def save_user(user_id: str, username: str, last_date: str, result: str, streak: int, time: str):
    query = """
        INSERT INTO himamikuji (user_id, username, last_date, result, streak, time)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (user_id)
        DO UPDATE SET username=$2, last_date=$3, result=$4, streak=$5, time=$6;
    """
    await bot.db.execute(query, user_id, username, last_date, result, streak, time)

# --- Google Sheet 更新 ---
def update_sheet(user_id, username, last_date, now_time, streak, result):
    records = sheet.get_all_records()
    for i, row in enumerate(records, start=2):  # 1行目はヘッダー
        if str(row["ユーザーID"]) == user_id:
            # 既存ユーザー更新
            sheet.update_cell(i, 3, last_date)      # 直近日付
            sheet.update_cell(i, 4, now_time)       # 直近時間
            sheet.update_cell(i, 5, streak)         # 継続日数
            sheet.update_cell(i, 6, row["総回数"] + 1)  # 総回数
            sheet.update_cell(i, 7, max(row["最高継続"], streak))  # 最高継続
            # 役別カウント更新
            col_index = {"大大吉":8,"大吉":9,"吉":10,"中吉":11,"小吉":12,"末吉":13,"凶":14,"大凶":15,"大大凶":16,"ひま吉":17,"C賞":18}
            sheet.update_cell(i, col_index[result], row[result]+1)
            return
    # 新規ユーザー追加
    new_row = [user_id, username, last_date, now_time, streak, 1, streak] + [0]*11
    new_row[7 + RESULTS.index((result, next(prob for n, prob in RESULTS if n==result)))] = 1
    sheet.append_row(new_row)

# --- Bot 起動 ---
@bot.event
async def on_ready():
    await init_db()
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Logged in as {bot.user}")
    print("BOT起動成功！🎉")

# --- スラッシュコマンド ---
@bot.tree.command(name="ひまみくじ", description="1日1回ひまみくじを引けます!", guild=discord.Object(id=GUILD_ID))
async def himamikuji(interaction: discord.Interaction):
    await interaction.response.defer()

    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M")

    user_data = await read_user(user_id)
    if user_data and user_data["last_date"] == today:
        streak = user_data["streak"]
        result = user_data["result"]
        time = user_data["time"]
        await interaction.followup.send(
            f"## {username}は今日はもうひまみくじを引きました！\n"
            f"## 結果：【{result}】［ひまみくじ継続中！！！ {streak}️⃣日目！！！］（{time} に引きました）"
        )
        return

    # 抽選
    result = draw_lottery()
    streak = (user_data["streak"] + 1) if user_data else 1

    # DB 保存
    await save_user(user_id, username, today, result, streak, now_time)
    # Sheet 更新
    update_sheet(user_id, username, today, now_time, streak, result)

    await interaction.followup.send(
        f"## {username} の今日の運勢は【{result}】です！\n"
        f"## ［ひまみくじ継続中！！！ {streak}️⃣日目！！！］（{now_time} に引きました）"
    )

# --- 実行 ---
bot.run(TOKEN)



