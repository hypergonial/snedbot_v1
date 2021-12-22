import asyncio
import datetime
import logging
import re

import discord
import Levenshtein as lev
from discord.ext import commands, tasks
from main import SnedBot

logger = logging.getLogger(__name__)

'''
The repo https://github.com/Rapptz/RoboDanny was massive help when writing this code,
and I used the same general structure as seen in /cogs/reminder.py there.
Also thanks to Vex#3110 from the discord.py discord for the original regex code, which
I tweaked to to be a bit more generally applicable (and possibly more shit) :verycool:
'''

async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)

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
    '''
    All timer-related functionality, including time conversion from strings,
    creation, scheduling & dispatching of timers.
    '''

    def __init__(self, bot:SnedBot):

        self.bot = bot
        self.current_timer = None
        self.currenttask = None
        self._ = self.bot.get_localization('timers', self.bot.lang)
        self.wait_for_active_timers.start() # pylint: disable=<no-member>



    def cog_unload(self):
        self.currenttask.cancel()
        self.wait_for_active_timers.cancel() # pylint: disable=<no-member>
    
    
    async def converttime(self, timestr : str, force_mode:str=None):
        '''
        Tries converting a string to datetime.datetime via regex, returns datetime.datetime and strings it extracted from if successful, otherwise raises ValueError
        Result of 12 hours of pain #remember
        '''

        logger.debug(f"String passed for time conversion: {timestr}")
        
        date_and_time_regex = re.compile(r"\d{4}-[0-1]\d-[0-3]\d [0-2]\d:[0-5]\d")
        date_regex = re.compile(r"\d{4}-[0-1]\d-[0-3]\d")
        date_and_time_match = date_and_time_regex.search(timestr)
        date_match = date_regex.search(timestr)
        if not force_mode or force_mode == "absolute":
            if date_and_time_match:
                time = datetime.datetime.strptime(date_and_time_match.group(), "%Y-%m-%d %H:%M")
                time = time.replace(tzinfo=datetime.timezone.utc)
                if time > datetime.datetime.now(datetime.timezone.utc):
                    return time, [date_and_time_match.group()]
                else:
                    raise ValueError("Date is not in the future.")
            elif date_match:
                time = datetime.datetime.strptime(date_match.group(), "%Y-%m-%d")
                time = time.replace(tzinfo=datetime.timezone.utc)
                if time > datetime.datetime.now(datetime.timezone.utc):
                    return time, [date_match.group()]
                else:
                    raise ValueError("Date is not in the future.")
        if not force_mode or force_mode == "relative": 
            #Relative time conversion
            #Get any pair of <number><word> with a single optional space in between, and return them as a dict (sort of)
            time_regex = re.compile(r"(\d+(?:[.,]\d+)?)\s{0,1}([a-zA-Z]+)")
            time_letter_dict = {"h":3600, "s":1, "m":60, "d":86400, "w":86400*7, "M":86400*30, "Y":86400*365, "y":86400*365}
            time_word_dict = {"hour":3600, "second":1, "minute":60, "day": 86400, "week": 86400*7, "month":86400*30, "year":86400*365, "sec": 1, "min": 60}
            matches = time_regex.findall(timestr)
            time = 0
            strings = [] #Stores all identified times
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
            logger.debug(f"Time: {time}")
            if time > 0:
                time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=time)
            else: #If time is 0, then we failed to parse or the user indeed provided 0, which makes no sense, so we raise an error.
                raise ValueError("Failed converting time from string. (Relative conversion)")
            return time, strings

    
    async def remindertime(self, timestr : str):
        '''
        Tries removing the times & dates from the beginning or end of a string, while converting the times to datetime object via converttime()
        Used to create a reminder note
        '''
        #Yeah this is stupid lol
        #TODO: Rework this garbage
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
        logger.debug("Getting latest timer...")
        result = await self.bot.pool.fetch('''SELECT * FROM timers WHERE expires < $1 ORDER BY expires LIMIT 1''', round((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).timestamp()))
        logger.debug(f"Latest timer from db: {result}")
        if len(result) != 0 and result[0]:
            timer = Timer(id=result[0].get('id'),guild_id=result[0].get('guild_id'),user_id=result[0].get('user_id'),channel_id=result[0].get('channel_id'),event=result[0].get('event'),expires=result[0].get('expires'),notes=result[0].get('notes'))
            #self.current_timer = timer
            logger.debug(f"Timer class created for latest: {timer}")
            return timer
    

    #The actual calling of the timer, deletes it from the db & dispatches the event
    async def call_timer(self, timer : Timer):
        logger.debug("Deleting timer entry {timerid}".format(timerid=timer.id))
        await self.bot.pool.execute('''DELETE FROM timers WHERE id = $1''', timer.id)
        #Set the currently evaluated timer to None
        self.current_timer = None
        logger.debug("Deleted")
        '''
        Dispatch an event named eventname_timer_complete, which will cause all listeners 
        for this event to fire. This function is not documented, so if anything breaks, it
        is probably in here. It passes on the Timer
        '''
        event = timer.event
        event_name = f'{event}_timer_complete'
        logger.debug("Dispatching: ", event_name)
        self.bot.dispatch(event_name, timer)
        logger.debug("Dispatched.")

    async def dispatch_timers(self):
        logger.debug("Dispatching timers.")
        try:
            while not self.bot.is_closed():
                logger.debug("Getting timer")
                timer = await self.get_latest_timer(days=40)
                self.current_timer=timer
                now = round(datetime.datetime.now(datetime.timezone.utc).timestamp())
                logger.debug(f"Now: {now}")
                logger.debug(f"Timer: {timer}")
                logger.debug("Has timer")
                if timer:
                    logger.debug("Evaluating timer.")
                    if timer.expires >= now:
                        sleep_time = (timer.expires - now)
                        logger.info(f"Awaiting next timer: '{timer.event}', which is in {sleep_time}s")
                        await asyncio.sleep(sleep_time)

                    logger.info(f"Dispatching timer: {timer.event}")
                    await self.call_timer(timer)
                else:
                    break #This is necessary because if on start-up there is no stored timer, it will go into an infinite loop
        
        except asyncio.CancelledError:
            raise
        except(OSError, discord.ConnectionClosed):
            self.currenttask.cancel()
            self.currenttask = self.bot.loop.create_task(self.dispatch_timers())

    async def update_timer(self, expires:datetime.datetime, entry_id:int, guild_id:int):
        '''Update a timer's expiry'''

        expires = round(expires.timestamp())
        await self.bot.pool.execute('''UPDATE timers SET expires = $1 WHERE id = $2 AND guild_id = $3''', expires, entry_id, guild_id)
        if self.current_timer and self.current_timer.id == entry_id:
            logger.debug("Updating timers resulted in reshuffling.")
            self.currenttask.cancel()
            self.currenttask = self.bot.loop.create_task(self.dispatch_timers())

    async def create_timer(self, expires:datetime.datetime, event:str, guild_id:int, user_id:int, channel_id:int=None, *, notes:str=None):
        '''Create a new timer, will dispatch on_<event>_timer_complete when finished.'''

        logger.debug(f"Expiry: {expires}")
        expires=round(expires.timestamp()) #Converting it to time since epoch
        await self.bot.pool.execute('''INSERT INTO timers (guild_id, channel_id, user_id, event, expires, notes) VALUES ($1, $2, $3, $4, $5, $6)''', guild_id, channel_id, user_id, event, expires, notes)
        logger.debug("Saved to database.")
        #If there is already a timer in queue, and it has an expiry that is further than the timer we just created
        #Then we reboot the dispatch_timers() function to re-check for the latest timer.
        if self.current_timer and expires < self.current_timer.expires:
            logger.debug("Reshuffled timers, this is now the latest timer.")
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
    
    @commands.command(aliases=["remindme", "remind"], usage="reminder <when>", help="Sets a reminder to the specified time.", description="""Sets a reminder to the specified time, with an optional message.
    **Time formatting:**

    __Relative:__
    `s` or `second(s)`
    `m` or `minute(s)`
    `h` or `hour(s)`
    `d` or `day(s)`
    `w` or `week(s)`
    `M` or `month(s)`
    `Y` or `year(s)`
    
    *Examples:* `reminder in 2 hours to go sleep` or `reminder 5d example message`
    
    __Absolute:__
    `YYYY-MM-dd hh-mm` (in UTC)
    `YYYY-MM-dd` (in UTC)

    *Examples:* `reminder 2021-04-03 12:35 example` or `reminder 2021-04-03 test`
    """)
    @commands.guild_only()
    async def reminder(self, ctx, *, timestr):
        if len(timestr) >= 1000:
            embed = discord.Embed(title="❌ " + self._("Reminder too long"), description=self._("Your reminder cannot exceed **1000** characters!"),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        await ctx.channel.trigger_typing()
        try:
            time, timestr = await self.remindertime(timestr)
            logger.debug(f"Received conversion: {time}")
            print(timestr)
        except ValueError as error:
            embed = discord.Embed(title=self.bot.errorDataTitle, description=self._("Your timeformat is invalid! Type `{prefix}help reminder` to see valid time formatting.\n**Error:** {error}").format(prefix=ctx.prefix, error=error),color=self.bot.errorColor)
            await ctx.send(embed=embed)
        else:
            if (time - datetime.datetime.now(datetime.timezone.utc)).total_seconds() >= 31536000*5:
                embed = discord.Embed(title=self.bot.errorDataTitle, description=self._("Sorry, but that's a bit too far in the future.").format(prefix=ctx.prefix),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                logger.debug(f"Timestrs length is: {len(timestr)}")
                if timestr is None or len(timestr) == 0:
                    timestr = "..."
                note = timestr+f"\n\n[Jump to original message!]({ctx.message.jump_url})"
                embed = discord.Embed(title="✅ " + self._("Reminder set"), description=self._("Reminder set for:  {timestamp} ({timestampR})").format(timestamp=discord.utils.format_dt(time), timestampR=discord.utils.format_dt(time, style='R')), color=self.bot.embedGreen)
                embed = self.bot.add_embed_footer(ctx, embed)
                await self.create_timer(expires=time, event="reminder", guild_id=ctx.guild.id,user_id=ctx.author.id, channel_id=ctx.channel.id, notes=note)
                await ctx.send(embed=embed)


    @commands.command(usage="reminders", help="Lists all reminders you have pending.", description="Lists all your pending reminders, you can get a reminder's ID here to delete it.", aliases=["myreminders", "listreminders"])
    @commands.guild_only()
    async def reminders(self, ctx):
        results = await self.bot.pool.fetch('''SELECT * FROM timers WHERE guild_id = $1 AND user_id = $2 ORDER BY expires LIMIT 10''', ctx.guild.id, ctx.author.id)
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
                    reminderstr = reminderstr + f"**ID: {timer.id}** - {discord.utils.format_dt(time)} ({discord.utils.format_dt(time, style='R')})\n{timer.notes}\n"
                else:
                    reminderstr = reminderstr + f"**ID: {timer.id}** - {discord.utils.format_dt(time)} ({discord.utils.format_dt(time, style='R')})\n"
        else:
            reminderstr = self._("You have no reminders. You can set one via `{prefix}reminder`!").format(prefix=ctx.prefix)
        embed=discord.Embed(title="✉️ " + self._("Your reminders:"),description=reminderstr, color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.send(embed=embed)
    
    @commands.command(usage="delreminder <reminder_ID>", help="Deletes a reminder.", description="Deletes a reminder by it's ID, which you can obtain via the `reminders` command.")
    @commands.guild_only()
    async def delreminder(self, ctx, ID : int):
        async with self.bot.pool.acquire() as con:
            result = await con.fetch('''SELECT ID FROM timers WHERE user_id = $1 AND id = $2 AND event = $3''', ctx.author.id, ID, "reminder")
            if result:
                await con.execute('''DELETE FROM timers WHERE user_id = $1 AND id = $2''', ctx.author.id, ID)
                embed = discord.Embed(title="✅ " + self._("Reminder deleted"), description=self._("Reminder **{ID}** has been deleted.").format(ID=ID), color=self.bot.embedGreen)
                embed = self.bot.add_embed_footer(ctx, embed)
                await ctx.send(embed=embed)
                #If we just deleted the currently running timer, then we re-evaluate to find the next timer.
                if self.current_timer and self.current_timer.id == int(ID):
                    self.currenttask.cancel()
                    self.currenttask = self.bot.loop.create_task(self.dispatch_timers())
            else:
                embed = discord.Embed(title="❌ " + self._("Reminder not found"), description=self._("Cannot find reminder with ID **{ID}**.").format(ID=ID), color=self.bot.errorColor)
                embed = self.bot.add_embed_footer(ctx, embed)
                await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_reminder_timer_complete(self, timer : Timer):
        logger.debug("on_reminder_timer_complete received.")
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
                    logger.info(f"Failed to deliver a reminder to user {user}.")
                    return

def setup(bot):
    logger.info("Adding cog: Timers...")
    bot.add_cog(Timers(bot))
