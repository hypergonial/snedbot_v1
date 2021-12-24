import asyncio
import datetime
import logging

import discord
from discord.ext import commands, pages

from extensions.utils import components

logger = logging.getLogger(__name__)

help_menu_strings = {
    "Permissions": {
        "description": "All commands related to handling command permissions",
        "emoji": "📖"
    },
    "Admin Commands": {
        "description": "All commands related to admin duties & bot configuration",
        "emoji": "🔑"
    },
    "Role-Buttons": {
        "description": "Configure roles that can hand out roles to users",
        "emoji": "🔘"
    },
    "Events": {
        "description": "Set up, organize, and manage events",
        "emoji": "📅"
    },
    "Keep On Top": {
        "description": "Manage keep-on-top settings",
        "emoji": "⬆️"
    },
    "Matchmaking": {
        "description": "Show all Annoverse matchmaking related commands",
        "emoji": discord.PartialEmoji.from_str("annoverse:923758544661143582")
    },
    "Tags": {
        "description": "Call, create, claim, search for tags",
        "emoji": "💬"
    },
    "Logging": {
        "description": "Manage logging configuration",
        "emoji": "📝"
    },
    "Timers": {
        "description": "Create and manage timers and reminders",
        "emoji": "🕓"
    },
    "Falling Frontier": {
        "description": "Functionality exclusive to Falling Frontier",
        "emoji": discord.PartialEmoji.from_str("ff_serverlogo:923759064230535199")
    },
    "Annoverse": {
        "description": "Functionality exclusive to Annoverse",
        "emoji": discord.PartialEmoji.from_str("annoverse:923758544661143582")
    },
    "Giveaway": {
        "description": "Create and manage giveaways",
        "emoji": "🎉"
    },
    "Miscellaneous Commands": {
        "description": "Commands that do not fit in other categories",
        "emoji": "❔"
    },
    "Settings": {
        "description": "Configure and customize the bot",
        "emoji": "🔧"
    },
    "Jishaku": {
        "description": "Owner-only, stop looking",
        "emoji": "🤫"
    },
    "Auto-Moderation": {
        "description": "Configure & customize automoderation filters & settings",
        "emoji": "🤖"
    },
    "Fun": {
        "description": "Commands that hopefully make your day a little better",
        "emoji": "🙃"
    },
    "Moderation": {
        "description": "All commands related to moderator duties",
        "emoji": discord.PartialEmoji.from_str("mod_shield:923752735768190976")
    },

}

