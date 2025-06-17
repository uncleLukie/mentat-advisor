import discord
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup


# This is the main view for our demand report message
class DemandReportView(discord.ui.View):
    def __init__(self, db_handler):
        super().__init__(timeout=None)
        self.db = db_handler
        self.build_view()

    def build_view(self):
        items = self.db.get_all_by_demand(levels=["high", "medium"])
        items.sort(key=lambda x: x['name'])

        # Limit to 25 components, as that's the max on a message
        for item in items[:25]:
            self.add_item(DemandSelect(item, self.db))


# This is the dropdown menu component for each item in the report
class DemandSelect(discord.ui.Select):
    def __init__(self, item: dict, db_handler):
        self.item_data = item
        self.db = db_handler

        options = [
            discord.SelectOption(label="🔥 High", value="high", description=f"Set demand for {item['name']} to High."),
            discord.SelectOption(label="🟠 Medium", value="medium",
                                 description=f"Set demand for {item['name']} to Medium."),
            discord.SelectOption(label="🟢 Low", value="low", description=f"Set demand for {item['name']} to Low.")
        ]

        super().__init__(
            placeholder=f"Demand: {item['demand'].capitalize()} - {item['name']}",
            options=options,
            custom_id=f"demand_select_{item['id']}"
        )

    async def callback(self, interaction: discord.Interaction):
        new_demand = self.values[0]
        self.db.set_demand(self.item_data['id'], new_demand)

        await interaction.response.send_message(f"Demand for **{self.item_data['name']}** set to **{new_demand}**.",
                                                ephemeral=True)

        advisor_cog = interaction.client.get_cog('AdvisorCog')
        if advisor_cog and interaction.channel:
            await advisor_cog.post_demand_report(interaction.channel)


class AdvisorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_handler

    # Define command groups
    report = SlashCommandGroup("report", "Commands for managing the resource demand report.")
    demand = SlashCommandGroup("demand", "Commands for manually setting resource demand.")

    @tasks.loop(minutes=30)
    async def report_loop(self):
        channel_id = self.db.get_setting('report_channel_id')
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await self.post_demand_report(channel)

    async def post_demand_report(self, channel: discord.TextChannel):
        items = self.db.get_all_by_demand(levels=["high", "medium"])
        embed = discord.Embed(title="Arrakis Resource Demand",
                              description="Mentat analysis of current resource requirements. Set demand levels below.",
                              color=discord.Color.orange())

        if not items:
            embed.description = "All resource demands are currently low. No pressing needs."
            embed.color = discord.Color.green()
            view = discord.ui.View(timeout=None)
        else:
            high_demand_items = sorted([item for item in items if item['demand'] == 'high'], key=lambda x: x['name'])
            medium_demand_items = sorted([item for item in items if item['demand'] == 'medium'],
                                         key=lambda x: x['name'])

            if high_demand_items:
                value = "\n".join([f"[{item['name']}]({item['dgt_slug']})" for item in high_demand_items])
                embed.add_field(name="🔥 High Demand", value=value, inline=False)
            if medium_demand_items:
                value = "\n".join([f"[{item['name']}]({item['dgt_slug']})" for item in medium_demand_items])
                embed.add_field(name="🟠 Medium Demand", value=value, inline=False)

            embed.set_thumbnail(
                url=high_demand_items[0]['image_url'] if high_demand_items else medium_demand_items[0]['image_url'])
            embed.set_footer(text="The Spice must flow. This message will auto-update.")
            view = DemandReportView(self.db)

        await self.update_or_post_message(channel, embed, view)

    async def update_or_post_message(self, channel, embed, view):
        last_message_id = self.db.get_setting('last_report_message_id')
        if last_message_id:
            try:
                message = await channel.fetch_message(last_message_id)
                await message.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.Forbidden):
                pass

        new_message = await channel.send(embed=embed, view=view)
        self.db.set_setting('last_report_message_id', new_message.id)

    # --- BOT COMMANDS ---
    @report.command(name="start", description="Sets this channel for automatic demand reports.")
    @discord.default_permissions(manage_guild=True)
    async def start_reporting(self, ctx: discord.ApplicationContext):
        self.db.set_setting('report_channel_id', ctx.channel.id)
        await ctx.respond(f"Confirmed. I will now post demand reports in this channel.", ephemeral=True)
        await self.post_demand_report(ctx.channel)

    @report.command(name="interval", description="Changes the time between reports.")
    @discord.default_permissions(manage_guild=True)
    async def set_interval(self, ctx: discord.ApplicationContext,
                           minutes: discord.Option(int, "New interval in minutes", min_value=1)):
        self.db.set_setting('report_interval_minutes', minutes)
        self.report_loop.change_interval(minutes=minutes)
        await ctx.respond(f"Reporting interval changed to **{minutes} minutes**.", ephemeral=True)

    @report.command(name="now", description="Forces an immediate demand report in the configured channel.")
    async def report_now(self, ctx: discord.ApplicationContext):
        channel_id = self.db.get_setting('report_channel_id')
        if not channel_id:
            return await ctx.respond("The report channel has not been set. Use `/report start` first.", ephemeral=True)
        channel = self.bot.get_channel(channel_id)
        if channel:
            await ctx.respond("Generating a fresh report now...", ephemeral=True)
            await self.post_demand_report(channel)
        else:
            await ctx.respond(f"Error: I can't find the configured channel (ID: {channel_id}).", ephemeral=True)

    @report.command(name="sync", description="Forces a data sync from the Google Sheet database.")
    @discord.default_permissions(manage_guild=True)
    async def sync_db(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        self.db.sync_from_google_sheet()
        await ctx.followup.send("Database sync with Google Sheet complete.")

    # --- THIS IS THE FIXED AUTOCOMPLETE FUNCTION ---
    async def search_items(self, ctx: discord.AutocompleteContext):
        """Autocompletes item names, sorted alphabetically by name."""
        query = ctx.value.lower()
        all_items = self.db.get_all_resources()

        # Re-sort the entire list by name for better discoverability.
        all_items.sort(key=lambda x: x['name'])

        # Filter the newly sorted list based on the user's input.
        filtered_items = [
            item['name'] for item in all_items
            if query in item['name'].lower()
        ]

        return filtered_items[:25]  # Return the first 25 matches

    @demand.command(name="set", description="Manually set the demand for a specific resource.")
    async def set_demand_cmd(self, ctx: discord.ApplicationContext,
                             item: discord.Option(str, "The name of the item to set.", autocomplete=search_items),
                             level: discord.Option(str, "The demand level.", choices=["high", "medium", "low"])
                             ):
        selected_item = self.db.resources_table.get(self.db.Resource.name == item)
        if not selected_item:
            return await ctx.respond("Error: Could not find that item.", ephemeral=True)

        self.db.set_demand(selected_item['id'], level)
        await ctx.respond(f"Manual demand for **{selected_item['name']}** set to **{level}**.", ephemeral=True)


def setup(bot):
    bot.add_cog(AdvisorCog(bot))