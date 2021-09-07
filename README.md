# Sned

## A Discord bot made with [discord.py](https://github.com/Rapptz/discord.py).

### Update on development
With the discontinuation of discord.py, I see no way for this bot to move forward, and will most likely end development soon. 

### Features:
 - Easy to use commands
 - Moderation capabilities
 - Auto-Moderation
 - Role-Buttons
 - Events
 - Tags
 - Logging
 - Fun commands (e.g: coinflipping, cat pictures, typeracing, reminders etc..)

### Commands & usage:
 - For a full list of commands use `sn help`
 - If you changed the prefix of the bot but forgot it, mention the bot. (Default prefix is `sn `)

### How to set up:
Install dependencies from `requirements.txt`, then create `config.py`. For the formatting of this file and the available options, see `config_example.py`.
You will also need to create a postgresql database called `sned` with user postgres and point the `postgres_dsn` in `config.py` to it. The bot should then run correctly.
