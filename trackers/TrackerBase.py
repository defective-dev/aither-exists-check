import csv
import logging
import os
import AppConfig

logger = logging.getLogger("customLogger")

class TrackerBase:
    def __init__(self):
        self.banned_groups = []
        self.radarr_not_found_file = None
        self.radarr_trump_file = None
        self.radarr_trump_writer = None
        self.sonarr_not_found_file = None
        self.sonarr_trump_file = None
        self.sonarr_trump_writer = None
        pass

    def setup_log_files(self, app_configs: AppConfig):
        output_path = app_configs.log_files.get("output_path")
        if output_path is not None:
            log_path = os.path.join(os.path.expanduser(output_path), self.__class__.__name__)
        else:
            log_path = os.path.join(os.path.expanduser(self.__class__.__name__))
        os.makedirs(log_path, exist_ok=True)
        csv_headers = ['file', 'reason']

        if app_configs.radarr.get("enabled"):
            out_category = os.path.join(log_path, app_configs.log_files['not_found_radarr'])
            out_trump = os.path.join(log_path, app_configs.log_files['trump_radarr'])
            self.radarr_not_found_file = open(out_category, "w", encoding="utf-8", buffering=1)
            self.radarr_trump_file = open(out_trump, 'w', newline='', encoding='utf-8', buffering=1)
            self.radarr_trump_writer = csv.DictWriter(self.radarr_trump_file, fieldnames=csv_headers, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            self.radarr_trump_writer.writeheader()

        if app_configs.radarr.get("enabled"):
            out_category = os.path.join(log_path, app_configs.log_files['not_found_sonarr'])
            out_trump = os.path.join(log_path, app_configs.log_files['trump_sonarr'])
            self.sonarr_not_found_file = open(out_category, "w", encoding="utf-8", buffering=1)
            self.sonarr_trump_file = open(out_trump, 'w', newline='', encoding='utf-8', buffering=1)
            self.sonarr_trump_writer = csv.DictWriter(self.sonarr_trump_file, fieldnames=csv_headers, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            self.sonarr_trump_writer.writeheader()

    def is_group_banned(self, release_group, log_prefix="") -> bool:
        # check if banned groups still empty and display warning.
        if len(self.banned_groups) == 0:
            logger.error(
                f"{log_prefix}ERROR: Banned groups missing. Checks will be skipped."
            )
        elif len(release_group) == 0:
            logger.warning(
                f"\nERROR: Release group missing. Checks will be skipped."
            )
        else:
            if release_group.casefold() in map(str.casefold, self.banned_groups):
                logger.info(
                    f"{log_prefix}Skipped. local file banned group: {release_group}"
                )
                return True
        return False
