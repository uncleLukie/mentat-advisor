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
        self.Resource = Query()

        # Load environment variables to get the sheet URL
        load_dotenv()
        self.google_sheet_url = os.getenv('GOOGLE_SHEET_URL')

    def sync_from_google_sheet(self):
        """
        Fetches all data from the Google Sheet URL specified in the .env file
        and overwrites the local database.
        """
        # Check if the URL was loaded from the .env file
        if not self.google_sheet_url:
            print("--- DATABASE SYNC SKIPPED ---")
            print("GOOGLE_SHEET_URL not found in .env file.")
            print("The bot will use existing local data.\n")
            return

        print(f"Attempting to sync database from Google Sheet...")
        try:
            response = requests.get(self.google_sheet_url, timeout=15)
            response.raise_for_status()

            csv_content = response.content.decode('utf-8').splitlines()
            reader = csv.DictReader(csv_content)

            items_from_sheet = []
            for row in reader:
                item_id = row.get('Name', '').lower().replace(' ', '_').replace(':', '')
                # Ensure the row has a name before processing it
                if not item_id:
                    continue

                items_from_sheet.append({
                    'id': item_id,
                    'name': row.get('Name', ''),
                    'type': row.get('Type', ''),
                    'tier': int(row['Tier']) if row.get('Tier', '').isdigit() else 0,
                    'details': row.get('Details', ''),
                    'image_url': row.get('ImageURL', ''),
                    'dgt_slug': row.get('dgtSlug', ''),
                    'demand': 'low'
                })

            if not items_from_sheet:
                print("WARNING: No data was found in the Google Sheet. Database will not be changed.")
                return

            print(f"Successfully fetched {len(items_from_sheet)} items from Google Sheet.")
            print("Syncing to local database...")
            self.resources_table.truncate()
            self.resources_table.insert_multiple(items_from_sheet)
            print("Database sync complete.")

        except requests.RequestException as e:
            print(f"\n--- DATABASE SYNC FAILED ---")
            print(f"Could not fetch data from Google Sheets. Error: {e}")
            print("The bot will use existing local data.\n")

    # --- Other database functions ---

    def set_demand(self, resource_id: str, level: str) -> bool:
        """Sets the demand for a resource. Returns True on success."""
        result = self.resources_table.update({'demand': level}, self.Resource.id == resource_id)
        return len(result) > 0

    def get_resource(self, resource_id: str):
        """Gets a single resource by its ID."""
        return self.resources_table.get(self.Resource.id == resource_id)

    def get_all_by_demand(self, level: str):
        """Gets all resources with a specific demand level."""
        return self.resources_table.search(self.Resource.demand == level)

    def get_all_resources(self):
        """Returns all resources in the database."""
        return self.resources_table.all()