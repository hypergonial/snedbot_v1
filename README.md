# Sned

## A Discord bot made with [discord.py](https://github.com/Rapptz/discord.py).

### Features:
 - Easy to use commands
 - Setup commands to simplify configuration for administrators
 - Moderation capabilities
 - Auto-Moderation
 - Reaction Roles
 - Tags
 - Logging
 - Fun commands (e.g: coinflipping, cat pictures, typeracing, reminders etc..)

### Commands & usage:
 - For a full list of commands use `sn help` or see the [documentation](https://sned.hypersden.com/docs/).
 - If you changed the prefix of the bot but forgot it, mention the bot. (Default prefix is `sn `)

### How to set up:
If you don't absolutely need this bot, I would prefer if you don't create an instance of it. Instead, invite it via the [dashboard](https://sned.hypersden.com/dashboard). Regardless, here is how you set it up:

Install dependencies from `requirements.txt`, then create a .env in your project folder with your bot token in this format: `TOKEN=yourtokenhere`. The bot should then run correctly.

You will also need to create a postgresql database called `sned` with user postgres and modify the pool definition in line 69. (nice) Your password should be in your .env file with this format:`DBPASS=yourpass`.
