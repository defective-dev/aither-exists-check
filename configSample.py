from aiohttp_retry import ExponentialRetry


class CONFIG:
    # time to sleep between API calls.
    SLEEP_TIMER = 10

    # create config.py and mimic this file
    RADARR = {
        # scan radarr. using command line --radarr or --sonarr will override this value
        "enabled": True,
        # radarr -> settings -> general
        "api_key": "",
        # radarr port typically 7878, local DNS should work if you have it setup, else "localhost" if local machine
        "url": "http://localhost:7878",
        "api_suffix": "/api/v3/movie"
    }

    SONARR = {
        # scan sonarr. using command line --radarr or --sonarr will override this value
        "enabled": True,
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
        "trump_radarr": "radarr-trump.csv",
        "trump_sonarr": "sonarr-trump.csv"
    }

    TRACKERS_SEARCH = ["AITHER"]
    TRACKER_LIST = {
        "AITHER": {
            # https://aither.cc/users/YOUR_USERNAME/settings/security
            "api_key": ""
        },
        "BHD": {
            # https://beyond-hd.me/settings/security/apikey
            "api_key": ""
        }
    }

    # ADVANCED Configs. Probably no need to edit these.

    # Configure ExponentialRetry with desired parameters
    # attempts: Maximum number of retry attempts
    # start_timeout: Initial delay before the first retry
    # factor: Multiplier for increasing the delay between retries
    # statuses: HTTP status codes that trigger a retry (default includes 5xx)
    http_retry_options = ExponentialRetry(
        attempts=3,
        start_timeout=5.0,  # 0.5 seconds initial delay
        factor=2.0,  # Double the delay each time
        max_timeout=40.0,  # Maximum delay between retries
        statuses={429, 500, 502, 503, 504}  # Retry on common server errors
    )