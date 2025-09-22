import asyncio
import os
import time
from os.path import basename

from guessit import guessit
import logging

import utils
from config import CONFIG

logger = logging.getLogger("customLogger")

async def get_season_episodes(session, show, season_number, app_configs: CONFIG):
    url = app_configs.SONARR['url'] + f"/api/v3/episode?seriesId={show["id"]}&seasonNumber={season_number}&includeSeries=false&includeEpisodeFile=true&includeImages=false"
    async with session.get(url, headers={"X-Api-Key": app_configs.SONARR['api_key']}) as response:
        response.raise_for_status()  # Raise an exception if the request failed
        res = await response.json()
        return res

# Function to process each show
async def process_show(session, show, trackers, app_configs: CONFIG):
    # add newline to put list below title if multiple checks
    # and tab indent sub items
    indented = False
    if len(trackers) > 1:
        indented = True

    # loop through shows seasons
    season_number = None
    for season in show["seasons"]:
        season_number = season["seasonNumber"]

        # skip specials and incomplete seasons for now
        if season_number > 0 and season['statistics']["percentOfEpisodes"] == 100:
            # pull episodes for the season
            episodes = await get_season_episodes(session, show, season_number, app_configs)
            # get resolution and type from first ep. assume season pack and all the same
            episode = episodes[0]

            # should be issue due to 100% check. incase file missing sonarr hasn't been updated.
            if "episodeFile" in episode:
                filename = episode.get("episodeFile").get("relativePath")
                if "sceneName" in episode.get("episodeFile"):
                    filename = episode.get("episodeFile").get("sceneName")
                logger.debug(
                    f"\tSource: {basename(filename)}"
                )
                # display missing release group warning. So only once and not duplicated per tracker.
                if "releaseGroup" in episode["episodeFile"] and not episode["episodeFile"]["releaseGroup"].strip():
                    logger.warning(
                        f"\tWarning: Release group missing. Banned checks will be skipped."
                    )
                tasks = [tracker.search_show(session, show, season_number, episode, indented) for tracker in trackers]
                await asyncio.gather(*tasks)
                time.sleep(app_configs.SLEEP_TIMER)
            else:
                logger.debug(
                    f"\tSeason {"{:02d}".format(season_number)} SKIPPED. Missing local files."
                )
        else:
            if season_number != 0:
                logger.info(
                    f"\tSeason {"{:02d}".format(season_number)} SKIPPED. Incomplete season."
                )
            else:
                logger.info(
                    f"\tSeason {"{:02d}".format(season_number)} SKIPPED. Specials not implemented."
                )

# Function to get all shows from Sonarr
async def get_all_shows(session, app_configs: CONFIG):
    sonarr_url = app_configs.SONARR['url'] + app_configs.SONARR['api_suffix']
    async with session.get(sonarr_url, headers={"X-Api-Key": app_configs.SONARR['api_key']})as response:
        response.raise_for_status()  # Ensure we handle request errors properly
        shows = await response.json()
        return shows