import logging
import os

from guessit import guessit

import utils
from AppConfig import AppConfig
from radarr import Radarr
from trackers.TrackerBase import TrackerBase, PTracker

logger = logging.getLogger("customLogger")


class AITHER(TrackerBase, PTracker):
    def __init__(self, app_configs: AppConfig):
        super().__init__()
        self.URL = "https://aither.cc"
        trkr = next(
            (
                sub
                for sub in app_configs.tracker_configs
                if sub["name"] == __class__.__name__
            ),
            None,
        )
        if trkr:
            self.api_key = trkr.get("api_key")
        self.app_configs = app_configs
        self.setup_log_files(app_configs)
        pass

    def get_cat_id(self, category_name):
        category_id = {
            "MOVIE": "1",
            "TV": "2",
        }.get(category_name, "0")
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
            "8640p": 10,
        }

        if resolution is not None:
            # Return the ID for the given resolution
            return resolution_mapping.get(
                resolution, 0
            )  # Default to '0' for unknown resolutions
        else:
            return 0

    def get_res_name(self, resolution=None):
        resolution_mapping = {
            1: "4320",
            2: "2160",
            3: "1080",
            4: "1080p",
            5: "720",
            6: "576",
            7: "576p",
            8: "480",
            9: "480p",
            10: "8640p",
        }

        if resolution is not None:
            # Return the ID for the given resolution
            return resolution_mapping.get(
                resolution, "unknown"
            )  # Default to '0' for unknown resolutions
        else:
            return "unknown"

    def get_video_resolutions(self, video_resolution):
        resolutions = []

        if video_resolution not in ["1080", "1080p", "576", "576p", "480", "480p"]:
            resolution_id = self.get_res_id(video_resolution)
            if resolution_id != 0:
                resolutions.append(resolution_id)
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

    def get_search_url(
        self,
        category,
        video_resolutions,
        video_type,
        tmdb_id=None,
        tvdb_id=None,
        season_number=None,
    ):
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

    def get_metadata_status(
        self,
        video_resolutions,
        tracker_type_id,
        tracker_type,
        file_type,
        file_source,
        radarr_source,
    ):
        # status checks
        status = []

        # check if we found map between source and tracker for resolution and type
        # check media info resolution vs quality resolution
        if len(video_resolutions) == 0 or video_resolutions[0] == 0:
            status.append(
                "TRACKER_RESOLUTION_NOT_FOUND"
            )  # make this less generic. split to file and radarr
        # mostly for SD types like DVD check to make sure remuxes, dvdrips, encodes don't get mixed up
        if not tracker_type_id:  # make this less generic. split to file and radarr
            status.append("TRACKER_TYPE_NOT_FOUND")

        # media type checks
        if not file_type:
            status.append("FILE_TYPE_MISSING")
        if tracker_type.lower() == "remux":
            if isinstance(file_type, str) and "remux" not in file_type.lower():
                status.append("FILE_RADARR_TYPE_MISMATCH")
            if isinstance(file_type, list) and "remux" not in [
                item.lower() for item in file_type
            ]:
                status.append("FILE_RADARR_TYPE_MISMATCH")
        if tracker_type.lower() == "encode":
            if isinstance(file_type, str) and "remux" in file_type.lower():
                status.append("FILE_RADARR_TYPE_MISMATCH")
            if isinstance(file_type, list) and "remux" in [
                item.lower() for item in file_type
            ]:
                status.append("FILE_RADARR_TYPE_MISMATCH")

        # media source checks
        if not file_source:
            status.append("FILE_SOURCE_MISSING")
        if (
            isinstance(file_source, str)
            and file_source.lower() == "dvd"
            and radarr_source.lower() != "dvd"
        ):
            status.append("FILE_RADARR_SOURCE_MISMATCH")
        if (
            isinstance(file_source, list)
            and "dvd" in [item.lower() for item in file_source]
            and radarr_source.lower() != "dvd"
        ):
            status.append("FILE_RADARR_SOURCE_MISMATCH")

        return status

    async def search_movie(self, session, movie, indented, metadata_log_row=None):
        # update banned groups if tracker supports it
        if len(self.banned_groups) == 0:
            try:
                banned_groups = await self.fetch_banned_groups(session)
                self.banned_groups = banned_groups
            except Exception as e:
                logger.error(
                    f"\n[{self.__class__.__name__}]Error fetching banned groups failed: {str(e)}"
                )

        tmdb_id = movie["tmdbId"]
        quality_info = movie.get("movieFile", {}).get("quality", {}).get("quality", {})
        radarr_source = quality_info.get("source", None)
        radarr_modifier = quality_info.get("modifier", None)
        radarr_resolution = str(Radarr.get_radarr_resolution(movie))
        radarr_quality_name = quality_info.get("name", "")
        if (
            radarr_quality_name.lower() == "dvd-r"
            or radarr_quality_name.lower() == "br-disk"
        ):
            logger.info(
                f"SKIPPED. Full disc: {radarr_quality_name} currently unsupported"
            )
            return

        # map the radarr or file resolution to tracker resolution
        video_resolutions = self.get_video_resolutions(radarr_resolution)
        # if blank try to parse resolution from file name. mainly for dvd675
        filename_resolution = None
        if len(video_resolutions) == 0 or video_resolutions[0] == 0:
            release_info = guessit(movie.get("movieFile").get("relativePath"))
            if "screen_size" in release_info:
                filename_resolution = release_info["screen_size"]
                video_resolutions = self.get_video_resolutions(filename_resolution)
        # source is dvd set NTSC & PAL as search resolutions.
        if radarr_source == "dvd":
            video_resolutions = self.get_video_resolutions("480")
            video_resolutions.extend(self.get_video_resolutions("576"))
        # DEBUG: check missing values. usually some xvid BS
        # if len(video_resolutions) == 0 or video_resolutions[0] == 0:
        #     logger.warning("no resolution found. ")

        # map the radarr or file video type to tracker video type
        # if source is tv map to sdtv or hdtv
        if radarr_source == "tv":
            if int(radarr_resolution) > 576:
                radarr_source = "HDTV"
            else:
                radarr_source = "SDTV"
        tracker_type = utils.get_video_type(radarr_source, radarr_modifier)
        file_video_type = None
        if not tracker_type or tracker_type == "OTHER":
            # if radarr_modifier and radarr_source == "dvd":
            release_info = guessit(movie.get("movieFile").get("relativePath"))
            if "source" in release_info:
                file_video_type = release_info.get("source")
                tracker_type = utils.get_video_type(radarr_source, file_video_type)
            if "other" in release_info:
                file_video_type = release_info.get("other")
                tracker_type = utils.get_video_type(radarr_source, file_video_type)
        tracker_type_id = None
        if tracker_type != "OTHER":
            tracker_type_id = self.get_type_id(tracker_type.upper())
        # DEBUG: check missing values. if unknown, or cam in radarr. should fix the quality there then search again.
        # if not tracker_type_id:
        #     logger.warning("no video type found. ")

        # build the search url
        log_prefix = ""
        if indented:
            log_prefix += f"\t{self.__class__.__name__}: "
        log_prefix += f"[{radarr_resolution} {tracker_type if radarr_source == 'SDTV' or tracker_type_id else 'UNKNOWN'}]... "
        # only search for ia and resolution. Do type check below so can check for trumps.
        # mainly sd: dvd remux over encode.
        search_url = self.get_search_url("MOVIE", video_resolutions, [], tmdb_id)

        # check if local group is banned on tracker
        if (
            "releaseGroup" in movie["movieFile"]
            and movie["movieFile"]["releaseGroup"].strip()
        ):
            release_group = movie["movieFile"]["releaseGroup"]
            if self.is_group_banned(release_group, log_prefix):
                return

        if not self.app_configs.skip_search and not self.app_configs.skip_search_all:
            try:
                # async with session.get(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
                async with session.get(
                    search_url, headers={"Authorization": f"Bearer {self.api_key}"}
                ) as response:
                    res = await response.json()
                    torrents = res["data"]

                    if len(torrents) == 0:
                        try:
                            movie_file = movie["movieFile"]["path"]
                            if movie_file:
                                logger.info(f"{log_prefix}not found")
                                self.radarr_not_found_file.write(f"{movie_file}\n")
                            else:
                                logger.info(f"{log_prefix}not found. (No media file)")
                        except KeyError:
                            logger.info(f"{log_prefix}not found. (No media file)")
                    else:
                        release_info = guessit(
                            torrents[0].get("attributes").get("name")
                        )
                        if "release_group" in release_info and release_info[
                            "release_group"
                        ].casefold() in map(str.casefold, self.banned_groups):
                            title = movie["title"]
                            logger.info(
                                f"{log_prefix} Trumpable: Banned Group: {release_info['release_group']}"
                            )
                            movie_file = movie["movieFile"]["path"]
                            if movie_file:
                                self.radarr_trump_writer.writerow(
                                    {"file": movie_file, "reason": "Banned group"}
                                )
                        else:
                            logger.info(f"{log_prefix}already exists")
            except Exception as e:
                if "429" in str(e):
                    logger.error(f"{log_prefix}Rate limit exceeded.")
                else:
                    logger.error(f"{log_prefix}Error: {str(e)}")
                    self.radarr_not_found_file.write(f"{title} - Error: {str(e)}\n")
        else:
            logger.debug(f"{log_prefix}debugging search skipped")
            if self.app_configs.skip_search or self.app_configs.skip_search_all:
                # self.get_metadata_log_row(movie, video_resolutions, tracker_type_id, tracker_type)
                release_info = guessit(movie.get("movieFile").get("relativePath"))
                file_source = release_info.get("source", "")
                file_type = release_info.get("other", "")
                metadata_status = self.get_metadata_status(
                    video_resolutions,
                    tracker_type_id,
                    tracker_type,
                    file_type,
                    file_source,
                    radarr_source,
                )
                tracker_res = ""
                for index, resolution in enumerate(video_resolutions):
                    if index > 0:
                        tracker_res += ","
                    tracker_res += f"{self.get_res_name(resolution)}"

                metadata_log_row[f"{__class__.__name__} resolution"] = tracker_res
                metadata_log_row[f"{__class__.__name__} type"] = tracker_type
                metadata_log_row[f"{__class__.__name__} issues"] = ",".join(
                    metadata_status
                )

        # if skip search it dumps to file, no need for extra debug logs
        if not self.app_configs.skip_search and not self.app_configs.skip_search_all:
            # build debug statement for search parameters
            parm_log = (
                f"\t[{self.__class__.__name__}] Resolution: radarr={radarr_resolution}"
            )
            if filename_resolution:
                parm_log += f", file={filename_resolution}"
            if len(video_resolutions) > 0:
                parm_log += ", trackerIds="
                for resolution in video_resolutions:
                    parm_log += f"[{resolution}={self.get_res_name(resolution)}]"
            logger.debug(parm_log)

            parm_log = f"\t[{self.__class__.__name__}] Video Type: radarr={radarr_source}-{radarr_modifier}"
            if file_video_type:
                parm_log += f", file={file_video_type}"
            parm_log += f", tracker=[{tracker_type_id}={tracker_type}]"
            logger.debug(parm_log)

        # log tracker search string
        logger.debug(f"\t[{self.__class__.__name__}] search url: {search_url}")

    async def search_show(self, session, show, season_number, episode, indented):
        # update banned groups if tracker supports it
        if len(self.banned_groups) == 0:
            try:
                banned_groups = await self.fetch_banned_groups(session)
                self.banned_groups = banned_groups
            except Exception as e:
                logger.error(
                    f"\n[{self.__class__.__name__}]\nError fetching banned groups failed: {str(e)}"
                )

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
        search_url = self.get_search_url(
            "TV",
            video_resolutions,
            tracker_type,
            tvdb_id=tvdb_id,
            season_number=season_number,
        )
        log_prefix = f"\t"
        if indented:
            log_prefix += f"[{self.__class__.__name__}] "
        log_prefix += f"Season {'{:02d}'.format(season_number)} [{media_resolution} {video_type}]... "

        # check if local group is banned on tracker
        if (
            "releaseGroup" in episode["episodeFile"]
            and episode["episodeFile"]["releaseGroup"].strip()
        ):
            release_group = episode["episodeFile"]["releaseGroup"]
            if self.is_group_banned(release_group, log_prefix):
                return

        try:
            # async with session.get(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
            async with session.get(
                search_url, headers={"Authorization": f"Bearer {self.api_key}"}
            ) as response:
                res = await response.json()
                torrents = res["data"]

                if len(torrents) == 0:
                    logger.info(f"{log_prefix}not found")
                    filepath = os.path.dirname(episode["episodeFile"]["path"])
                    self.sonarr_not_found_file.write(f"{filepath}\n")
                else:
                    release_info = guessit(torrents[0].get("attributes").get("name"))
                    if "release_group" in release_info and release_info[
                        "release_group"
                    ].casefold() in map(str.casefold, self.banned_groups):
                        logger.info(
                            f"{log_prefix} Trumpable: Banned Group: {release_info['release_group']}"
                        )
                        filepath = os.path.dirname(episode["episodeFile"]["path"])
                        if filepath:
                            self.sonarr_trump_writer.writerow(
                                {"file": filepath, "reason": "Banned group"}
                            )
                    else:
                        logger.info(f"{log_prefix}already exists")
        except Exception as e:
            if "429" in str(e):
                logger.error(f"{log_prefix}Rate limit exceeded while checking.")
            else:
                logger.error(f"{log_prefix}Error: {str(e)}")
                self.sonarr_not_found_file.write(f"Error: {str(e)}\n")

        logger.debug(f"\t[{self.__class__.__name__}] search url: {search_url}")

    # pull banned groups from aither api
    async def fetch_banned_groups(self, session):
        # logger.info("Fetching banned groups")

        banned_groups = []
        url = f"{self.URL}/api/blacklists/releasegroups?api_token={self.api_key}"
        try:
            # async with session.get(search_url, headers={"Authorization": f"Bearer {self.api_key}"}) as response:
            async with session.get(
                url, headers={"Authorization": f"Bearer {self.api_key}"}
            ) as response:
                res = await response.json()
                groups = res["data"]
                banned_groups = [d["name"] for d in groups]
        except Exception as e:
            if "429" in str(e):
                logger.warning(f"Rate limit exceeded while checking.")
            else:
                logger.error(f"Error: {str(e)}")
        return banned_groups
