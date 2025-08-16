import apiKey
import requests
import time
import argparse
from guessit import guessit
import logging
import os

# Just to sameline the logs while logging to file also
class NoNewlineStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            if record.levelno == logging.INFO and (msg.endswith("... ") or msg.endswith(" ")):
                stream.write(msg)
            else:
                stream.write(msg + "\n")
            self.flush()
        except Exception:
            self.handleError(record)


# Configurable constants
AITHER_URL = "https://aither.cc"
RADARR_API_SUFFIX = "/api/v3/movie"
SONARR_API_SUFFIX = "/api/v3/series"
NOT_FOUND_FILE_RADARR = "not_found_radarr.txt"
NOT_FOUND_FILE_SONARR = "not_found_sonarr.txt"

# LOGIC CONSTANT - DO NOT TWEAK !!!
# changing this may break resolution mapping for dvd in search_movie
RESOLUTION_MAP = {
    "4320": 1,
    "2160": 2,
    "1080": 3,
    "1080p": 4,
    "720": 5,
    "576": 6,
    "576p": 7,
    "480": 8,
    "480p": 9,
}

CATEGORY_MAP = {
    "movie": 1,
    "tv": 2
}

TYPE_MAP = {
    "FULL DISC": 1,
    "REMUX": 2,
    "ENCODE": 3,
    "WEB-DL": 4,
    "WEBRIP": 5,
    "HDTV": 6,
    "OTHER": 7,
    "MOVIE PACK": 10,
}

# Setup logging
logger = logging.getLogger("customLogger")
logger.setLevel(logging.INFO)

