import logging

import discord
from discord.ext import commands, pages
from extensions.utils import components

logger = logging.getLogger(__name__)

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

        Navigate via the ◀️ ▶️ buttons, or skip to the end via the ⏮️ ⏭️ buttons.
        You can stop this help session by pressing ⏹️.

        If you need support, please join the [support server](https://discord.gg/KNKr8FPmJa)!

        **Command Usage & Syntax**

        `<argument>` is a __required__ parameter
        `[argument]` is an __optional__ parameter
        `<foo|bar>` means foo __OR__ bar

        *Do not include the brackets in your commands!*        

        Press ▶️ to see the next page and what commands are available to you!
        ''')
        embed = ctx.bot.add_embed_footer(ctx, help_home_embed)
        help_pages = []
        help_pages.append(help_home_embed)
        #We retrieve all the commands from the mapping of cog,commands
        paginator = commands.Paginator(prefix='', suffix='', max_size=500)
        for cog, cmds in mapping.items():
            if cog: 
                print(cog.qualified_name)
                print(cmds)
            filtered = await self.filter_commands(cmds, sort=True)   #This will filter commands to those the user can actually execute
            command_signatures = [self.get_command_signature(ctx, command) for command in filtered]   #Get command signature in format as specified above
            #If we have any, put them in categories according to cogs, fallback is "Other"
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "Other") #Append items into a list of str, one item per cog
                paginator.add_line(f"\n**{cog_name}**")
                for signature in command_signatures:
                    paginator.add_line(signature)
        
        for page in paginator.pages:
            embed=discord.Embed(title="⚙️ " + "__Available commands:__", description="**Tip:** You can also type **`{prefix}help [command]`** to get more information about a specific command and see any subcommands a command may have.\n\n {page}".format(prefix=ctx.prefix, page=page), color=ctx.bot.embedBlue)
            embed = ctx.bot.add_embed_footer(ctx, embed)
            help_pages.append(embed)
        
        menu_paginator = components.SnedMenuPaginator(pages=help_pages, show_disabled=True, show_indicator=True)
        await menu_paginator.send(ctx, ephemeral=False)

    async def send_command_help(self, command):
        ctx = self.context   #Obtaining ctx
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
