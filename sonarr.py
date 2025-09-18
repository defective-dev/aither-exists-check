import asyncio
import os
import time
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

# Function to search for a show in Aither using its TVDB ID
# async def search_show(session, show, season_number, video_resolutions, video_type, tracker):
#     category_id = tracker.get_cat_id("TV")
#     tvdb_id = show["tvdbId"]
#
#     url = f"{tracker.URL}/api/torrents/filter?tvdbId={tvdb_id}&categories[0]={category_id}"
#     if season_number:
#         url += f"&seasonNumber={season_number}"
#     if len(video_resolutions) > 0:
#         for index, resolution in enumerate(video_resolutions):
#             url += f"&resolutions[{index}]={resolution}"
#     if video_type:
#         url += f"&types[0]={video_type}"
#     # print(f"url: {url}")
#
#     async with session.get(url, headers={"Authorization": f"Bearer {tracker.api_key}"}) as response:
#         response.raise_for_status()  # Raise an exception if the request failed
#         res = await response.json()
#         torrents = res["data"]
#         return torrents

# Function to process each show
async def process_show(session, show, trackers, app_configs: CONFIG):
    title = show["title"]

    if len(show["seasons"]) > 1:
        logger.info("")  # add newline to put season list below title.

    # add newline to put list below title if multiple checks
    # and tab indent sub items
    indented = False
    if len(trackers) > 1:
        indented = True

    # loop through shows seasons
    for season in show["seasons"]:
        season_number = season["seasonNumber"]

        # skip specials and incomplete seasons for now
        if season_number > 0 and season['statistics']["percentOfEpisodes"] == 100:
            # pull episodes for the season
            episodes = await get_season_episodes(session, show, season_number, app_configs)
            # get resolution and type from first ep. assume season pack and all the same
            episode = episodes[0]

            tasks = [tracker.search_show(session, show, season_number, episode, indented) for tracker in trackers]
            await asyncio.gather(*tasks)

                # torrents = await tracker.search_show(session, show, season_number, tracker_resolutions, tracker_type)
            # except Exception as e:
            #     if "429" in str(e):
            #         logger.warning(f"Rate limit exceeded while checking {title}. Will retry.")
            #     else:
            #         logger.error(f"Error: {str(e)}")
            #         tracker.radarr_not_found_file.write(f"{title} - Error: {str(e)}\n")
            # else:
            #     if len(torrents) == 0:
            #         logger.info(
            #             f"[{media_resolution} {video_type}] not found"
            #         )
            #         filepath = os.path.dirname(episode["episodeFile"]["path"])
            #         tracker.radarr_not_found_file.write(f"{filepath}\n")
            #     else:
            #         release_info = guessit(torrents[0].get("attributes").get("name"))
            #         if "release_group" in release_info \
            #                 and release_info["release_group"].casefold() in map(str.casefold, tracker.banned_groups):
            #             logger.info(
            #                 f"[Trumpable: Banned] group for {title} [{media_resolution} {video_type}]"
            #             )
            #             filepath = os.path.dirname(episode["episodeFile"]["path"])
            #             if filepath:
            #                 tracker.radarr_trump_file.writerow([filepath, 'Banned group'])
            #         else:
            #             logger.info(
            #                 f"[{media_resolution} {video_type}] already exists"
            #             )
            time.sleep(app_configs.SLEEP_TIMER)

# Function to get all shows from Sonarr
async def get_all_shows(session, app_configs: CONFIG):
    sonarr_url = app_configs.SONARR['url'] + app_configs.SONARR['api_suffix']
    async with session.get(sonarr_url, headers={"X-Api-Key": app_configs.SONARR['api_key']})as response:
        response.raise_for_status()  # Ensure we handle request errors properly
        shows = await response.json()
        return shows