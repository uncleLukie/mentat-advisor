import pytest
import discord
from discord.ext import commands
from unittest.mock import AsyncMock, MagicMock, patch
import pytest_asyncio
import pytest_asyncio
from src.cogs.advisor_cog import AdvisorCog, _quip, DemandView, DemandSelect

# Mock the MentatDB for testing purposes
@pytest.fixture
def mock_db():
    db = MagicMock()
    db.resources_table = MagicMock()
    db.settings_table = MagicMock()
    db.Resource = MagicMock()
    db.Setting = MagicMock()
    
    # Mock common DB methods
    db.get_resource.return_value = None
    db.set_demand.return_value = True
    db.get_setting.return_value = None
    db.set_setting.return_value = None
    db.get_all_by_demand.return_value = []
    db.get_all_resources.return_value = []
    return db

# Mock the bot instance
@pytest.fixture
def mock_bot(mock_db):
    bot = AsyncMock(spec=commands.Bot)
    bot.db_handler = mock_db
    bot.get_cog.return_value = None # Default for cog._post_single
    return bot

# Mock discord.Interaction
@pytest.fixture
def mock_interaction():
    inter = AsyncMock(spec=discord.Interaction)
    inter.response = AsyncMock()
    inter.client = MagicMock()
    return inter

# Mock discord.ApplicationContext (for slash commands)
@pytest.fixture
def mock_ctx():
    ctx = AsyncMock(spec=discord.ApplicationContext)
    ctx.channel = AsyncMock(spec=discord.TextChannel)
    ctx.respond = AsyncMock()
    return ctx

