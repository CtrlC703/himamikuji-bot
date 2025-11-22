import os
import random
from datetime import datetime
import discord
from discord.ext import commands
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

# --- dotenv 読み込み ---
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
GOOGLE_SERVICE_KEY = os.getenv("GOOGLE_SERVICE_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# --- Bot 初期化 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 役の設定と確率 ---
ROLES = [
    ("大大吉", 0.5), ("大吉", 15), ("吉", 20), ("中吉", 25),
    ("小吉", 35), ("末吉", 1), ("凶", 10), ("大凶", 5),
    ("大大凶", 0.1), ("ひま吉", 0.5), ("C賞", 0.5)
]

def draw_role():
    names, weights = zip(*ROLES)
    total = sum(weights)
    probs = [w/total for w in weights]
    return random.choices(names, probs)[0]

# --- Google Sheets 初期化 ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(GOOGLE_SERVICE_KEY, scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# --- ユーザー情報取得 ---
def get_sheet_data():
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="A2:S").execute()
    values = result.get("values", [])
    return values

def update_sheet_data(values):
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range="A2:S",
        valueInputOption="USER_ENTERED",
        body={"values": values}
    ).execute()

def find_user_row(user_id, data):
    for idx, row in enumerate(data):
        if len(row) > 0 and str(row[0]) == str(user_id):
            return idx
    return None

# --- Bot 起動時 ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("BOT起動成功！🎉")

# --- スラッシュコマンド ---
@bot.tree.command(name="ひまみくじ", description="1日1回ひまみくじを引けます!", guild=discord.Object(id=GUILD_ID))
async def himamikuji(interaction: discord.Interaction):
    await interaction.response.defer()  # 「考え中…」表示

    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M")

    data = get_sheet_data()
    row_idx = find_user_row(user_id, data)

    if row_idx is not None:
        row = data[row_idx]
        # 必要な列を拡張しておく
        while len(row) < 19:
            row.append("0")

        last_date = row[2] if len(row) > 2 else ""
        last_time = row[3] if len(row) > 3 else now_time
        last_result = row[4] if len(row) > 4 else ""
        streak = int(row[5]) if row[5] else 0
        total_count = int(row[6]) if row[6] else 0
        max_streak = int(row[7]) if row[7] else 0

        if last_date == today:
            # 今日すでに引いた場合
            await interaction.followup.send(
                f"## {username}は今日はもうひまみくじを引きました！\n"
                f"## 結果：【{last_result}】［ひまみくじ継続中！！！ {streak}️⃣日目！！！］（{last_time} に引きました）"
            )
            return
        else:
            # 日付が変わった場合、連続日数更新
            streak = streak + 1
            total_count = total_count + 1
    else:
        # 初回ユーザー
        streak = 1
        total_count = 1
        max_streak = 1
        row = [user_id, username] + [""] * 17
        data.append(row)
        row_idx = len(data) - 1

    # 抽選
    result = draw_role()

    # 最高継続更新
    max_streak = max(max_streak, streak)

    # 役のカウント更新
    role_idx_map = {name: i for i, (name, _) in enumerate(ROLES, start=7)}
    if result in role_idx_map:
        idx = role_idx_map[result]
        row[idx] = str(int(row[idx]) + 1 if row[idx] else 1)

    # 行を更新
    row[2] = today
    row[3] = now_time
    row[4] = result
    row[5] = str(streak)
    row[6] = str(total_count)
    row[7] = str(max_streak)
    row[1] = username  # 名前更新

    data[row_idx] = row
    update_sheet_data(data)

    await interaction.followup.send(
        f"## {username} の今日の運勢は【{result}】です！\n"
        f"## ［ひまみくじ継続中！！！ {streak}️⃣日目！！！］（{now_time} に引きました）"
    )

# --- 実行 ---
bot.run(TOKEN)