# Console handler with a simpler format
console_handler = NoNewlineStreamHandler()
console_formatter = logging.Formatter("%(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler with detailed format
# file_handler = logging.FileHandler("script.log")
# file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
# file_handler.setFormatter(file_formatter)
# logger.addHandler(file_handler)


# Setup function to prompt user for missing API keys and URLs if critical for the selected mode(s)
def setup(radarr_needed, sonarr_needed):
    missing = []

    if not apiKey.aither_key:
        missing.append("Aither API key")
        apiKey.aither_key = input("Enter your Aither API key: ")

    if radarr_needed:
        if not apiKey.radarr_key:
            missing.append("Radarr API key")
            apiKey.radarr_key = input("Enter your Radarr API key: ")
        if not apiKey.radarr_url:
            missing.append("Radarr URL")
            apiKey.radarr_url = input(
                "Enter your Radarr URL (e.g., http://RADARR_URL:RADARR_PORT): "
            )

    if sonarr_needed:
        if not apiKey.sonarr_key:
            missing.append("Sonarr API key")
            apiKey.sonarr_key = input("Enter your Sonarr API key: ")
        if not apiKey.sonarr_url:
            missing.append("Sonarr URL")
            apiKey.sonarr_url = input(
                "Enter your Sonarr URL (e.g., http://SONARR_URL:SONARR_PORT): "
            )

    if missing:
        with open("apiKey.py", "w") as f:
            f.write(f'aither_key = "{apiKey.aither_key}"\n')
            f.write(f'radarr_key = "{apiKey.radarr_key}"\n')
            f.write(f'sonarr_key = "{apiKey.sonarr_key}"\n')
            f.write(f'radarr_url = "{apiKey.radarr_url}"\n')
            f.write(f'sonarr_url = "{apiKey.sonarr_url}"\n')

    # Alert the user about missing non-critical variables
    if not radarr_needed and (not apiKey.radarr_key or not apiKey.radarr_url):
        logger.warning(
            "Radarr API key or URL is missing. Radarr functionality will be limited."
        )
    if not sonarr_needed and (not apiKey.sonarr_key or not apiKey.sonarr_url):
        logger.warning(
            "Sonarr API key or URL is missing. Sonarr functionality will be limited."
        )


# Function to get all movies from Radarr
def get_all_movies(session):
    radarr_url = apiKey.radarr_url + RADARR_API_SUFFIX
    response = session.get(radarr_url, headers={"X-Api-Key": apiKey.radarr_key})
    response.raise_for_status()  # Ensure we handle request errors properly
    movies = response.json()
    movies = sorted(movies, key=lambda x: x['title'])
    return movies


# Function to get all shows from Sonarr
def get_all_shows(session):
    sonarr_url = apiKey.sonarr_url + SONARR_API_SUFFIX
    response = session.get(sonarr_url, headers={"X-Api-Key": apiKey.sonarr_key})
    response.raise_for_status()  # Ensure we handle request errors properly
    shows = response.json()
    shows = sorted(shows, key=lambda x: x['title'])
    return shows


# Function to search for a movie in Aither using its TMDB ID + resolution if found
def search_movie(session, movie, video_resolution, video_type):
    tmdb_id = movie["tmdbId"]

    # build the search url
    url = f"{AITHER_URL}/api/torrents/filter?categories[0]={CATEGORY_MAP['movie']}&tmdbId={tmdb_id}"
    if video_resolution:
        for index, resolution in enumerate(video_resolution):
            url += f"&resolutions[{index}]={resolution}"
    if video_type:
        url += f"&types[0]={video_type}"
    
    while True:
        response = session.get(url, headers={"Authorization": f"Bearer {apiKey.aither_key}"})
        if response.status_code == 429:
            logger.warning(f"Rate limit exceeded.")
        else:
            response.raise_for_status()  # Raise an exception if the request failed
            torrents = response.json()["data"]
            return torrents


# Function to search for a show in Aither using its TVDB ID
def search_show(session, tvdb_id, season_number, video_resolution, video_type):
    url = f"{AITHER_URL}/api/torrents/filter?tvdbId={tvdb_id}&categories[0]={CATEGORY_MAP['tv']}"
    if season_number:
        url += f"&seasonNumber={season_number}"
    if video_resolution:
        for index, resolution in enumerate(video_resolution):
            url += f"&resolutions[{index}]={resolution}"
    if video_type:
        url += f"&types[0]={video_type}"

    # print(f"url: {url}")
    while True:
        response = session.get(url, headers={"Authorization": f"Bearer {apiKey.aither_key}"})
        if response.status_code == 429:
            logger.warning(f"Rate limit exceeded.")
        else:
            response.raise_for_status()  # Raise an exception if the request failed
            torrents = response.json()["data"]
            return torrents

def get_movie_resolution(movie):
    # get resolution from radarr if missing try pull from media info
    try:
        movie_resolution = movie.get("movieFile").get("quality").get("quality").get("resolution")
        # if no resolution like with dvd quality. try parse from mediainfo instead
        if not movie_resolution:
            mediainfo_resolution = movie.get("movieFile").get("mediaInfo").get("resolution")
            width, height = mediainfo_resolution.split("x")
            movie_resolution = height
    except KeyError:
        movie_resolution = None
    return movie_resolution

def get_video_type(source, modifier):
    if not isinstance(source, list):
        source = (source or '').lower()
    else:
        source = source[0].lower()
    if not isinstance(modifier, list):
        modifier = (modifier or '').lower()
    else:
        index_element = next((i for i, v in enumerate(modifier) if v.lower() == "remux"), None)
        if index_element != None:
            modifier = modifier[index_element].lower()
        else:
            index_element = next((i for i, v in enumerate(modifier) if v.lower() == "rip"), None)
            if index_element != None:
                modifier = modifier[index_element].lower()

    if source == 'bluray':
        if modifier == 'remux':
            return 'REMUX'
        elif modifier == 'full':
            return 'FULL DISC'
        else:
            return 'ENCODE'
    elif source == 'dvd':
        if modifier == 'remux':
            return 'REMUX'
        elif modifier == 'full':
            return 'FULL DISC'
        elif modifier == 'Rip':
            return 'ENCODE'
        else:
            return 'ENCODE'
    elif source in ['webdl', 'web-dl']:
        return 'WEB-DL'
    elif source in ['webrip', 'web-rip']:
        return 'WEBRIP'
    elif source == 'hdtv':
        return 'HDTV'
    # sonarr types
    elif source == "web" and "webdl" in modifier:
        return 'WEB-DL'
    elif "remux" in modifier:
        return 'REMUX'
    elif "hdtv" in modifier:
        return 'HDTV'
    elif "bluray" in modifier and "remux" not in modifier:
        return 'ENCODE'
    else:
        return 'OTHER'


# Function to process each movie
def process_movie(session, movie, not_found_file, banned_groups):
    title = movie["title"]

    # verify radarr actually has a file entry if not skip check and save api call
    if not "movieFile" in movie:
        logger.info(
            f"[Skipped: local]. No file found in radarr for {title}"
        )
        return

    # skip check if group is banned.
    banned_names = [d['name'] for d in banned_groups]
    if "releaseGroup" in movie["movieFile"] and \
            movie["movieFile"]["releaseGroup"].casefold() in map(str.casefold, banned_names):
        logger.info(
            f"[Banned: local] group ({movie['movieFile']['releaseGroup']}) for {title}"
        )
        return

    try:
        quality_info = movie.get("movieFile").get("quality").get("quality")
        source = quality_info.get("source")
        modifier = quality_info.get("modifier")
        if modifier == "none" and source == "dvd":
            release_info = guessit(movie.get("movieFile").get("relativePath"))
            modifier = release_info.get("other")
        video_type = get_video_type(source, modifier)
        aither_type = TYPE_MAP.get(video_type.upper())
        aither_type_id = None
        # if other don't include video type in search filters only resolution
        if aither_type != "OTHER":
            aither_type_id = TYPE_MAP.get(aither_type.upper())
        video_resolution = get_movie_resolution(movie)
        aither_resolutions = get_aither_resolutions(str(video_resolution))
        torrents = search_movie(session, movie, aither_resolutions, aither_type_id)
    except Exception as e:
        if "429" in str(e):
            logger.warning(f"Rate limit exceeded while checking {title}.")
        else:
            logger.error(f"Error: {str(e)}")
            not_found_file.write(f"{title} - Error: {str(e)}\n")
    else:
        if len(torrents) == 0:
            try:
                movie_file = movie["movieFile"]["path"]
                if movie_file:
                    logger.info(
                        f"[{video_resolution} {video_type}] not found on AITHER"
                    )
                    not_found_file.write(f"{movie_file}\n")
                else:
                    logger.info(
                        f"[{video_resolution} {video_type}] not found on AITHER (No media file)"
                    )
            except KeyError:
                logger.info(
                    f"[{video_resolution} {video_type}] not found on AITHER (No media file)"
                )
        else:
            release_info = guessit(torrents[0].get("attributes").get("name"))
            if "release_group" in release_info \
                    and release_info["release_group"].casefold() in map(str.casefold, banned_names):
                logger.info(
                    f"[Trumpable: Banned] group for {title} [{video_resolution} {video_type} {release_info['release_group']}] on AITHER"
                )
            else :
                logger.info(
                     f"[{video_resolution} {video_type}] already exists on AITHER"
                )

def get_aither_resolutions(video_resolution):
    resolutions = []

    if video_resolution not in ["1080", "1080p", "576", "576p", "480", "480p"]:
        resolutions.append(RESOLUTION_MAP.get(video_resolution))
    else:
        if video_resolution == "1080" or  video_resolution == "1080p":
            resolutions.append(RESOLUTION_MAP.get("1080"))
            resolutions.append(RESOLUTION_MAP.get("1080p"))

        if video_resolution == "576" or  video_resolution == "576p":
            resolutions.append(RESOLUTION_MAP.get("576"))
            resolutions.append(RESOLUTION_MAP.get("576p"))

        if video_resolution == "480" or  video_resolution == "480p":
            resolutions.append(RESOLUTION_MAP.get("480"))
            resolutions.append(RESOLUTION_MAP.get("480p"))

    return resolutions

def get_season_episodes(session, show,season_number):
    sonarr_url = apiKey.sonarr_url + f"/api/v3/episode?seriesId={show["id"]}&seasonNumber={season_number}&includeSeries=false&includeEpisodeFile=true&includeImages=false"
    response = session.get(sonarr_url, headers={"X-Api-Key": apiKey.sonarr_key})
    response.raise_for_status()  # Ensure we handle request errors properly
    shows = response.json()
    return shows

# Function to process each show
def process_show(session, show, not_found_file, banned_groups, sleep_timer):
    title = show["title"]
    tvdb_id = show["tvdbId"]

    if len(show["seasons"]) > 1:
        logger.info("")  # add newline to put season list below title.

    # loop through shows seasons
    for season in show["seasons"]:
        season_number = season["seasonNumber"]
        # print(f"season: {season_number}")
        logger.info(f"Season {season_number}... ")

        # skip specials and incomplete seasons for now
        if season_number > 0 and season['statistics']["percentOfEpisodes"] == 100:
            # pull episodes for the season
            episodes = get_season_episodes(session, show, season_number)
            # get resolution and type from first ep. assume season pack and all the same
            episode = episodes[0]

            # skip if there are no episode files
            if "episodeFile" in episode:
                # skip check if group is banned.
                banned_names = [d['name'] for d in banned_groups]
                if "releaseGroup" in episode["episodeFile"] and \
                        episode["episodeFile"]["releaseGroup"].casefold() in map(str.casefold, banned_names):
                    logger.info(
                        f"[Banned: local] group ({episode['episodeFile']['releaseGroup']}) for {title}"
                    )
                    return

                quality_info = episode.get("episodeFile").get("quality").get("quality")
                source = quality_info.get("source")
                video_type = quality_info.get("name")
                if video_type.lower() == "dvd" and source.lower() == "dvd":
                    release_info = guessit(episode.get("episodeFile").get("relativePath"))
                    video_type = release_info.get("other")
                # print(f"\nsource: {source}, video_type: {video_type}")
                aither_type = get_video_type(source, video_type)
                aither_type_id = None
                # if other don't include video type in search filters only resolution
                if aither_type != "OTHER":
                    aither_type_id = TYPE_MAP.get(aither_type.upper())
                video_resolution = quality_info.get("resolution")
                aither_resolutions = get_aither_resolutions(str(video_resolution))

                try:
                    torrents = search_show(session, tvdb_id, season_number, aither_resolutions, aither_type_id)
                except Exception as e:
                    if "429" in str(e):
                        logger.warning(f"Rate limit exceeded while checking {title}. Will retry.")
                    else:
                        logger.error(f"Error: {str(e)}")
                        not_found_file.write(f"{title} - Error: {str(e)}\n")
                else:
                    if len(torrents) == 0:
                        logger.info(
                            f"[{video_resolution} {aither_type}] not found on AITHER"
                        )
                        filepath = os.path.dirname(episode["episodeFile"]["path"])
                        not_found_file.write(f"{filepath}\n")
                    else:
                        release_info = guessit(torrents[0].get("attributes").get("name"))
                        if "release_group" in release_info \
                                and release_info["release_group"].casefold() in map(str.casefold, banned_names):
                            logger.info(
                                f"[Trumpable: Banned] group for {title} [{video_resolution} {aither_type}] on AITHER"
                            )
                        else:
                            logger.info(
                                f"[{video_resolution} {aither_type}] already exists on AITHER"
                            )
                time.sleep(sleep_timer)
            else:
                logger.info(f"[{season['statistics']["percentOfEpisodes"]}%] skipping missing file")
        else:
            if season_number == 0:
                logger.info(f"skipping specials")
            else:
                logger.info(f"[{season['statistics']["percentOfEpisodes"]}%] skipping incomplete")

# pull banned groups from aither api
def get_banned_groups(session):
    logger.info("Fetching banned groups")

    url = f"{AITHER_URL}/api/blacklists/releasegroups?api_token={apiKey.aither_key}"
    while True:
        response = session.get(url)
        if response.status_code == 429:
            logger.warning(f"Rate limit exceeded.")
        else:
            response.raise_for_status()  # Raise an exception if the request failed
            groups = response.json()["data"]
            return groups

# Main function to handle both Radarr and Sonarr
def main():
    parser = argparse.ArgumentParser(
        description="Check Radarr or Sonarr library against Aither"
    )
    parser.add_argument("--radarr", action="store_true", help="Check Radarr library")
    parser.add_argument("--sonarr", action="store_true", help="Check Sonarr library")
    parser.add_argument("-o", "--output-path", required=False, help="Output file path")
    parser.add_argument("-s", "--sleep-timer", type=int, default=10, help="Sleep time between calls")

    args = parser.parse_args()

    script_log = "script.log"
    if args.output_path is not None:
        script_log = os.path.join(os.path.expanduser(args.output_path), script_log)
    file_handler = logging.FileHandler(f"{script_log}")
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    radarr_needed = args.radarr or (not args.sonarr and not args.radarr)
    sonarr_needed = args.sonarr or (not args.sonarr and not args.radarr)
    setup(
        radarr_needed=radarr_needed, sonarr_needed=sonarr_needed
    )  # Ensure API keys and URLs are set

    if not args.radarr and not args.sonarr:
        logger.info("No arguments specified. Running both Radarr and Sonarr checks.\n")

    try:
        with requests.Session() as session:
            banned_groups = get_banned_groups(session)
            if args.radarr or (not args.sonarr and not args.radarr):
                if apiKey.radarr_key and apiKey.radarr_url:
                    movies = get_all_movies(session)
                    out_radarr = NOT_FOUND_FILE_RADARR
                    if args.output_path is not None:
                        out_radarr = os.path.join(os.path.expanduser(args.output_path), NOT_FOUND_FILE_RADARR)
                    with open(
                        out_radarr, "w", encoding="utf-8", buffering=1
                    ) as not_found_file:
                        total = len(movies)
                        for index, movie in enumerate(movies):
                            logger.info(f"[{index + 1}/{total}] Checking {movie["title"]}: ")
                            process_movie(session, movie, not_found_file, banned_groups)
                            time.sleep(args.sleep_timer)  # Respectful delay
                else:
                    logger.warning(
                        "Skipping Radarr check: Radarr API key or URL is missing.\n"
                    )

            if args.sonarr or (not args.sonarr and not args.radarr):
                if apiKey.sonarr_key and apiKey.sonarr_url:
                    shows = get_all_shows(session)
                    out_sonarr = NOT_FOUND_FILE_SONARR
                    if args.output_path is not None:
                        out_sonarr = os.path.join(os.path.expanduser(args.output_path), NOT_FOUND_FILE_SONARR)
                    with open(
                        out_sonarr, "w", encoding="utf-8", buffering=1
                    ) as not_found_file:
                        total = len(shows)
                        for index, show in enumerate(shows):
                            logger.info(f"[{index+1}/{total}] Checking {show["title"]}: ")
                            process_show(session, show, not_found_file, banned_groups, args.sleep_timer)
                            time.sleep(args.sleep_timer)  # Respectful delay
                else:
                    logger.warning(
                        "Skipping Sonarr check: Sonarr API key or URL is missing.\n"
                    )
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user. Exiting.\n")


if __name__ == "__main__":
    main()
