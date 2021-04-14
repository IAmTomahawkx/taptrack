from discord.ext import commands

from . import state

class TapTrack(commands.Cog):
    """
    TapTrack error tracking
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if state.TAPTRACK_STORAGE in ("postgres", "postgresql"):
            self.state = state.PostgresState(self)
        else:
            raise ValueError("yeet")

    @commands.Cog.listener()
    async def on_command_error(self, context: commands.Context, exception: Exception):
        print(exception)
        if isinstance(exception, commands.CommandInvokeError):
            v = await self.state.put_error(context, exception.original)
            print(v._to_dict())
            return

    async def cog_check(self, ctx: commands.Context) -> bool:
        if not await ctx.bot.is_owner(ctx.author):
            raise commands.NotOwner("You must own this bot to use this command")

        return True

    @commands.group("taptrack", invoke_without_command=True)
    async def _core(self, ctx: commands.Context):
        """
        This command will give an overview of the current error statistics.
        """
        pass

    @_core.command("error")
    async def _core_error_select(self, ctx: commands.Context, error_no: int):
        pass

#    @_core.command("")
