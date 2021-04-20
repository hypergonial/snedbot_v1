# Anno Bot "Sned" v3.4.3

## A Discord bot made with [discord.py](https://github.com/Rapptz/discord.py)  for matchmaking and other purposes on the Annoverse discord guild.

### Features:
 - Generate neatly formatted multiplayer listings based on a list of criteria
 - Allow users to add themselves to these listings and express join intent
 - Easy to use commands
 - Setup commands to simplify configuration
 - Moderation capabilities
 - Logging
 - Fun commands
 - Customizable localization

### Commands:
 - For all commands use `!help`

### How to set up:
If you don't absolutely need this bot, I would prefer if you don't create an instance of it. Instead, join the Annoverse discord, or reach out to me directly. Regardless, here is how you set it up:

Install dependencies from `requirements.txt`, then create a .env in your project folder with your bot token in this format: `TOKEN=yourtokenhere`. The bot should then run correctly.

Note: The bot is configured by default to look for a database with the name `database.db`, either modify the dbName/dbPath variable in code, or create a database with matching name in the same folder. You can use `database_template.db` for this purpose.

