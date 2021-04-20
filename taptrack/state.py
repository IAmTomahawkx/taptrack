import os
import types
from typing import TYPE_CHECKING, Optional, List, Union

import aiohttp
import discord
from discord.ext import commands

from .record import Record, _serialize_message, _dumps
from .errors import *

if TYPE_CHECKING:
    from .cog import TapTrack

TAPTRACK_ERROR_HOOK = os.getenv("TAPTRACK_WEBHOOK_URL", None)
TAPTRACK_STORAGE = os.getenv("TAPTRACK_STORAGE", default="json").lower()
if TAPTRACK_STORAGE in ("postgres", "postgresql"):
    try:
        import asyncpg
    except:
        raise MissingDependency(f"TAPTRACK_STORAGE is set to {TAPTRACK_STORAGE} but dependency 'asyncpg' is not installed")


__all__ = "AbstractState",

class AbstractState:
    def __init__(self, cog: "TapTrack"):
        self.__cog = cog
        if TAPTRACK_ERROR_HOOK:
            self.hook: Optional[discord.Webhook] = discord.Webhook.from_url(TAPTRACK_ERROR_HOOK, adapter=discord.AsyncWebhookAdapter(aiohttp.ClientSession()))
        else:
            self.hook: Optional[discord.Webhook] = None

    async def webhook_send(self, content: Union[discord.Embed, str]):
        if not self.hook:
            return

        args = {
            "content" if isinstance(content, str) else "embed": content
        }
        await self.hook.send(**args)

    async def webhook_put_error(self, record: Record):
        if not self.hook:
            return

        fmt = f"A new error has occurred at {record.frames[-1]['filename']} in function {record.frames[-1]['function']}. It has been marked as #{record.id}.\n\n"
        tb = "".join(record.stack)
        if len(tb) >= (1990-len(fmt)):
            fmt += "Traceback was not included as it is too long."
        else:
            fmt += f"```py\n{tb}\n```"

        await self.webhook_send(fmt)

    async def webhook_put_occurrence(self, record: Record):
        if not self.hook:
            return

        if record.handled:
            fmt = f"Previously handled error #{record.id} has occurred again. It has been marked as UNHANDLED, " \
                  f"and has occurred {record.occurrences+1} times.\n\n"
        else:
            fmt = f"Error #{record.id} has occurred again. It has occurred {record.occurrences+1} times.\n\n"

        tb = "".join(record.stack)
        if len(tb) >= (1990 - len(fmt)):
            fmt += "Traceback was not included as it is too long."
        else:
            fmt += f"```py\n{tb}\n```"

        await self.webhook_send(fmt)

    async def webhook_put_handled(self, record: Record, state: bool):
        if not self.hook:
            return

        fmt = f"Error #{record.id} has been marked as {'HANDLED' if state else 'UNHANDLED'}."
        await self.webhook_send(fmt)

    def eject(self):
        raise NotImplementedError

    async def _put(self, record: Record) -> int:
        raise NotImplementedError

    async def _add_occurrence(self, record_id: int, message: dict):
        raise NotImplementedError

    async def put_error(self, ctx: commands.Context, error: Exception) -> Record:
        exists = await self._get_by_value(error.__traceback__, [str(x) for x in error.args])
        if exists:
            await self._add_occurrence(exists.id, _serialize_message(ctx.message))
            await self.webhook_put_occurrence(exists)
            return exists

        else:
            record = Record(
                error,
                ctx.message,
                occurred_at=ctx.message.created_at
            )
            record_id = await self._put(record)
            record.id = record_id
            await self.webhook_put_error(record)
            return record

    async def _get_by_value(self, tb: types.TracebackType, args: List[str]) -> Optional[Record]:
        raise NotImplementedError

    async def _get(self, record_id: int) -> Optional[Record]:
        raise NotImplementedError

    async def get_error(self, record_id: int) -> Optional[Record]:
        return await self._get(record_id)

    async def _set_handled(self, record_id: int, state: bool) -> Optional[Record]:
        raise NotImplementedError

    async def set_handled(self, record_id: int, state: bool) -> Optional[Record]:
        record = await self._set_handled(record_id, state)
        if record:
            await self.webhook_put_handled(record, state)

        return record

    async def get_all_unhandled(self) -> List[Record]:
        raise NotImplementedError


