# Anno Bot "Sned" v3.2.0 EXPERIMENTAL
#### Note: Experimental builds use the `?` prefix instead of `!`.

## A Discord bot made with [discord.py](https://github.com/Rapptz/discord.py)  for matchmaking and other purposes on the Annoverse discord guild.

### Features:
 - Generate neatly formatted multiplayer listings based on a list of criteria
 - Allow users to add themselves to these listings and express join intent
 - Easy to use commands
 - Setup commands to simplify configuration
 - Customizable localization

### Commands:
`!help` Displays all commands a user has permission to execute. Alternatively, use `!help <command>` to get more information about a specific command.

`!ping` Returns the ping of the bot in ms.

`!about` Displays information about the bot.

`!avatar <user>` Return the avatar of the specified user. Has a 30 second cooldown per user.

`!tag <name>` Calls and displays the contents of a tag. Has a 60 second cooldown per user.

`!tags` Lists all available tags. Has a 60 second cooldown per user.

`!matchmaking` Starts the matchmaking system. Creates a multiplayer listing in desired channel upon completion. Has a 12 hour cooldown per user.

### Commands for server owners & admins:
`!addpriviligedrole <rolename>` Adds a role to priviliged roles. This will allow them to access bot admin commands. Can only be executed by a guild owner.

`!removepriviligedrole <rolename>` Removes a role from priviliged roles, thus revoking their access from bot admin commands. Can only be executed by a guild owner.

`!priviligedroles` Lists all priviliged roles. Can only be executed by a guild owner.

`!setup <setuptype>` Initialize a setup, for configuring the server. Example: `!setup LFG` will start a setup helping you set up reaction roles. Requires priviliged access. Current setups: `LFG, matchmaking, keepontop, logging`

`!settings` Displays all settings for the current guild. Requires priviliged access.

`!resetsettings` Resets all bot settings, irreversible. Also erases all tags. Requires priviliged access.

`!createtag <name> <messageID>` Creates a tag out of the specified message. Command **must be** executed in the same channel where the message resides. Requires priviliged access.

`!deltag <name>` Deletes a tag of the specified name. Requires priviliged access.

`!modify <datatype> <value>` Modifies a datatype in settings to a new value. Improper use will break things, use setups if you don't know what you're doing! Requires priviliged access.

`!warn <user> [reason]` Warns a user, and sends warn to logging channel if set up. Will not function if `LOGCHANNEL` is not set.

`!quack` ???
### How to use:
Install dependencies via pipenv, then create a .env in your project folder with your bot token in this format: `TOKEN=yourtokenhere`. The bot should then run correctly.

Note: The bot is configured by default to look for a database with the name `database.db`, either modify the dbName/dbPath variable in code, or create a database with matching name in the same folder. You can use `database_template.db` for this purpose.

