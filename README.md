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
    -v ./config:/config \
    -v ./logs:/logs/ \
    ghcr.io/defective-dev/aither-exists-check:latest --radarr
    ```

## Configuration

1. cd config (in the project directory)
2. cp [configSample.toml](config/configSample.toml) to`config/config.toml` - refer to configSample.toml
3. Fill in all `api_key` & `url` values for Sonarr, Radarr & trackers.

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
default path: `logs/<tracker_name>/`
- `radarr-not_found.txt`: Lists movies in Radarr not found on current tracker.
- `sonarr-not_found.txt`: Lists shows in Sonarr not found on current tracker.
- `radarr-trump.csv`: Lists movies from Radarr that can trump on current tracker.
- `sonarr-trump.csv`: Lists shows from Sonarr that can trump on current tracker.
- 
## Logging

Detailed logs are stored in `logs/script.log`, while concise output is displayed on the console.

## Contributors

Special thanks to those who have contributed:

- [@DefectiveDev](https://github.com/defectivedev)
