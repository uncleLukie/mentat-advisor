# ─────────────────────── src/main.py ───────────────────────
import os, discord
from dotenv import load_dotenv
from src.core.database import MentatDB

print("Mentat Advisor is starting up…")
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# initialise DB
db_handler = MentatDB()
db_handler.sync_from_google_sheet()

# bot
intents = discord.Intents.default()
bot = discord.Bot(intents=intents)
bot.db_handler = db_handler

@bot.event
async def on_ready():
    # start the scheduled loop in AdvisorCog
    advisor = bot.get_cog("AdvisorCog")
    if advisor and not advisor.report_loop.is_running():
        interval = bot.db_handler.get_setting("report_interval_minutes") or 30
        advisor.report_loop.change_interval(minutes=interval)
        advisor.report_loop.start()
        print(f"Report loop running every {interval} min.")
    print(f"Logged in as {bot.user} ({bot.user.id}) — Mentat online.")

# load cogs
COGS_DIR = os.path.join(os.path.dirname(__file__), "cogs")
for fn in os.listdir(COGS_DIR):
    if fn.endswith(".py") and not fn.startswith("__"):
        bot.load_extension(f"src.cogs.{fn[:-3]}")
        print(f"Loaded cog: {fn}")

print("Connecting to Discord…")
bot.run(TOKEN)