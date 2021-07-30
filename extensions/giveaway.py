import asyncio
import datetime
import logging
import random

import discord
from discord.ext import commands


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)


class Giveaway(commands.Cog):
    '''
    Miscellanious featureset to create giveaways. It 100% uses the existing timer structure,
    with no additional database/storage features. I wrote it in like 3 hours so it might suck. :)
    '''
    def __init__(self, bot):
        self.bot = bot
        self._ = self.bot.get_localization('giveaway', self.bot.lang)
    
    async def cog_check(self, ctx):
        return await ctx.bot.custom_checks.has_permissions(ctx, 'giveaway') or await ctx.bot.custom_checks.has_permissions(ctx, 'mod_permitted')

    @commands.group(help="Create and manage giveaways. See sub-commands for more.", description="Create and manage giveaways on this server. See sub-commands below.", usage="giveaway [subcommand]", invoke_without_command=True, case_insensitive=True)
    async def giveaway(self, ctx):
        await ctx.send_help(ctx.command)

    @giveaway.command(name="create", help="Starts the giveaway creation wizard.", description="Starts the giveaway creation wizard to help you set up a new giveaway.", usage="giveaway create")
    async def giveaway_create(self, ctx):
        cogs = await self.bot.current_cogs()
        if "Timers" not in cogs:
            embed=discord.Embed(title=self.bot.errorMissingModuleTitle, description="This setup requires the extension `timers` to be active.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        embed=discord.Embed(title="🛠️ Giveaway creator", description="Please mention the channel where the giveaway message should be sent!", color=self.bot.embedBlue)
        await ctx.channel.send(embed=embed)
        def check(message):
            return message.author == ctx.author and message.channel.id == ctx.channel.id
        try:
            message = await self.bot.wait_for('message', timeout=60.0, check=check)
            giveaway_channel = await commands.TextChannelConverter().convert(ctx, message.content)
            embed=discord.Embed(title="🛠️ Giveaway creator", description="Now specify the amount of winners by typing in a number!", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            message = await self.bot.wait_for('message', timeout=60.0, check=check)
            try:
                winners = int(message.content)
            except (ValueError, TypeError):
                embed=discord.Embed(title="❌ Error: Invalid value", description="Invalid value entered. Operation cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return

            embed=discord.Embed(title="🛠️ Giveaway creator", description="How long should the giveaway last? Examples: `12 hours` or `7 days and 5 minutes`", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            message = await self.bot.wait_for('message', timeout=60.0, check=check)
            try:
                time, timestr = await self.bot.get_cog("Timers").converttime(message.content)
            except ValueError:
                embed=discord.Embed(title="❌ Error: Invalid value", description="Invalid time entered. Operation cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return


            embed=discord.Embed(title="🛠️ Giveaway creator", description="Now, as a last step, type in what you are going to give away! This will show up in the message part of the giveaway.", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            message = await self.bot.wait_for('message', timeout=60.0, check=check)
            giveaway_text = message.content

            try:
                embed = discord.Embed(title="🎉 Giveaway!", description=f"""**{giveaway_text}**
                **-------------**
                **End date:** {discord.utils.format_dt(time, style='F')}
                **Number of winners:** `{winners}`""", color=0xd76b00)
                embed.set_footer(text=f"Hosted by {ctx.author}", icon_url=ctx.author.avatar.url)
                giveaway_msg = await giveaway_channel.send(embed=embed)
                await giveaway_msg.add_reaction("🎉")
                embed = discord.Embed(title="✅ " + "Giveaway created", description="Giveaway created successfully!", color=self.bot.embedGreen)
                await ctx.send(embed=embed)
            except Exception as error:
                embed=discord.Embed(title="❌ Error: Cannot send message", description=f"Unable to send the giveaway message to the given channel.\n**Error:** ```{error}```", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return


            await self.bot.get_cog("Timers").create_timer(expires=time, event="giveaway", guild_id=ctx.guild.id, user_id=ctx.author.id, channel_id=giveaway_channel.id, notes=f"{giveaway_msg.id}\n{winners}")
            

        except commands.ChannelNotFound:
            embed=discord.Embed(title="❌ Error: Channel not found", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        except asyncio.TimeoutError:
            embed=discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return

    @giveaway.command(name="list", usage="giveaway list", help="Lists all running giveaways for the server.", description="Lists all running giveaways for this server, and their ID. Displays only up to 10 entries.")
    @commands.guild_only()
    async def giveaway_list(self, ctx):
        async with self.bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM timers WHERE guild_id = $1 AND user_id = $2 AND event = $3 ORDER BY expires LIMIT 10''', ctx.guild.id, ctx.author.id, "giveaway")
        giveaways = []
        list_str = ""

        if len(results) != 0:
            for result in results:
                time = datetime.datetime.fromtimestamp(result.get('expires'))
                channel = self.bot.get_channel(result.get('channel_id'))
                list_str = list_str + f"**ID: {result.get('id')}** - {channel.mention} - Concludes: {discord.utils.format_dt(time)}\n"
        else:
            list_str = self._("There are currently no running giveaways on this server. You can create one via `{prefix}giveaway create`!").format(prefix=ctx.prefix)
        embed=discord.Embed(title="🎉 " + self._("List of giveaways:"),description=list_str, color=self.bot.embedBlue)
        embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
        await ctx.send(embed=embed)

    @giveaway.command(name="cancel", aliases=["del", "delete", "remove"], usage="giveaway delete <giveaway_ID>", help="Cancels a running giveaway.", description="Cancels a giveaway by it's ID, which you can obtain via the `giveaway list` command.")
    @commands.guild_only()
    async def giveaway_delete(self, ctx, ID : int):
        async with self.bot.pool.acquire() as con:
            result = await con.fetch('''SELECT * FROM timers WHERE event = $1 AND id = $2''', "giveaway", ID)
            if result:
                await con.execute('''DELETE FROM timers WHERE event = $1 AND id = $2''', "giveaway", ID)
                embed = discord.Embed(title="✅ " + self._("Giveaway deleted"), description=self._("Giveaway **{ID}** has been cancelled and deleted.").format(ID=ID), color=self.bot.embedGreen)
                await ctx.send(embed=embed)
                #If we just deleted the currently running timer, then we re-evaluate to find the next timer.
                if self.bot.get_cog("Timers").current_timer and self.bot.get_cog("Timers").current_timer.id == int(ID):
                    self.bot.get_cog("Timers").currenttask.cancel()
                    self.bot.get_cog("Timers").currenttask = self.bot.get_cog("Timers").bot.loop.create_task(self.bot.get_cog("Timers").dispatch_timers())
            else:
                embed = discord.Embed(title="❌ " + self._("Giveaway not found"), description=self._("Cannot find giveaway with ID **{ID}**.").format(ID=ID), color=self.bot.errorColor)
                embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
                await ctx.send(embed=embed)

    @giveaway.command(name="end", aliases=["terminate"], usage="giveaway end <giveaway_ID>", help="Forces a running giveaway to end.", description="Forces a running giveaway to conclude, causing the winners to be calculated immediately.")
    @commands.guild_only()
    async def giveaway_terminate(self, ctx, ID : int):
        async with self.bot.pool.acquire() as con:
            result = await con.fetch('''SELECT * FROM timers WHERE event = $1 AND id = $2''', "giveaway", ID)
            if result:
                await con.execute('''DELETE FROM timers WHERE event = $1 AND id = $2''', "giveaway", ID)
                embed = discord.Embed(title="✅ " + self._("Giveaway terminated"), description=self._("Giveaway **{ID}** has been forced to end, and winners have been calculated.").format(ID=ID), color=self.bot.embedGreen)
                await ctx.send(embed=embed)
                #If we just deleted the currently running timer, then we re-evaluate to find the next timer.
                if self.bot.get_cog("Timers").current_timer and self.bot.get_cog("Timers").current_timer.id == int(ID):
                    self.bot.get_cog("Timers").currenttask.cancel()
                    self.bot.get_cog("Timers").currenttask = self.bot.get_cog("Timers").bot.loop.create_task(self.bot.get_cog("Timers").dispatch_timers())


                #Calculating the winners
                channel = self.bot.get_channel(result[0].get('channel_id'))
                message = await channel.fetch_message(int(result[0].get('notes').split("\n")[0]))
                embed = message.embeds[0]

                for reaction in message.reactions:
                    if reaction.emoji == "🎉":
                        tada_react = reaction
                users = await tada_react.users().flatten()
                for user in users:
                    if user.bot:    users.remove(user)

                winner_count = int(result[0].get('notes').split('\n')[1])

                if len(users) >= winner_count:
                    winners = []
                    for i in range(0, winner_count):
                        winners.append(random.choice(users))
                        users.remove(winners[len(winners)-1])
                    
                    winners_str = "\n".join([f"{winner.mention} `({winner.name}#{winner.discriminator})`" for winner in winners])
                    embed.description = f"{embed.description}\n\n**Winners:**\n {winners_str}"
                    await message.edit(embed=embed)

                    winner_mentions = ", ".join([winner.mention for winner in winners])
                    await channel.send(f"Giveaway was forced to terminate by a moderator.\n{winner_mentions} **won the giveaway!** 🎉")
                else:
                    err_embed=discord.Embed(title="🎉 Not enough participants", description="The giveaway was forced to end by a moderator with insufficient participants.", color=self.bot.errorColor)
                    err_embed.set_footer(text="Hint: You could try lowering the amount of winners.")
                    await channel.send(embed=err_embed)


            else:
                embed = discord.Embed(title="❌ " + self._("Giveaway not found"), description=self._("Cannot find giveaway with ID **{ID}**.").format(ID=ID), color=self.bot.errorColor)
                embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
                await ctx.send(embed=embed)


    
    @commands.Cog.listener()
    async def on_giveaway_timer_complete(self, timer):
        channel = self.bot.get_channel(timer.channel_id)
        message = await channel.fetch_message(int(timer.notes.split("\n")[0]))
        embed = message.embeds[0]

        for reaction in message.reactions:
            if reaction.emoji == "🎉":
                tada_react = reaction
        users = await tada_react.users().flatten()
        for user in users:
            if user.bot:    users.remove(user)

        winner_count = int(timer.notes.split('\n')[1])

        if len(users) >= winner_count:
            winners = []
            for i in range(0, winner_count):
                winners.append(random.choice(users))
                users.remove(winners[len(winners)-1])
            
            winners_str = "\n".join([f"{winner.mention} `({winner.name}#{winner.discriminator})`" for winner in winners])
            embed.description = f"{embed.description}\n\n**Winners:**\n {winners_str}"
            await message.edit(embed=embed)

            winner_mentions = ", ".join([winner.mention for winner in winners])
            await channel.send(f"{winner_mentions} **won the giveaway!** 🎉")
        else:
            err_embed=discord.Embed(title="🎉 Not enough participants", description="The giveaway ended with insufficient participants.", color=self.bot.errorColor)
            err_embed.set_footer(text="Hint: You could try lowering the amount of winners.")
            await channel.send(embed=err_embed)


def setup(bot):
    logging.info('Adding cog: Giveaway...')
    bot.add_cog(Giveaway(bot))
