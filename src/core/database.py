import requests
import csv
import os
from tinydb import TinyDB, Query
from dotenv import load_dotenv

# --- Database Setup ---
DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'db.json')


class MentatDB:
    def __init__(self):
        """Initializes the database connection."""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.db = TinyDB(DB_PATH, indent=4)
        self.resources_table = self.db.table('resources')
        self.settings_table = self.db.table('settings')
        self.missions_table = self.db.table('missions')
        self.user_settings_table = self.db.table('user_settings')
        self.Resource = Query()
        self.Setting = Query()
        self.Mission = Query()
        self.UserSetting = Query()

        load_dotenv()
        self.google_sheet_url = os.getenv('GOOGLE_SHEET_URL')

    def close(self):
        """Closes the database connection."""
        self.db.close()

    def close(self):
        """Closes the database connection."""
        self.db.close()

    def sync_from_google_sheet(self):
        """Fetches data from the Google Sheet and syncs it with the resources table."""
        if not self.google_sheet_url:
            print("--- DATABASE SYNC SKIPPED: GOOGLE_SHEET_URL not in .env file.")
            return

        print("Attempting to sync database from Google Sheet...")
        try:
            response = requests.get(self.google_sheet_url, timeout=15)
            response.raise_for_status()
            csv_content = response.content.decode('utf-8').splitlines()
            reader = csv.DictReader(csv_content)

            items_from_sheet = []
            for row in reader:
                item_id = row.get('Name', '').lower().replace(' ', '_').replace(':', '')
                if not item_id: continue
                items_from_sheet.append({
                    'id': item_id, 'name': row.get('Name', ''), 'type': row.get('Type', ''),
                    'tier': int(row['Tier']) if row.get('Tier', '').isdigit() else 0,
                    'details': row.get('Details', ''), 'image_url': row.get('ImageURL', ''),
                    'dgt_slug': row.get('dgtSlug', ''), 'demand': 'low'
                })

            if not items_from_sheet:
                print("WARNING: No data found in Google Sheet. DB not changed.")
                return

            print(f"Fetched {len(items_from_sheet)} items. Syncing to local database...")
            # We preserve demand levels for existing items during a sync
            all_local_items = self.resources_table.all()
            for sheet_item in items_from_sheet:
                for local_item in all_local_items:
                    if sheet_item['id'] == local_item['id']:
                        sheet_item['demand'] = local_item['demand']
                        break

            self.resources_table.truncate()
            self.resources_table.insert_multiple(items_from_sheet)
            print("Database sync complete.")
        except requests.RequestException as e:
            print(f"--- DATABASE SYNC FAILED: {e}. Bot will use local data.")

    # --- Resource Functions ---
    def set_demand(self, resource_id: str, level: str) -> bool:
        return self.resources_table.update({'demand': level}, self.Resource.id == resource_id)

    def get_resource(self, resource_id: str):
        return self.resources_table.get(self.Resource.id == resource_id)

    def get_all_by_demand(self, levels: list[str]):
        return self.resources_table.search(self.Resource.demand.one_of(levels))

    def get_all_resources(self):
        return self.resources_table.all()

    # --- NEW Settings Functions ---
    def get_setting(self, key: str):
        """Gets a setting value from the database."""
        result = self.settings_table.get(self.Setting.key == key)
        return result['value'] if result else None

    def set_setting(self, key: str, value):
        """Saves a setting value to the database."""
        self.settings_table.upsert({'key': key, 'value': value}, self.Setting.key == key)

    # --- Mission Functions ---
    def create_mission(self, mission_id: int, message_id: int, channel_id: int, creator_id: int, details: str, time: str):
        self.missions_table.insert({
            'id': mission_id,
            'message_id': message_id,
            'channel_id': channel_id,
            'creator_id': creator_id,
            'details': details,
            'time': time,
            'participants': [creator_id]
        })

    def get_mission(self, message_id: int):
        return self.missions_table.get(self.Mission.message_id == message_id)

    def get_all_missions(self):
        return self.missions_table.all()

    def update_mission_participants(self, message_id: int, participants: list[int]):
        self.missions_table.update({'participants': participants}, self.Mission.message_id == message_id)

    def delete_mission(self, message_id: int):
        self.missions_table.remove(self.Mission.message_id == message_id)

    # --- User Settings Functions ---
    def set_user_timezone(self, user_id: int, timezone: str):
        self.user_settings_table.upsert({'user_id': user_id, 'timezone': timezone}, self.UserSetting.user_id == user_id)

    def get_user_timezone(self, user_id: int):
        result = self.user_settings_table.get(self.UserSetting.user_id == user_id)
        return result['timezone'] if result else None