import asyncio
import datetime
import gettext
import logging
import re

import asyncpg
import discord
import Levenshtein as lev
from discord.ext import commands, tasks

'''
The repo https://github.com/Rapptz/RoboDanny was massive help when writing this code,
and I used the same general structure as seen in /cogs/reminder.py there.
Also thanks to Vex#3110 from the discord.py discord for the original regex code, which
I tweaked to to be a bit more generally applicable (and possibly more shit) :verycool:
'''

async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_priviliged(ctx):
    return await ctx.bot.custom_checks.has_priviliged(ctx)

class Timer():
    '''
    Represents a timer object.
    '''
    def __init__(self, id, guild_id, user_id,event, channel_id=None, expires=None, notes=None):
        self.id = id
        self.guild_id = guild_id
        self.user_id = user_id
        self.channel_id = channel_id
        self.event = event
        self.expires = expires
        self.notes = notes

class Timers(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.current_timer = None
        self.currenttask = None
        self._ = self.bot.get_localization('timers', self.bot.lang)
        self.wait_for_active_timers.start() # pylint: disable=<no-member>



    def cog_unload(self):
        self.currenttask.cancel()
        self.wait_for_active_timers.cancel() # pylint: disable=<no-member>
    
    
    async def converttime(self, timestr : str):
        '''
        Tries converting a string to datetime.datetime via regex, returns datetime.datetime and strings it extracted from if successful, otherwise raises ValueError
        Result of 12 hours of pain #remember
        '''
        logging.debug(f"String passed: {timestr}")
        #timestr = timestr.replace(' ', '')
        #Get any pair of <number><word> with a single optional space in between, and return them as a dict (sort of)
        time_regex = re.compile(r"(\d+(?:[.,]\d+)?)\s{0,1}([a-zA-Z]+)")
        time_letter_dict = {"h":3600, "s":1, "m":60, "d":86400, "w":86400*7, "M":86400*30, "Y":86400*365, "y":86400*365}
        time_word_dict = {"hour":3600, "second":1, "minute":60, "day": 86400, "week": 86400*7, "month":86400*30, "year":86400*365, "sec": 1, "min": 60}
        matches = time_regex.findall(timestr)
        time = 0
        strings = [] #Stores all identified times
        logging.debug(f"Matches: {matches}")
        for val, category in matches:
            val = val.replace(',', '.') #Replace commas with periods to correctly register decimal places
            #If this is a single letter
            if len(category) == 1:
                if category in time_letter_dict.keys():
                    strings.append(val + category)
                    strings.append(val + " " + category) #Append both with space & without
                    time += time_letter_dict[category]*float(val)
            else:
                #If a partial match is found with any of the keys
                #Reason for making the same code here is because words are case-insensitive, as opposed to single letters
                for string in time_word_dict.keys():
                    if lev.distance(category.lower(), string.lower()) <= 1: #If str has 1 or less different letters (For plural) pylint: disable=<no-member>
                        time += time_word_dict[string]*float(val)
                        strings.append(val + category)
                        strings.append(val + " " + category)
                        break
        logging.debug(f"Time: {time}")
        if time > 0:
            time = datetime.datetime.utcnow() + datetime.timedelta(seconds=time)
        else: #If time is 0, then we failed to parse or the user indeed provided 0, which makes no sense, so we raise an error.
             raise ValueError("Failed converting time from string.")
        return time, strings

    
    async def remindertime(self, timestr : str):
        '''
        Tries removing the times & dates from the beginning or end of a string, while converting the times to datetime object via converttime()
        Used to create a reminder note
        '''
        #Yeah this is stupid lol
        time, strings = await self.converttime(timestr)

        for string in strings:
            timestr = timestr.strip()
            if timestr.startswith(string):
                timestr = timestr.replace(string, "")
            elif timestr.startswith("in " + string + " to"):
                timestr = timestr.replace("in " + string + " to", "")
            elif timestr.startswith("in " + string):
                 timestr = timestr.replace("in " + string, "")
            elif timestr.startswith(string + " from now"):
                 timestr = timestr.replace(string + " from now", "")
            elif timestr.startswith(string + " later"):
                 timestr = timestr.replace(string + " later", "")
            elif timestr.startswith("to "):
                timestr = timestr[3 : len(timestr)]
            elif timestr.startswith("for "):
                timestr = timestr[4 : len(timestr)]
            elif timestr.startswith("and "):
                timestr = timestr[4 : len(timestr)]
            if timestr.startswith(" "):
                timestr = timestr[1 : len(timestr)]

        for string in strings:
            timestr = timestr.strip()
            if timestr.endswith("in " + string):
                timestr = timestr.replace("in " + string, "")
            elif timestr.endswith("after " + string):
                timestr = timestr.replace("after" + string, "")
            elif timestr.endswith("in " + string + " from now"):
                timestr = timestr.replace("in " + string + " from now", "")
            elif timestr.endswith(string + " from now"):
                timestr = timestr.replace(string + " from now", "")
            elif timestr.endswith(string + " later"):
                timestr = timestr.replace(string + " later", "")
            elif timestr.endswith(string):
                timestr = timestr.replace(string, "")
        
        timestr = timestr.capitalize()
        return time, timestr

    #Gets the first timer that is about to expire in X days, and returns it. Return None if no timers are found in that scope.
    async def get_latest_timer(self, days=7):
        await self.bot.wait_until_ready() #This must be included or you get a lot of NoneType errors while booting up, and timers do not get delivered
        logging.debug("Getting latest timer...")
        async with self.bot.pool.acquire() as con:
            result = await con.fetch('''SELECT * FROM timers WHERE expires < $1 ORDER BY expires LIMIT 1''', round((datetime.datetime.utcnow() + datetime.timedelta(days=days)).timestamp()))
            logging.debug(f"Latest timer from db: {result}")
            if len(result) != 0 and result[0]:
                timer = Timer(id=result[0].get('id'),guild_id=result[0].get('guild_id'),user_id=result[0].get('user_id'),channel_id=result[0].get('channel_id'),event=result[0].get('event'),expires=result[0].get('expires'),notes=result[0].get('notes'))
                #self.current_timer = timer
                logging.debug(f"Timer class created for latest: {timer}")
                return timer
    

    #The actual calling of the timer, deletes it from the db & dispatches the event
    async def call_timer(self, timer : Timer):
        logging.debug("Deleting timer entry {timerid}".format(timerid=timer.id))
        async with self.bot.pool.acquire() as con:
            await con.execute('''DELETE FROM timers WHERE id = $1''', timer.id)
            #Set the currently evaluated timer to None
            self.current_timer = None
            logging.debug("Deleted")
            '''
            Dispatch an event named eventname_timer_complete, which will cause all listeners 
            for this event to fire. This function is not documented, so if anything breaks, it
            is probably in here. It passes on the Timer
            '''
            logging.debug("Dispatching..")
            event = timer.event
            event_name = f'{event}_timer_complete'
            logging.debug(event_name)
            self.bot.dispatch(event_name, timer)
            logging.debug("Dispatched.")

    async def dispatch_timers(self):
        logging.debug("Dispatching timers.")
        try:
            while not self.bot.is_closed():
                logging.debug("Getting timer")
                timer = await self.get_latest_timer(days=40)
                self.current_timer=timer
                now = round(datetime.datetime.utcnow().timestamp())
                logging.debug(f"Now: {now}")
                logging.debug(f"Timer: {timer}")
                logging.debug("Has timer")
                if timer:
                    logging.debug("Evaluating timer.")
                    if timer.expires >= now:
                        sleep_time = (timer.expires - now)
                        logging.info(f"Awaiting next timer: '{timer.event}', which is in {sleep_time}s")
                        await asyncio.sleep(sleep_time)

                    logging.info(f"Dispatching timer: {timer.event}")
                    await self.call_timer(timer)
                else:
                    break #This is necessary because if on start-up there is no stored timer, it will go into an infinite loop
        
        except asyncio.CancelledError:
            raise
        except(OSError, discord.ConnectionClosed):
            self.currenttask.cancel()
            self.currenttask = self.bot.loop.create_task(self.dispatch_timers())

    async def create_timer(self, expires:datetime.datetime, event:str, guild_id:int, user_id:int, channel_id:int=None, *, notes:str=None):
        logging.debug(f"Expiry: {expires}")
        expires=round(expires.timestamp()) #Converting it to time since epoch
        async with self.bot.pool.acquire() as con:
            await con.execute('''INSERT INTO timers (guild_id, channel_id, user_id, event, expires, notes) VALUES ($1, $2, $3, $4, $5, $6)''', guild_id, channel_id, user_id, event, expires, notes)
        logging.debug("Saved to database.")
        #If there is already a timer in queue, and it has an expiry that is further than the timer we just created
        #Then we reboot the dispatch_timers() function to re-check for the latest timer.
        if self.current_timer and expires < self.current_timer.expires:
            logging.debug("Reshuffled timers, this is now the latest timer.")
            self.currenttask.cancel()
            self.currenttask = self.bot.loop.create_task(self.dispatch_timers())
        elif self.current_timer is None:
            self.currenttask = self.bot.loop.create_task(self.dispatch_timers())

    #Loop every hour to check if any timers entered the 40 day max sleep range if we have no timers queued
    #This allows us to have timers of infinite length practically
    @tasks.loop(hours=1.0)
    async def wait_for_active_timers(self):
        if self.currenttask is None:
            self.currenttask = self.bot.loop.create_task(self.dispatch_timers())
    
    @commands.command(aliases=["remindme", "remind"], usage="reminder <when>", help="Sets a reminder to the specified time.", description="Sets a reminder to the specified time, with an optional message.\n\n**Time formatting:**\n`s` or `second(s)`\n`m` or `minute(s)`\n`h` or `hour(s)`\n`d` or `day(s)`\n`w` or `week(s)`\n`M` or `month(s)`\n`Y` or `year(s)`\n\n**Example:** `reminder in 2 hours to go sleep` or `reminder 5d example message`")
    @commands.guild_only()
    async def reminder(self, ctx, *, timestr):
        if len(timestr) >= 1000:
            embed = discord.Embed(title="❌ " + self._("Reminder too long"), description=self._("Your reminder cannot exceed **1000** characters!"),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        await ctx.channel.trigger_typing()
        try:
            time, timestr = await self.remindertime(timestr)
            logging.debug(f"Received conversion: {time}")
            print(timestr)
        except ValueError:
            embed = discord.Embed(title=self.bot.errorDataTitle, description=self._("Your timeformat is invalid! Type `{prefix}help reminder` to see valid time formatting.").format(prefix=ctx.prefix),color=self.bot.errorColor)
            await ctx.send(embed=embed)
        else:
            if (time - datetime.datetime.utcnow()).total_seconds() >= 31536000*5:
                embed = discord.Embed(title=self.bot.errorDataTitle, description=self._("Sorry, but that's a bit too far in the future.").format(prefix=ctx.prefix),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                logging.debug(f"Timestrs length is: {len(timestr)}")
                if timestr is None or len(timestr) == 0:
                    timestr = "..."
                note = timestr+f"\n\n[Jump to original message!]({ctx.message.jump_url})"
                embed = discord.Embed(title="✅ " + self._("Reminder set"), description=self._("Reminder set for:  {timestamp} ({timestampR})").format(timestamp=f"<t:{round(time.replace(tzinfo=datetime.timezone.utc).timestamp())}>", timestampR=f"<t:{round(time.replace(tzinfo=datetime.timezone.utc).timestamp())}:R>"), color=self.bot.embedGreen)
                embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
                await self.create_timer(expires=time, event="reminder", guild_id=ctx.guild.id,user_id=ctx.author.id, channel_id=ctx.channel.id, notes=note)
                await ctx.send(embed=embed)


    @commands.command(usage="reminders", help="Lists all reminders you have pending.", description="Lists all your pending reminders, you can get a reminder's ID here to delete it.", aliases=["myreminders", "listreminders"])
    @commands.guild_only()
    async def reminders(self, ctx):
        async with self.bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM timers WHERE guild_id = $1 AND user_id = $2 ORDER BY expires LIMIT 10''', ctx.guild.id, ctx.author.id)
        timers = []
        reminderstr = ""
        for result in results :
            if result.get('event') == "reminder":
                note_stripped = result.get('notes').replace("\n", " ") #Avoid the reminder dialog breaking
                note_stripped = note_stripped.split("[Jump to original message!]")[0] #Remove jump url
                if len(note_stripped) > 50:
                    note_stripped = f"{note_stripped[slice(47)]}..."
                timers.append(Timer(id=result.get('id'),guild_id=result.get('guild_id'),user_id=result.get('user_id'),channel_id=result.get('channel_id'),event=result.get('event'),expires=result.get('expires'),notes=note_stripped))      

        if len(timers) != 0:
            for timer in timers:
                time = datetime.datetime.fromtimestamp(timer.expires)
                if timer.notes:
                    reminderstr = reminderstr + f"**ID: {timer.id}** - <t:{round(time.replace(tzinfo=datetime.timezone.utc).timestamp())}> (<t:{round(time.replace(tzinfo=datetime.timezone.utc).timestamp())}:R>)\n{timer.notes}\n"
                else:
                    reminderstr = reminderstr + f"**ID: {timer.id}** - <t:{round(time.replace(tzinfo=datetime.timezone.utc).timestamp())}> (<t:{round(time.replace(tzinfo=datetime.timezone.utc).timestamp())}:R>)\n"
        else:
            reminderstr = self._("You have no reminders. You can set one via `{prefix}reminder`!").format(prefix=ctx.prefix)
        embed=discord.Embed(title="✉️ " + self._("Your reminders:"),description=reminderstr, color=self.bot.embedBlue)
        embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
    
    @commands.command(usage="delreminder <reminder_ID>", help="Deletes a reminder.", description="Deletes a reminder by it's ID, which you can obtain via the `reminders` command.")
    @commands.guild_only()
    async def delreminder(self, ctx, ID : int):
        async with self.bot.pool.acquire() as con:
            result = await con.fetch('''SELECT ID FROM timers WHERE user_id = $1 AND id = $2 AND event = $3''', ctx.author.id, ID, "reminder")
            if result:
                await con.execute('''DELETE FROM timers WHERE user_id = $1 AND id = $2''', ctx.author.id, ID)
                embed = discord.Embed(title="✅ " + self._("Reminder deleted"), description=self._("Reminder **{ID}** has been deleted.").format(ID=ID), color=self.bot.embedGreen)
                embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=embed)
                #If we just deleted the currently running timer, then we re-evaluate to find the next timer.
                if self.current_timer and self.current_timer.id == int(ID):
                    self.currenttask.cancel()
                    self.currenttask = self.bot.loop.create_task(self.dispatch_timers())
            else:
                embed = discord.Embed(title="❌ " + self._("Reminder not found"), description=self._("Cannot find reminder with ID **{ID}**.").format(ID=ID), color=self.bot.errorColor)
                embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
                await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_reminder_timer_complete(self, timer : Timer):
        logging.debug("on_reminder_timer_complete received.")
        guild = self.bot.get_guild(timer.guild_id)
        if guild is None: #Check if bot did not leave guild
            return
        channel = await self.bot.fetch_channel(timer.channel_id)
        if guild.get_member(timer.user_id) != None: #Check if user did not leave guild
            user = guild.get_member(timer.user_id)
            embed=discord.Embed(title="✉️ " + self._("{user}, your reminder:").format(user=user.name), description=f"{timer.notes}", color=self.bot.embedBlue)
            try:
                await channel.send(embed=embed, content=user.mention)
            except (discord.Forbidden, discord.HTTPException, discord.errors.NotFound) :
                try: #Fallback to DM if cannot send in channel
                    await user.send(embed=embed, content="I lost access to the channel this reminder was sent from, so here it is!")
                except discord.Forbidden:
                    logging.info(f"Failed to deliver reminder to user {user}.")
                    return

def setup(bot):
    logging.info("Adding cog: Timers...")
    bot.add_cog(Timers(bot))
