import asyncio
import logging

import discord
from discord.ext import commands

async def hasOwner(ctx):
    return await ctx.bot.CommandChecks.hasOwner(ctx)
async def hasPriviliged(ctx):
    return await ctx.bot.CommandChecks.hasPriviliged(ctx)

class KeepOnTop(commands.Cog, name="Keep On Top"):
    
    def __init__(self, bot):
        self.bot = bot
        async def init_table():
            async with bot.pool.acquire() as con:
                await con.execute('''
                CREATE TABLE IF NOT EXISTS public.ktp
                (
                    guild_id bigint NOT NULL,
                    ktp_id serial NOT NULL,
                    ktp_channel_id bigint NOT NULL,
                    ktp_msg_id bigint NOT NULL,
                    ktp_content text NOT NULL,
                    PRIMARY KEY (guild_id, ktp_id),
                    FOREIGN KEY (guild_id)
                        REFERENCES global_config (guild_id)
                        ON DELETE CASCADE
                )''')
        bot.loop.run_until_complete(init_table())
    
    @commands.Cog.listener()
    async def on_message(self, message):
        '''
        Check if the message is no longer on top, delete the old, and move it to the "top" again
        Also update the message ID so we know which one to delete next time
        '''
        if message.guild:
            async with self.bot.pool.acquire() as con:
                results = await con.fetch('''SELECT * FROM ktp WHERE guild_id = $1''', message.guild.id)
                for result in results:
                    if result.get('ktp_channel_id') == message.channel.id and result.get('ktp_content') != message.content and result.get('ktp_msg_id') != message.id:
                        channel = message.channel
                        previous_top = channel.get_partial_message(result.get('ktp_msg_id'))
                        try:
                            await previous_top.delete() #Necessary to put in a try/except otherwise on a spammy channel this might spam the console to hell
                        except discord.errors.NotFound:
                            return
                        new_top = await channel.send(content=result.get('ktp_content'))
                        await con.execute('''UPDATE ktp SET ktp_msg_id = $1 WHERE guild_id = $2 AND ktp_id = $3''', new_top.id, message.guild.id, result.get('ktp_id'))
                        break


    @commands.group(aliases=["ktp"], help="Lists all keep-on-top messages. Subcommands can add/remove them.", description="Helps you list/manage keep-on-top messages. Keep-on-top messages are messages that are always the last message in the given channel, effectively being pinned.", usage="keepontop", invoke_without_command=True, case_insensitive=True)
    @commands.check(hasPriviliged)
    async def keepontop(self, ctx):
        '''
        Lets you "pin" a message to the top of a channel by 
        it being removed & resent by the bot every time a new message is
        sent in that channel.
        '''
        async with ctx.bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM ktp WHERE guild_id = $1''', ctx.guild.id)
            if results and len(results) != 0:
                text = ""
                for result in results:
                    text = f"{text}**#{result.get('ktp_id')}** - {ctx.guild.get_channel(result.get('ktp_channel_id')).mention}\n"
                embed=discord.Embed(title="Keep-On-Top messages for this server:", description=text, color=self.bot.embedBlue)
                await ctx.send(embed=embed)
            else:
                embed=discord.Embed(title="❌ Error: No keep-on-top messages", description="There are no keep-on-top messages for this server.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)

    @keepontop.command(name="add", aliases=["create", "new", "setup"], help="Initializes a setup to add a new keep-on-top message.", description="Initializes a setup to start configuring a new keep-on-top message. A server can have up to **3** keep-on-top messages. Takes no arguments.", usage="keepontop add")
    @commands.check(hasPriviliged)
    async def ktp_add(self, ctx):

        async with self.bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM ktp WHERE guild_id = $1''', ctx.guild.id)
        
        if results and len(results) >= 1:
            embed=discord.Embed(title="❌ Error: Too many keep-on-top messages", description="A server can only have up to **1** keep-on-top message(s) at a time.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return

        embed=discord.Embed(title="🛠️ Keep-On-Top Setup", description="Specify the channel where you want to keep a message on the top by mentioning it!", color=self.bot.embedBlue)
        await ctx.channel.send(embed=embed)
        try :
            def check(payload):
                return payload.author == ctx.author and payload.channel.id == ctx.channel.id
            payload = await self.bot.wait_for('message', timeout=60.0, check=check)
            ktp_channel = await commands.TextChannelConverter().convert(ctx, payload.content)

            for result in results:
                if result.get('ktp_channel_id') == ktp_channel.id:
                    embed=discord.Embed(title="❌ Error: Duplicate entry", description="You cannot have two keep-on-top messages in the same channel!", color=self.bot.errorColor)
                    await ctx.channel.send(embed=embed)
                    return

            embed=discord.Embed(title="🛠️ Keep-On-Top Setup", description=f"Channel set to {ktp_channel.mention}!", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)

            embed=discord.Embed(title="🛠️ Keep-On-Top Setup", description="Now type in the message you want to be kept on top!", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            payload = await self.bot.wait_for('message', timeout=300.0, check=check)
            ktp_content = payload.content
            first_top = await ktp_channel.send(ktp_content)

            async with self.bot.pool.acquire() as con:
                await con.execute('''
                INSERT INTO ktp (guild_id, ktp_channel_id, ktp_msg_id, ktp_content)
                VALUES ($1, $2, $3, $4)
                ''', ctx.guild.id, ktp_channel.id, first_top.id, ktp_content)

            embed=discord.Embed(title="🛠️ Keep-On-Top Setup", description=f"✅ Setup completed. This message will now be kept on top of {ktp_channel.mention}!", color=self.bot.embedGreen)
            await ctx.channel.send(embed=embed)

        except commands.ChannelNotFound:
            embed=discord.Embed(title="❌ Error: Unable to locate channel.", description="The setup process has been cancelled.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
    
    @keepontop.command(name="delete", aliases=["del", "remove"], help="Removes a keep-on-top message.", description="Removes a keep-on-top message entry, stopping the bot from keeping it on top anymore. You can get the keep-on-top entry ID via the `keepontop` command.", usage="keepontop delete <ID>")
    @commands.check(hasPriviliged)
    async def ktp_delete(self, ctx, id:int):
        async with self.bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM ktp WHERE guild_id = $1 AND ktp_id = $2''', ctx.guild.id, id)
            if results and len(results) != 0:
                await con.execute('''DELETE FROM ktp WHERE guild_id = $1 AND ktp_id = $2''', ctx.guild.id, id)
                embed=discord.Embed(title="✅ Keep-on-top message deleted", description="Keep-on-top message entry deleted and will no longer be kept in top!", color=self.bot.embedGreen)
                await ctx.channel.send(embed=embed)
            else:
                embed=discord.Embed(title="❌ Error: Not found", description="There is no keep-on-top entry by that ID.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)






def setup(bot):
    logging.info("Adding cog: KeepOnTop...")
    bot.add_cog(KeepOnTop(bot))
