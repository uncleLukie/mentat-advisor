import os
import discord
from dotenv import load_dotenv
from src.core.database import MentatDB
from src.cogs.advisor_cog import DemandReportView  # Import the view class

# --- Bot Startup ---
print("Mentat Advisor is starting up...")
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# --- Database Initialization ---
db_handler = MentatDB()
db_handler.sync_from_google_sheet()

# --- Bot Definition ---
intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

# Attach the database handler to the bot instance
bot.db_handler = db_handler
bot.persistent_views_added = False


@bot.event
async def on_ready():
    # Add the persistent view once the bot is connected.
    if not bot.persistent_views_added:
        bot.add_view(DemandReportView(bot.db_handler))
        bot.persistent_views_added = True
        print("Persistent view registered.")

    # Configure and start the report loop correctly.
    advisor_cog = bot.get_cog('AdvisorCog')
    if advisor_cog and not advisor_cog.report_loop.is_running():
        interval = bot.db_handler.get_setting('report_interval_minutes') or 30
        advisor_cog.report_loop.change_interval(minutes=interval)
        advisor_cog.report_loop.start()
        print(f"Report loop started with an interval of {interval} minutes.")

    print(f"Logged in as {bot.user} ({bot.user.id})")
    print("LogisticsMentat calculations are now online.")


# Load cogs from the cogs directory
COGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cogs')
for filename in os.listdir(COGS_PATH):
    if filename.endswith('.py') and not filename.startswith('__'):
        extension_path = f'src.cogs.{filename[:-3]}'
        bot.load_extension(extension_path)
        print(f"Loaded cog: {filename}")

# Run the bot
print("Connecting to Discord...")

bot.run(TOKEN)