import pytest
import os
from unittest.mock import patch, MagicMock
from tinydb import TinyDB, Query
from src.core.database import MentatDB

# Define a temporary database path for testing
TEST_DB_PATH = os.path.join(os.path.dirname(__file__), 'temp_test_db.json')

@pytest.fixture(autouse=True)
def run_around_tests():
    """Fixture to ensure a clean database for each test."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    
    # Patch DB_PATH to use the temporary test database
    with patch('src.core.database.DB_PATH', TEST_DB_PATH):
        yield
    
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@pytest.fixture
def db_instance():
    """Fixture to provide a MentatDB instance for tests."""
    with patch('src.core.database.DB_PATH', TEST_DB_PATH):
        db = MentatDB()
        db.resources_table.insert_multiple([
            {'id': 'spice', 'name': 'Spice', 'type': 'Resource', 'tier': 1, 'demand': 'low'},
            {'id': 'water', 'name': 'Water', 'type': 'Resource', 'tier': 1, 'demand': 'medium'},
            {'id': 'solari', 'name': 'Solari', 'type': 'Currency', 'tier': 0, 'demand': 'high'}
        ])
        yield db

class TestMentatDB:
    def test_db_initialization(self):
        """Test that the database initializes correctly and tables are created."""
        with patch('src.core.database.DB_PATH', TEST_DB_PATH):
            db = MentatDB()
            assert isinstance(db.db, TinyDB)
            assert db.resources_table is not None
            assert db.settings_table is not None
            assert db.missions_table is not None
            assert db.user_settings_table is not None

    def test_set_demand(self, db_instance):
        """Test setting the demand level for a resource."""
        assert db_instance.set_demand('spice', 'high')
        resource = db_instance.get_resource('spice')
        assert resource['demand'] == 'high'

    def test_get_resource(self, db_instance):
        """Test retrieving a single resource by ID."""
        resource = db_instance.get_resource('water')
        assert resource['name'] == 'Water'
        assert resource['demand'] == 'medium'

        non_existent_resource = db_instance.get_resource('non_existent')
        assert non_existent_resource is None

    def test_get_all_by_demand(self, db_instance):
        """Test retrieving resources filtered by demand level."""
        low_demand_resources = db_instance.get_all_by_demand(['low'])
        assert len(low_demand_resources) == 1
        assert low_demand_resources[0]['id'] == 'spice'

        high_medium_demand_resources = db_instance.get_all_by_demand(['high', 'medium'])
        assert len(high_medium_demand_resources) == 2
        assert any(r['id'] == 'water' for r in high_medium_demand_resources)
        assert any(r['id'] == 'solari' for r in high_medium_demand_resources)

        no_demand_resources = db_instance.get_all_by_demand(['very_high'])
        assert len(no_demand_resources) == 0

    def test_get_all_resources(self, db_instance):
        """Test retrieving all resources."""
        all_resources = db_instance.get_all_resources()
        assert len(all_resources) == 3
        assert any(r['id'] == 'spice' for r in all_resources)
        assert any(r['id'] == 'water' for r in all_resources)
        assert any(r['id'] == 'solari' for r in all_resources)

    @patch('src.core.database.requests.get')
    @patch('src.core.database.os.getenv')
    def test_sync_from_google_sheet_success(self, mock_getenv, mock_requests_get):
        """Test successful sync from Google Sheet."""
        mock_getenv.return_value = "http://example.com/sheet.csv"
        mock_response = MagicMock()
        mock_response.content = b"Name,Type,Tier,Details,ImageURL,dgtSlug\nSpice,Resource,1,A valuable resource,,spice_slug\nWater,Resource,1,Essential for life,,water_slug"
        mock_requests_get.return_value = mock_response

        with patch('src.core.database.DB_PATH', TEST_DB_PATH):
            db = MentatDB()
            db.sync_from_google_sheet()

            resources = db.resources_table.all()
            assert len(resources) == 2
            assert db.get_resource('spice')['name'] == 'Spice'
            assert db.get_resource('water')['type'] == 'Resource'
            assert db.get_resource('spice')['dgt_slug'] == 'spice_slug'

    @patch('src.core.database.requests.get')
    @patch('src.core.database.os.getenv')
    def test_sync_from_google_sheet_empty_data(self, mock_getenv, mock_requests_get):
        """Test sync from Google Sheet with empty data."""
        mock_getenv.return_value = "http://example.com/sheet.csv"
        mock_response = MagicMock()
        mock_response.content = b"Name,Type,Tier,Details,ImageURL,dgtSlug" # Only header
        mock_requests_get.return_value = mock_response

        with patch('src.core.database.DB_PATH', TEST_DB_PATH):
            db = MentatDB()
            db.resources_table.insert({'id': 'existing', 'name': 'Existing', 'demand': 'low'}) # Add some existing data
            
            db.sync_from_google_sheet()

            # Database should not be truncated if no data is found in sheet
            resources = db.resources_table.all()
            assert len(resources) == 1
            assert db.get_resource('existing')['name'] == 'Existing'

    @patch('src.core.database.os.getenv')
    def test_sync_from_google_sheet_no_url(self, mock_getenv):
        """Test sync from Google Sheet when GOOGLE_SHEET_URL is not set."""
        mock_getenv.return_value = None

        with patch('src.core.database.DB_PATH', TEST_DB_PATH):
            db = MentatDB()
            db.resources_table.insert({'id': 'existing', 'name': 'Existing', 'demand': 'low'}) # Add some existing data
            
            db.sync_from_google_sheet()

            # Database should remain unchanged
            resources = db.resources_table.all()
            assert len(resources) == 1
            assert db.get_resource('existing')['name'] == 'Existing'

    @patch('src.core.database.requests.get')
    @patch('src.core.database.os.getenv')
    def test_sync_from_google_sheet_request_exception(self, mock_getenv, mock_requests_get):
        """Test sync from Google Sheet when a RequestException occurs."""
        mock_getenv.return_value = "http://example.com/sheet.csv"
        mock_requests_get.side_effect = requests.exceptions.RequestException("Test Error")

        with patch('src.core.database.DB_PATH', TEST_DB_PATH):
            db = MentatDB()
            db.resources_table.insert({'id': 'existing', 'name': 'Existing', 'demand': 'low'}) # Add some existing data
            
            db.sync_from_google_sheet()

            # Database should remain unchanged
            resources = db.resources_table.all()
            assert len(resources) == 1
            assert db.get_resource('existing')['name'] == 'Existing'

    @patch('src.core.database.requests.get')
    @patch('src.core.database.os.getenv')
    def test_sync_from_google_sheet_preserves_demand(self, mock_getenv, mock_requests_get):
        """Test that demand levels are preserved during sync."""
        mock_getenv.return_value = "http://example.com/sheet.csv"
        mock_response = MagicMock()
        mock_response.content = b"Name,Type,Tier,Details,ImageURL,dgtSlug\nSpice,Resource,1,A valuable resource,,spice_slug\nWater,Resource,1,Essential for life,,water_slug"
        mock_requests_get.return_value = mock_response

        with patch('src.core.database.DB_PATH', TEST_DB_PATH):
            db = MentatDB()
            # Set initial demand for spice
            db.resources_table.insert({'id': 'spice', 'name': 'Spice', 'type': 'Resource', 'tier': 1, 'demand': 'very_high'})
            db.resources_table.insert({'id': 'old_item', 'name': 'Old Item', 'type': 'Junk', 'tier': 0, 'demand': 'low'})

            db.sync_from_google_sheet()

            spice_resource = db.get_resource('spice')
            assert spice_resource['demand'] == 'very_high' # Demand should be preserved
            assert db.get_resource('old_item') is None # Old item should be removed if not in sheet

            water_resource = db.get_resource('water')
            assert water_resource['demand'] == 'low' # New item should have default demand

    def test_set_and_get_setting(self, db_instance):
        """Test setting and getting a general setting."""
        db_instance.set_setting('welcome_message', 'Hello, adventurer!')
        assert db_instance.get_setting('welcome_message') == 'Hello, adventurer!'

        db_instance.set_setting('welcome_message', 'Welcome back!') # Update existing
        assert db_instance.get_setting('welcome_message') == 'Welcome back!'

        assert db_instance.get_setting('non_existent_setting') is None

    def test_mission_crud(self, db_instance):
        """Test CRUD operations for missions."""
        # Create
        db_instance.create_mission(1, 100, 200, 300, 'Gather spice', 'tomorrow')
        mission = db_instance.get_mission(100)
        assert mission['id'] == 1
        assert mission['message_id'] == 100
        assert mission['participants'] == [300]

        # Get all
        all_missions = db_instance.get_all_missions()
        assert len(all_missions) == 1

        # Update participants
        db_instance.update_mission_participants(100, [300, 400, 500])
        updated_mission = db_instance.get_mission(100)
        assert updated_mission['participants'] == [300, 400, 500]

        # Delete
        db_instance.delete_mission(100)
        assert db_instance.get_mission(100) is None
        assert len(db_instance.get_all_missions()) == 0

    def test_user_timezone_crud(self, db_instance):
        """Test CRUD operations for user timezones."""
        # Set
        db_instance.set_user_timezone(123, 'America/New_York')
        assert db_instance.get_user_timezone(123) == 'America/New_York'

        db_instance.set_user_timezone(123, 'Europe/London') # Update
        assert db_instance.get_user_timezone(123) == 'Europe/London'

        # Get non-existent
        assert db_instance.get_user_timezone(456) is None
