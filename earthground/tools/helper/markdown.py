import logging
import re
from typing import Dict, List

LOG = logging.getLogger("Markdown")


class SimpleMarkdown:
    def __init__(self, data: Dict[str, str], raw: str):
        self._data = data
        self._raw = raw

    @staticmethod
    def image_strip(line: str) -> str:
        return re.sub(r"\!\[Image\]\(data:image(.*?)\)", "", line)

    @classmethod
    def parse(cls, path: str) -> "SimpleMarkdown":
        """
        Parse the markdown content into a dictionary of headings and their corresponding sections.

        Returns:
            A dictionary where keys are heading titles and values are the section content.
        """
        LOG.info(f"Parsing markdown file: {path}")
        data = {}
        raw = []
        with open(path, "r") as f:
            last_heading = None
            for line in f.readlines():
                raw.append(SimpleMarkdown.image_strip(line).strip())
                if line.startswith("#"):
                    last_heading = line.strip("#").strip()
                elif last_heading:
                    if last_heading not in data:
                        data[last_heading] = ""
                    data[last_heading] += SimpleMarkdown.image_strip(line)
            LOG.debug(f"Parsed {len(data)} sections from markdown")
            return cls(data, raw)

    def get_all_text_from_search(self, search: str | List[str]) -> str:
        result = ""
        headings_used = []
        if isinstance(search, str):
            search = [search]
        LOG.debug(f"Searching for sections containing: {search}")
        for heading, section in self._data.items():
            if any(s.lower() in heading.lower() for s in search):
                result += section
                headings_used.append(heading)
        LOG.info(f"Search headings key={search} result={headings_used}")
        return result

    def get_text_from_chapter(self, chapter: int) -> str:
        result = ""
        for heading, section in self._data.items():
            if re.match(rf"^{chapter}(\.\d+)*\s", heading):
                LOG.info(f"Found chapter {chapter}: {heading}")
                result += section
        return result

    def get_lines(self, start: int, end: int) -> str:
        return "\n".join(self._raw[start:end])