class PostgresState(AbstractState):
    schema = """
    CREATE TABLE IF NOT EXISTS taptrack_errors (
        id serial primary key,
        stack jsonb not null,
        frames jsonb not null,
        args text[] not null,
        occurrences int not null default 1,
        occurred_at timestamp without time zone not null,
        messages jsonb[] not null,
        handled bool not null,
        tracking_filename text not null,
        tracking_function text not null,
        unique (tracking_filename, tracking_function, args)
    );
    """
    def __init__(self, cog: "TapTrack"):
        super().__init__(cog)
        dsn = os.getenv("TAPTRACK_DB_URI", None)
        if not dsn:
            raise TapTracksError("TAPTRACK_DB_URI environment variable was empty")

        self._dsn: str = dsn
        self.conn: Optional[asyncpg.Connection] = None

    def eject(self):
        async def inner():
            if self.conn and not self.conn.is_closed():
                await self.conn.close()

        self.__cog.bot.loop.create_task(inner())

    async def do_query(self, query: str, *args) -> list:
        if self.conn is None:
            self.conn = await asyncpg.connect(self._dsn) # type: asyncpg.Connection
            await self.conn.execute(self.schema)

        return await self.conn.fetch(query, *args)

    async def _get_by_value(self, tb: types.TracebackType, args: List[str]) -> Optional[Record]:
        query = """
        SELECT
            *
        FROM
            taptrack_errors
        WHERE
            tracking_filename = $1
            AND (
                tracking_function = $2
                OR args = $3
            )
        """
        def _get_last_frame(_frame):
            if _frame.tb_next:
                return _get_last_frame(_frame.tb_next)
            return _frame

        frame = _get_last_frame(tb)
        data = await self.do_query(query, frame.tb_frame.f_code.co_filename, frame.tb_frame.f_code.co_name, args)

        if not data:
            return None

        r = Record.from_psql(data[0])
        return r

    async def _get(self, record_id: int) -> Optional[Record]:
        query = """
        SELECT
            *
        FROM
            taptrack_errors
        WHERE
            id = $1
        """
        data = await self.do_query(query, record_id)
        if not data:
            return None

        rec = Record.from_psql(data[0])
        return rec

    async def _put(self, record: Record) -> int:
        query = """
        INSERT INTO taptrack_errors
            (stack, frames, args, occurrences, occurred_at, messages, handled, tracking_filename, tracking_function)
        VALUES
            ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING
            id
        """
        serial = record._to_dict(strict=False)
        data = await self.do_query(
            query,
            serial['stack'],
            serial['frames'],
            serial['args'],
            serial['occurrences'],
            serial['occurred_at'],
            serial['messages'],
            serial['handled'],
            serial['tracking_filename'],
            serial['tracking_function']
        )
        return data[0]['id']

    async def _add_occurrence(self, record_id: int, message: dict) -> None:
        query = """
        UPDATE taptrack_errors
        SET
            occurrences = occurrences + 1,
            messages = array_append(messages, $2),
            handled = false
        WHERE
            id = $1
        """
        await self.do_query(query, record_id, _dumps(message))

    async def _set_handled(self, record_id: int, state: bool) -> Optional[Record]:
        query = """
        UPDATE taptrack_errors
        SET
            handled = $2
        WHERE
            id = $1
        RETURNING
            *
        """
        data = await self.do_query(query, record_id, state)
        if not data:
            return None

        rec = Record.from_psql(data[0])
        return rec

    async def get_all_unhandled(self) -> List[Record]:
        query = """
        SELECT
            *
        FROM taptrack_errors
        WHERE
            handled = false
        """
        data = await self.do_query(query)
        return [Record.from_psql(x) for x in data]
