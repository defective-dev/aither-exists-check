import logging
import tomllib
import utils
from aiohttp_retry import ExponentialRetry

from trackers.TrackerBase import TrackerBase

logger = logging.getLogger("customLogger")


class ValidationError(Exception):
    """Custom exception raised for a specific error condition."""

    def __init__(self, message="A validation error occurred"):
        self.message = message
        super().__init__(self.message)


class AppConfig:
    def __init__(self):
        # load default values
        self.sleep_timer: int = 10
        self.radarr: dict = {
            # scan radarr. using command line --radarr or --sonarr will override this value
            "enabled": True,
            # radarr -> settings -> general
            "api_key": "",
            # radarr port typically 7878, local DNS should work if you have it setup, else "localhost" if local machine
            "url": "http://localhost:7878",
            "api_suffix": "/api/v3/movie"
        }

        self.sonarr: dict = {
            # scan sonarr. using command line --radarr or --sonarr will override this value
            "enabled": True,
            # sonarr -> settings -> general
            "api_key": "",
            # sonarr port typically 8989, local DNS should work if you have it setup, else "localhost" if local machine
            "url": "http://localhost:8989",
            "api_suffix": "/api/v3/series"
        }

        self.log_files: dict = {
            "output_path": "logs/",
            "script_log": "script.log",
            "not_found_radarr": "radarr-not_found.txt",
            "not_found_sonarr": "sonarr-not_found.txt",
            "trump_radarr": "radarr-trump.csv",
            "trump_sonarr": "sonarr-trump.csv"
        }

        # list of trackers to search
        self.trackers: list[TrackerBase] = []
        self.tracker_configs: list = []

        # ADVANCED Configs. Probably no need to edit these.

        # Configure ExponentialRetry with desired parameters
        # attempts: Maximum number of retry attempts
        # start_timeout: Initial delay before the first retry
        # factor: Multiplier for increasing the delay between retries
        # statuses: HTTP status codes that trigger a retry (default includes 5xx)
        self.http_retry_options: ExponentialRetry = ExponentialRetry(
            attempts=4,
            start_timeout=5.0,  # 0.5 seconds initial delay
            factor=2.0,  # Double the delay each time
            max_timeout=40.0,  # Maximum delay between retries
            statuses={429, 500, 502, 503, 504}  # Retry on common server errors
        )

    # def create_config_file(self, config_file: str):
    #     logger.info(f"Creating config template: {config_file}")
    #     # Iterates a dataclass configuration object and writes its contents to a TOML file.
    # 
    #     config_dict = asdict(self)  # Convert dataclass to a dictionary
    #     toml_document = tomlkit.document()
    # 
    #     def add_to_toml(parent_doc, data_dict):
    #         for key, value in data_dict.items():
    #             if isinstance(value, dict):
    #                 # Create a new table for nested dictionaries
    #                 table = tomlkit.table()
    #                 parent_doc.add(key, table)
    #                 add_to_toml(table, value)
    #             else:
    #                 parent_doc.add(key, value)
    # 
    #     add_to_toml(toml_document, config_dict)
    # 
    #     with open(config_file, "w") as f:
    #         f.write(toml_document.as_string())

    def load_config_file(self, config_file: str):
        logger.info(f"Loading config: {config_file}")

        # Load from a file
        # try:
        with open(config_file, "rb") as f:
            config_data = tomllib.load(f)
        logger.info(f"Loaded config file: {config_file}")
        logger.debug(f"config data: {config_data}")
        self.sleep_timer = config_data.get("sleep_timer", 10)

        self.radarr["enabled"] = config_data.get("radarr").get("enabled", True)
        self.radarr["api_key"] = config_data.get("radarr").get("api_key", "")
        self.radarr["url"] = config_data.get("radarr").get("url", "http://localhost:7878")
        self.radarr["api_suffix"] = config_data.get("radarr").get("api_suffix", "/api/v3/movie")

        self.sonarr["enabled"] = config_data.get("sonarr").get("enabled", True)
        self.sonarr["api_key"] = config_data.get("sonarr").get("api_key", "")
        self.sonarr["url"] = config_data.get("sonarr").get("url", "http://localhost:8989")
        self.sonarr["api_suffix"] = config_data.get("sonarr").get("api_suffix", "/api/v3/series")

        self.log_files["output_path"] = config_data.get("log_files").get("output_path", "logs/")
        self.log_files["script_log"] = config_data.get("log_files").get("script_log", "script.log")
        self.log_files["not_found_radarr"] = config_data.get("log_files").get("not_found_radarr", "radarr-not_found.txt")
        self.log_files["not_found_sonarr"] = config_data.get("log_files").get("not_found_sonarr", "sonarr-not_found.txt")
        self.log_files["trump_radarr"] = config_data.get("log_files").get("trump_radarr", "radarr-trump.csv")
        self.log_files["trump_sonarr"] = config_data.get("log_files").get("trump_sonarr", "sonarr-trump.csv")

        # store the tracker data from configs but don't laod yet. Wait till after merge in command line args
        trackers_list = config_data.get("trackers", [])
        self.tracker_configs = trackers_list

    def load_trackers(self):
        trackers_list = self.tracker_configs
        if len(trackers_list) > 0:
            self.trackers = utils.sites_from_config(trackers_list, self)

            # validate they are enabled and have api keys
            cnt = 0
            for tracker in self.trackers:
                if len(tracker.api_key) == 0:
                    raise ValidationError(f"No api key for {tracker.__class__.__name__}")
                else:
                    cnt += 1

            if cnt == 0:
                raise ValidationError("No enabled trackers found.")
        else:
            raise ValidationError("No enabled trackers found.")
        # for tracker in config_data.get("trackers", []):

