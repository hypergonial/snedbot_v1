import logging
import sys
import traceback

from types.bot import SnedBot

try:
    from config import config
except ImportError:
    logging.error(
        "Failed loading configuration. Please make sure 'config.py' exists in the root directory of the project and contains valid data."
    )
    exit()

try:
    import uvloop

    uvloop.install()
except (ModuleNotFoundError, ImportError):
    logging.warning(
        'Failed to import uvloop, expect degraded performance!\nFor best performance, please "pip install uvloop"!'
    )

"""
All extensions that are loaded on boot-up, change these to alter what modules you want.
Please note that removing essential extensions may cause fatal errors to occur.
"""
initial_extensions = (
    # Essential
    "extensions.permissions",
    "extensions.admin_commands",
    "extensions.timers",
    "extensions.help",
    "extensions.homeguild",
    # Non-essential
    "extensions.moderation",
    "extensions.settings",
    "extensions.automod",
    "extensions.role_buttons",
    "extensions.events",
    "extensions.ktp",
    "extensions.matchmaking",
    "extensions.tags",
    "extensions.userlog",
    "extensions.fun",
    "extensions.fallingfrontier",
    "extensions.annoverse",
    "extensions.giveaway",
    "extensions.ipc",
    "extensions.misc_commands",
    "extensions.context_menus",
    "jishaku",
)

TOKEN = config["token"]
bot = SnedBot(config)

if __name__ == "__main__":
    """
    Loading extensions from the list of extensions defined in initial_extensions
    """

    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
            logging.error(f"Failed to load extension {extension}.")
            traceback.print_exc()


# Run bot with token from config.py
if __name__ == "__main__":
    try:
        if hasattr(bot, "ipc"):
            logging.info("IPC was disabled.")
            # bot.ipc.start()
        else:
            logging.warn("IPC was not found, or configured correctly!")
        bot.run(TOKEN)
    except KeyboardInterrupt:
        bot.loop.run_until_complete(bot.pool.close())
        bot.close()
