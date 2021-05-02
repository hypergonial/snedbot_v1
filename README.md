# Sned v4.1.0

## A Discord bot made with [discord.py](https://github.com/Rapptz/discord.py)  originally made for matchmaking and other purposes on the Annoverse discord guild.

### Features:
 - Easy to use commands
 - Setup commands to simplify configuration for administrators
 - Moderation capabilities
 - Auto-Moderation [WIP]
 - Reaction Roles
 - Keep-On-Top Messages
 - Logging
 - Fun commands (e.g: coinflipping, cat pictures, typeracing, reminders etc..)

### Commands & usage:
 - For a full list of commands use `!help`
 - If you changed the prefix of the bot but forgot it, mention the bot. (Default prefix is `!`)

### How to set up:
If you don't absolutely need this bot, I would prefer if you don't create an instance of it. Instead, join the Annoverse discord, or reach out to me directly. Regardless, here is how you set it up:

Install dependencies from `requirements.txt`, then create a .env in your project folder with your bot token in this format: `TOKEN=yourtokenhere`. The bot should then run correctly.

You will also need to create a postgresql database called `sned` with user postgres and modify the pool definition in line 69. (nice) Your password should be in your .env file with this format:`DBPASS=yourpass`.
