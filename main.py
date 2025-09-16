import sys
import asyncio
import aiohttp
import time
import argparse
import os
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

    args = parser.parse_args()
    # merge in config file with command line parms. should probably switch to ChainMap instead of mess below
    # env_vars = {k.lower().replace('app_', ''): v for k, v in os.environ.items() if k.startswith('APP_')}
    # config = ChainMap(args, env_vars, defaults)
    configs: CONFIG = CONFIG
    if args.output_path:
        configs.LOG_FILES["output_path"] = args.output_path
    configs.RADARR["enabled"] = args.radarr or (not args.sonarr and not args.radarr)
    configs.SONARR["enabled"] = args.sonarr or (not args.sonarr and not args.radarr)

    if args.sleep_timer is not None:
        configs.SLEEP_TIMER = args.sleep_timer

    setup_logging(configs)
    if args.output_path is not None:
        script_log = os.path.join(os.path.expanduser(args.output_path), configs.LOG_FILES["script_log"])
    file_handler = logging.FileHandler(f"{configs.LOG_FILES["script_log"]}")
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    radarr_needed = args.radarr or (not args.sonarr and not args.radarr)
    sonarr_needed = args.sonarr or (not args.sonarr and not args.radarr)
    setup(
        radarr_needed=radarr_needed, sonarr_needed=sonarr_needed, app_configs=configs
    )  # Ensure API keys and URLs are set

    if not args.radarr and not args.sonarr:
        logger.info("No arguments specified. Running both Radarr and Sonarr checks.\n")

    # Read list of trackers to search from configs
    sites = utils.sites_from_config(configs.TRACKERS_SEARCH, configs)
    if len(sites) == 0:
        sys.exit("No trackers to search.")

    try:
        async with aiohttp.ClientSession()as session:
            if args.radarr or (not args.sonarr and not args.radarr):
                if configs.RADARR['api_key'] and configs.RADARR['url']:
                    movies = await radarr.get_all_movies(session, configs)
                    for movie in movies:
                        tasks = [radarr.process_movie(session, movie, tracker) for tracker in sites]
                        await asyncio.gather(*tasks)
                        time.sleep(configs.SLEEP_TIMER)  # Respectful delay
                else:
                    logger.warning(
                        "Skipping Radarr check: Radarr API key or URL is missing.\n"
                    )

            if args.sonarr or (not args.sonarr and not args.radarr):
                if configs.SONARR['api_key'] and configs.SONARR['url']:
                    shows = await sonarr.get_all_shows(session, configs)
                    for show in shows:
                        tasks = [sonarr.process_show(session, show, configs, tracker) for tracker in sites]
                        await asyncio.gather(*tasks)
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