class TestAdvisorCog:
    @pytest.fixture(autouse=True)
    def setup(self, mock_bot, mock_db):
        self.bot = mock_bot
        self.db = mock_db
        self.cog = AdvisorCog(self.bot)

    def test_quip_returns_string(self):
        """Test that _quip returns a string."""
        assert isinstance(_quip(), str)
        assert len(_quip()) > 0

    @pytest.mark.asyncio
    async def test_demand_view_init(self):
        """Test DemandView initialization."""
        item = {'id': 'test', 'name': 'Test Item', 'tier': 1, 'demand': 'low'}
        view = DemandView(item, self.db)
        assert len(view.children) == 1
        assert isinstance(view.children[0], DemandSelect)

    @pytest.mark.asyncio
    async def test_demand_select_callback(self, mock_interaction):
        """Test DemandSelect callback method."""
        item = {'id': 'spice', 'name': 'Spice', 'tier': 1, 'demand': 'low'}
        select = DemandSelect(item, self.db)
        select.values = ['high']
        
        # Mock get_cog to return the current cog instance for _post_single call
        mock_interaction.client.get_cog.return_value = self.cog

        await select.callback(mock_interaction)

        self.db.set_demand.assert_called_once_with('spice', 'high')
        mock_interaction.response.send_message.assert_called_once_with(
            "**Spice** demand set to **high**.", ephemeral=True
        )
        # Verify _post_single was called. We can't directly assert on the private method
        # but we can check if the underlying db.get_resource was called by it.
        self.db.get_resource.assert_called_once_with('spice')

    def test_advisor_cog_init(self):
        """Test AdvisorCog initialization."""
        assert self.cog.bot == self.bot
        assert self.cog.db == self.db

    @pytest.mark.asyncio
    async def test_report_loop_no_channel(self):
        """Test report_loop when no report channel is set."""
        self.db.get_setting.return_value = None
        await self.cog.report_loop()
        self.db.get_setting.assert_called_once_with("report_channel_id")
        self.bot.get_channel.assert_not_called()
        # Ensure post_demand_report was not called
        self.db.get_all_by_demand.assert_not_called()

    @pytest.mark.asyncio
    async def test_report_loop_with_channel(self):
        """Test report_loop when a report channel is set."""
        mock_channel = AsyncMock(spec=discord.TextChannel)
        self.db.get_setting.return_value = 12345
        self.bot.get_channel.return_value = mock_channel
        self.db.get_all_by_demand.return_value = [{'id': 'spice', 'demand': 'high'}]
        self.db.get_resource.return_value = {'id': 'spice', 'name': 'Spice', 'type': 'Resource', 'tier': 1, 'demand': 'high'}

        await self.cog.report_loop()

        self.db.get_setting.assert_called_once_with("report_channel_id")
        self.bot.get_channel.assert_called_once_with(12345)
        self.db.get_all_by_demand.assert_called_once_with(["high", "medium"])
        # Verify _post_single was called (indirectly via db.get_resource)
        self.db.get_resource.assert_called_once_with('spice')

    @pytest.mark.asyncio
    async def test_post_demand_report_no_items_purges_orphans(self):
        """Test post_demand_report when no high/medium items, purges orphans."""
        self.db.get_all_by_demand.return_value = []
        self.db.settings_table.__iter__.return_value = [
            {'key': 'msg_spice', 'value': '12345'},
            {'key': 'msg_water', 'value': '67890'}
        ]
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message_spice = AsyncMock()
        mock_message_water = AsyncMock()
        mock_channel.fetch_message.side_effect = [mock_message_spice, mock_message_water]

        await self.cog.post_demand_report(mock_channel)

        self.db.get_all_by_demand.assert_called_once_with(["high", "medium"])
        mock_channel.fetch_message.assert_any_call(12345)
        mock_channel.fetch_message.assert_any_call(67890)
        mock_message_spice.delete.assert_called_once()
        mock_message_water.delete.assert_called_once()
        self.db.settings_table.remove.assert_any_call(self.db.Setting.key == 'msg_spice')
        self.db.settings_table.remove.assert_any_call(self.db.Setting.key == 'msg_water')

    @pytest.mark.asyncio
    async def test_post_demand_report_with_items(self):
        """Test post_demand_report with high/medium items."""
        self.db.get_all_by_demand.return_value = [
            {'id': 'spice', 'demand': 'high'},
            {'id': 'water', 'demand': 'medium'}
        ]
        # Mock _post_single to prevent actual message sending during this test
        with patch.object(self.cog, '_post_single', new=AsyncMock()) as mock_post_single:
            mock_channel = AsyncMock(spec=discord.TextChannel)
            await self.cog.post_demand_report(mock_channel)

            self.db.get_all_by_demand.assert_called_once_with(["high", "medium"])
            mock_post_single.assert_any_call(mock_channel, 'spice')
            mock_post_single.assert_any_call(mock_channel, 'water')
            assert mock_post_single.call_count == 2

    @pytest.mark.asyncio
    async def test_post_single_low_demand_or_not_found(self):
        """Test _post_single when item is low demand or not found (should delete message)."""
        self.db.get_resource.return_value = None # Item not found
        self.db.get_setting.return_value = '12345' # Existing message ID
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock()
        mock_channel.fetch_message.return_value = mock_message

        await self.cog._post_single(mock_channel, 'non_existent_item')

        self.db.get_resource.assert_called_once_with('non_existent_item')
        self.db.get_setting.assert_called_once_with('msg_non_existent_item')
        mock_channel.fetch_message.assert_called_once_with(12345)
        mock_message.delete.assert_called_once()
        self.db.settings_table.remove.assert_called_once_with(self.db.Setting.key == 'msg_non_existent_item')

    @pytest.mark.asyncio
    async def test_post_single_new_message(self):
        """Test _post_single sends a new message and saves its ID."""
        item = {
            'id': 'spice', 'name': 'Spice', 'type': 'Resource', 'tier': 1,
            'demand': 'high', 'details': 'Valuable resource', 'image_url': 'http://example.com/spice.png'
        }
        self.db.get_resource.return_value = item
        self.db.get_setting.return_value = None # No existing message
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock(id=98765)
        mock_channel.send.return_value = mock_message

        await self.cog._post_single(mock_channel, 'spice')

        self.db.get_resource.assert_called_once_with('spice')
        self.db.get_setting.assert_called_once_with('msg_spice')
        mock_channel.send.assert_called_once()
        self.db.set_setting.assert_called_once_with('msg_spice', 98765)

        # Verify embed content (basic checks)
        args, kwargs = mock_channel.send.call_args
        embed = kwargs['embed']
        assert embed.title == 'Spice'
        assert 'Demand: High' in embed.description
        assert embed.colour == discord.Color.dark_orange()
        assert embed.thumbnail.url == 'http://example.com/spice.png'

    @pytest.mark.asyncio
    async def test_post_single_update_existing_message(self):
        """Test _post_single updates an existing message."""
        item = {
            'id': 'spice', 'name': 'Spice', 'type': 'Resource', 'tier': 1,
            'demand': 'high', 'details': 'Valuable resource', 'image_url': 'http://example.com/spice.png'
        }
        self.db.get_resource.return_value = item
        self.db.get_setting.return_value = '12345' # Existing message ID
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_message = AsyncMock()
        mock_channel.fetch_message.return_value = mock_message

        await self.cog._post_single(mock_channel, 'spice')

        self.db.get_resource.assert_called_once_with('spice')
        self.db.get_setting.assert_called_once_with('msg_spice')
        mock_channel.fetch_message.assert_called_once_with(12345)
        mock_message.edit.assert_called_once()
        self.db.set_setting.assert_not_called() # Should not set again

    @pytest.mark.asyncio
    async def test_rep_start_command(self, mock_ctx):
        """Test /report start command."""
        mock_ctx.channel.id = 123
        with patch.object(self.cog, 'post_demand_report', new=AsyncMock()) as mock_post_demand_report:
            await self.cog.rep_start(mock_ctx)

            self.db.set_setting.assert_called_once_with("report_channel_id", 123)
            mock_ctx.respond.assert_called_once_with("Channel registered for reports.", ephemeral=True)
            mock_post_demand_report.assert_called_once_with(mock_ctx.channel)

    @pytest.mark.asyncio
    async def test_rep_now_command(self, mock_ctx):
        """Test /report now command."""
        with patch.object(self.cog, 'post_demand_report', new=AsyncMock()) as mock_post_demand_report:
            await self.cog.rep_now(mock_ctx)

            mock_post_demand_report.assert_called_once_with(mock_ctx.channel)
            mock_ctx.respond.assert_called_once_with("Reports refreshed.", ephemeral=True)

    @pytest.mark.asyncio
    async def test_ac_autocomplete(self):
        """Test _ac autocomplete method."""
        self.db.get_all_resources.return_value = [
            {'id': 'spice', 'name': 'Spice'},
            {'id': 'water', 'name': 'Water'},
            {'id': 'melange', 'name': 'Melange'},
            {'id': 'sand', 'name': 'Sand'},
        ]
        mock_ctx = MagicMock(spec=discord.AutocompleteContext)
        mock_ctx.value = 's'

        results = await self.cog._ac(mock_ctx)
        assert 'Sand' in results
        assert 'Spice' in results
        assert 'Water' not in results # Should not match 's' at start
        assert len(results) == 2

        mock_ctx.value = 'me'
        results = await self.cog._ac(mock_ctx)
        assert results == ['Melange']

        mock_ctx.value = 'non_existent'
        results = await self.cog._ac(mock_ctx)
        assert results == []

    @pytest.mark.asyncio
    async def test_demand_set_command_item_not_found(self, mock_ctx):
        """Test /demand set when item is not found."""
        self.db.resources_table.get.return_value = None
        await self.cog.demand_set(mock_ctx, item='NonExistent', level='high')
        mock_ctx.respond.assert_called_once_with("Item not found.", ephemeral=True)
        self.db.set_demand.assert_not_called()

    @pytest.mark.asyncio
    async def test_demand_set_command_success(self, mock_ctx):
        """Test /demand set command success."""
        item_data = {'id': 'spice', 'name': 'Spice', 'type': 'Resource', 'tier': 1, 'demand': 'low'}
        self.db.resources_table.get.return_value = item_data
        self.db.set_demand.return_value = True

        with patch.object(self.cog, '_post_single', new=AsyncMock()) as mock_post_single:
            await self.cog.demand_set(mock_ctx, item='Spice', level='high')

            self.db.resources_table.get.assert_called_once_with(self.db.Resource.name == 'Spice')
            self.db.set_demand.assert_called_once_with('spice', 'high')
            mock_ctx.respond.assert_called_once_with("**Spice** demand set to **high**.", ephemeral=True)
            mock_post_single.assert_called_once_with(mock_ctx.channel, 'spice')
