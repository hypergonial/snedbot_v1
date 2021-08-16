import logging

import discord
from discord.ext import commands, menus
from discord.ext.menus.views import ViewMenuPages


class HelpPages(ViewMenuPages):
    '''
    Subclassing MenuPages to add an offset for the homepage (so it does not swallow the first page)
    '''
    def __init__(self, initial_message, source, **kwargs):
        self.initial_message = initial_message
        super().__init__(source, **kwargs)
    
    async def send_initial_message(self, _, channel):
        self.current_page = -1
        print("Sending view...")
        return await self.send_with_view(channel, embed=self.initial_message)
        #return await channel.send(embed=self.initial_message)


class HelpSource(menus.ListPageSource):
    '''
    Takes a list, and puts it into an embed menu, 1 item per page
    '''
    def __init__(self, data):
        super().__init__(data, per_page=1)

    async def format_page(self, menu, entries):
        self._ = menu.ctx.bot.get_localization('help', menu.ctx.bot.lang)
        offset = menu.current_page * self.per_page
        embed=discord.Embed(title="⚙️ " + self._("__Available commands:__"), description=self._("**Tip:** You can also type **`{prefix}help [command]`** to get more information about a specific command and see any subcommands a command may have.\n\n").format(prefix=menu.ctx.prefix) + ''.join(f'{v}' for i, v in enumerate(entries, start=offset)), color=menu.ctx.bot.embedBlue)
        embed.set_footer(text=menu.ctx.bot.requestFooter.format(user_name=menu.ctx.author.name, discrim=menu.ctx.author.discriminator) + f"  |  Page {menu.current_page + 1}/{self.get_max_pages()}", icon_url=menu.ctx.author.avatar.url)
        return embed

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
        self._ = ctx.bot.get_localization('help', ctx.bot.lang)
        #We retrieve all the commands from the mapping of cog,commands
        paginator = commands.Paginator(prefix='', suffix='', max_size=500)
        for cog, cmds in mapping.items(): 
            filtered = await self.filter_commands(cmds, sort=True)   #This will filter commands to those the user can actually execute
            command_signatures = [self.get_command_signature(ctx, command) for command in filtered]   #Get command signature in format as specified above
            #If we have any, put them in categories according to cogs, fallback is "Other"
            """ if command_signatures:
                cog_name = getattr(cog, "qualified_name", "Other") #Append items into a list of str, one item per cog
                cmdslist.append("**{cn}**\n{cs}\n".format(cn=cog_name, cs='\n'.join(command_signatures))) """
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "Other") #Append items into a list of str, one item per cog
                paginator.add_line(f"\n**{cog_name}**")
                for signature in command_signatures:
                    paginator.add_line(signature)
        
        help_home_embed=discord.Embed(title="🏠 " + self._("__Help Home__"), color=ctx.bot.embedBlue, description='''**How to navigate this help dialogue**

        Navigate via the ◀️ ▶️ buttons, or skip to the end via the ⏮️ ⏭️ buttons.
        You can stop this help session by pressing ⏹️.

        You can also check out the [documentation](https://sned.hypersden.com/docs/) for more information.
        If you need support, please join the [support server](https://discord.gg/KNKr8FPmJa)!

        **Command Usage & Syntax**

        `<argument>` is a __required__ parameter
        `[argument]` is an __optional__ parameter
        `<foo|bar>` means foo __OR__ bar

        *Do not include the brackets in your commands!*        

        React with ▶️ to see the next page and what commands are available to you!
        ''')
        help_home_embed.set_footer(text=ctx.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
        help_pages = HelpPages(help_home_embed, source=HelpSource(paginator.pages), clear_reactions_after=True) #Feed the list of commands into the menu system
        await help_pages.start(ctx)

    async def send_command_help(self, command):
        ctx = self.context   #Obtaining ctx
        self._ = ctx.bot.get_localization('help', ctx.bot.lang)
        if command.parents:
            detail_embed=discord.Embed(title="⚙️ " + self._("Command: {prefix}{parent} {command}").format(prefix=ctx.clean_prefix, parent=command.full_parent_name, command=command.name), color=ctx.bot.embedBlue)
        else:
            detail_embed=discord.Embed(title="⚙️ " + self._("Command: {prefix}{command}").format(prefix=ctx.clean_prefix, command=command.name), color=ctx.bot.embedBlue)
        if command.description:
            detail_embed.add_field(name=self._("Description:"), value=command.description)  #Getting command description
        elif command.help:
            detail_embed.add_field(name=self._("Description:"), value=command.help)  #Fallback to help attribute if description does not exist
        if command.usage:
            detail_embed.add_field(name=self._("Usage:"), value=f"**`{ctx.clean_prefix}{command.usage}`**", inline=False) #Getting command usage & formatting it
        aliases = []
        for alias in command.aliases:
            if command.parents:
                aliases.append(f"**`{ctx.clean_prefix}{command.full_parent_name} {alias}`**")
            else:
                aliases.append(f"**`{ctx.clean_prefix}{alias}`**")  #Adding some custom formatting to each alias
        if aliases:
            detail_embed.add_field(name=self._("Aliases:"), value=", ".join(aliases), inline=False)   #If any aliases exist, we add those to the embed in new field
        detail_embed.set_footer(text=ctx.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
        channel = self.get_destination()   #Send it to destination
        await channel.send(embed=detail_embed)

    async def send_cog_help(self, cog):
        #I chose not to implement help for cogs, but if you want to do something, do it here
        ctx = self.context
        self._ = ctx.bot.get_localization('help', ctx.bot.lang)
        embed=discord.Embed(title=ctx.bot.unknownCMDstr, description=self._("Use `{prefix}help` for a list of available commands.").format(prefix=ctx.prefix), color=ctx.bot.unknownColor)
        embed.set_footer(text=ctx.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_group_help(self, group):
        ctx = self.context
        self._ = ctx.bot.get_localization('help', ctx.bot.lang)
        group_embed = discord.Embed(title="⚙️ " + self._("Group: {prefix}{group}").format(prefix=ctx.prefix, group=group.name), description=self._("**Note:**\nTo see detailed information about one of the subcommands, type **`{prefix}help {group} [subcommand]`**").format(prefix=ctx.prefix, group=group.name), color=ctx.bot.embedBlue)
        if group.description:
            group_embed.add_field(name=self._("Description:"), value=group.description)  #Getting command description
        elif group.help:
            group_embed.add_field(name=self._("Description:"), value=group.help)  #Fallback to help attribute if description does not exist
        if group.usage:
            group_embed.add_field(name=self._("Usage:"), value=f"**`{ctx.clean_prefix}{group.usage}`**", inline=False) #Getting command usage & formatting it
        aliases = []
        for alias in group.aliases:
            aliases.append(f"**`{ctx.clean_prefix}{alias}`**")  #Adding some custom formatting to each alias
        if aliases:
            group_embed.add_field(name=self._("Aliases:"), value=", ".join(aliases), inline=False)   #If any aliases exist, we add those to the embed in new field
        sub_cmds = []
        filtered = await self.filter_commands(group.walk_commands(), sort=True)
        for command in filtered:
            sub_cmds.append(self.get_subcommand_signature(ctx, group, command))
        if sub_cmds:
            sub_cmds = "\n".join(sub_cmds)
            group_embed.add_field(name=self._("Sub-commands:"), value=f"{sub_cmds}")
        channel = self.get_destination()
        await channel.send(embed=group_embed)

    async def send_error_message(self, error):   #Overriding the default help error message
        ctx = self.context
        self._ = ctx.bot.get_localization('help', ctx.bot.lang)
        embed=discord.Embed(title=ctx.bot.unknownCMDstr, description=self._("Use `{prefix}help` for a list of available commands.").format(prefix=ctx.prefix), color=ctx.bot.unknownColor)
        embed.set_footer(text=ctx.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
        channel = self.get_destination()
        await channel.send(embed=embed)


class Help(commands.Cog):
    '''Cog that implements a custom help command'''

    def __init__(self, bot):
        bot.help_command = SnedHelp()
        self.bot = bot

def setup(bot):
    logging.info("Adding cog: Help...")
    bot.add_cog(Help(bot))
