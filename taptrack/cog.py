from discord.ext import commands, menus

from . import state, paginators

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
        if isinstance(exception, commands.CommandInvokeError):
            await self.state.put_error(context, exception.original)
            return

    async def cog_check(self, ctx: commands.Context) -> bool:
        return await commands.is_owner().predicate(ctx)

    @commands.group("taptrack", invoke_without_command=True)
    async def _core(self, ctx: commands.Context):
        """
        This command will give an overview of the current error statistics.
        """
        unhandled = await self.state.get_all_unhandled()
        try:
            recent = max(unhandled, key=lambda r: r.id)
            common = max(unhandled, key=lambda r: r.occurrences)
        except:
            recent = None
            common = None

        fmt = ""
        fmt += f"There are currently {len(unhandled)} unhandled errors.\n"
        fmt += f"The most recent error is #{recent.id if recent else 'N/A'}, and was first seen on {recent.occurred_at.strftime('%a, %b %d at %H:%M %Z') if recent else 'N/A'}.\n"
        fmt += f"The most common error is #{common.id if common else 'N/A'}, and has occurred {common.occurrences if common else 'N/A'} times."

        await ctx.send(fmt)

    @_core.command("error")
    async def _core_error_select(self, ctx: commands.Context, error_no: int):
        error = await self.state.get_error(error_no)
        if not error:
            return await ctx.send(f"Error #{error_no} does not exist.")

        fmt = ""

        fmt += f"Error #{error_no} has occurred {error.occurrences} times, and is currently {'HANDLED' if error.handled else 'UNHANDLED'}.\n"
        fmt += f"It was first seen on {error.occurred_at.strftime('%a, %b %d at %H:%M %Z')}\n"
        context = "".join(error.stack[-3:]).strip()
        fmt += f"```py\n{context}\n```\n"
        fmt += f"To see messages that caused this error, use `{ctx.prefix}taptrack messages {error_no}`\n"
        fmt += f"To see stack frames and scopes, use `{ctx.prefix}taptrack frames {error_no}`\n"
        fmt += f"To see the full traceback, use `{ctx.prefix}taptrack trace {error_no}`\n"
        if not error.handled:
            fmt += f"To mark this error as handled, use `{ctx.prefix}taptrack handled {error_no} yes`"

        await ctx.send(fmt)

    @_core.command("handled")
    async def _core_handled(self, ctx: commands.Context, error_no: int, handled: bool=None):
        if handled is None:
            error = await self.state.get_error(error_no)
            if not error:
                return await ctx.send(f"Error #{error_no} does not exist.")

            await ctx.send(f"Error #{error_no} is {'HANDLED' if error.handled else 'UNHANDLED'}")
        else:
            error = await self.state.set_handled(error_no, handled)
            if not error:
                return await ctx.send(f"Error #{error_no} does not exist.")

            await ctx.send(f"Error #{error_no} is now {'HANDLED' if error.handled else 'UNHANDLED'}")

    @_core.command("trace")
    async def _core_traceback(self, ctx: commands.Context, error_no: int):
        error = await self.state.get_error(error_no)
        if not error:
            return await ctx.send(f"Error #{error_no} does not exist.")

        trace = "".join(error.stack)
        if len(trace) > 1989:
            # TODO upload to mystbin
            await ctx.send("Traceback too large")
        else:
            await ctx.send(f"```py\n{trace}\n```")

    @_core.command("frames")
    async def _core_frames(self, ctx: commands.Context, error_no: int):
        error = await self.state.get_error(error_no)
        if not error:
            return await ctx.send(f"Error #{error_no} does not exist.")

        src = paginators.StackFrameDataSource(error.frames)
        m = menus.MenuPages(src)
        m.delete_message_after = True
        await m.start(ctx)

    @_core.command("messages")
    async def _core_messages(self, ctx: commands.Context, error_no: int):
        error = await self.state.get_error(error_no)
        if not error:
            return await ctx.send(f"Error #{error_no} does not exist.")

        src = paginators.MessageFrameDataSource(error.messages)
        m = menus.MenuPages(src)
        m.delete_message_after = True
        await m.start(ctx)