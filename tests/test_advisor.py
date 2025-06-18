# SPDX-Identifier: MIT
"""Integration-style tests for AdvisorCog using dpytest."""

import asyncio, pytest, discord
import discord.ext.test as dpytest          # provided by the 'dpytest' package

from src.cogs.advisor_cog import AdvisorCog
from src.core.database import MentatDB
from tinydb.storages import MemoryStorage


@pytest.fixture()
def bot(event_loop: asyncio.AbstractEventLoop):
    """Fresh bot + in-memory DB for every test."""
    intents = discord.Intents.none()
    test_bot = discord.Bot(intents=intents)

    # use an in-memory TinyDB to avoid filesystem writes
    mem_db = MentatDB()
    mem_db.db.storage = MemoryStorage()     # type: ignore
    test_bot.db_handler = mem_db

    # load the cog
    test_bot.add_cog(AdvisorCog(test_bot))

    # hand bot instance to dpytest
    dpytest.configure(test_bot, loop=event_loop)
    return test_bot


@pytest.mark.asyncio
async def test_demand_set_command(bot):
    # --- seed DB -----------------------------------------------------------
    bot.db_handler.resources_table.insert({
        "id": "jasmium_crystal",
        "name": "Jasmium Crystal",
        "type": "Resources",
        "tier": 5,
        "details": "Sparkling.",
        "demand": "low",
        "dgt_slug": "https://example.com",
        "image_url": ""
    })

    # --- invoke slash-command ---------------------------------------------
    await dpytest.slash().invoke("demand set",
                                 item="Jasmium Crystal",
                                 level="high")

    # --- assertion ---------------------------------------------------------
    res = bot.db_handler.get_resource("jasmium_crystal")
    assert res["demand"] == "high"


@pytest.mark.asyncio
async def test_single_embed_contents(bot):
    # --- seed DB with a high-demand resource -------------------------------
    bot.db_handler.resources_table.insert({
        "id": "spice",
        "name": "Spice",
        "type": "Commodity",
        "tier": 1,
        "details": "Melange! The most precious substance in the universe.",
        "demand": "high",
        "dgt_slug": "https://example.com",
        "image_url": ""
    })

    # --- call the private helper ------------------------------------------
    cog: AdvisorCog = bot.get_cog("AdvisorCog")
    channel = dpytest.get_config().guild.text_channels[0]
    await cog._post_single(channel, "spice")

    # --- inspect the message ----------------------------------------------
    sent = dpytest.get_message()
    embed: discord.Embed = sent.embeds[0]

    assert "**Demand:** High" in embed.description
    assert embed.color == discord.Color.dark_orange()
    assert "Tier 1" in embed.description
