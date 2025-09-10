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
        # episodes = res["data"]
        return res

# Function to search for a show in Aither using its TVDB ID
async def search_show(session, tvdb_id, season_number, video_resolution, video_type, tracker):
    category_id = tracker.get_cat_id("TV")
    url = f"{tracker.URL}/api/torrents/filter?tvdbId={tvdb_id}&categories[0]={category_id}"
    if season_number:
        url += f"&seasonNumber={season_number}"
    if video_resolution:
        for index, resolution in enumerate(video_resolution):
            url += f"&resolutions[{index}]={resolution}"
    if video_type:
        url += f"&types[0]={video_type}"
    # print(f"url: {url}")

    async with session.get(url, headers={"Authorization": f"Bearer {tracker.api_key}"}) as response:
        response.raise_for_status()  # Raise an exception if the request failed
        res = await response.json()
        torrents = res["data"]
        return torrents

# Function to process each show
async def process_show(session, show, app_configs: CONFIG, tracker):
    title = show["title"]
    tvdb_id = show["tvdbId"]

    # loop through shows seasons
    for season in show["seasons"]:
        season_number = season["seasonNumber"]
        # print(f"season: {season_number}")

        # skip specials and incomplete seasons for now
        if season_number > 0 and season['statistics']["percentOfEpisodes"] == 100:
            logger.info(f"Checking {title} Season {season_number}... ")
            # pull episodes for the season
            episodes = await get_season_episodes(session, show, season_number, app_configs)
            # get resolution and type from first ep. assume season pack and all the same
            episode = episodes[0]

            # skip check if group is banned.
            if len(tracker.banned_groups) == 0:
                banned_groups = await tracker.get_banned_groups(session)
            # check if banned groups still empty and display warning.
            if len(tracker.banned_groups) == 0:
                logger.error(
                    f"Banned groups missing. Checks will be skipped."
                )
            else:
                if "releaseGroup" in episode["episodeFile"] and \
                        episode["episodeFile"]["releaseGroup"].casefold() in map(str.casefold, tracker.banned_groups):
                    logger.info(
                        f"[Banned: local] group ({episode['episodeFile']['releaseGroup']}) for {title}"
                    )
                    return

            quality_info = episode.get("episodeFile").get("quality").get("quality")
            source = quality_info.get("source")
            video_type = quality_info.get("name") # WEBDL-1080p
            if video_type.lower() == "dvd" and source.lower() == "dvd":
                release_info = guessit(episode.get("episodeFile").get("relativePath"))
                video_type = release_info.get("other")
            # print(f"\nsource: {source}, video_type: {video_type}")

            video_type = utils.get_video_type(source, video_type)
            tracker_type = tracker.get_type_id(video_type.upper())
            media_resolution = str(quality_info.get("resolution"))
            tracker_resolutions = utils.get_video_resolutions(tracker, media_resolution)
            try:
                torrents = await search_show(session, tvdb_id, season_number, tracker_resolutions, tracker_type, tracker)
            except Exception as e:
                if "429" in str(e):
                    logger.warning(f"Rate limit exceeded while checking {title}. Will retry.")
                else:
                    logger.error(f"Error: {str(e)}")
                    tracker.radarr_not_found_file.write(f"{title} - Error: {str(e)}\n")
            else:
                if len(torrents) == 0:
                    logger.info(
                        f"[{media_resolution} {video_type}] not found on AITHER"
                    )
                    filepath = os.path.dirname(episode["episodeFile"]["path"])
                    tracker.radarr_not_found_file.write(f"{filepath}\n")
                else:
                    release_info = guessit(torrents[0].get("attributes").get("name"))
                    if "release_group" in release_info \
                            and release_info["release_group"].casefold() in map(str.casefold, tracker.banned_groups):
                        logger.info(
                            f"[Trumpable: Banned] group for {title} [{media_resolution} {video_type}] on AITHER"
                        )
                    else:
                        logger.info(
                            f"[{media_resolution} {video_type}] already exists on AITHER"
                        )
            time.sleep(app_configs.SLEEP_TIMER)

# Function to get all shows from Sonarr
async def get_all_shows(session, app_configs: CONFIG):
    sonarr_url = app_configs.SONARR['url'] + app_configs.SONARR['api_suffix']
    async with session.get(sonarr_url, headers={"X-Api-Key": app_configs.SONARR['api_key']})as response:
        response.raise_for_status()  # Ensure we handle request errors properly
        shows = await response.json()
        return shows