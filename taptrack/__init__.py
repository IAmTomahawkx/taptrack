from discord.ext import commands

from .cog import TapTrack


def setup(bot: commands.Bot):
    bot.add_cog(TapTrack(bot))
