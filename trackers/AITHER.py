import logging
import os

from aiohttp_retry import RetryClient
from guessit import guessit
import radarr
import utils
from config import CONFIG
from trackers.TrackerBase import TrackerBase

logger = logging.getLogger("customLogger")

class AITHER(TrackerBase):
    def __init__(self, app_configs: CONFIG):
        super().__init__()
        self.URL =  "https://aither.cc"
        self.api_key = app_configs.TRACKER_LIST[__class__.__name__].get("api_key")
        self.app_configs = app_configs
        self.setup_log_files(app_configs)
        pass

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

    def get_video_resolutions(self, video_resolution):
        resolutions = []

        if video_resolution not in ["1080", "1080p", "576", "576p", "480", "480p"]:
            resolutions.append(self.get_res_id(video_resolution))
        else:
            if video_resolution == "1080" or video_resolution == "1080p":
                resolutions.append(self.get_res_id("1080"))
                resolutions.append(self.get_res_id("1080p"))

            if video_resolution == "576" or video_resolution == "576p":
                resolutions.append(self.get_res_id("576"))
                resolutions.append(self.get_res_id("576p"))

            if video_resolution == "480" or video_resolution == "480p":
                resolutions.append(self.get_res_id("480"))
                resolutions.append(self.get_res_id("480p"))

        return resolutions

    def get_search_url(self, category, video_resolutions, video_type, tmdb_id=None, tvdb_id=None, season_number=None):
        # build the search url
        category_id = self.get_cat_id(category.upper())
        search_url = f"{self.URL}/api/torrents/filter?categories[0]={category_id}"
        if tmdb_id:
            search_url += f"&tmdbId={tmdb_id}"
        if tvdb_id:
            search_url += f"&tvdbId={tvdb_id}"
        if len(video_resolutions) > 0:
            for index, resolution in enumerate(video_resolutions):
                if resolution != 0:
                    search_url += f"&resolutions[{index}]={resolution}"
        if video_type:
            search_url += f"&types[0]={video_type}"
        if season_number:
            search_url += f"&seasonNumber={season_number}"

        return search_url

    async def search_movie(self, session, movie, indented):
        # update banned groups if tracker supports it
        if len(self.banned_groups) == 0:
            try:
                banned_groups = await self.fetch_banned_groups(session)
                self.banned_groups = banned_groups
            except Exception as e:
                logger.error(f"\n[{self.__class__.__name__}]Error fetching banned groups failed: {str(e)}")

        tmdb_id = movie["tmdbId"]
        quality_info = movie.get("movieFile").get("quality").get("quality")
        source = quality_info.get("source")
        modifier = quality_info.get("modifier")
        if modifier == "none" and source == "dvd":
            release_info = guessit(movie.get("movieFile").get("relativePath"))
            modifier = release_info.get("other")
        video_type = utils.get_video_type(source, modifier)
        video_type_id = None
        if video_type != "OTHER":
            video_type_id = self.get_type_id(video_type.upper())
        media_resolution = str(radarr.get_movie_resolution(movie))
        video_resolutions = self.get_video_resolutions(media_resolution)
        # build the search url
        log_prefix = ""
        if indented:
            log_prefix += f"\t{self.__class__.__name__}: "
        log_prefix += f"[{media_resolution} {video_type}]... "
        search_url = self.get_search_url("MOVIE", video_resolutions, video_type_id, tmdb_id)

        # check if local group is banned on tracker
        if "releaseGroup" in movie["movieFile"]:
            release_group = movie["movieFile"]["releaseGroup"]
            if self.is_group_banned(release_group, log_prefix):
                return

        try:
            # async with session.get(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
            async with session.get(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
                res = await response.json()
                torrents = res["data"]

                if len(torrents) == 0:
                    try:
                        movie_file = movie["movieFile"]["path"]
                        if movie_file:
                            logger.info(
                                f"{log_prefix}not found"
                            )
                            self.radarr_not_found_file.write(f"{movie_file}\n")
                        else:
                            logger.info(
                                f"{log_prefix}not found. (No media file)"
                            )
                    except KeyError:
                        logger.info(
                            f"{log_prefix}not found. (No media file)"
                        )
                else:
                    release_info = guessit(torrents[0].get("attributes").get("name"))
                    if "release_group" in release_info \
                            and release_info["release_group"].casefold() in map(str.casefold, self.banned_groups):
                        title = movie["title"]
                        logger.info(
                            f"{log_prefix} Trumpable: Banned Group: {release_info['release_group']}"
                        )
                        movie_file = movie["movieFile"]["path"]
                        if movie_file:
                            self.radarr_trump_writer.writerow({'file': movie_file, 'reason': 'Banned group'})
                    else:
                        logger.info(
                            f"{log_prefix}already exists"
                        )
        except Exception as e:
            if "429" in str(e):
                logger.error(f"{log_prefix}Rate limit exceeded.")
            else:
                logger.error(f"{log_prefix}Error: {str(e)}")
                self.radarr_not_found_file.write(f"{title} - Error: {str(e)}\n")

        logger.debug(
            f"{"\t"if indented else ""}[{self.__class__.__name__}] search url: {search_url}"
        )

    async def search_show(self, session, show, season_number, episode, indented):
        # update banned groups if tracker supports it
        if len(self.banned_groups) == 0:
            try:
                banned_groups = await self.fetch_banned_groups(session)
                self.banned_groups = banned_groups
            except Exception as e:
                logger.error(f"\n[{self.__class__.__name__}] Error fetching banned groups failed: {str(e)}")

        quality_info = episode.get("episodeFile").get("quality").get("quality")
        source = quality_info.get("source")
        video_type = quality_info.get("name")  # WEBDL-1080p
        if video_type.lower() == "dvd" and source.lower() == "dvd":
            release_info = guessit(episode.get("episodeFile").get("relativePath"))
            video_type = release_info.get("other")

        video_type = utils.get_video_type(source, video_type)
        tracker_type = None
        if video_type != "OTHER":
            tracker_type = self.get_type_id(video_type.upper())
        media_resolution = str(quality_info.get("resolution"))
        video_resolutions = self.get_video_resolutions(media_resolution)
        tvdb_id = show["tvdbId"]

        # search_url = f"{self.URL}/api/torrents/filter?tvdbId={tvdb_id}&categories[0]={category_id}"
        search_url = self.get_search_url("TV", video_resolutions, tracker_type, tvdb_id=tvdb_id, season_number=season_number)
        log_prefix = f"\t"
        if indented:
            log_prefix += f"[{self.__class__.__name__}]:"
        log_prefix += " Season {season_number}... "

        # check if local group is banned on tracker
        if "releaseGroup" in episode["episodeFile"]:
            release_group = episode["episodeFile"]["releaseGroup"]
            if self.is_group_banned(release_group, log_prefix):
                return

        try:
            # async with session.get(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
            async with session.get(search_url,
                                        headers={"Authorization": f"Bearer {self.api_key}"}) as response:
                res = await response.json()
                torrents = res["data"]

                if len(torrents) == 0:
                    logger.info(
                        f"{log_prefix}not found"
                    )
                    filepath = os.path.dirname(episode["episodeFile"]["path"])
                    self.sonarr_not_found_file.write(f"{filepath}\n")
                else:
                    release_info = guessit(torrents[0].get("attributes").get("name"))
                    if "release_group" in release_info \
                            and release_info["release_group"].casefold() in map(str.casefold, self.banned_groups):
                        logger.info(
                            f"{log_prefix} Trumpable: Banned Group: {release_info['release_group']}"
                        )
                        filepath = os.path.dirname(episode["episodeFile"]["path"])
                        if filepath:
                            self.sonarr_trump_writer.writerow({'file': filepath, 'reason': 'Banned group'})
                    else:
                        logger.info(
                            f"{log_prefix}already exists"
                        )
        except Exception as e:
            if "429" in str(e):
                logger.error(f"{log_prefix}Rate limit exceeded while checking.")
            else:
                logger.error(f"{log_prefix}Error: {str(e)}")
                self.sonarr_not_found_file.write(f"Error: {str(e)}\n")

        logger.debug(
            f"\t[{self.__class__.__name__}] search url: {search_url}"
        )

    # pull banned groups from aither api
    async def fetch_banned_groups(self, session):
        # logger.info("Fetching banned groups")

        banned_groups = []
        url = f"{self.URL}/api/blacklists/releasegroups?api_token={self.api_key}"
        try:
            # async with session.get(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
            async with session.get(url,
                                        headers={"Authorization": f"Bearer {self.api_key}"}) as response:
                res = await response.json()
                groups = res["data"]
                banned_groups = [d['name'] for d in groups]
        except Exception as e:
            if "429" in str(e):
                logger.warning(f"Rate limit exceeded while checking.")
            else:
                logger.error(f"Error: {str(e)}")
        return banned_groups
