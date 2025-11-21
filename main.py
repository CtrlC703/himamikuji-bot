import os
import random
from datetime import datetime
import discord
from discord.ext import commands
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
import asyncpg

# --- dotenv 読み込み ---
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_SERVICE_KEY = os.getenv("GOOGLE_SERVICE_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# --- Bot 初期化 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- おみくじ結果と確率 ---
RESULTS = [
    ("大大吉", 0.5), ("大吉", 15), ("吉", 20), ("中吉", 25), 
    ("小吉", 35), ("末吉", 1), ("凶", 10), ("大凶", 5),
    ("大大凶", 0.1), ("ひま吉", 0.5), ("C賞", 0.5)
]

def draw_result():
    choices, weights = zip(*RESULTS)
    return random.choices(choices, weights=weights, k=1)[0]

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
    await bot.db.execute("""
        INSERT INTO himamikuji (user_id, username, last_date, result, streak, time)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (user_id)
        DO UPDATE SET username=$2, last_date=$3, result=$4, streak=$5, time=$6;
    """, user_id, username, last_date, result, streak, time)

# --- Google Sheets 初期化 ---
scope = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_info(eval(GOOGLE_SERVICE_KEY), scopes=scope)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(SPREADSHEET_ID).sheet1  # 1枚目のシート使用

# --- Google Sheet 更新関数 ---
def update_sheet(user_id, username, today, now_time, streak, result):
    rows = sheet.get_all_records()
    user_found = False
    for i, row in enumerate(rows):
        if str(row['ユーザーID']).strip() == user_id:
            user_found = True
            row_index = i + 2  # 1行目はヘッダー
            # 日付が変わったら直近時間を更新
            if row['直近日付'] != today:
                sheet.update_cell(row_index, 3, today)  # 直近日付 C列
                sheet.update_cell(row_index, 4, now_time)  # 直近時間 D列
            # 継続日数
            sheet.update_cell(row_index, 5, streak)  # E列
            # 総回数
            sheet.update_cell(row_index, 6, row['総回数'] + 1)  # F列
            # 最高継続
            max_streak = max(row['最高継続'], streak)
            sheet.update_cell(row_index, 7, max_streak)  # G列
            # 役別カウント
            role_cols = {
                "大大吉": 8, "大吉": 9, "吉": 10, "中吉": 11, "小吉": 12,
                "末吉": 13, "凶": 14, "大凶": 15, "大大凶": 16, "ひま吉": 17, "C賞": 18
            }
            sheet.update_cell(row_index, role_cols[result], row.get(result, 0) + 1)
            break
    # 初めてのユーザー
    if not user_found:
        new_row = [
            user_id, username, today, now_time, streak, 1, streak,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        ]
        # 新規役のカウント
        role_cols = ["大大吉","大吉","吉","中吉","小吉","末吉","凶","大凶","大大凶","ひま吉","C賞"]
        for idx, r in enumerate(role_cols):
            if r == result:
                new_row[7 + idx] = 1
        sheet.append_row(new_row)

# --- Bot 起動時 ---
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

    # DB 読み込み
    user_data = await read_user(user_id)

    # 今日すでに引いた場合
    if user_data and user_data["last_date"] == today:
        streak = user_data["streak"]
        result = user_data["result"]
        time = user_data["time"]
        await interaction.followup.send(
            f"{username}は今日はもうひまみくじを引きました！\n"
            f"結果：【{result}】［ひまみくじ継続中！！！ {streak}️⃣日目！！！］（{time} に引きました）"
        )
        return

    # 抽選
    result = draw_result()
    streak = (user_data["streak"] + 1) if user_data else 1

    # DB 保存
    await save_user(user_id, username, today, result, streak, now_time)

    # Google Sheet 更新
    update_sheet(user_id, username, today, now_time, streak, result)

    # 結果送信
    await interaction.followup.send(
        f"{username} の今日の運勢は【{result}】です！\n"
        f"［ひまみくじ継続中！！！ {streak}️⃣日目！！！］（{now_time} に引きました）"
    )

# --- 実行 ---
bot.run(TOKEN)



