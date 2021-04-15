import datetime
import types
from typing import List, Dict, Union, Any, Optional

import discord
import prettify_exceptions

formatter = prettify_exceptions.DefaultFormatter()
formatter.theme['_ansi_enabled'] = False

try:
    import ujson
    def _dumps(obj: Union[dict, list]) -> str:
        return ujson.dumps(obj)

    def _loads(obj: str) -> Union[dict, list]:
        return ujson.loads(obj)

except ModuleNotFoundError:
    import json
    def _dumps(obj: dict) -> str:
        return json.dumps(obj)

    def _loads(obj: str) -> dict:
        return json.loads(obj)

def _serialize_user(user: Union[discord.User, discord.Member]) -> dict:
    return {
        "id": user.id,
        "username": user.name,
        "avatar": user.avatar,
        "discriminator": user.discriminator,
        "publicFlags": user.public_flags.value,
        "bot": user.bot,
        "system": user.system,
        "nick": getattr(user, "nick", None),
        "_guild_id": getattr(user, "guild", None) and user.guild.id
    }

def _serialize_channel(channel: discord.TextChannel) -> dict:
    return {
        "id": channel.id,
        "parent_id": channel.category_id,
        "position": channel.position,
        "type": channel._type,
        "nsfw": channel.nsfw,
        "topic": channel.topic
    }

def _serialize_guild(guild: discord.Guild) -> dict:
    return {
        "id": guild.id,
        "owner_id": guild.owner_id,
        "large": guild._large,
        "mfa_level": guild.mfa_level,
        "unavailable": guild.unavailable,
        "name": guild.name,
        "features": guild.features,
        "premium_tier": guild.premium_tier,
        "preferred_locale": guild.preferred_locale
    }

def _serialize_attachments(message: discord.Message):
    if not message.attachments:
        return []

    attch = []
    for atch in message.attachments:
        attch.append({
            "content_type": atch.content_type,
            "filename": atch.filename,
            "id": atch.id,
            "height":atch.height,
            "width": atch.width,
            "proxy_url": atch.proxy_url,
            "size": atch.size,
            "url": atch.url,
            "spoiler": atch.is_spoiler()
        })

def _serialize_stickers(message: discord.Message) -> list:
    return [
        {
            "id": x.id,
            "name": x.name,
            "description": x.description,
            "pack": x.pack_id,
            "image": x.image,
            "preview_image": x.preview_image,
            "tags": x.tags,
            "format": x.format.value
        } for x in message.stickers
    ]

def _serialize_reference(message: discord.Message) -> Optional[dict]:
    return message.reference.to_dict() if message.reference else None


def _serialize_message(message: discord.Message) -> dict:
    return {
        "id": message.id,
        "webhook_id": message.webhook_id,
        "content": message.content,
        "pinned": message.pinned,
        "flags": message.flags.value,
        "mention_everyone": message.mention_everyone,
        "mentions": message.raw_mentions,
        "channel_mentions": message.raw_channel_mentions,
        "role_mentions": message.raw_role_mentions,
        "reference": _serialize_reference(message),
        "stickers": _serialize_stickers(message),
        "embeds": [e.to_dict() for e in message.embeds],
        "author": _serialize_user(message.author),
        "channel": _serialize_channel(message.channel),
        "guild": message.guild and _serialize_guild(message.guild),
        "tts": message.tts,
        "attachments": _serialize_attachments(message)
    }

VALID_SERIALIZATIONS = {
    int: int,
    str: str,
    bool: bool,
    discord.Message: _serialize_message,
    discord.User: _serialize_user,
    discord.Member: _serialize_user,
    discord.TextChannel: _serialize_channel,
    discord.Guild: _serialize_guild
}

def _default_serialization(obj: Any) -> Union[dict, str]:
    if hasattr(obj, "__taptrack_serialize__"):
        return obj.__taptrack_serialize__()

    if type(obj) is types.ModuleType:
        return f"<module {obj.__package__ or obj.__name__}>"

    return f"<unserializable {obj!r}>"

def _serialize_frame_scope(scope: Dict[str, Any]) -> Dict[str, Union[int, str, bool, dict]]:
    output_scope = {}

    for name, value in scope.items():
        if type(value) not in VALID_SERIALIZATIONS:
            output_scope[name] = _default_serialization(value)

        output_scope[name] = VALID_SERIALIZATIONS[type(name)](value)

    return output_scope

def _serialize_tb_frame(frame: types.TracebackType) -> dict:
    return {
        "filename": frame.tb_frame.f_code.co_filename,
        "function": frame.tb_frame.f_code.co_name,
        "lineno": frame.tb_lineno,
        "scope": _serialize_frame_scope(frame.tb_frame.f_locals)
    }

def _serialize_traceback(frame: types.TracebackType) -> List[dict]:
    frames = []
    current = frame
    frames.append(_serialize_tb_frame(current))

    while current.tb_next is not None:
        current = current.tb_next
        frames.append(_serialize_tb_frame(current))

    return frames

class Record:
    def __init__(
            self,
            exception: Exception,
            message: discord.Message,
            occurred_at: datetime.datetime = None,
            stack = None
    ):
        self.id = None
        self.stack = stack or list(formatter.format_exception(type(exception), exception, exception.__traceback__))
        while "\n" in self.stack:
            self.stack.remove("\n")

        self.args = [str(x) for x in exception.args]
        self.occurred_at = occurred_at.replace(tzinfo=None)
        self.frames = _serialize_traceback(exception.__traceback__)

        self._tracking_filename = self.frames[-1]['filename']
        self._tracking_function = self.frames[-1]['function']

        self.occurrences = 1
        self.handled = False
        self.messages = [_serialize_message(message)]

    @classmethod
    def from_json(cls, data: str) -> "Record":
        data = _loads(data)
        self = cls.__new__(cls)
        self.id = data['id']
        self.handled = data['handled']
        self.stack = _loads(data['stack'])
        self.frames = _loads(data['frames'])
        self.args = data['args']
        self.occurrences = data['occurrences']
        self.occurred_at = datetime.datetime.fromisoformat(data['occurred_at'])
        self.messages = [_loads(x) for x in data['messages']]
        self._tracking_filename = data['tracking_filename']
        self._tracking_function = data['tracking_function']

        return self

    @classmethod
    def from_psql(cls, data: Any) -> "Record":
        self = cls.__new__(cls)
        self.id = data['id']
        self.handled = data['handled']
        self.stack = _loads(data['stack'])
        self.frames = _loads(data['frames'])
        self.args = data['args']
        self.occurrences = data['occurrences']
        self.occurred_at = data['occurred_at']
        self.messages = [_loads(x) for x in data['messages']]
        self._tracking_filename = data['tracking_filename']
        self._tracking_function = data['tracking_function']

        return self

    def _to_dict(self, strict=False) -> dict:
        return {
            "id": self.id,
            "stack": _dumps(self.stack),
            "handled": self.handled,
            "frames": _dumps(self.frames),
            "args": self.args,
            "occurred_at": self.occurred_at if not strict else self.occurred_at.isoformat(),
            "occurrences": self.occurrences,
            "messages": [_dumps(x) for x in self.messages],
            "tracking_filename": self._tracking_filename,
            "tracking_function": self._tracking_function
        }
