import discord

class CustomSelect(discord.ui.Select):
    '''Select that returns it's data to the view'''
    def __init__(self, placeholder:str, options=[discord.SelectOption], min_values:int=1, max_values:int=1, response_msg:str=None):
        super().__init__(placeholder=placeholder, options=options, min_values=min_values, max_values=max_values)
        self.response_msg = response_msg
    
    async def callback(self, interaction: discord.Interaction):
        if self.response_msg:
            await interaction.response.send_message(self.response_msg, ephemeral=True)
        self.view.value = interaction.data
        self.view.stop()

