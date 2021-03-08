# Anno Matchmaking Bot v1.0

## A Discord bot written with [Discord.py](https://github.com/Rapptz/discord.py)  for matchmaking on the Annoverse discord guild.

### Features:
 - Generate neatly formatted multiplayer listings based on a list of criteria
 - Easy to use commands
 - Setup commands to simplify configuration (WIP)

### Commands:
`!ping` Returns the ping of the bot in ms.

`!init` Starts the matchmaking system. Creates a multiplayer listing in desired channel upon completion.

### Commands for server owners & admins:
`!addpriviligedrole <rolename>` Adds a role to priviliged roles. This will allow them to access bot admin commands. Can only be executed by a guild owner.

`!removepriviligedrole <rolename>` Removes a role from priviliged roles, thus revoking their access from bot admin commands. Can only be executed by a guild owner.

`!setup <setuptype>` Initialize a setup, for configuring the server. Example: `!setup LFG` will start a setup helping you set up reaction roles. Requires priviliged access.

`!settings` Displays all settings for the current guild. Requires priviliged access.

`!resetsettings` Resets all bot settings, irreversible. Requires priviliged access.

`!modify <datatype> <value>` Modifies a datatype in settings to a new value. Improper use will break things, use setups if you don't know what you're doing! Requires priviliged access.
### How to use:
After installing discord.py, create a .env in your project folder with your bot token in this format: `TOKEN=yourtokenhere` The bot should then run correctly.

