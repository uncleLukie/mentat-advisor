# ──────────────── tests/test_mission_cog.py ────────────────
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import datetime
import pytz
from src.cogs.mission_cog import MissionCog, MissionModal, ConfirmView, MissionView

class TestMissionCog(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.bot = AsyncMock()
        self.bot.db_handler = MagicMock()
        self.cog = MissionCog(self.bot)

    async def test_create_mission_no_timezone(self):
        """Test that mission creation fails if the user has not set a timezone."""
        self.bot.db_handler.get_user_timezone.return_value = None
        ctx = AsyncMock()
        await self.cog.create_mission.callback(self.cog, ctx)
        ctx.respond.assert_called_once_with(
            "To create a mission, you must first set your timezone. Use the `/user set_timezone` command. This is a one-time setup.",
            ephemeral=True
        )

    async def test_create_mission_with_timezone(self):
        """Test that the mission creation modal is sent when the user has a timezone."""
        self.bot.db_handler.get_user_timezone.return_value = "UTC"
        ctx = AsyncMock()
        await self.cog.create_mission.callback(self.cog, ctx)
        ctx.send_modal.assert_called_once()

    async def test_set_timezone(self):
        """Test that a user's timezone can be set successfully."""
        ctx = AsyncMock()
        await self.cog.set_timezone.callback(self.cog, ctx, "UTC")
        self.bot.db_handler.set_user_timezone.assert_called_once_with(ctx.author.id, "UTC")
        ctx.respond.assert_called_once_with("Your timezone has been set to UTC. You can now use `/mission create`.", ephemeral=True)

    async def test_set_invalid_timezone(self):
        """Test that setting an invalid timezone returns an error message."""
        ctx = AsyncMock()
        await self.cog.set_timezone.callback(self.cog, ctx, "Invalid/Timezone")
        self.bot.db_handler.set_user_timezone.assert_not_called()
        ctx.respond.assert_called_once_with("Invalid timezone. Please select a valid timezone from the list.", ephemeral=True)

class TestMissionUI(unittest.IsolatedAsyncioTestCase):

    async def test_modal_callback(self):
        """Test that the mission modal callback sends a confirmation view."""
        db = MagicMock()
        modal = MissionModal(db, "UTC")
        interaction = AsyncMock()
        modal.children[0].value = "Test Mission"
        modal.children[1].value = "2025-01-01"
        modal.children[2].value = "12:00"

        with patch('src.cogs.mission_cog.ConfirmView') as MockConfirmView:
            MockConfirmView.return_value = ConfirmView(db, MagicMock(), datetime.datetime.now(pytz.utc)) # Return an actual instance
            await modal.callback(interaction)
            interaction.response.send_message.assert_called_once()
            self.assertTrue(interaction.response.send_message.call_args.kwargs['ephemeral'])
            self.assertIsInstance(interaction.response.send_message.call_args.kwargs['view'], ConfirmView)

    async def test_confirm_view_confirm_button(self):
        """Test that the confirm button posts the mission."""
        db = MagicMock()
        embed = MagicMock()
        mission_time = datetime.datetime.now(pytz.utc)
        view = ConfirmView(db, embed, mission_time)
        interaction = AsyncMock()

        await view.confirm_button.callback(interaction)

        interaction.channel.send.assert_called_once_with(embed=embed)
        db.create_mission.assert_called_once()
        interaction.response.edit_message.assert_called_once_with(content="Mission posted.", view=None)

    async def test_confirm_view_cancel_button(self):
        """Test that the cancel button cancels mission creation."""
        db = MagicMock()
        embed = MagicMock()
        mission_time = datetime.datetime.now(pytz.utc)
        view = ConfirmView(db, embed, mission_time)
        interaction = AsyncMock()

        await view.cancel_button.callback(interaction)

        interaction.response.edit_message.assert_called_once_with(content="Mission creation cancelled.", view=None)

    async def test_mission_view_join_button(self):
        """Test that a user can join a mission."""
        db = MagicMock()
        view = MissionView(123, db)
        interaction = AsyncMock()
        interaction.user.id = 1
        db.get_mission.return_value = {'participants': [2], 'creator_id': 2}

        with patch.object(view, 'update_embed', new=AsyncMock()) as mock_update_embed:
            await view.join_button.callback(interaction)
            db.update_mission_participants.assert_called_once_with(123, [2, 1])
            mock_update_embed.assert_called_once_with(interaction)
            interaction.response.send_message.assert_called_once_with("You have joined the mission.", ephemeral=True)

    async def test_mission_view_leave_button(self):
        """Test that a user can leave a mission."""
        db = MagicMock()
        view = MissionView(123, db)
        interaction = AsyncMock()
        interaction.user.id = 1
        db.get_mission.return_value = {'participants': [1, 2], 'creator_id': 2}

        with patch.object(view, 'update_embed', new=AsyncMock()) as mock_update_embed:
            await view.leave_button.callback(interaction)
            db.update_mission_participants.assert_called_once_with(123, [2])
            mock_update_embed.assert_called_once_with(interaction)
            interaction.response.send_message.assert_called_once_with("You have left the mission.", ephemeral=True)

    async def test_mission_view_cancel_mission_button(self):
        """Test that the mission creator can cancel the mission.""" 
        db = MagicMock()
        view = MissionView(123, db)
        interaction = AsyncMock()
        interaction.user.id = 1
        db.get_mission.return_value = {'creator_id': 1}

        await view.cancel_button.callback(interaction)

        interaction.message.delete.assert_called_once()
        db.delete_mission.assert_called_once_with(123)
        interaction.response.send_message.assert_called_once_with("Mission cancelled.", ephemeral=True)
