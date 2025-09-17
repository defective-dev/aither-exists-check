import logging
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

    def get_search_url(self, category, video_resolutions, video_type, tmdb_id=None, tvdb_id=None):
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

        return search_url

    # def is_group_banned(self, movie) -> bool:
    #     # skip check if group is banned.
    #
    #     # check if banned groups still empty and display warning.
    #     if len(self.banned_groups) == 0:
    #         logger.error(
    #             f"Banned groups missing. Checks will be skipped."
    #         )
    #     else:
    #         if "releaseGroup" in movie["movieFile"] and \
    #                 movie["movieFile"]["releaseGroup"].casefold() in map(str.casefold, self.banned_groups):
    #             title = movie.get("title")
    #             logger.info(
    #                 f"[Banned: local] group ({movie['movieFile']['releaseGroup']}) for {title}"
    #             )
    #             return True
    #     return False

    async def search_movie(self, session, movie, indented):
        # update banned groups if tracker supports it
        if len(self.banned_groups) == 0:
            try:
                banned_groups = await self.fetch_banned_groups(session)
                self.banned_groups = banned_groups
            except Exception as e:
                logger.error(f"\n[{self.__class__.__name__}] Error fetching banned groups failed: {str(e)}")
        # check if local group is banned on tracker
        if "releaseGroup" in movie["movieFile"]:
            release_group = movie["movieFile"]["releaseGroup"]
            if self.is_group_banned(release_group):
                return

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
        log_prefix = f"{"\t" if indented else ""}{self.__class__.__name__ if indented else ""} [{media_resolution} {video_type}]... "
        search_url = self.get_search_url("MOVIE", video_resolutions, video_type_id, tmdb_id)

        async with session.get(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
            response.raise_for_status()  # Raise an exception if the request failed
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
                        f"{log_prefix}[Trumpable: Banned Group] for {title} [{media_resolution} {video_type} {release_info['release_group']}]"
                    )
                    movie_file = movie["movieFile"]["path"]
                    if movie_file:
                        self.radarr_trump_file.writerow([movie_file, 'Banned group'])
                else:
                    logger.info(
                        f"{log_prefix}already exists"
                    )

        logger.debug(
            f"[{self.__class__.__name__}] search url: {search_url}"
        )

    async def search_show(self, session, show, season_number):
        category_id = self.get_cat_id("TV")
        tvdb_id = show["tvdbId"]

        url = f"{self.URL}/api/torrents/filter?tvdbId={tvdb_id}&categories[0]={category_id}"
        if season_number:
            url += f"&seasonNumber={season_number}"
        if len(video_resolutions) > 0:
            for index, resolution in enumerate(video_resolutions):
                url += f"&resolutions[{index}]={resolution}"
        if video_type:
            url += f"&types[0]={video_type}"
        # print(f"url: {url}")

        async with session.get(url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
            response.raise_for_status()  # Raise an exception if the request failed
            res = await response.json()
            torrents = res["data"]
            return torrents

    # pull banned groups from aither api
    async def fetch_banned_groups(self, session):
        # logger.info("Fetching banned groups")

        banned_groups = []
        url = f"{self.URL}/api/blacklists/releasegroups?api_token={self.api_key}"
        async with session.get(url) as response:
            # if response.status_code == 429:
            #     logger.warning(f"Rate limit exceeded.")
            # else:
            response.raise_for_status()  # Raise an exception if the request failed
            res = await response.json()
            groups = res["data"]
            banned_groups = [d['name'] for d in groups]
        return banned_groups
