"""Real university website inputs for Experiment 10-4.

中文说明：实验 10-4 的网站输入（数据而非 mock）。DEFAULT_SITES 为 10 个
真实斯坦福页面（目录页与人物页混合，模拟用户真实会给的输入）；
load_sites 支持从 JSON 文件加载（--sites-json）并按 --agents 截断，
每项为 Website(name, college, url)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Website:
    name: str
    college: str
    url: str


TARGET = "Andrew Ng"

# All are real Stanford-owned web pages. They intentionally mix directories and
# school/center profiles, as a user-supplied experiment should. URLs are data, not
# mocked content; every worker launches an isolated Playwright browser context.
DEFAULT_SITES: List[Website] = [
    Website("medicine-profiles", "School of Medicine", "https://med.stanford.edu/profiles/browse"),
    Website("law-faculty", "Stanford Law School", "https://law.stanford.edu/directory/?tax_and_terms=1067"),
    Website("education-faculty", "Graduate School of Education", "https://ed.stanford.edu/faculty"),
    Website("business-faculty", "Graduate School of Business", "https://www.gsb.stanford.edu/faculty-research/faculty"),
    Website("sustainability-faculty", "Doerr School of Sustainability", "https://sustainability.stanford.edu/people/faculty"),
    Website("humanities-faculty", "School of Humanities and Sciences", "https://humsci.stanford.edu/about/leadership-and-administration/deans-office"),
    Website("engineering-faculty", "School of Engineering", "https://engineering.stanford.edu/faculty-research/faculty"),
    Website("computer-science", "School of Engineering / Computer Science", "https://www.cs.stanford.edu/people/faculty"),
    Website("stanford-profiles", "Stanford Profiles", "https://profiles.stanford.edu/andrew-ng"),
    Website("human-ai", "Stanford HAI", "https://hai.stanford.edu/people/andrew-ng"),
]


def load_sites(path: str | None, limit: int | None = None) -> List[Website]:
    if path:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        sites = [Website(**item) for item in raw]
    else:
        sites = list(DEFAULT_SITES)
    if limit is not None:
        sites = sites[:limit]
    if not sites:
        raise ValueError("网站列表不能为空")
    for site in sites:
        if not site.url.startswith(("http://", "https://")):
            raise ValueError(f"{site.name} 不是 HTTP(S) URL")
    return sites
