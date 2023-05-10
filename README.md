<img align="left" src="https://em-content.zobj.net/thumbs/120/google/350/rainbow_1f308.png" />
<h1>EuphieRR</h1>
<p>An Asynchronous Headless Sonarr-like Downloader Made for a Certain Cat Website</p>

This headless app should be executed is made with Linux and cron in mind where you can exeecute the main entrypoint file.

The reason why I made this is because I only need a script to download shit, wait for it, rename, and move it to my Jellyfin series folders, so I do not need to manually download stuff.

Application name are based on a character from **[The Magical Revolution of the Reincarnated Princess and the Genius Young Lady][Anilist]**

**NOTE:** This project is made for my personal use, if it doesn't work for you don't complain too much.

## Requirements
1. Python 3.8+
2. Virtualenv
3. qbittorrent
4. Jellyfin

## Jellyfin Setup
You need to have a series library that target a folder, the folder itself should follows Jellyfin recommended setup:
- Series Name
  - Season XX
    - Episode SXXEYY.mkv

This would make sure Jellyfin detect the series properly.

## Installation
1. Clone this Repo/Download this Repo
2. Rename `config.yml.example` to `config.yml`
3. Create a new virtual environment with `virtualenv` or something similar:
   ```bash
   $ virtualenv .venv
   ```
4. Enter the virtualenv, and install `requirements.txt`
4. Fill up the configuration, you can see the [Configuration](#configuration) section for more info.
5. Setup cron to run the `main.py` to whatever you want, you can use [Crontab.guru][Crontab] to help it.

## Configuration

```yaml
# qBittorrent configuration
qbt:
  # The URL to qBittorrent's WebUI
  url: http://localhost:8080
  # The username to log in with
  username: admin
  # The password to log in with
  password: adminadmin
  # The category to add torrents to
  category: null
# The series to watch/track/download
series:
  # The RSS feed to watch, must be from nyaa.si RSS
  - rss: https://nyaa.si/?page=rss&q=Heavenly+Delusion&c=1_2&f=0&u=Tsundere-Raws
    # The regex to match the episode number and the season from the torrent title
    # for example you have: Heavenly Delusion S01E01 1080p WEB H.264 AAC -Tsundere-Raws (DSNP) (Tengoku Daimakyou / MultiSubs)
    # in the torrent title, you can use: Heavenly Delusion S(?P<season>\d+)E(?P<episode>\d+)
    # to match the season and episode number
    # The `episode` match group is required, the `season` match group is optional
    # See more about regex: https://regex101.com/
    episode_regex: Heavenly Delusion S(?P<season>\d+)E(?P<episode>\d+)
    # The series folder that Jellyfin will use, the downloaded torrent will be moved to this folder
    target_dir: /home/nao/jellyfin-library/Heavenly Delusion
    # The season number, if you don't have a season number in the torrent title
    # you can set this to 1, or whatever as a fallback
    season: 1
    # Extra matches to check for in the torrent title, case insensitive
    matches:
    - 1080p
    - DSNP
    # Ignore keyword matches, case insensitive
    ignore_matches:
    - 720p
    - DUAL
    # The time the episode will air, this is used to determine if we should download the episode
    # or not by checking if the current time is near the airtime with the provided grace period
    airtime: 2023-04-06T22:30:00+09:00
    # The grace period in minutes, used with airtime to determine if we should download the episode
    # or not by checking if the current time is near the airtime with the provided grace period.
    grace_period: 120
```

### Explanation

TODO

[Anilist]: https://anilist.co/anime/153629/
[Crontab]: https://crontab.guru/