# ──────────────── src/cogs/user_cog.py ────────────────
import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
import pytz

class UserCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db_handler

    user = SlashCommandGroup("user", "User settings")

    @user.command(name="set_timezone")
    async def set_timezone(self, ctx: discord.ApplicationContext, timezone: str):
        try:
            pytz.timezone(timezone)
            self.db.set_user_timezone(ctx.author.id, timezone)
            await ctx.respond(f"Your timezone has been set to {timezone}.", ephemeral=True)
        except pytz.UnknownTimeZoneError:
            await ctx.respond("Invalid timezone. Please use a valid timezone from the IANA Time Zone Database (e.g., `UTC`, `America/New_York`).", ephemeral=True)

def setup(bot):
    bot.add_cog(UserCog(bot))
