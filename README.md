# Aither Exists Check

A lightweight Python script to check your Radarr and Sonarr media libraries against Aither's uploaded movie torrents.
As this script becomes more granular, and checking against Aither's resolutions, editions etc. it is more and more recommended you *double check* before proceeding to upload!

## Features

- Compare your Radarr and Sonarr libraries with Aither's torrent listings.
- Log missing movies and TV shows from your libraries, respecting banned groups, trumpables, etc.
- Respect Aither's API rate limits.

## Prerequisites

- Python 3.x installed on your system.
- Radarr and/or Sonarr configured and running.

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/brah/aither-exists-check.git
   ```

2. Navigate to the project directory:

   ```bash
   cd aither-exists-check
   ```

3. Install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

## Docker
1. Run the docker image. Correct the paths below to map correct config file location and output directory.
    ```bash
    docker run --user 1000:1000 --name aither-exists --rm -it \
    -v ./config/config.py:/aither-exists-check/config.py \
    -v ./output:/output/ \
    ghcr.io/defective-dev/aither-exists-check:latest --radarr
    ```

## Configuration

1. Rename `configSample.py` to `config.py` in the project directory with the following contents - refer to configSample.py:

   ```python
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
   ```

2. Fill in all `apt_key` values and the Sonarr & tracker `url` values.

## Usage

To run the script, use one of the following commands:

- To check the Radarr library:

  ```bash
  python main.py --radarr
  ```

- To check the Sonarr library:

  ```bash
  python main.py --sonarr
  ```

- To check both libraries (default):

  ```bash
  python main.py
  ```

## Output

The script generates two output files:

- `<tracker_name>/not_found-radarr.txt`: Lists movies in Radarr not found in Aither.
- `<tracker_name>/not_found-sonarr.txt`: Lists shows in Sonarr not found in Aither.

## Logging

Detailed logs are stored in `script.log`, while concise output is displayed on the console.

## Contributors

Special thanks to those who have contributed:

- [@DefectiveDev](https://github.com/defectivedev)
