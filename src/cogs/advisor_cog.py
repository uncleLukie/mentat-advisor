# ──────────────── src/cogs/advisor_cog.py ────────────────
import random, textwrap, discord
from discord.ext import commands, tasks
from discord.commands import SlashCommandGroup

# ────────────────────── Mentat quips ──────────────────────
def _quip() -> str:
    lines = [
        "“Plans within plans, Baron.”",
        "“The spice must flow — and so must the supplies.”",
        "“Echoes of the Dune hears the whispers of Arrakis.”",
        "“Efficiency is the best form of terror.”",
        "“Harkonnen profits favour the prepared.”",
        "“Statistics predict victory when stockpiles endure.”",
        "“Calculations confirm: fear sharpens loyalty.”",
        "“Fear delivers results the ledger can respect.”",
        "“A single mis-count is a silent betrayal.”",
        "“Logistics is the whip; demand is the scream.”",
        "“Deserts keep no secrets from a patient mind.”",
        "“Our figures walk ahead of us, scouting profit.”",
        "“Echo patterns confirm: rivals drown in their own audits.”",
        "“Precision today prevents bloodshed tomorrow… theirs, preferably.”",
        "“Spice intoxicates; mathematics sobers. Combine both.”",
        "“Where hope falters, quotas prevail.”",
        "“Mentat prognosis: opportunists perish, strategists inherit.”",
        "“An empty silo is an invitation to rebellion.”",
        "“Baron, the court obeys whomever commands the caravans.”",
        "“Data without brutality is merely trivia.”",
        "“Sand and numbers shift, but we steer both.”",
        "“Excess melange is inelegant—sell it, weaponise scarcity.”",
        "“My calculations thirst for their desperation.”",
        "“Echoes whisper the market’s fear; we shout its price.”",
        "“We tally corpses as readily as credits.”",
        "“Probability kneels before meticulous cruelty.”",
        "“A mentat remembers: profit is the Baron’s mercy.”",
        "“Opponents misplace crates; we misplace opponents.”",
        "“Scarcity is the slowest yet surest assassin.”",
        "“Strength lies in stockpiles, not slogans.”",
        "“An audit can slice deeper than a crysknife.”",
        "“Spreadsheets reveal what spies conceal.”",
        "“Our silence is worth more than their screams.”",
        "“House Harkonnen: where data is sharpened into dread.”",
        "“The desert punishes the sloppy; we merely expedite.”",
        "“Balance sheets foretell sieges better than oracles.”",
        "“In chaos we calculate; in order we collect.”",
        "“Waste is treason against the Baron’s coffers.”",
        "“Fortunes are fermented in well-guarded warehouses.”",
        "“Failures are just numbers waiting to be rounded down.”",
        "“Echoes report: hope depreciates faster than spice.”",
        "“A full depot sings louder than any bard.”",
        "“Mercy was omitted from the quarterly forecast.”",
        "“Audit complete: fear index within profitable range.”",
        "“Every ration withheld is leverage gained.”",
        "“Consensus is inefficient; precision is absolute.”",
        "“Mentats calculate — sandworms corroborate.”",
        "“House Atreides counts dreams; we count dividends.”",
        "“A shortage for them is an advantage for us.”",
        "“Baron, excess pity devalues the share price.”",
        "“The dune is indifferent; we are not.”",
        "“Extrapolation confirms: victory by attrition and arithmetic.”",
        "“Spice, statistics, supremacy — the triple sibilant of success.”",
        "“Disloyalty is a rounding error we refuse to carry.”",
    ]
    return random.choice(lines)

# ────────────────────── View & Select ──────────────────────
class DemandView(discord.ui.View):
    def __init__(self, item: dict, db):
        super().__init__(timeout=None)
        self.add_item(DemandSelect(item, db))

class DemandSelect(discord.ui.Select):
    def __init__(self, item: dict, db):
        self.item, self.db = item, db
        options = [
            discord.SelectOption(label="🔥 High",   value="high"),
            discord.SelectOption(label="🟠 Medium", value="medium"),
            discord.SelectOption(label="🟢 Low",    value="low"),
        ]
        super().__init__(
            placeholder=f"{item['name']} (T{item['tier']}) • {item['demand'].capitalize()}",
            options=options,
            custom_id=f"demand_{item['id']}"
        )

    async def callback(self, inter: discord.Interaction):
        lvl = self.values[0]
        self.db.set_demand(self.item["id"], lvl)
        await inter.response.send_message(
            f"**{self.item['name']}** demand set to **{lvl}**.",
            ephemeral=True,
        )
        cog = inter.client.get_cog("AdvisorCog")
        if cog:
            await cog._post_single(inter.channel, self.item["id"])

