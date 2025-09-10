class CONFIG:
    # time to sleep between API calls.
    SLEEP_TIMER = 10

    # create config.py and mimic this file
    RADARR = {
        # radarr -> settings -> general
        "api_key": "",
        # radarr port typically 7878, local DNS should work if you have it setup, else "localhost" if local machine
        "url": "http://localhost:7878",
        "api_suffix": "/api/v3/movie"
    }

    SONARR = {
        # sonarr -> settings -> general
        "api_key": "",
        # sonarr port typically 8989, local DNS should work if you have it setup, else "localhost" if local machine
        "url": "http://localhost:8989",
        "api_suffix": "/api/v3/series"
    }

    LOG_FILES = {
        "output_path": "",
        "script_log": "script.log",
        "not_found_radarr": "radarr-not_found.txt",
        "not_found_sonarr": "sonarr-not_found.txt",
        "trump_radarr": "radarr-trump.txt",
        "trump_sonarr": "sonarr-trump.txt"
    }

    TRACKERS_SEARCH = ["AITHER"]
    TRACKER_LIST = {
        "AITHER": {
            # https://aither.cc/users/YOUR_USERNAME/settings/security
            "api_key": ""
        }
    }