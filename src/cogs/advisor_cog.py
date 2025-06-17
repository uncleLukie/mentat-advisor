import discord
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup

# ───────────────────────────── VIEW & COMPONENTS ────────────────────────────
class DemandReportView(discord.ui.View):
    def __init__(self, db_handler):
        super().__init__(timeout=None)
        self.db = db_handler
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        items = self.db.get_all_by_demand(levels=["high", "medium"])
        items.sort(key=lambda x: x["name"])
        for item in items[:25]:            # Discord hard-limit = 25
            self.add_item(DemandSelect(item, self.db))


class DemandSelect(discord.ui.Select):
    def __init__(self, item: dict, db_handler):
        self.item_data = item
        self.db = db_handler

        options = [
            discord.SelectOption(
                label="🔥 High",
                value="high",
                description=f"Set demand for {item['name']} to High."
            ),
            discord.SelectOption(
                label="🟠 Medium",
                value="medium",
                description=f"Set demand for {item['name']} to Medium."
            ),
            discord.SelectOption(
                label="🟢 Low",
                value="low",
                description=f"Set demand for {item['name']} to Low."
            ),
        ]

        super().__init__(
            placeholder=f"Demand: {item['demand'].capitalize()} – {item['name']}",
            options=options,
            custom_id=f"demand_select_{item['id']}",
        )

    async def callback(self, interaction: discord.Interaction):
        new_level = self.values[0]
        self.db.set_demand(self.item_data["id"], new_level)
        await interaction.response.send_message(
            f"Demand for **{self.item_data['name']}** set to **{new_level}**.",
            ephemeral=True,
        )

        # auto-refresh the live embed
        advisor = interaction.client.get_cog("AdvisorCog")
        if advisor and interaction.channel:
            await advisor.post_demand_report(interaction.channel)

# ────────────────────────────────── COG ─────────────────────────────────────
class AdvisorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db_handler

    report = SlashCommandGroup("report", "Resource-report commands")
    demand = SlashCommandGroup("demand", "Set resource demand manually")

    # scheduler --------------------------------------------------------------
    @tasks.loop(minutes=30)
    async def report_loop(self):
        chan_id = self.db.get_setting("report_channel_id")
        channel = self.bot.get_channel(chan_id) if chan_id else None
        if isinstance(channel, discord.TextChannel):
            await self.post_demand_report(channel)

    # embed/post logic -------------------------------------------------------
    async def post_demand_report(self, channel: discord.TextChannel):
        items = self.db.get_all_by_demand(levels=["high", "medium"])
        embed = discord.Embed(
            title="Arrakis Resource Demand",
            description="Mentat analysis of current needs.",
            color=discord.Color.orange()
        )

        view: discord.ui.View | None = None
        if items:
            high = sorted([i for i in items if i["demand"] == "high"], key=lambda x: x["name"])
            med  = sorted([i for i in items if i["demand"] == "medium"], key=lambda x: x["name"])

            if high:
                embed.add_field(
                    name="🔥 High Demand",
                    value="\n".join(f"[{i['name']}]({i['dgt_slug']})" for i in high),
                    inline=False,
                )
            if med:
                embed.add_field(
                    name="🟠 Medium Demand",
                    value="\n".join(f"[{i['name']}]({i['dgt_slug']})" for i in med),
                    inline=False,
                )

            thumb_src = (high or med)[0]["image_url"]
            embed.set_thumbnail(url=thumb_src)
            embed.set_footer(text="The Spice must flow. This message auto-updates.")
            view = DemandReportView(self.db)
        else:
            embed.description = "All demands are low – no pressing needs."
            embed.color = discord.Color.green()

        await self._upsert_message(channel, embed, view)

    async def _upsert_message(self, channel, embed, view):
        msg_id = self.db.get_setting("last_report_message_id")
        if msg_id:
            try:
                msg = await channel.fetch_message(int(msg_id))
                await msg.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.Forbidden):
                pass
        sent = await channel.send(embed=embed, view=view)
        self.db.set_setting("last_report_message_id", sent.id)

    # ──────────────── /report commands ─────────────────────────────────────
    @report.command(name="start", description="Use this channel for auto-reports")
    @discord.default_permissions(manage_guild=True)
    async def report_start(self, ctx: discord.ApplicationContext):
        self.db.set_setting("report_channel_id", ctx.channel.id)
        await ctx.respond("Channel registered for reports.", ephemeral=True)
        await self.post_demand_report(ctx.channel)

    @report.command(name="interval", description="Change report frequency")
    @discord.default_permissions(manage_guild=True)
    async def report_interval(
        self, ctx: discord.ApplicationContext,
        minutes: discord.Option(int, "Interval in minutes", min_value=1)
    ):
        self.db.set_setting("report_interval_minutes", minutes)
        self.report_loop.change_interval(minutes=minutes)
        await ctx.respond(f"Interval set to **{minutes} min**.", ephemeral=True)

    @report.command(name="now", description="Generate a report immediately")
    async def report_now(self, ctx: discord.ApplicationContext):
        chan_id = self.db.get_setting("report_channel_id")
        channel = self.bot.get_channel(chan_id) if chan_id else None
        if not channel:
            return await ctx.respond("Report channel not configured.", ephemeral=True)
        await ctx.respond("Generating report…", ephemeral=True)
        await self.post_demand_report(channel)

    @report.command(name="sync", description="Force Google-Sheet DB sync")
    @discord.default_permissions(manage_guild=True)
    async def report_sync(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        self.db.sync_from_google_sheet()
        await ctx.followup.send("Database sync complete.", ephemeral=True)

    # ──────────────── /demand set ───────────────────────────────────────────
    async def _ac_items(self, ctx: discord.AutocompleteContext):
        q = ctx.value.lower()
        items = sorted(self.db.get_all_resources(), key=lambda x: x["name"])
        return [i["name"] for i in items if q in i["name"].lower()][:25]

    @demand.command(name="set", description="Override an item’s demand")
    async def demand_set(
        self, ctx: discord.ApplicationContext,
        item: discord.Option(str, autocomplete=_ac_items),
        level: discord.Option(str, choices=["high", "medium", "low"])
    ):
        entry = self.db.resources_table.get(self.db.Resource.name == item)
        if not entry:
            return await ctx.respond("Item not found.", ephemeral=True)
        self.db.set_demand(entry["id"], level)
        await ctx.respond(f"Demand for **{entry['name']}** set to **{level}**.", ephemeral=True)

        chan_id = self.db.get_setting("report_channel_id")
        channel = self.bot.get_channel(chan_id) if chan_id else None
        if isinstance(channel, discord.TextChannel):
            await self.post_demand_report(channel)

def setup(bot):
    bot.add_cog(AdvisorCog(bot))
