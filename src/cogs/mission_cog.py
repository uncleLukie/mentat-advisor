# ──────────────── src/cogs/mission_cog.py ────────────────
import discord
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup
from discord.ui import Modal, InputText
import datetime
import pytz
import random

# ────────────────────── Mentat quips ──────────────────────
def _quip() -> str:
    lines = [
        """The slow blade penetrates the shield.""",
        """He who controls the spice controls the universe.""",
        """The sleeper must awaken.""",
        """Fear is the mind-killer.""",
        """A plan is only as good as its execution.""",
        """The spice must flow."""
    ]
    return random.choice(lines)

# ─────────────────── Autocomplete Functions ───────────────────
async def timezone_autocomplete(ctx: discord.AutocompleteContext):
    """Returns a list of matching timezones."""
    return [tz for tz in pytz.all_timezones if ctx.value.lower() in tz.lower()][:25]

# ────────────────────── Mission Modal ──────────────────────
class MissionModal(Modal):
    def __init__(self, db, timezone):
        super().__init__(title="Create a new mission")
        self.db = db
        self.timezone = timezone

        now = datetime.datetime.now(pytz.timezone(timezone))

        self.add_item(InputText(label="Mission Details", style=discord.InputTextStyle.long))
        self.add_item(InputText(label="Date (YYYY-MM-DD)", value=now.strftime("%Y-%m-%d")))
        self.add_item(InputText(label="Time (24-hour format)", value=now.strftime("%H:%M")))

    async def callback(self, interaction: discord.Interaction):
        details = self.children[0].value
        date_str = self.children[1].value
        time_str = self.children[2].value

        try:
            mission_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            tz = pytz.timezone(self.timezone)
            mission_time = tz.localize(mission_time)
        except (ValueError, pytz.UnknownTimeZoneError):
            await interaction.response.send_message("Invalid date or time format. Please use YYYY-MM-DD and HH:MM.", ephemeral=True)
            return

        embed = discord.Embed(
            title="💀 Harkonnen Directive 💀",
            description=f"""By order of the Baron, the following operation is decreed:\n
_{details}_""",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="\u200b", value="\u200b", inline=False) # Spacer
        ts = int(mission_time.timestamp())
        embed.add_field(name="🕰️ Commencement", value=f"<t:{ts}:F> (<t:{ts}:R>)", inline=False)
        embed.add_field(name=" operatives", value=f"<@{interaction.user.id}>", inline=False)
        embed.set_footer(text=_quip())

        view = ConfirmView(self.db, embed, mission_time)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ────────────────────── Confirm View ──────────────────────
class ConfirmView(discord.ui.View):
    def __init__(self, db, embed, mission_time):
        super().__init__(timeout=None)
        self.db = db
        self.embed = embed
        self.mission_time = mission_time

    @discord.ui.button(label="Confirm & Post", style=discord.ButtonStyle.success)
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        message = await interaction.channel.send(embed=self.embed)
        self.db.create_mission(message.id, message.id, interaction.channel.id, interaction.user.id, self.embed.description, self.mission_time.isoformat())
        
        view = MissionView(message.id, self.db)
        await message.edit(view=view)
        await interaction.response.edit_message(content="Mission posted.", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Mission creation cancelled.", view=None)

# ────────────────────── Mission View ──────────────────────
class MissionView(discord.ui.View):
    def __init__(self, mission_id: int, db):
        super().__init__(timeout=None)
        self.mission_id = mission_id
        self.db = db

    async def update_embed(self, interaction: discord.Interaction):
        mission = self.db.get_mission(self.mission_id)
        embed = interaction.message.embeds[0]
        participant_list = "\n".join([f"<@{p}>" for p in mission['participants']]) or "_No one yet_"
        embed.set_field_at(2, name=" operatives", value=participant_list, inline=False)
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Join", style=discord.ButtonStyle.success)
    async def join_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        mission = self.db.get_mission(self.mission_id)
        if not mission:
            return await interaction.response.send_message("This mission no longer exists.", ephemeral=True)

        if interaction.user.id in mission['participants']:
            return await interaction.response.send_message("You have already joined this mission.", ephemeral=True)

        mission['participants'].append(interaction.user.id)
        self.db.update_mission_participants(self.mission_id, mission['participants'])
        await self.update_embed(interaction)
        await interaction.response.send_message("You have joined the mission.", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary)
    async def leave_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        mission = self.db.get_mission(self.mission_id)
        if not mission:
            return await interaction.response.send_message("This mission no longer exists.", ephemeral=True)

        if interaction.user.id not in mission['participants']:
            return await interaction.response.send_message("You are not part of this mission.", ephemeral=True)

        mission['participants'].remove(interaction.user.id)
        self.db.update_mission_participants(self.mission_id, mission['participants'])
        await self.update_embed(interaction)
        await interaction.response.send_message("You have left the mission.", ephemeral=True)

    @discord.ui.button(label="Cancel Mission", style=discord.ButtonStyle.danger)
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        mission = self.db.get_mission(self.mission_id)
        if not mission:
            return await interaction.response.send_message("This mission no longer exists.", ephemeral=True)

        if interaction.user.id != mission['creator_id']:
            return await interaction.response.send_message("You are not the creator of this mission.", ephemeral=True)

        await interaction.message.delete()
        self.db.delete_mission(self.mission_id)
        await interaction.response.send_message("Mission cancelled.", ephemeral=True)

# ──────────────────────────── COG ────────────────────────────
class MissionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db_handler
        self.cleanup_loop.start()

    mission = SlashCommandGroup("mission", "Mission commands")
    user = SlashCommandGroup("user", "User settings")

    @mission.command(name="create")
    async def create_mission(self, ctx: discord.ApplicationContext):
        timezone = self.db.get_user_timezone(ctx.author.id)
        if not timezone:
            await ctx.respond("To create a mission, you must first set your timezone. Use the `/user set_timezone` command. This is a one-time setup.", ephemeral=True)
            return

        modal = MissionModal(self.db, timezone)
        await ctx.send_modal(modal)

    @user.command(name="set_timezone")
    async def set_timezone(self, ctx: discord.ApplicationContext, timezone: discord.Option(str, autocomplete=timezone_autocomplete)):
        try:
            pytz.timezone(timezone)
            self.db.set_user_timezone(ctx.author.id, timezone)
            await ctx.respond(f"Your timezone has been set to {timezone}. You can now use `/mission create`.", ephemeral=True)
        except pytz.UnknownTimeZoneError:
            await ctx.respond("Invalid timezone. Please select a valid timezone from the list.", ephemeral=True)

    @tasks.loop(hours=1)
    async def cleanup_loop(self):
        for mission in self.db.get_all_missions():
            mission_time = datetime.datetime.fromisoformat(mission['time'])
            if datetime.datetime.now(pytz.utc) > mission_time + datetime.timedelta(hours=4):
                try:
                    channel = await self.bot.fetch_channel(mission['channel_id'])
                    message = await channel.fetch_message(mission['message_id'])
                    await message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
                self.db.delete_mission(mission['message_id'])

def setup(bot):
    bot.add_cog(MissionCog(bot))
