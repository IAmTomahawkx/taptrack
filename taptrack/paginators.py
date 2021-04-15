from typing import List
import pprint

from discord.ext import menus

class StackFrameDataSource(menus.ListPageSource):
    def __init__(self, entries: List[dict]):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu, page):
        data = pprint.pformat(page['scope'], indent=2)
        header = f"File \"{page['filename']}\", line {page['lineno']}, in {page['function']}\n"
        return header + "```py\n"+data + "\n```"


class MessageFrameDataSource(menus.ListPageSource):
    def __init__(self, entries: List[dict]):
        super().__init__(entries, per_page=1)

    async def format_page(self, menu, page):
        data = pprint.pformat(page, indent=2)
        return "```py\n"+data + "\n```"