import os
import random
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# ====== ENV ======
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_SERVICE_KEY = os.getenv("GOOGLE_SERVICE_KEY")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN が .env に設定されていません")

# ===== Discord Bot =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== Google Sheet =====
SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(GOOGLE_SERVICE_KEY, scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open("ひまみくじデータ").sheet1  # 位置は絶対に変えない


def get_sheet_row(user_id):
    rows = sheet.get_all_values()
    for i, row in enumerate(rows):
        if row[0] == user_id:
            return i, row
    return None, None


def write_sheet(user_id, username, date, time, result, streak, total, best, counts):
    row_index, row = get_sheet_row(user_id)

    values = [user_id, username, date, time, result, streak, total, best] + counts

    if row_index is not None:
        sheet.update(f"A{row_index+1}:S{row_index+1}", [values])
    else:
        sheet.append_row(values)


# ===== ひまみくじ確率 =====
fortune_list = [
    "大大吉","大吉","吉","中吉","小吉","末吉","凶","大凶","大大凶","ひま吉","C賞"
]
fortune_weights = [0.5,15,20,25,35,1,10,5,0.1,0.5,0.5]


def draw_fortune():
    return random.choices(fortune_list, weights=fortune_weights, k=1)[0]


# ===== コマンド =====
@bot.tree.command(name="ひまみくじ", description="1日1回ひまみくじを引けます!", guild=discord.Object(id=GUILD_ID))
async def himamikuji(interaction: discord.Interaction):

    await interaction.response.defer()

    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M")

    row_index, row = get_sheet_row(user_id)

    # ============ 初回ユーザー ============
    if row is None:
        result = draw_fortune()
        streak = 1
        total = 1
        best = 1
        counts = [1 if f == result else 0 for f in fortune_list]

        write_sheet(user_id, username, today, now_time, result, streak, total, best, counts)

        return await interaction.followup.send(
            f"## 🎉 **{username} の今日の運勢は【{result}】です！**\n"
            f"## [ひまみくじ継続中！！！ 🔥1️⃣ 日目！！！]"
        )

    # ============ 既存ユーザー ============
    last_date = row[2]
    last_time = row[3]
    last_result = row[4]

    streak = int(row[5])
    total = int(row[6])
    best = int(row[7])
    counts = list(map(int, row[8:19]))  # A〜S列フォーマットをそのまま使用

    # 今日すでに引いた場合
    if last_date == today:
        return await interaction.followup.send(
            f"## 💡 {username} は今日はもうひまみくじを引きました！\n"
            f"## 結果：【{last_result}】 [ひまみくじ継続中！！！ {streak}️⃣日目！！！]\n"
            f"（{last_time} に引きました）"
        )

    # ============ 本日初回処理 ============
    result = draw_fortune()

    # streak
    if (datetime.strptime(today, "%Y-%m-%d") -
        datetime.strptime(last_date, "%Y-%m-%d")) == timedelta(days=1):
        streak += 1
    else:
        streak = 1

    total += 1
    best = max(best, streak)

    counts[fortune_list.index(result)] += 1

    write_sheet(user_id, username, today, now_time, result, streak, total, best, counts)

    return await interaction.followup.send(
        f"## 🎉 **{username} の今日の運勢は【{result}】です！**\n"
        f"## [ひまみくじ継続中！！！ {streak}️⃣ 日目！！！]"
    )


# ===== 起動 =====
@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    print("ひまみくじ BOT 起動しました！")


bot.run(DISCORD_TOKEN)


