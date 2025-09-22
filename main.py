import sys
import asyncio
import aiohttp
import time
import argparse
import os

from aiohttp_retry import RetryClient

import sonarr
import radarr
import utils
import logging

from config import CONFIG
from logs import setup_logging

logger = logging.getLogger("customLogger")

# Setup function to prompt user for missing API keys and URLs if critical for the selected mode(s)
def setup(radarr_needed, sonarr_needed, app_configs: CONFIG):
    missing = []

    # if not configs.aither_key:
    #     missing.append("Aither API key")
    #     configs.aither_key = input("Enter your Aither API key: ")

    # Alert the user about missing non-critical variables
    if not radarr_needed and (not app_configs.RADARR['api_key'] or not app_configs.RADARR['api_key']):
        logger.error(
            "Radarr API key or URL is missing. Radarr functionality will be limited."
        )
    if not sonarr_needed and (not app_configs.SONARR['api_key'] or not app_configs.SONARR['url']):
        logger.error(
            "Sonarr API key or URL is missing. Sonarr functionality will be limited."
        )

# Main function to handle both Radarr and Sonarr
async def main():
    parser = argparse.ArgumentParser(
        description="Check Radarr or Sonarr library against Aither"
    )
    parser.add_argument("--radarr", action="store_true", help="Check Radarr library")
    parser.add_argument("--sonarr", action="store_true", help="Check Sonarr library")
    parser.add_argument("-o", "--output-path", required=False, help="Output file path")
    parser.add_argument("-s", "--sleep-timer", type=int, required=False, default=None, help="Sleep time between calls")
    parser.add_argument("--debug", action="store_true", help="Enable debug logs")

    args = parser.parse_args()
    # merge in config file with command line parms. should probably switch to ChainMap instead of mess below
    # env_vars = {k.lower().replace('app_', ''): v for k, v in os.environ.items() if k.startswith('APP_')}
    # config = ChainMap(args, env_vars, defaults)
    configs: CONFIG = CONFIG

    #TODO: setup config default values for those that don't update config

    if args.output_path:
        configs.LOG_FILES["output_path"] = args.output_path
    configs.RADARR["enabled"] = args.radarr or (not args.sonarr and not args.radarr)
    configs.SONARR["enabled"] = args.sonarr or (not args.sonarr and not args.radarr)

    if args.sleep_timer is not None:
        configs.SLEEP_TIMER = args.sleep_timer

    setup_logging(configs)
    if args.debug is not None:
        logger.setLevel(logging.DEBUG)

    #TODO: proper validation of configs
    radarr_needed = args.radarr or (not args.sonarr and not args.radarr)
    sonarr_needed = args.sonarr or (not args.sonarr and not args.radarr)
    setup(
        radarr_needed=radarr_needed, sonarr_needed=sonarr_needed, app_configs=configs
    )  # Ensure API keys and URLs are set

    if not args.radarr and not args.sonarr:
        logger.info("No arguments specified. Running both Radarr and Sonarr checks.\n")

    # Read list of trackers to search from configs
    trackers = utils.sites_from_config(configs.TRACKERS_SEARCH, configs)
    if len(trackers) == 0:
        sys.exit("No trackers to search.")

    try:
        async with RetryClient(retry_options=configs.http_retry_options) as session:
            if args.radarr or (not args.sonarr and not args.radarr):
                if configs.RADARR['api_key'] and configs.RADARR['url']:
                    movies = await radarr.get_all_movies(session, configs)
                    total = len(movies)
                    for index, movie in enumerate(movies):
                        # if index < 3425:  continue  #DEBUG: skip entries to problem area
                        if "movieFile" in movie:
                            logger.debug(
                                f"Source: {movie.get("movieFile").get("relativePath")}"
                            )
                        logger.info(f"[{index + 1}/{total}] Checking {movie["title"]}: ")

                        if not "movieFile" in movie:
                            logger.info(
                                f"SKIPPED. missing local file"
                            )
                        else :
                            await radarr.process_movie(session, movie, trackers)
                            time.sleep(configs.SLEEP_TIMER)  # Respectful delay
                else:
                    logger.warning(
                        "Skipping Radarr check: Radarr API key or URL is missing.\n"
                    )

            if args.sonarr or (not args.sonarr and not args.radarr):
                if configs.SONARR['api_key'] and configs.SONARR['url']:
                    shows = await sonarr.get_all_shows(session, configs)
                    total = len(shows)
                    for index, show in enumerate(shows):
                        logger.info(f"[{index + 1}/{total}] Checking {show["title"]}: ")
                        await sonarr.process_show(session, show, trackers, configs)
                        time.sleep(configs.SLEEP_TIMER)  # Respectful delay
                else:
                    logger.warning(
                        "Skipping Sonarr check: Sonarr API key or URL is missing.\n"
                    )
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user. Exiting.\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nMain: Program interrupted by user.")
    finally:
        logger.info("\nMain: Program exiting.")