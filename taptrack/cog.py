import os
import pprint
from typing import Tuple, Optional

import aiohttp
import prettify_exceptions
import yarl
from discord.ext import commands, menus

from . import state, paginators

formatter = prettify_exceptions.DefaultFormatter()

def _frame(t):
    header = f"File \"{t['filename']}\", line {t['lineno']}, in {t['function']}\n"
    return header + pprint.pformat(t['scope'])

class TapTrack(commands.Cog):
    """
    TapTrack error tracking
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._haste_cache = {}
        self._haste_target = yarl.URL(os.getenv("TAPTRACK_HASTE_SITE", "https://mystb.in/")).with_path("documents")

        self._session = None
        if state.TAPTRACK_STORAGE in ("postgres", "postgresql"):
            self.state = state.PostgresState(self)
        else:
            raise ValueError("yeet")

    def cog_unload(self):
        self.state.eject()
        if self._session:
            self.bot.loop.create_task(self._session.close())

    async def upload_haste(self, content: str) -> Tuple[Optional[str], Optional[str]]:
        hashed = hash(content)
        if hashed in self._haste_cache:
            return self._haste_cache[hashed], None

        if not self._session:
            headers = {}
            auth = os.getenv("TAPTRACK_HASTE_AUTHORIZATION", None)
            if auth:
                headers['Authorization'] = auth

            self._session = aiohttp.ClientSession(headers=headers)

        async with self._session.post(self._haste_target, data=content) as resp:
            if 200 > resp.status >= 300:
                return None, resp.reason

            data = await resp.json()
            url = data.get("key")
            if url:
                url = str(self._haste_target.with_path(url))
                self._haste_cache[hashed] = url
                return url, None

            return None, f"Failed to upload to {self._haste_target}"

    @commands.Cog.listener()
    async def on_command_error(self, context: commands.Context, exception: Exception):
        if isinstance(exception, commands.CommandInvokeError):
            try:
                await self.state.put_error(context, exception.original)
            except Exception as e:
                print("".join(formatter.format_exception(type(e), e, e.__traceback__)))

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
        """
        This command gives an overview of a specific error.
        """
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
        """
        This command updates the handled state of an error.
        """
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
        """
        This command will show the full traceback, including values from the scopes inside the traceback.
        """
        error = await self.state.get_error(error_no)
        if not error:
            return await ctx.send(f"Error #{error_no} does not exist.")

        trace = "".join(error.stack)
        if len(trace) > 1989:
            url, reason = await self.upload_haste(trace)
            if reason:
                await ctx.send(f"Traceback is too long for discord, but couldn't be uploaded to {self._haste_target.host}. Reason: {reason}")
            else:
                await ctx.send(f"Traceback is too long for discord, it has been uploaded to {url}")
        else:
            await ctx.send(f"```py\n{trace}\n```")

    @_core.command("frames")
    async def _core_frames(self, ctx: commands.Context, error_no: int):
        """
        This command shows you the variables inside each frame of the traceback.
        """
        error = await self.state.get_error(error_no)
        if not error:
            return await ctx.send(f"Error #{error_no} does not exist.")

        frames = [_frame(x) for x in error.frames]
        if any(len(x) >= 1990 for x in frames):
            output = "\n\n".join(frames)
            url, reason = await self.upload_haste(output)
            if reason:
                await ctx.send(f"Frames are too long for a discord message, but they couldn't be uploaded to {self._haste_target}. Reason: {reason}")
            else:
                await ctx.send(f"Frames are too long for discord, they've been uploaded to {url}")

        else:
            src = paginators.StackFrameDataSource(error.frames)
            m = menus.MenuPages(src)
            m.delete_message_after = True
            await m.start(ctx)

    @_core.command("messages")
    async def _core_messages(self, ctx: commands.Context, error_no: int):
        """
        This command will give you a detailed view of each message that has caused the error.
        """
        error = await self.state.get_error(error_no)
        if not error:
            return await ctx.send(f"Error #{error_no} does not exist.")

        src = paginators.MessageFrameDataSource(error.messages)
        m = menus.MenuPages(src)
        m.delete_message_after = True
        await m.start(ctx)