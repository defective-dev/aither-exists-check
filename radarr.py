import asyncio
import logging
from xml.etree.ElementTree import indent

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

# Function to process each movie
async def process_movie(session, movie, trackers):
    # add newline to put list below title if multiple checks
    # and tab indent sub items
    indented = False
    if len(trackers) > 1:
        logger.info("")
        indented = True

    # display missing release group warning. So only once and not duplicated per tracker.
    if "releaseGroup" in movie["movieFile"] and not movie["movieFile"]["releaseGroup"].strip():
        logger.warning(
            f"{"\t" if indented else ""}Warning: Release group missing. Banned checks will be skipped."
        )
    tasks = [tracker.search_movie(session, movie, indented) for tracker in trackers]
    await asyncio.gather(*tasks)


# Function to get all movies from Radarr
async def get_all_movies(session, app_configs: CONFIG):
    radarr_url = app_configs.RADARR['url'] + app_configs.RADARR['api_suffix']
    async with session.get(radarr_url, headers={"X-Api-Key": app_configs.RADARR['api_key']}) as response:
        response.raise_for_status()  # Ensure we handle request errors properly
        movies = await response.json()
        return movies
