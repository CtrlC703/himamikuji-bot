import os
import json
import random
from flask import Flask
import discord
from discord.ext import commands
import gspread
from google.oauth2.service_account import Credentials

# ============================
# Flask（Render の Web 停止対策）
# ============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Himamikuji Bot is running!"

# ============================
# Google Sheets 接続設定
# ============================
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

if not GOOGLE_CREDENTIALS:
    raise Exception("GOOGLE_CREDENTIALS が設定されていません")

creds_dict = json.loads(GOOGLE_CREDENTIALS)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
gc = gspread.authorize(credentials)

# ❗ スプレッドシート ID はこれだけ（URL ではない）
SPREADSHEET_ID = "1LDx3y_j1CukwVtj0186z9kP6bspPkfsz_oVW79WNOCU"

sheet = gc.open_by_key(SPREADSHEET_ID).worksheet("ひまみくじデータ")

# ============================
# Discord BOT セットアップ
# ============================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise Exception("DISCORD_TOKEN が設定されていません")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# ============================
# コマンド
# ============================
@bot.command()
async def ひまみくじ(ctx):
    fortunes = [
        "大吉", "中吉", "小吉", "末吉", "凶", "大凶",
        "ひま吉", "C賞"
    ]

    result = random.choice(fortunes)

    # シートに記録
    sheet.append_row([str(ctx.author.id), ctx.author.name, result])

    await ctx.send(f"{ctx.author.mention} の今日の運勢は… **{result}** ！")

# ============================
# Bot 起動
# ============================
def run_discord():
    bot.run(DISCORD_TOKEN)

# ============================
# Main
# ============================
if __name__ == "__main__":
    # Flask はバックグラウンドで動かす
    import threading
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000)).start()

    # Discord bot
    run_discord()
