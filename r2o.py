from __future__ import annotations
import json
import os
import re
import sys
from typing import Match, cast
from typing_extensions import Final, NotRequired, TypedDict

from dateutil.parser import parse
from tqdm import tqdm

re_daily: Final = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December) ([0-9]+)[a-z]{2}, ([0-9]{4})"
)
re_daylink: Final = re.compile(
    r"(\[\[)([January|February|March|April|May|June|July|August|September|October|November|December [0-9]+[a-z]{2}, [0-9]{4})(\]\])"
)
re_blockmentions: Final = re.compile(r"({{mentions: \(\()(.{9})(\)\)}})")
re_blockembed: Final = re.compile(r"({{embed: \(\()(.{9})(\)\)}})")
re_blockref: Final = re.compile(r"(\(\()(.{9})(\)\))")


class BlockBase(TypedDict):
    """Base for the ``Block`` and ``ExtendedBlock`` typed dictionaries."""

    uid: str
    string: str
    heading: NotRequired[int]


class Block(BlockBase):
    """Dictionary that represents how a block is stored in Roam's JSON format."""

    children: NotRequired[list[Block]]


class ExtendedBlock(BlockBase):
    """A block that has been extended with a link to its page."""

    children: NotRequired[list[ExtendedBlock]]
    page: ParsedPage


class Page(TypedDict):
    """A page from Roam's JSON format."""

    uid: str
    title: str
    children: NotRequired[list[Block]]


class ParsedPage(TypedDict):
    """Slightly modified version of ``Page``."""

    title: str
    children: list[ExtendedBlock]
    daily: bool


class ErrorPage(TypedDict):
    """A helper for error reporting."""

    page: ParsedPage
    content: list[str]


