import os
import discord
from dotenv import load_dotenv
from src.core.database import MentatDB

# --- Bot Startup ---
print("Mentat Advisor is starting up...")

# Load environment variables from .env file
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# --- Database Initialization and Sync ---
# This is the new block. It runs before the bot even logs in.
db_handler = MentatDB()
db_handler.sync_from_google_sheet()
# --- End of New Block ---


# Define bot with necessary intents
intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print("LogisticsMentat calculations are now online.")

# Load all cogs from the cogs directory
# This assumes your cogs are correctly set up to use the MentatDB class
# (e.g., by passing the db_handler instance to them or having them create their own)
for filename in os.listdir('./src/cogs'):
    if filename.endswith('.py') and not filename.startswith('__'):
        bot.load_extension(f'src.cogs.{filename[:-3]}')
        print(f"Loaded cog: {filename}")

# Run the bot
print("Connecting to Discord...")
bot.run(TOKEN)