import os
import sys
import asyncio
import tomllib
from os.path import basename
import time
import argparse
from aiohttp_retry import RetryClient
import sonarr
import radarr
import logging

from AppConfig import AppConfig, ValidationError
from logs import setup_logging

logger = logging.getLogger("customLogger")

# Setup function to prompt user for missing API keys and URLs if critical for the selected mode(s)
def setup(app_configs: AppConfig):
    # Alert the user about missing non-critical variables
    if not app_configs.radarr['enabled'] and (not app_configs.radarr['api_key'] or not app_configs.radarr['url']):
        raise ValidationError("Radarr API key or URL is missing.")
    if not app_configs.sonarr["enabled"] and (not app_configs.sonarr['api_key'] or not app_configs.sonarr['url']):
        raise ValidationError("Sonarr API key or URL is missing. Sonarr functionality will be limited.")

async def main():
    parser = argparse.ArgumentParser(
        description="Check Radarr or Sonarr library against Aither"
    )
    parser.add_argument("--radarr", action="store_true", help="Check Radarr library")
    parser.add_argument("--sonarr", action="store_true", help="Check Sonarr library")
    parser.add_argument("--log-path", required=False, default="logs/", help="Output file path")
    parser.add_argument("-s", "--sleep-timer", type=int, required=False, default=None, help="Sleep time between calls")
    parser.add_argument("--debug", action="store_true", default=False, help="Enable debug logs")
    parser.add_argument("--config-path", required=False, default="config/", help="Config file path")

    args = parser.parse_args()
    # merge in config file with command line parms. should probably switch to ChainMap instead of mess below
    # env_vars = {k.lower().replace('app_', ''): v for k, v in os.environ.items() if k.startswith('APP_')}
    # config = ChainMap(args, env_vars, defaults)

    configs: AppConfig = AppConfig()
    config_file = os.path.join(args.config_path, 'config.toml')
    try:
        configs.load_config_file(config_file)

        if args.log_path:
            configs.log_files["output_path"] = args.log_path

        configs.radarr["enabled"] = args.radarr or (not args.sonarr and not args.radarr)
        configs.sonarr["enabled"] = args.sonarr or (not args.sonarr and not args.radarr)

        if args.sleep_timer is not None:
            configs.SLEEP_TIMER = args.sleep_timer

        # load tracker objects after merge in args and env values
        configs.load_trackers()

        setup_logging(configs)
        if args.debug:
            logger.setLevel(logging.DEBUG)

        setup(app_configs=configs)  # Ensure API keys and URLs are set
    except FileNotFoundError:
        # logger.error(f"Error config file not found: {config_file}")
        sys.exit(
            f"Error missing config. Copy template config/comfigSample.toml to {config_file} and fill in values."
        )
    except tomllib.TOMLDecodeError as e:
        # logger.error(f"Error decoding TOML file[{config_file}]: {e}")
        sys.exit(f"Error decoding TOML file[{config_file}]: {e}")
    except ValidationError as e:
        # logger.error(f"Validation Error: {e}")
        sys.exit(f"Validation Error: {e}")

    # if not args.radarr and not args.sonarr:
    #     logger.info("No arguments specified. Running both Radarr and Sonarr checks.\n")

    try:
        async with RetryClient(retry_options=configs.http_retry_options) as session:
            if args.radarr or (not args.sonarr and not args.radarr):
                movies = await radarr.get_all_movies(session, configs)
                total = len(movies)
                for index, movie in enumerate(movies):
                    # if index < 3474:  continue  #DEBUG: skip entries to problem area
                    if "movieFile" in movie:
                        filename = movie.get("movieFile").get("relativePath")
                        if "sceneName" in movie.get("movieFile"):
                            filename = movie.get("movieFile").get("sceneName")
                        logger.debug(
                            f"Source: {basename(filename)}"
                        )
                    logger.info(f"[{index + 1}/{total}] Checking {movie["title"]}: ")

                    if not "movieFile" in movie:
                        logger.info(
                            f"SKIPPED. missing local file"
                        )
                    else :
                        await radarr.process_movie(session, movie, configs.trackers)
                        time.sleep(configs.sleep_timer)  # Respectful delay

            if args.sonarr or (not args.sonarr and not args.radarr):
                shows = await sonarr.get_all_shows(session, configs)
                total = len(shows)
                for index, show in enumerate(shows):
                    # if index < 874:  continue  #DEBUG: skip entries to problem area
                    logger.info(f"[{index + 1}/{total}] Checking {show["title"]}:")
                    await sonarr.process_show(session, show, configs.trackers, configs)
                    time.sleep(configs.sleep_timer)  # Respectful delay
    except Exception as e:
        sys.exit(f"Error: {e}")
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user. Exiting.\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nMain: Program interrupted by user.")
    finally:
        logger.info("\nMain: Program exiting.")