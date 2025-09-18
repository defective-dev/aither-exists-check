import logging
import os

import utils
from config import CONFIG
from trackers.TrackerBase import TrackerBase
from guessit import guessit


logger = logging.getLogger("customLogger")

class BHD(TrackerBase):
    def __init__(self, app_configs: CONFIG):
        super().__init__()
        self.URL =  "https://beyond-hd.me"
        self.api_key = app_configs.TRACKER_LIST[__class__.__name__].get("api_key")
        self.setup_log_files(app_configs)
        self.banned_groups = ['Sicario', 'TOMMY', 'x0r', 'nikt0', 'FGT', 'd3g', 'MeGusta', 'YIFY', 'tigole', 'TEKNO3D', 'C4K', 'RARBG', '4K4U', 'EASports', 'ReaLHD', 'Telly', 'AOC', 'WKS', 'SasukeducK']
        pass

    def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    def get_source_id(self, source):
        src = source.lower()
        sources = {
            "blu-ray": "Blu-ray",
            "bluray": "Blu-ray",
            "hddvd": "HD-DVD",
            "hd dvd": "HD-DVD",
            "web": "WEB",
            "webdl": "WEB",
            "web-dl": "WEB",
            "webrip": "WEB",
            "hdtv": "HDTV",
            "uhdtv": "HDTV",
            "dvd": "DVD",
            "ntsc": "DVD", "ntsc dvd": "DVD",
            "pal": "DVD", "pal dvd": "DVD",
        }

        source_id = sources.get(src)
        return str(source_id)

    def get_types(self,source, modifier):
        type_id = None
        if source.lower() == "dvd" and modifier.lower() == "remux":
            type_id = "DVD Remux"
        elif source.lower() == "bluray" and modifier.lower() == "remux":
            type_id = "BD Remux"
        elif source.lower() == "uhd" and modifier.lower() == "remux":
            type_id = "UHD Remux"
        return type_id

    def get_video_resolutions(self, video_resolution):
        resolutions = []

        match video_resolution:
            case 480:
                resolutions.append("480p")
            case 540:
                resolutions.append("540p")
            case 576:
                resolutions.append("576i")
                resolutions.append("576p")
            case 720:
                resolutions.append("720p")
            case 1080:
                resolutions.append("1080i")
                resolutions.append("1080p")
            case 2160:
                resolutions.append("2160p")
            # case _:  # The default case
            #     resolutions.append("Other")

        return resolutions

    def get_search_url(self, category, tracker_types, tracker_source, tmdb_id=None, imdb_id=None, season_number=None):
        # build the search url
        category_id = self.get_cat_id(category)
        url = f"{self.URL}/api/torrents/{self.api_key}?action=search&categories={category_id}"
        if tmdb_id:
            url += f"&tmdb_id={category.lower()}%2F{tmdb_id}"
        if imdb_id:
            url += f"&imdb_id={imdb_id}"
        if len(tracker_source) > 0 and "Remux" not in tracker_types:
            url += f"&sources={tracker_source}"
        if len(tracker_types) > 0:
            if "Remux" not in tracker_types and len(tracker_types) == 1:
                url += f"&types="
                for index, item in enumerate(tracker_types):
                    if index > 0:
                        url += ","
                    url += f"{item.replace(" ", "%20")}"
            else:
                url += f"&types={tracker_types.replace(" ", "%20")}"
        if season_number:
            url += f"&search=S{"0" if season_number < 10 else ""}{season_number}"
        return url

    async def search_movie(self, session, movie, indented):
        tmdb_id = movie["tmdbId"]

        # update banned groups if tracker supports it
        if len(self.banned_groups) == 0:
            logger.error(f"\n[{self.__class__.__name__}] Banned groups empty. Skipping checks.")
        # check if local group is banned on tracker
        if "releaseGroup" in movie["movieFile"]:
            release_group = movie["movieFile"]["releaseGroup"]
            if self.is_group_banned(release_group):
                return

        quality_info = movie.get("movieFile").get("quality").get("quality")
        source = quality_info.get("source")
        modifier = quality_info.get("modifier")
        resolution = quality_info.get("resolution")
        tracker_source = self.get_source_id(source)
        if tracker_source is None or "DVD" in tracker_source.upper():
            release_info = guessit(movie.get("movieFile").get("relativePath"))
            source = release_info.get("source")
            modifier = release_info.get("other")
            if resolution == 0 and "screen_size" in release_info:
                resolution = release_info.get("screen_size")
                resolution = int("".join(char for char in resolution if char.isdigit()))  # Removes any character that is NOT a digit
        modifier = utils.get_video_type(source, modifier)
        if modifier.lower() != "remux" and resolution != 0:
            tracker_types = self.get_video_resolutions(resolution)
        else:
            tracker_types = self.get_types(source, modifier)
            # resolution = tracker_types
            tracker_source = tracker_types

        # build the search url
        log_prefix = f"{"\t" if indented else ""}{self.__class__.__name__ if indented else ""} [{resolution} {tracker_source}]... "
        search_url = self.get_search_url("MOVIE", tracker_types, tracker_source, tmdb_id)
        # print(f"url: {url}")
        async with session.post(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
            response.raise_for_status()  # Raise an exception if the request failed
            res = await response.json()
            torrents = res["results"]

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
                release_info = guessit(torrents[0].get("name"))
                if "release_group" in release_info \
                        and release_info["release_group"].casefold() in map(str.casefold, self.banned_groups):
                    title = movie["title"]
                    logger.info(
                        f"{log_prefix}[Trumpable: Banned Group] for {title} [{resolution} {tracker_source} {release_info['release_group']}]"
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

    async def search_show(self, session, show, season_number, episode, indented):
        # update banned groups if tracker supports it
        if len(self.banned_groups) == 0:
            try:
                banned_groups = await self.fetch_banned_groups(session)
                self.banned_groups = banned_groups
            except Exception as e:
                logger.error(f"\n[{self.__class__.__name__}] Error fetching banned groups failed: {str(e)}")
        # check if local group is banned on tracker
        if "releaseGroup" in episode["episodeFile"]:
            release_group = episode["episodeFile"]["releaseGroup"]
            if self.is_group_banned(release_group):
                return

        quality_info = episode.get("episodeFile").get("quality").get("quality")
        source = quality_info.get("source")
        modifier = quality_info.get("modifier")
        resolution = quality_info.get("resolution")
        tracker_source = self.get_source_id(source)
        if tracker_source is None or "DVD" in tracker_source.upper():
            release_info = guessit(episode.get("episodeFile").get("relativePath"))
            source = release_info.get("source")
            if modifier is None:
                modifier = release_info.get("other")
            if resolution == 0 and "screen_size" in release_info:
                resolution = release_info.get("screen_size")
                resolution = int("".join(char for char in resolution if char.isdigit()))  # Removes any character that is NOT a digit
        modifier = utils.get_video_type(source, modifier)
        if modifier.lower() != "remux" and resolution != 0:
            tracker_types = self.get_video_resolutions(resolution)
        else:
            tracker_types = self.get_types(source, modifier)
            # resolution = tracker_types
            tracker_source = tracker_types

        # build the search url
        tmdb_id = show["tmdbId"]
        imdb_id = show["imdbId"]
        log_prefix = f"\t"
        if indented:
            log_prefix += f"[{self.__class__.__name__ if indented else ""}]"
        log_prefix += " Season {season_number}... "
        search_url = self.get_search_url("TV", tracker_types, tracker_source, tmdb_id=tmdb_id, imdb_id=imdb_id,
                                         season_number=season_number)
        # no season number in search. have to filter the results
        try:
            async with session.post(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
                response.raise_for_status()  # Raise an exception if the request failed
                res = await response.json()
                torrents = res["results"]

                if len(torrents) == 0:
                    logger.info(
                        f"{log_prefix}not found"
                    )
                    filepath = os.path.dirname(episode["episodeFile"]["path"])
                    self.sonarr_not_found_file.write(f"{filepath}\n")
                else:
                    release_info = guessit(torrents[0].get("name"))
                    if "release_group" in release_info \
                            and release_info["release_group"].casefold() in map(str.casefold, self.banned_groups):
                        logger.info(
                            f"[Trumpable: Banned] group for [{resolution} {source}]"
                        )
                        filepath = os.path.dirname(episode["episodeFile"]["path"])
                        if filepath:
                            self.sonarr_not_found_file.writerow([filepath, 'Banned group'])
                    else:
                        logger.info(
                            f"{log_prefix}already exists"
                        )
        except Exception as e:
            if "429" in str(e):
                logger.warning(f"Rate limit exceeded while checking. Will retry.")
            else:
                logger.error(f"Error: {str(e)}")
                self.sonarr_not_found_file.write(f"Error: {str(e)}\n")

        logger.debug(
            f"\t[{self.__class__.__name__}] search url: {search_url}"
        )