def main():
    if len(sys.argv) == 1:
        print("Usage:")
        print("    python r2o.py <roam json file>")
        return

    j: list[Page] = json.load(
        open(sys.argv[1], mode="rt", encoding="utf-8", errors="ignore")
    )

    odir = "md"  # output dir
    ddir = "md"  # output dir for daily notes
    os.makedirs(ddir, exist_ok=True)

    print("Pass 1: scan all pages", flush=True)

    uid2block: dict[str, ExtendedBlock] = {}
    referenced_uids: set[str] = set()
    pages: list[ParsedPage] = []

    for page in tqdm(j):
        title = (
            page["title"]
            .replace(":", " -")  # no colons allowed in file names
            .replace('"', "")
            .replace("^", "")
            .replace("\\", "")  # backslashes are also a bad idea
        )
        children = page.get("children", [])

        is_daily = False
        m = re_daily.match(title)
        if m:
            is_daily = True
            dt = parse(title)
            title = dt.isoformat().split("T")[0]

        # type checking complains because there is an implicit conversion going on here
        # that is hard to express as types
        page_: ParsedPage = {"title": title, "children": children, "daily": is_daily}
        uid2block.update(scan_blocks(children, page_))
        pages.append(page_)

    print(f"found {len(uid2block)} UIDs", flush=True)
    print("Pass 2: track blockrefs", flush=True)
    for page in tqdm(pages):
        render_children(page["children"], uid2block, referenced_uids, render=False)
    print(f"found {len(referenced_uids)} referenced UIDs")

    print("Pass 3: generate")
    error_pages: list[ErrorPage] = []
    for page in tqdm(pages):
        title = page["title"]
        if not title:
            continue
        ofiln = f'{odir}/{page["title"]}.md'
        if page["daily"]:
            ofiln = f'{ddir}/{page["title"]}.md'

        # hack for crazy slashes in titles
        if "/" in title:
            d = odir
            for part in title.split("/")[:-1]:
                d = os.path.join(d, part)
                os.makedirs(d, exist_ok=True)

        lines = render_children(
            page["children"], uid2block, referenced_uids, render=True
        )
        try:
            with open(ofiln, mode="wt", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except:
            error_pages.append({"page": page, "content": lines})

    if error_pages:
        print("The following pages had errors:")
        for ep in error_pages:
            page = ep["page"]
            t = page["title"]
            c = ep["content"]
            print(f"Title: >{t}<")
            print(f"Content:")
            print("    " + "\n    ".join(c))
    print("Done!")


def scan_blocks(blocks: list[Block], page: ParsedPage) -> dict[str, ExtendedBlock]:
    """Create a look-up table that allows us to find a block given its UID.

    For that, we recursively traverse the blocks in a page and record the encountered UIDs together
    with the block in a dictionary.
    """
    u2b: dict[str, ExtendedBlock] = {}
    for block in blocks:
        children = block.get("children", [])

        # turn the block into an extended block; this means adding the ``page`` entry
        # unfortunately I don't know how to express this
        block["page"] = page
        block = cast(ExtendedBlock, block)

        u2b[block["uid"]] = block
        u2b.update(scan_blocks(children, page))
    return u2b


def render_children(
    children: list[ExtendedBlock],
    uid2block: dict[str, ExtendedBlock],
    referenced_uids: set[str],
    render: bool,
) -> list[str]:
    """Traverse all blocks in a page and render them as markdown strings.

    If ``render`` is set to ``False``, however, we just populate the list of all referenced UIDs.
    """
    unexpanded_lines: list[str | list[ExtendedBlock]] = [children]
    has_unexpanded = True
    level = 0

    while has_unexpanded:
        lines: list[str | list[ExtendedBlock]] = []
        has_unexpanded = False
        for string_or_blocks in unexpanded_lines:
            if isinstance(string_or_blocks, str):
                lines.append(string_or_blocks)
                continue
            blocks = string_or_blocks
            for block in blocks:
                s = block["string"]

                if render:
                    s = render_blockrefs(s, uid2block, referenced_uids)
                    prefix = ""
                    if level >= 1:
                        prefix = "\t" * level
                    prefix += "- "

                    headinglevel = block.get("heading", None)
                    if headinglevel is not None:
                        prefix += "#" * (headinglevel) + " "

                    uid = block["uid"]
                    if uid in referenced_uids:
                        postfix = f" ^{uid}"
                    else:
                        postfix = ""

                    # b id magic
                    s = prefix + s + postfix
                    if "\n" in s:
                        new_s = s[:-1]
                        new_s = new_s.replace("\n", "\n" + prefix[:-2] + "  ")
                        new_s += s[-1]
                        s = new_s + "\n"

                    lines.append(s)
                else:
                    get_referenced_uids(s, uid2block, referenced_uids)
                    lines.append("")

                new_children = block.get("children", [])
                if new_children:
                    lines.append(new_children)
                    has_unexpanded = True  # another pass is needed unfortunately
        unexpanded_lines = lines
        level += 1

    # type checking complains here that the list may still contain
    # unrendered list of blocks, but the algorithm is written in a way
    # where that is not possible
    return unexpanded_lines


def render_blockrefs(
    s: str, uid2block: dict[str, ExtendedBlock], referenced_uids: set[str]
) -> str:
    """Render block references from Roam such that Obsidian can understand them."""
    new_s = s
    startpos = 0
    while True:
        m, is_embed = find_blockrefs(new_s, startpos=startpos)
        if m is None:
            break

        uid = m.group(2)
        if uid not in uid2block:
            print("************** uid not found:", uid)
            startpos = m.end(2)
        else:
            referenced_uids.add(uid)
            head = new_s[: m.start(1)]
            r_block = uid2block[uid]
            # Obsidian doesn't like underscores
            safe_block_id = r_block["uid"].replace("_", "")
            if is_embed:
                replacement = f'![[{r_block["page"]["title"]}#^{safe_block_id}]]'
            else:
                # TODO: should the block content be sanitized?
                block_content = r_block["string"]
                replacement = (
                    f'[[{r_block["page"]["title"]}#^{safe_block_id}|{block_content}]]'
                )
            tail = new_s[m.end(3) :]
            new_s = head + replacement + tail
    return replace_daylinks(new_s)


def get_referenced_uids(
    s: str, uid2block: dict[str, ExtendedBlock], referenced_uids: set[str]
) -> None:
    """Extract all UIDs that are referenced in the given string."""
    startpos = 0
    while True:
        m, _ = find_blockrefs(s, startpos)
        if m is None:
            break
        uid = m.group(2)
        if uid in uid2block:
            referenced_uids.add(uid)
        # continue searching after the match
        startpos = m.end(2)


def find_blockrefs(s: str, startpos: int) -> tuple[Match[str] | None, bool]:
    """Find all block references in the given string."""
    m = re_blockembed.search(s, pos=startpos)
    is_embed = True
    if m is None:
        is_embed = False
        m = re_blockmentions.search(s, pos=startpos)
        if m is None:
            m = re_blockref.search(s, pos=startpos)
    return m, is_embed


def replace_daylinks(s: str) -> str:
    """Replace links to the daily notes."""
    new_s = s
    while True:
        m = re_daylink.search(new_s)
        if not m:
            break
        else:
            head = new_s[: m.end(1)]
            dt = parse(m.group(2))
            replacement = dt.isoformat()[:10]
            tail = "]]" + new_s[m.end(0) :]
            new_s = head + replacement + tail
    return new_s


if __name__ == "__main__":
    main()
