<img align="left" src="https://em-content.zobj.net/thumbs/120/google/350/rainbow_1f308.png" />
<h1>EuphieRR</h1>
<p>A Headless Sonarr-like Downloader Made for a Certain Cat Website</p>

This headless app should be executed is made with Linux and cron in mind where you can exeecute the main entrypoint file.

The reason why I made this is because I only need a script to download shit, wait for it, rename, and move it to my Jellyfin series folders, so I do not need to manually download stuff.

Application name are based on a character from **[The Magical Revolution of the Reincarnated Princess and the Genius Young Lady][Anilist]**

## Requirements
1. Python 3.8+
2. Virtualenv
3. qbittorrent

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
TODO
```

### Explanation

TODO

[Anilist]: https://anilist.co/anime/153629/
[Crontab]: https://crontab.guru/