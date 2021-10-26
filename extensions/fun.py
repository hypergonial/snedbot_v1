import asyncio
import datetime
import logging
import os
import random
from pathlib import Path
from textwrap import fill

import aiohttp
import discord
import Levenshtein as lev
import uwuify
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)

logger = logging.getLogger(__name__)

class Fun(commands.Cog):
    '''All the fun!'''

    def __init__(self, bot):
        self.bot = bot
        self._ = self.bot.get_localization('fun', self.bot.lang)

    async def cog_check(self, ctx):
        return await ctx.bot.custom_checks.has_permissions(ctx, 'fun') or await ctx.bot.custom_checks.has_permissions(ctx, 'mod_permitted')

    @commands.command(help="Displays a user's avatar.", description="Displays a user's avatar for your viewing (or stealing) pleasure.", usage=f"avatar [user]")
    @commands.cooldown(1, 10, type=commands.BucketType.member)
    @commands.guild_only()
    async def avatar(self, ctx, member:discord.Member=None) :
        if not member: member=ctx.author
        embed=discord.Embed(title=self._("{member_name}'s avatar:").format(member_name=member.name), color=member.colour)
        embed.set_image(url=member.avatar.url)
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.channel.send(embed=embed)

    @commands.command(aliases=["typerace"], help="See who can type the fastest!", description="Starts a typerace where you can see who can type the fastest. You can optionally specify the difficulty and the length of the race.\n\n**Difficulty options:**\n`easy` - 1-4 letter words\n`medium` - 5-8 letter words (Default)\n`hard` 9+ letter words\n\n**Length:**\n`1-20` - (Default: `5`) Specifies the amount of words in the typerace", usage="typeracer [difficulty] [length]")
    @commands.max_concurrency(1, per=commands.BucketType.channel,wait=False)
    async def typeracer(self, ctx, difficulty:str="medium", length=5):
        if length not in range(1, 21) or difficulty.lower() not in ("easy", "medium", "hard"):
            embed=discord.Embed(title="🏁 " + self._("Typeracer"), description=self._("Invalid data entered! Check `{prefix}help typeracer` for more information.").format(prefix=ctx.prefix), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(title="🏁 " + self._("Typeracing begins in 10 seconds!"), description=self._("Prepare your keyboard of choice!"), color=self.bot.embedBlue)
        await ctx.send(embed=embed)
        await asyncio.sleep(10)
        words_path = Path(self.bot.BASE_DIR, 'etc', f'words_{difficulty.lower()}.txt')
        with open(words_path, 'r') as fp:
            words = fp.readlines()
        text = []
        words = [x.strip() for x in words]
        for i in range (0, length):
            text.append(random.choice(words))
        text = " ".join(text)
        typeracer_text = text #The raw text that needs to be typed
        text = fill(text, 60) #Limit a line to 60 chars, then \n
        tempimg_path = Path(self.bot.BASE_DIR, 'temp', 'typeracer.png')

        async def create_image():
            img = Image.new("RGBA", (1, 1), color=0) #img of size 1x1 full transparent
            draw = ImageDraw.Draw(img) 
            font = ImageFont.truetype('arial.ttf', 40) #Font
            textwidth, textheight = draw.textsize(text, font) #Size text will take up on image
            margin = 20
            img = img.resize((textwidth + margin, textheight + margin)) #Resize image to size of text
            draw = ImageDraw.Draw(img) #This needs to be redefined after resizing image
            draw.text((margin / 2, margin / 2), text, font=font, fill="white") #Draw the text in between the two margins
            img.save(tempimg_path)
            with open(tempimg_path, 'rb') as fp:
                embed = discord.Embed(description="🏁 " + self._("Type in the text from above as fast as you can!"), color=self.bot.embedBlue)
                await ctx.send(embed=embed, file=discord.File(fp, 'snedtyperace.png'))
            os.remove(tempimg_path)
        
        self.bot.loop.create_task(create_image())

        winners = {}
        ending = asyncio.Event()
        start_time=datetime.datetime.now(datetime.timezone.utc).timestamp()

        #on_message, but not really
        def tr_check(message):
            if ctx.channel.id == message.channel.id and message.channel == ctx.channel:
                if typeracer_text.lower() == message.content.lower():
                    winners[message.author] = datetime.datetime.now(datetime.timezone.utc).timestamp() - start_time #Add winner to list
                    self.bot.loop.create_task(message.add_reaction("✅"))
                    ending.set() #Set the event ending, which starts the ending code
                #If it is close enough, we will add a marker to show that it is incorrect
                elif lev.distance(typeracer_text.lower(), message.content.lower()) < 3: # pylint: disable=<no-member>
                     self.bot.loop.create_task(message.add_reaction("❌"))

        #This is basically an on_message created temporarily, since the check will never return True
        listen_for_msg = ctx.bot.loop.create_task(self.bot.wait_for('message', check=tr_check))

        #Wait for ending to be set, which happens on the first message that meets check
        try:
            await asyncio.wait_for(ending.wait(), timeout=60)
        except asyncio.TimeoutError:
            embed=discord.Embed(title="🏁 " + self._("Typeracing results"), description=self._("Nobody was able to complete the typerace within **60** seconds. Typerace cancelled."), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        else:
            embed=discord.Embed(title="🏁 " + self._("First Place"), description=self._("{winner} finished first, everyone else has **15 seconds** to submit their reply!").format(winner=list(winners.keys())[0].mention), color=self.bot.embedGreen)
            await ctx.send(embed=embed)
            await asyncio.sleep(15)
            desc = self._("**Participants:**\n")
            for winner in winners:
                desc = (f"{desc}**#{list(winners.keys()).index(winner)+1}** {winner.mention} **{round(winners[winner], 1)}** seconds - **{round((len(typeracer_text)/5) / (winners[winner] / 60))}**WPM\n")
            embed=discord.Embed(title="🏁 " + self._("Typeracing results"), description=desc, color=self.bot.embedGreen)
            await ctx.send(embed=embed)
        finally:
            listen_for_msg.cancel() #Stop listening for messages
    
    @commands.command(help="Googles something for you.", description="Googles something for you because you could not be bothered to do it...", usage="google <search query>", aliases=["lmgtfy"])
    @commands.guild_only()
    async def google(self, ctx, *, query):
        query = query.replace(" ", "+")
        link = f"https://letmegooglethat.com/?q={query}"
        embed = discord.Embed(title=self._("Googled it for you!"), description=self._("[Click me!]({link})").format(link=link), color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.send(embed=embed)

    @commands.command(hidden=True, help="Our cool ducky friends are back.", description="Searches duckduckgo instead of Google for you, because privacy is cool.", usage="ddg <search query>", aliases=["lmddgtfy"])
    @commands.guild_only()
    async def ddg(self, ctx, *, query):
        query = query.replace(" ", "%20")
        link = f"https://lmddgtfy.net/?q={query}"
        embed = discord.Embed(title="🦆 " + self._("I ducked it for you!"), description=self._("[Click me!]({link})").format(link=link), color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.send(embed=embed)
    
    @commands.command(help="Twanswoms tewt intuwu", description="Twanswoms tewt intuwu... What havew I donuwu...", aliases=["uwuify"], usage="uwuify <text>")
    @commands.guild_only()
    async def uwu(self, ctx, *, text:str):
        await ctx.send(uwuify.uwu(text))

    @commands.command(help="Boom!", description="Because who doesn't like blowing stuff up?", usage="boom")
    async def boom(self, ctx):
        embed=discord.Embed(title="💥 BOOM!", color=discord.Colour.gold())
        embed.set_image(url='https://media1.tenor.com/images/ed5f49e5717a642812b019deb19ad264/tenor.gif')
        await ctx.send(embed=embed)
    
    @commands.group(help='Shows a random fun fact.', description="Shows a fun fact. Why? Why not?\n\nFacts painstakingly gathered by `fusiongames#8748`.", usage="funfact", invoke_without_command=True, case_insensitive=True)
    @commands.guild_only()
    async def funfact(self, ctx):
        fun_path = Path(self.bot.BASE_DIR, 'etc', 'funfacts.txt')
        fun_facts = open(fun_path, "r").readlines()
        embed = discord.Embed(title="🤔 Did you know?", description=f"{random.choice(fun_facts)}", color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.send(embed=embed)
        
    @funfact.command(hidden=True, help='Shows a random fun fact about Minecraft.', description="Shows a fun fact about Minecraft. Watch out for creepers.\n\nFacts painstakingly gathered by `fusiongames#8748`.", usage="funfact minecraft", aliases=["mc"])
    @commands.guild_only()
    async def minecraft(self, ctx):
        fun_path = Path(self.bot.BASE_DIR, 'etc', 'minecraft_funfacts.txt')
        fun_facts = open(fun_path, "r").readlines()
        embed = discord.Embed(title="🤔 Did you know? - Minecraft Edition", description=f"{random.choice(fun_facts)}", color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.send(embed=embed)

    @commands.command(help="Shows a fact about penguins.", description="Shows a random fact about penguins. Why? Why not?", usage="penguinfact")
    @commands.cooldown(1, 10, type=commands.BucketType.member)
    @commands.guild_only()
    async def penguinfact(self, ctx):
        penguin_path = Path(self.bot.BASE_DIR, 'etc', 'penguinfacts.txt')
        penguin_facts = open(penguin_path, "r").readlines()
        embed = discord.Embed(title="🐧 Penguin Fact", description=f"{random.choice(penguin_facts)}", color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.send(embed=embed)
    
    #Coin flipper
    @commands.command(help="Flips a coin.", description="Flips a coin, not much to it really..", usage="flipcoin", aliases=["flip"])
    @commands.max_concurrency(1, per=commands.BucketType.user,wait=False)
    @commands.cooldown(1, 5, type=commands.BucketType.member)
    @commands.guild_only()
    async def flipcoin(self, ctx):
        options=["heads", "tails"]
        flip=random.choice(options)
        embed=discord.Embed(title="🪙 " + self._("Flipping coin..."), description=self._("Hold on...").format(result=flip), color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(2)
        embed=discord.Embed(title="🪙 " + self._("Coin flipped"), description=self._("It's **{result}**!").format(result=flip), color=self.bot.embedGreen)
        embed = self.bot.add_embed_footer(ctx, embed)
        await msg.edit(embed=embed)

    #Does about what you would expect it to do. Uses thecatapi
    @commands.command(help="Shows a random cat.", description="Searches the interwebz™️ for a random cat picture.", usage="randomcat", aliases=["cat"])
    @commands.max_concurrency(1, per=commands.BucketType.user,wait=False)
    @commands.cooldown(1, 15, type=commands.BucketType.member)
    @commands.guild_only()
    async def randomcat(self, ctx):
        embed=discord.Embed(title="🐱 " + self._("Random kitten"), description=self._("Looking for kitty..."), color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        msg=await ctx.send(embed=embed)
        #Get a json file from thecatapi as response, then take url from dict
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.thecatapi.com/v1/images/search') as response:
                if response.status == 200:
                    catjson = await response.json()
                    #Print kitten to user
                    embed=discord.Embed(title="🐱 " + self._("Random kitten"), description=self._("Found one!"), color=self.bot.embedBlue)
                    embed = self.bot.add_embed_footer(ctx, embed)
                    embed = self.bot.add_embed_footer(ctx, embed)
                    embed.set_image(url=catjson[0]["url"])
                    await msg.edit(embed=embed)
                else:
                    embed=discord.Embed(title="🐱 " + self._("Random kitten"), description=self._("Oops! Looks like the cat delivery service is unavailable! Check back later."), color=self.bot.errorColor)
                    await msg.edit(embed=embed)

    @commands.command(help="Shows a random dog.", description="Searches the interwebz™️ for a random dog picture.", usage="randomdog", aliases=["dog"])
    @commands.max_concurrency(1, per=commands.BucketType.user,wait=False)
    @commands.cooldown(1, 15, type=commands.BucketType.member)
    @commands.guild_only()
    async def randomdog(self, ctx):
        embed=discord.Embed(title="🐶 " + self._("Random doggo"), description=self._("Looking for pupper..."), color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        msg=await ctx.send(embed=embed)
        #Get a json file from thedogapi as response, then take url from dict
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.thedogapi.com/v1/images/search') as response:
                if response.status == 200:
                    dogjson = await response.json()
                    #Print doggo to user
                    embed=discord.Embed(title="🐶 " + self._("Random doggo"), description=self._("Found one!"), color=self.bot.embedBlue)
                    embed = self.bot.add_embed_footer(ctx, embed)
                    embed.set_image(url=dogjson[0]["url"])
                    await msg.edit(embed=embed)
                else:
                    embed=discord.Embed(title="🐶 " + self._("Random doggo"), description=self._("Oops! Looks like the dog delivery service is unavailable! Check back later."), color=self.bot.errorColor)
                    await msg.edit(embed=embed)

    @commands.command(hidden=True, help="Why?...", description="I have no idea why this exists...", usage="catdog", aliases=["randomcatdog", "randomdogcat", "dogcat"])
    @commands.guild_only()
    async def catdog(self, ctx):
        embed=discord.Embed(title="🐱🐶 " + self._("Ahh yes.. the legendary catdog!"), color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        embed.set_image(url="https://media1.tenor.com/images/203c3c6047b3c905962fc55ac7fa9548/tenor.gif")
        await ctx.send(embed=embed)

    
    @commands.command(help="Searches Wikipedia for results.", description="Searches Wikipedia and returns the 5 most relevant entries to your query.", usage="wiki <query>")
    @commands.max_concurrency(1, per=commands.BucketType.user, wait=False)
    @commands.cooldown(1, 10, type=commands.BucketType.member)
    @commands.guild_only()
    async def wiki(self, ctx, *, query):
        await ctx.channel.trigger_typing()
        link = "https://en.wikipedia.org/w/api.php?action=opensearch&search={query}&limit=5"

        async with aiohttp.ClientSession() as session:
            async with session.get(link.format(query=query.replace(" ", "+"))) as response:
                results_dict = await response.json()
                results_text = results_dict[1] #2nd element contains text, 4th links
                results_link = results_dict[3]

        desc=""
        if len(results_text) > 0:
            for result in results_text:
                desc = f"{desc}[{result}]({results_link[results_text.index(result)]})\n"
            embed=discord.Embed(title=self._("Wikipedia: {query}").format(query=query), description=desc, color=self.bot.miscColor)
        else:
            embed=discord.Embed(title="❌ " + self._("No results"), description=self._("Could not find anything related to your query."), color=self.bot.errorColor)
        await ctx.send(embed=embed)

    #Fun command, because yes. (Needs mod privilege as it can be abused for spamming)
    #This may or may not have been a test command for testing priviliges & permissions :P
    @commands.command(hidden=True, brief = "Deploys the duck army.", description="🦆 I am surprised you even need help for this...", usage=f"quack")
    @commands.guild_only()
    async def quack(self, ctx):
        await ctx.channel.send("🦆")
        await ctx.message.delete()

    @commands.command(hidden=True, brief = "Hmm...", description="I mean... what did you expect?", usage="die")
    @commands.guild_only()
    async def die(self, ctx):
        await ctx.send(f"{ctx.author.mention} died.")

    @commands.command(aliases=["bigmoji"],brief="Returns a jumbo-sized emoji.", description="Converts an emoji into it's jumbo-sized variant. Only supports custom emojies. No, the recipe is private.", usage="jumbo <emoji>")
    @commands.guild_only()
    async def jumbo(self, ctx, emoji : discord.PartialEmoji):
        embed=discord.Embed(color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        embed.set_image(url=emoji.url)
        await ctx.send(embed=embed)
        

def setup(bot):
    logger.info("Adding cog: Fun...")
    bot.add_cog(Fun(bot))
