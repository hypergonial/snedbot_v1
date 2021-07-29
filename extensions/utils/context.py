import logging

import discord
from discord.ext import commands


class Confirm(discord.ui.View):
    '''Confirmation view
    verbose:bool - Decides if a response should be given
    confirm_msg - If verbose, confirmation message contents
    cancel_msg - If verbose, cancelation message contents'''

    def __init__(self, verbose:bool=False, confirm_msg:str=None, cancel_msg:str=None):
        super().__init__()
        self.value = None
        self.verbose = verbose
        self.confirm_msg=confirm_msg if confirm_msg else "Confirmed!"
        self.cancel_msg=cancel_msg if cancel_msg else "Cancelled!"
    
    @discord.ui.button(label='✔️', style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.verbose:
            await interaction.response.send_message(self.confirm_msg, ephemeral=True)
        self.value = True
        self.stop()
    
    @discord.ui.button(label="❌", style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.verbose:
            await interaction.response.send_message(self.cancel_msg, ephemeral=True)
        self.value = False
        self.stop()



class Context(commands.Context):
    '''Custom context'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    

    async def confirm(self, message_content=None, *, embed:discord.Embed=None, delete_after:bool=True, confirm_msg:str=None, cancel_msg:str=None) -> bool:
        '''Creates an interactive button-prompt to confirm an action. Returns True if user confirmed.'''

        if message_content is None and embed is None:
            raise ValueError('Either content or embed must not be None.')

        if confirm_msg or cancel_msg:
            view = Confirm(verbose=True, confirm_msg=confirm_msg, cancel_msg=cancel_msg)
        else:
            view = Confirm()

        message = await self.send(content=message_content, embed=embed, view=view)
        await view.wait()

        if delete_after:
            try:
                await message.delete()
            except discord.Forbidden:
                logging.debug('Failed to delete_after in ctx.confirm. (discord.Forbidden)')
        return view.value
        