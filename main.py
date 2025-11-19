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

# --- Flask keep-alive（必要なら有効） ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ThreadでFlaskを起動（もし外部Pingを使っているなら残す）
Thread(target=run_flask).start()

# --- Google Sheets 認証 ---
service_key_json = os.environ.get("GOOGLE_SERVICE_KEY")
if not service_key_json:
    raise Exception("GOOGLE_SERVICE_KEY が設定されていません")
SERVICE_ACCOUNT_INFO = json.loads(service_key_json)

scope = ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive"]
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
    try:
        with open("data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data_file(data):
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- 絵文字変換（そのまま） ---
def number_to_emoji(num):
    digits = {"0":"0️⃣","1":"1️⃣","2":"2️⃣","3":"3️⃣","4":"4️⃣",
              "5":"5️⃣","6":"6️⃣","7":"7️⃣","8":"8️⃣","9":"9️⃣"}
    return "".join(digits[d] for d in str(num))

# --- おみくじデータ（そのまま） ---
omikuji_results = [
    ("大大吉", 0.3), ("大吉", 15), ("吉", 20), ("中吉", 25),
    ("小吉", 35), ("末吉", 1), ("凶", 10), ("大凶", 5),
    ("大大凶", 0.1), ("ひま吉", 0.5), ("C賞", 0.5)
]

# --- 結果列マップ（A=1なので、I列は9） ---
RESULT_COL_MAP = {
    "大大吉": 9,  # I
    "大吉": 10,   # J
    "吉": 11,     # K
    "中吉": 12,   # L
    "小吉": 13,   # M
    "末吉": 14,   # N
    "凶": 15,     # O
    "大凶": 16,   # P
    "大大凶": 17, # Q
    "ひま吉": 18, # R
    "C賞": 19     # S
}

# --- 起動時の処理 ---
@bot.event
async def on_ready():
    global data_cache
    print(f"ログイン完了：{bot.user}")
    data_cache = load_data_file()
    print("data.json → キャッシュ復元完了")

    # スラッシュコマンド同期（既存の処理）
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

# --- シート更新ユーティリティ ---
def find_user_row(user_id):
    """A列（ユーザーID）で行を探す。見つかれば行番号、見つからなければ None を返す。"""
    try:
        cell = sheet.find(str(user_id), in_column=1)
        return cell.row
    except gspread.exceptions.CellNotFound:
        return None

def safe_int(val):
    try:
        return int(val)
    except:
        return 0

def update_existing_row(row, user_id, username, date_str, time_str, result):
    """
    指定行を更新：
    C(3)=date, D(4)=time, E(5)=result,
    F(6)=streak, G(7)=total, H(8)=best,
    I(9)-S(19) increment result column
    """
    # 現在の行データを取得（可能な限り）
    existing = sheet.row_values(row)
    # extend to length 19 for safe index
    while len(existing) < 19:
        existing.append("")

    # 前回の日付（C列）
    prev_date_str = existing[2]  # index0 -> A, so C is index2
    prev_streak = safe_int(existing[5])    # F (index5)
    prev_total = safe_int(existing[6])     # G (index6)
    prev_best = safe_int(existing[7])      # H (index7)

    # 日付判定
    today = datetime.now(JST).date()
    if prev_date_str:
        try:
            prev_date = datetime.strptime(prev_date_str, "%Y-%m-%d").date()
        except:
            # 形式が違ったらリセット扱い
            prev_date = None
    else:
        prev_date = None

    # 継続判定
    if prev_date is not None and today - prev_date == timedelta(days=1):
        streak = prev_streak + 1
    elif prev_date is not None and today == prev_date:
        # 同じ日なら既存の streak を維持（重複更新はしないように呼び出し側で制御）
        streak = prev_streak
    else:
        streak = 1

    # 総回数は +1（同日重複は事前に防いでいる想定）
    total = prev_total + 1

    best = max(prev_best, streak)

    # 結果列の増分処理：既存の値を int にして +1
    result_col = RESULT_COL_MAP.get(result)
    result_counts = [safe_int(existing[i]) for i in range(8, 19)]  # I(9) index8 ... S index18
    if result_col:
        idx = result_col - 9  # result_counts のインデックス
        result_counts[idx] = result_counts[idx] + 1

    # 新しい行配列（A〜S）
    new_row = [""] * 19
    new_row[0] = str(user_id)         # A
    new_row[1] = username             # B
    new_row[2] = date_str             # C
    new_row[3] = time_str             # D
    new_row[4] = str(streak)          # E -> F列? careful: Note mapping below
    # NOTE: your requested mapping is: F:連続日数 (col6). Since new_row is 0-based, index5 corresponds to F.
    # We'll fill according to column mapping:
    # index 4 -> column E, but we want E to be "直近の結果". So actually:
    # Let's correct mapping below properly.

    # Build according to final A..S mapping:
    # A idx0, B idx1, C idx2, D idx3, E idx4, F idx5, G idx6, H idx7, I idx8 ... S idx18
    new_row[4] = result               # E: 直近結果 (overwrite result text)
    new_row[5] = str(streak)          # F: 連続日数
    new_row[6] = str(total)           # G: 総回数
    new_row[7] = str(best)            # H: 最高継続日数

    # fill result counts into I..S (idx 8..18)
    for i in range(11):  # 11 result columns I..S
        new_row[8 + i] = str(result_counts[i])

    # Finally update the row in sheet (A..S)
    sheet.update(f"A{row}:S{row}", [new_row])

def create_new_row(user_id, username, date_str, time_str, result):
    # 初回行（A..S）
    streak = 1
    total = 1
    best = 1
    # prepare 19 columns
    new_row = [""] * 19
    new_row[0] = str(user_id)  # A
    new_row[1] = username      # B
    new_row[2] = date_str      # C
    new_row[3] = time_str      # D
    new_row[4] = result        # E: 直近結果
    new_row[5] = str(streak)   # F
    new_row[6] = str(total)    # G
    new_row[7] = str(best)     # H

    # result counts I..S
    for i in range(11):
        new_row[8 + i] = "0"
    # increment the appropriate result column
    result_col = RESULT_COL_MAP.get(result)
    if result_col:
        idx = result_col - 9
        new_row[8 + idx] = "1"

    sheet.append_row(new_row)

# --- スラッシュコマンド ---
@bot.tree.command(name="ひまみくじ", description="1日1回 ひまみくじを引けます！")
async def himamikuji(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    username = interaction.user.display_name
    today = datetime.now(JST).date()
    today_str = today.strftime("%Y-%m-%d")
    time_str = datetime.now(JST).strftime("%H:%M")

    # キャッシュ初期化
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
    streak_cache = user["streak"]

    # 同日重複チェック（キャッシュベース）
    if last_date == str(today):
        emoji_streak = number_to_emoji(streak_cache)
        await interaction.response.send_message(
            f"## {username}は今日はもうひまみくじを引きました！\n"
            f"## 結果：［ひまみくじ継続中！！！ {emoji_streak}日目！！！］（{last_time} に引きました）"
        )
        return

    # 抽選
    results = [r[0] for r in omikuji_results]
    weights = [r[1] for r in omikuji_results]
    result = random.choices(results, weights)[0]

    # シート更新（行検索して更新 or 新規作成）
    try:
        row = find_user_row(user_id)
        if row:
            update_existing_row(row, user_id, username, today_str, time_str, result)
        else:
            create_new_row(user_id, username, today_str, time_str, result)
    except Exception as e:
        print("Google Sheets 書き込み失敗:", e)

    # キャッシュ更新
    # 継続判定（キャッシュベースで保存）
    if last_date == str(today - timedelta(days=1)):
        streak_cache += 1
    else:
        streak_cache = 1

    time_str_short = datetime.now(JST).strftime("%H:%M")
    data_cache[user_id] = {
        "last_date": str(today),
        "result": result,
        "streak": streak_cache,
        "time": time_str_short
    }
    save_data_file(data_cache)

    emoji_streak = number_to_emoji(streak_cache)
    await interaction.response.send_message(
        f"## {username} の今日の運勢はです！\n"
        f"## ［ひまみくじ継続中！！！ {emoji_streak}日目！！！］"
    )

# --- 実行 ---
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    raise Exception("DISCORD_TOKEN が設定されていません")

bot.run(TOKEN)

