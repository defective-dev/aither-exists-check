
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


# Function to search for a movie in Aither using its TMDB ID + resolution if found
async def search_movie(session, movie, video_resolutions, video_type, tracker):
    tmdb_id = movie["tmdbId"]
    category_id = tracker.get_cat_id("MOVIE")

    # build the search url
    url = f"{tracker.URL}/api/torrents/filter?categories[0]={category_id}&tmdbId={tmdb_id}"
    if len(video_resolutions) > 0:
        for index, resolution in enumerate(video_resolutions):
            if resolution != 0:
                url += f"&resolutions[{index}]={resolution}"
    if video_type:
        url += f"&types[0]={video_type}"

    async with session.get(url, headers={"Authorization": f"Bearer {tracker.api_key}"}) as response:
        response.raise_for_status()  # Raise an exception if the request failed
        res = await response.json()
        torrents = res["data"]
        return torrents


# Function to process each movie
async def process_movie(session, movie, tracker):
    title = movie["title"]
    logger.info(f"Checking {title}... ")

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
        quality_info = movie.get("movieFile").get("quality").get("quality")
        source = quality_info.get("source")
        modifier = quality_info.get("modifier")
        if modifier == "none" and source == "dvd":
            release_info = guessit(movie.get("movieFile").get("relativePath"))
            modifier = release_info.get("other")
        video_type = utils.get_video_type(source, modifier)
        tracker_type = None
        if video_type != "OTHER":
            tracker_type = tracker.get_type_id(video_type.upper())
        media_resolution = str(get_movie_resolution(movie))
        tracker_resolutions = utils.get_video_resolutions(tracker, media_resolution)
        torrents = await search_movie(session, movie, tracker_resolutions, tracker_type, tracker)
    except Exception as e:
        if "429" in str(e):
            logger.warning(f"Rate limit exceeded while checking {title}.")
        else:
            logger.error(f"Error: {str(e)}")
            tracker.radarr_not_found_file.write(f"{title} - Error: {str(e)}\n")
    else:
        if len(torrents) == 0:
            try:
                movie_file = movie["movieFile"]["path"]
                if movie_file:
                    logger.info(
                        f"[{media_resolution} {video_type}] not found on AITHER"
                    )
                    tracker.radarr_not_found_file.write(f"{movie_file}\n")
                else:
                    logger.info(
                        f"[{media_resolution} {video_type}] not found on AITHER (No media file)"
                    )
            except KeyError:
                logger.info(
                    f"[{media_resolution} {video_type}] not found on AITHER (No media file)"
                )
        else:
            release_info = guessit(torrents[0].get("attributes").get("name"))
            if "release_group" in release_info \
                    and release_info["release_group"].casefold() in map(str.casefold, tracker.banned_groups):
                logger.info(
                    f"[Trumpable: Banned] group for {title} [{media_resolution} {video_type} {release_info['release_group']}] on AITHER"
                )
            else:
                logger.info(
                    f"[{media_resolution} {video_type}] already exists on AITHER"
                )


# Function to get all movies from Radarr
async def get_all_movies(session, app_configs: CONFIG):
    radarr_url = app_configs.RADARR['url'] + app_configs.RADARR['api_suffix']
    async with session.get(radarr_url, headers={"X-Api-Key": app_configs.RADARR['api_key']}) as response:
        response.raise_for_status()  # Ensure we handle request errors properly
        movies = await response.json()
        return movies
