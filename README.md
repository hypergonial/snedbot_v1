# Sned

## A Discord bot made with [discord.py](https://github.com/Rapptz/discord.py).

### Features:
 - Easy to use commands
 - Dashboard to simplify configuration for administrators *(Heavy WIP)*
 - Comprehensive documentation
 - Moderation capabilities
 - Auto-Moderation
 - Role-Buttons
 - Events
 - Tags
 - Logging
 - Fun commands (e.g: coinflipping, cat pictures, typeracing, reminders etc..)

### Commands & usage:
 - For a full list of commands use `sn help` or see the [documentation](https://sned.hypersden.com/docs/).
 - If you changed the prefix of the bot but forgot it, mention the bot. (Default prefix is `sn `)

### How to set up:
If you don't absolutely need this bot self-hosted, I would prefer if you don't create an instance of it. Instead, invite it via the [dashboard](https://sned.hypersden.com/dashboard). Regardless, here is how you set it up:

Install dependencies from `requirements.txt`, then create `config.py`. For the formatting of this file and the available options, see `config_example.py`.
You will also need to create a postgresql database called `sned` with user postgres and point the `dsn` in `config.py` to it. The bot should then run correctly.
