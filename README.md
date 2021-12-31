# Sned

## A Discord bot made with [PyCord](https://github.com/Pycord-Development/pycord).

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

### Get:
[Add it to your server!](https://discord.com/oauth2/authorize?client_id=817730141722902548&permissions=3691506934&scope=bot%20applications.commands)

### How to set up (Unsupported):
Install dependencies from `requirements.txt`, then create `config.py`. For the formatting of this file and the available options, see `config_example.py`.
You will also need to create a postgresql database called `sned` with user `postgres` and point the `postgres_dsn` in `config.py` to it. The bot should then run correctly. You may also optionally configure a `home_guild` where debug information is sent.

### Contribution:
Please make sure that you run the following command **before** working on the project:
```
git config core.hooksPath .githooks
```
This ensures that the pre-commit hook that automatically formats the code runs properly.