class SnedHelp(commands.HelpCommand):
    '''
    The custom help command subclassing the dpy one. 
    See the docs or this guide (https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96) on how this was made.
    '''
    #Method to get information about a command to display in send_bot_help
    def get_command_signature(self, ctx, command):
        return '**`{prefix}{parent}{command}`** - {commandbrief}'.format(prefix=ctx.clean_prefix, parent=command.full_parent_name, command=command.name, commandbrief=command.short_doc) #short_doc goes to brief first, otherwise gets first line of help
    
    def get_subcommand_signature(self, ctx, group, command): #Essentially the same as get_command_signature but appends the group name in front of the command
        return '**`{prefix}{group} {command}`** - {commandbrief}'.format(prefix=ctx.clean_prefix, group=group.name, command=command.name, commandbrief=command.short_doc)
    
    #Send generic help message with all commands included
    async def send_bot_help(self, mapping):

        ctx = self.context   #Obtaining ctx

        help_home_embed=discord.Embed(title="🏠 " + "__Help Home__", color=ctx.bot.embedBlue, description='''**How to navigate this help dialogue**

        Navigate to different sections of this help dialogue via the **dropdown** below!

        If you need support, please join the [support server](https://discord.gg/KNKr8FPmJa)!

        **Command Usage & Syntax**

        `<argument>` is a __required__ parameter
        `[argument]` is an __optional__ parameter
        `<foo|bar>` means foo __OR__ bar

        *Do not include the brackets in your commands!*        

        Thank you for using Sned!
        ''')
        embed = ctx.bot.add_embed_footer(ctx, help_home_embed)
        help_pages = []
        help_pages.append(help_home_embed)
        all_commands = {} # Key: cog_name, Value: all command_signatures for cog
        cog_embeds = {} # Key: cog_name, Value: embed
        #We retrieve all the commands from the mapping of cog,commands
        select_options = []
        for cog, cmds in mapping.items():
            filtered = await self.filter_commands(cmds, sort=True)   #This will filter commands to those the user can actually execute
            command_signatures = [self.get_command_signature(ctx, command) for command in filtered]   #Get command signature in format as specified above
            #If we have any, put them in categories according to cogs, fallback is "Other"
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "Other") #Append items into a list of str, one item per cog
                all_commands[cog_name] = "\n".join(command_signatures)
        
        for cog_name in all_commands.keys():
            emoji = help_menu_strings[cog_name]['emoji'] if cog_name in help_menu_strings.keys() and help_menu_strings[cog_name]['emoji'] and isinstance(help_menu_strings[cog_name]['emoji'], str) else '⚙️'
            embed=discord.Embed(title=f"{emoji} __Help Page for {cog_name}:__", description="**Tip:** You can also type **`{prefix}help [command]`** to get more information about a specific command, see usage syntax, and see any subcommands a command may have.\n\n {commands}".format(prefix=ctx.prefix, commands=all_commands[cog_name]), color=ctx.bot.embedBlue)
            embed = ctx.bot.add_embed_footer(ctx, embed)
            cog_embeds[cog_name] = embed
            select_options.append(discord.SelectOption(label=cog_name, value=cog_name, description=help_menu_strings[cog_name]["description"] if cog_name in help_menu_strings.keys() else None, emoji=help_menu_strings[cog_name]["emoji"] if cog_name in help_menu_strings.keys() else None))
        
        class HelpView(components.AuthorOnlyView):
            async def on_timeout(self):
                await message.edit(view=None) # Remove timed out view

        class HelpSelect(discord.ui.Select):
            def __init__(self, cog_embeds:dict, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.cog_embeds = cog_embeds
            
            async def callback(self, interaction:discord.Interaction):
                await message.edit(embed=self.cog_embeds[interaction.data["values"][0]])

        view = HelpView(ctx)
        view.add_item(HelpSelect(cog_embeds, placeholder="Select a category...", options=select_options))
        message = await ctx.send(embed=help_home_embed, view=view)
        

    async def send_command_help(self, command):
        ctx = self.context
        if command.parents:
            detail_embed=discord.Embed(title="⚙️ " + "Command: {prefix}{parent} {command}".format(prefix=ctx.clean_prefix, parent=command.full_parent_name, command=command.name), color=ctx.bot.embedBlue)
        else:
            detail_embed=discord.Embed(title="⚙️ " + "Command: {prefix}{command}".format(prefix=ctx.clean_prefix, command=command.name), color=ctx.bot.embedBlue)
        if command.description:
            detail_embed.add_field(name="Description:", value=command.description)  #Getting command description
        elif command.help:
            detail_embed.add_field(name="Description:", value=command.help)  #Fallback to help attribute if description does not exist
        if command.usage:
            detail_embed.add_field(name="Usage:", value=f"**`{ctx.clean_prefix}{command.usage}`**", inline=False) #Getting command usage & formatting it
        aliases = []
        for alias in command.aliases:
            if command.parents:
                aliases.append(f"**`{ctx.clean_prefix}{command.full_parent_name} {alias}`**")
            else:
                aliases.append(f"**`{ctx.clean_prefix}{alias}`**")  #Adding some custom formatting to each alias
        if aliases:
            detail_embed.add_field(name="Aliases:", value=", ".join(aliases), inline=False)   #If any aliases exist, we add those to the embed in new field
        detail_embed = ctx.bot.add_embed_footer(ctx, detail_embed)
        channel = self.get_destination()   #Send it to destination
        await channel.send(embed=detail_embed)

    async def send_cog_help(self, cog):
        #I chose not to implement help for cogs, but if you want to do something, do it here
        ctx = self.context
        embed=discord.Embed(title=ctx.bot.unknownCMDstr, description="Use `{prefix}help` for a list of available commands.".format(prefix=ctx.prefix), color=ctx.bot.unknownColor)
        embed = ctx.bot.add_embed_footer(ctx, embed)
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_group_help(self, group):
        ctx = self.context
        group_embed = discord.Embed(title="⚙️ " + "Group: {prefix}{group}".format(prefix=ctx.prefix, group=group.name), description="**Note:**\nTo see detailed information about one of the subcommands, type **`{prefix}help {group} [subcommand]`**".format(prefix=ctx.prefix, group=group.name), color=ctx.bot.embedBlue)
        if group.description:
            group_embed.add_field(name="Description:", value=group.description)  #Getting command description
        elif group.help:
            group_embed.add_field(name="Description:", value=group.help)  #Fallback to help attribute if description does not exist
        if group.usage:
            group_embed.add_field(name="Usage:", value=f"**`{ctx.clean_prefix}{group.usage}`**", inline=False) #Getting command usage & formatting it
        aliases = []
        for alias in group.aliases:
            aliases.append(f"**`{ctx.clean_prefix}{alias}`**")  #Adding some custom formatting to each alias
        if aliases:
            group_embed.add_field(name="Aliases:", value=", ".join(aliases), inline=False)   #If any aliases exist, we add those to the embed in new field
        sub_cmds = []
        filtered = await self.filter_commands(group.walk_commands(), sort=True)
        for command in filtered:
            sub_cmds.append(self.get_subcommand_signature(ctx, group, command))
        if sub_cmds:
            sub_cmds = "\n".join(sub_cmds)
            group_embed.add_field(name="Sub-commands:", value=f"{sub_cmds}")
        channel = self.get_destination()
        await channel.send(embed=group_embed)

    async def send_error_message(self, error):   #Overriding the default help error message
        ctx = self.context
        embed=discord.Embed(title=ctx.bot.unknownCMDstr, description="Use `{prefix}help` for a list of available commands.".format(prefix=ctx.prefix), color=ctx.bot.unknownColor)
        embed = ctx.bot.add_embed_footer(ctx, embed)
        channel = self.get_destination()
        await channel.send(embed=embed)


class Help(commands.Cog):
    '''Cog that implements a custom help command'''

    def __init__(self, bot):
        bot.help_command = SnedHelp()
        self.bot = bot

def setup(bot):
    logger.info("Adding cog: Help...")
    bot.add_cog(Help(bot))
