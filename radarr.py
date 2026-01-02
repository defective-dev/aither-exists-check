import asyncio
import csv
import logging
import os
from os.path import basename
from urllib.parse import urljoin

from guessit import guessit

from AppConfig import AppConfig

logger = logging.getLogger("customLogger")


class Radarr:
    def __init__(self, app_configs: AppConfig):
        self.metadata_file = None
        self.metadata_writer = None
        self.app_configs = app_configs

        # create log file and headers
        if app_configs.skip_search or app_configs.skip_search_all:
            self.setup_metadata_log()
        pass

    def setup_metadata_log(self):
        log_path = self.app_configs.log_files.get("output_path")
        os.makedirs(log_path, exist_ok=True)

        csv_meta_headers = [
            "file",
            "file resolution",
            "file source",
            "file type",
            "radarr quality",
            "radarr resolution",
            "radarr source",
            "radarr modifier",
            "radarr_url",
            "mediainfo audioBitrate",
            "mediainfo audioCodec",
            "mediainfo audioChannels",
            "mediainfo audioStreamCount",
            "mediainfo audioStreamLangs",
            "mediainfo resolution",
            "mediainfo videoBitrate",
            "mediainfo videoCodec",
            "mediainfo videoBitDepth",
            "mediainfo videoFps",
            "mediainfo videoDynamicRange",
            "mediainfo videoDynamicRangeType",
            "mediainfo scanType",
            "mediainfo runTime",
            "mediainfo subtitles",
            "issues",
        ]

        for tracker in self.app_configs.trackers:
            csv_meta_headers.append(f"{tracker.__class__.__name__} resolution")
            csv_meta_headers.append(f"{tracker.__class__.__name__} type")
            csv_meta_headers.append(f"{tracker.__class__.__name__} issues")

        radarr_meta_file = os.path.join(
            log_path, self.app_configs.log_files["metadata_radarr"]
        )
        self.metadata_file = open(
            radarr_meta_file, "w", encoding="utf-8", buffering=100
        )
        self.metadata_writer = csv.DictWriter(
            self.metadata_file,
            fieldnames=csv_meta_headers,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
        )
        self.metadata_writer.writeheader()

    def get_metadata_log_row(self, movie):

        radarr_movie_url = urljoin(
            urljoin(self.app_configs.radarr.get("url"), "movie/"), str(movie["tmdbId"])
        )

        file_info = guessit(movie.get("movieFile").get("relativePath"))
        file_source = file_info.get("source", "")
        file_type = file_info.get("other", "")
        file_res = file_info.get("screen_size", "")

        media_info = movie.get("movieFile", {}).get("mediaInfo", {})
        quality_info = movie.get("movieFile", {}).get("quality", {}).get("quality", {})

        log_row = {
            "file": basename(movie.get("movieFile").get("relativePath")),
            "file resolution": file_res,
            "file source": file_source,
            "file type": file_type,
            "radarr quality": quality_info.get("name", ""),
            "radarr resolution": quality_info.get("resolution", None),
            "radarr source": quality_info.get("source"),
            "radarr modifier": quality_info.get("modifier", ""),
            "radarr_url": radarr_movie_url,
            "mediainfo audioBitrate": media_info.get("audioBitrate", None),
            "mediainfo audioCodec": media_info.get("audioCodec", None),
            "mediainfo audioChannels": media_info.get("audioChannels", None),
            "mediainfo audioStreamCount": media_info.get("audioStreamCount", None),
            "mediainfo audioStreamLangs": media_info.get("audioLanguages", None),
            "mediainfo resolution": media_info.get("resolution", None),
            "mediainfo videoBitrate": media_info.get("videoBitrate", None),
            "mediainfo videoCodec": media_info.get("videoCodec", ""),
            "mediainfo videoBitDepth": media_info.get("videoBitDepth", None),
            "mediainfo videoFps": media_info.get("videoFps", None),
            "mediainfo videoDynamicRange": media_info.get("videoDynamicRange", ""),
            "mediainfo videoDynamicRangeType": media_info.get(
                "videoDynamicRangeType", ""
            ),
            "mediainfo scanType": media_info.get("scanType", None),
            "mediainfo runTime": media_info.get("runTime", None),
            "mediainfo subtitles": media_info.get("subtitles", None),
        }
        return log_row

    def get_metadata_status(
        self,
        file_type,
        file_source,
        radarr_source,
    ):
        # status checks
        status = []

        # media type checks
        if not file_type:
            status.append("FILE_TYPE_MISSING")

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

    # might need move this to tracker class
    @staticmethod
    def get_radarr_resolution(movie):
        # get resolution from radarr if missing try pull from media info
        try:
            movie_resolution = (
                movie.get("movieFile", {})
                .get("quality", {})
                .get("quality", {})
                .get("resolution", None)
            )
            # if no resolution like with dvd quality. try parse from mediainfo instead
            if not movie_resolution:
                mediainfo_resolution = (
                    movie.get("movieFile", {})
                    .get("mediaInfo", {})
                    .get("resolution", None)
                )
                if mediainfo_resolution:
                    width, height = mediainfo_resolution.split("x")
                    movie_resolution = height
        except KeyError:
            movie_resolution = None
        return movie_resolution

    # Function to process each movie
    async def process_movie(self, session, movie):
        # add newline to put list below title if multiple checks
        # and tab indent sub items
        indented = False
        if len(self.app_configs.trackers) > 1:
            logger.info("")
            indented = True

        # display missing release group warning. So only once and not duplicated per tracker.
        if (
            "releaseGroup" in movie["movieFile"]
            and not movie["movieFile"]["releaseGroup"].strip()
        ):
            logger.warning(
                f"{'\t' if indented else ''}Warning: Release group missing. Banned checks will be skipped."
            )

        metadata_log_row = None
        if self.app_configs.skip_search or self.app_configs.skip_search_all:
            metadata_log_row = self.get_metadata_log_row(movie)

        tasks = [
            tracker.search_movie(session, movie, indented, metadata_log_row)
            for tracker in self.app_configs.trackers
        ]
        await asyncio.gather(*tasks)

        if self.app_configs.skip_search_all:
            release_info = guessit(movie.get("movieFile").get("relativePath"))
            file_source = release_info.get("source", "")
            file_type = release_info.get("other", "")
            quality_info = (
                movie.get("movieFile", {}).get("quality", {}).get("quality", {})
            )
            radarr_source = quality_info.get("source", None)
            metadata_issues = self.get_metadata_status(
                file_type, file_source, radarr_source
            )
            metadata_log_row["issues"] = ",".join(metadata_issues)
            self.metadata_writer.writerow(metadata_log_row)

    # Function to get all movies from Radarr
    async def get_all_movies(self, session):
        radarr_url = (
            self.app_configs.radarr["url"] + self.app_configs.radarr["api_suffix"]
        )
        async with session.get(
            radarr_url, headers={"X-Api-Key": self.app_configs.radarr["api_key"]}
        ) as response:
            response.raise_for_status()  # Ensure we handle request errors properly
            movies = await response.json()
            return movies