# ──────────────────────────── COG ────────────────────────────
class AdvisorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot, self.db = bot, bot.db_handler

    # slash-command groups
    report = SlashCommandGroup("report", "Demand-report commands")
    demand = SlashCommandGroup("demand", "Manual demand override")

    # ─── scheduler ────────────────────────────────────────────
    @tasks.loop(minutes=30)
    async def report_loop(self):
        cid = self.db.get_setting("report_channel_id")
        chan = self.bot.get_channel(cid) if cid else None
        if isinstance(chan, discord.TextChannel):
            await self.post_demand_report(chan)

    # ─── rebuild all high/medium posts ───────────────────────
    async def post_demand_report(self, channel: discord.TextChannel):
        items = self.db.get_all_by_demand(["high", "medium"])
        if not items:
            # purge any orphan messages
            for s in list(self.db.settings_table):
                if s["key"].startswith("msg_"):
                    try:
                        m = await channel.fetch_message(int(s["value"]))
                        await m.delete()
                    except Exception:
                        pass
                    self.db.settings_table.remove(self.db.Setting.key == s["key"])
            return
        for it in items:
            await self._post_single(channel, it["id"])

    # ─── one embed per resource ───────────────────────────────
    async def _post_single(self, channel, item_id: str):
        item = self.db.get_resource(item_id)
        key = f"msg_{item_id}"

        if not item or item["demand"] == "low":
            # delete & forget
            mid = self.db.get_setting(key)
            if mid:
                try:
                    m = await channel.fetch_message(int(mid)); await m.delete()
                except Exception:
                    pass
                self.db.settings_table.remove(self.db.Setting.key == key)
            return

        # build embed
        detail = item.get("details", "").strip()
        detail = textwrap.shorten(detail, width=350, placeholder=" …") if detail else "—"
        body = (f"**Demand:** {item['demand'].capitalize()}\n"
                f"*{item['type']} • Tier {item['tier']}*\n\n"
                f"{detail}")

        colour = discord.Color.dark_orange() if item["demand"] == "high" else discord.Color.orange()
        embed = discord.Embed(title=item["name"], url=item["dgt_slug"],
                              description=body, colour=colour)
        if item.get("image_url"): embed.set_thumbnail(url=item["image_url"])
        embed.set_footer(text=_quip())

        view = DemandView(item, self.db)

        mid = self.db.get_setting(key)
        if mid:
            try:
                msg = await channel.fetch_message(int(mid))
                await msg.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.Forbidden):
                pass
        msg = await channel.send(embed=embed, view=view)
        self.db.set_setting(key, msg.id)

    # ─── /report commands ────────────────────────────────────
    @report.command(name="start")
    @discord.default_permissions(manage_guild=True)
    async def rep_start(self, ctx):
        self.db.set_setting("report_channel_id", ctx.channel.id)
        await ctx.respond("Channel registered for reports.", ephemeral=True)
        await self.post_demand_report(ctx.channel)

    @report.command(name="now")
    async def rep_now(self, ctx):
        await self.post_demand_report(ctx.channel)
        await ctx.respond("Reports refreshed.", ephemeral=True)

    # ─── /demand set ──────────────────────────────────────────
    async def _ac(self, ctx: discord.AutocompleteContext):
        q = ctx.value.lower()
        items = sorted(self.db.get_all_resources(), key=lambda x: x["name"])
        return [i["name"] for i in items if q in i["name"].lower()][:25]

    @demand.command(name="set")
    async def demand_set(self, ctx,
                         item: discord.Option(str, autocomplete=_ac),
                         level: discord.Option(str, choices=["high", "medium", "low"])):
        ent = self.db.resources_table.get(self.db.Resource.name == item)
        if not ent:
            return await ctx.respond("Item not found.", ephemeral=True)
        self.db.set_demand(ent["id"], level)
        await ctx.respond(f"**{item}** demand set to **{level}**.", ephemeral=True)
        await self._post_single(ctx.channel, ent["id"])

# required for extension loader
def setup(bot): bot.add_cog(AdvisorCog(bot))
