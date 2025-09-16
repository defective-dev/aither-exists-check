
from guessit import guessit
import logging
import utils
from config import CONFIG

logger = logging.getLogger("customLogger")


# might need move this to tracker class
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


# Function to search for a movie on tracker using its TMDB ID + resolution if found
# async def search_movie(session, movie, video_resolutions, video_type, tracker):
#     tmdb_id = movie["tmdbId"]
#
#     # build the search url
#     url = tracker.get_search_url("MOVIE", video_resolutions, video_type, tmdb_id)
#
#     async with session.post(url, headers={"Authorization": f"Bearer {tracker.api_key}"}) as response:
#         response.raise_for_status()  # Raise an exception if the request failed
#         res = await response.json()
#         torrents = res["data"]
#         return torrents


# Function to process each movie
async def process_movie(session, movie, tracker):
    title = movie["title"]
    logger.info(f"[{tracker.__class__.__name__}] Checking {title}... ")

    # verify radarr actually has a file entry if not skip check and save api call
    if not "movieFile" in movie:
        logger.info(
            f"[Skipped: local]. No file found in radarr for {title}"
        )
        return

    # skip check if group is banned.
    if len(tracker.banned_groups) == 0:
        banned_groups = await tracker.get_banned_groups(session)
    # check if banned groups still empty and display warning.
    if len(tracker.banned_groups) == 0:
        logger.error(
            f"Banned groups missing. Checks will be skipped."
        )
    else:
        if "releaseGroup" in movie["movieFile"] and \
                movie["movieFile"]["releaseGroup"].casefold() in map(str.casefold, tracker.banned_groups):
            logger.info(
                f"[Banned: local] group ({movie['movieFile']['releaseGroup']}) for {title}"
            )
            return

    try:
        await tracker.search_movie(session, movie)
    except Exception as e:
        if "429" in str(e):
            logger.warning(f"Rate limit exceeded while checking {title}.")
        else:
            logger.error(f"Error: {str(e)}")
            tracker.radarr_not_found_file.write(f"{title} - Error: {str(e)}\n")


# Function to get all movies from Radarr
async def get_all_movies(session, app_configs: CONFIG):
    radarr_url = app_configs.RADARR['url'] + app_configs.RADARR['api_suffix']
    async with session.get(radarr_url, headers={"X-Api-Key": app_configs.RADARR['api_key']}) as response:
        response.raise_for_status()  # Ensure we handle request errors properly
        movies = await response.json()
        return movies
