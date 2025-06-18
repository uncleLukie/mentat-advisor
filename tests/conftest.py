# SPDX-Identifier: MIT
"""
Global test fixtures + compatibility shims.
Executed **before** test collection.
"""
import inspect, types, asyncio, discord                         # ➊

# ------------------------------------------------------------------
# ➋  compatibility:  Py-Cord ≥ 2.6 no longer exposes Interaction.respond
# ------------------------------------------------------------------
if not hasattr(discord.Interaction, "respond"):
    async def _respond(self, *args, **kwargs):
        """Back-port shim – simply proxy to Interaction.response."""
        return await self.response.send_message(*args, **kwargs)

    # expose as *method* so copy_doc() sees it
    discord.Interaction.respond = types.MethodType(_respond,
                                                   discord.Interaction)

# ------------------------------------------------------------------
# ➌  event-loop fixture for dpytest / pytest-asyncio
# ------------------------------------------------------------------
import pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped loop so dpytest & pytest-asyncio share it."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
