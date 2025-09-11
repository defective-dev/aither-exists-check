import logging
import os
import csv
from config import CONFIG

logger = logging.getLogger("customLogger")

class AITHER:
    def __init__(self, app_configs: CONFIG):
        self.URL =  "https://aither.cc"
        self.api_key = app_configs.TRACKER_LIST[__class__.__name__].get("api_key")
        self.banned_groups = []
        self.radarr_not_found_file = None
        self.radarr_trump_file = None
        self.sonarr_not_found_file = None
        self.sonarr_trump_file = None
        self.setup_log_files(app_configs)
        pass

    def setup_log_files(self, app_configs: CONFIG):
        output_path = app_configs.LOG_FILES.get("output_path")
        out_radarr = CONFIG.LOG_FILES['not_found_radarr']
        if output_path is not None:
            log_path = os.path.join(os.path.expanduser(output_path), self.__class__.__name__)
        else:
            log_path = os.path.join(os.path.expanduser(self.__class__.__name__))
        os.makedirs(log_path, exist_ok=True)
        # if app_configs.RADARR.enabled:
        out_category = os.path.join(log_path, CONFIG.LOG_FILES['not_found_radarr'])
        out_trump = os.path.join(log_path, CONFIG.LOG_FILES['trump_radarr'])
        self.radarr_not_found_file = open(out_category, "w", encoding="utf-8", buffering=1)
        csv_headers = ['File', 'Reason']
        with open(out_trump, 'w', newline='', encoding='utf-8') as csv_file:
            self.radarr_trump_file = csv.DictWriter(csv_file, fieldnames=csv_headers, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            self.radarr_trump_file.writeheader()
            # self.radarr_trump_file = csv.writer(out_trump, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # if app_configs.SONARR.enabled:
        out_category = os.path.join(log_path, CONFIG.LOG_FILES['not_found_sonarr'])
        out_trump = os.path.join(log_path, CONFIG.LOG_FILES['trump_sonarr'])
        self.sonarr_not_found_file = open(out_category, "w", encoding="utf-8", buffering=1)
        with open(out_trump, 'w', newline='', encoding='utf-8') as csv_file:
            self.sonarr_trump_file = csv.DictWriter(csv_file, fieldnames=csv_headers, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            self.sonarr_trump_file.writeheader()
            # self.sonarr_trump_file = csv.writer(out_trump, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    def get_type_id(self, type=None):
        type_mapping = {
            "FULL DISC": 1,
            "REMUX": 2,
            "ENCODE": 3,
            "WEB-DL": 4,
            "WEBRIP": 5,
            "HDTV": 6,
            "OTHER": 7,
            "MOVIE PACK": 10,
        }

        if type is not None:
            # Return the specific type ID
            return type_mapping.get(type, 0)
        else:
            # Return the full mapping
            return type_mapping

    def get_res_id(self, resolution=None):
        resolution_mapping = {
            "4320": 1,
            "2160": 2,
            "1080": 3,
            "1080p": 4,
            "720": 5,
            "576": 6,
            "576p": 7,
            "480": 8,
            "480p": 9,
            '8640p': 10
        }

        if resolution is not None:
            # Return the ID for the given resolution
            return resolution_mapping.get(resolution, '0')  # Default to '0' for unknown resolutions
        else:
            # Return the full mapping
            return resolution_mapping

    # pull banned groups from aither api
    async def get_banned_groups(self, session):
        # logger.info("Fetching banned groups")

        groups = []
        url = f"{self.URL}/api/blacklists/releasegroups?api_token={self.api_key}"
        async with session.get(url) as response:
            # if response.status_code == 429:
            #     logger.warning(f"Rate limit exceeded.")
            # else:
            response.raise_for_status()  # Raise an exception if the request failed
            res = await response.json()
            groups = res["data"]
            self.banned_groups = [d['name'] for d in groups]
        return self.banned_groups
