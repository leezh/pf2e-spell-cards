#!/usr/bin/env python

import json
import os
import pathlib
import re
import textwrap
import unicodedata

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag
from markdown import markdown
from opensearchpy import OpenSearch

BASE_DIR = pathlib.Path(os.path.dirname(__file__)) / "data"

NETHYS_HOST = 'elasticsearch.aonprd.com'
NETHYS_PORT = 443
NETHYS_SSL = True
NETHYS_INDEX = 'aon'
NETHYS_BATCH_SIZE = 50
SOURCES = {
    "Player Core": "2023 Paizo Inc.",
    "Player Core 2": "2024 Paizo Inc.",
}


def to_slug(text: str) -> str:
    text = (
        unicodedata.normalize("NFKD", text)
        .lower()
        .replace(" ", "_")
        .encode("ASCII", "ignore")
        .decode("ASCII")
    )
    return "".join([c for c in text if c.isalnum() or c == "_"])


def strip_element(soup: BeautifulSoup | Tag, name: str, string: str | None = None):
    element = soup.find(name, string=string)
    if isinstance(element, Tag):
        element.extract()


def text_to_soup(text: str) -> BeautifulSoup:
    soup = BeautifulSoup(text, "html.parser")
    for elem in [*soup.descendants]:
        if (
            isinstance(elem, NavigableString)
            and elem.parent
            and elem.parent.name in ["li", "td"]
        ):
            elem_soup = BeautifulSoup(markdown(str(elem)), "html.parser")
            contents = []
            for e in elem_soup.find_all("p"):
                contents.extend(e.contents)
            elem.replace_with(*contents)
    html = markdown(str(soup))
    soup = BeautifulSoup(html, "html.parser")
    for sup in soup.find_all("sup"):
        sup.extract()
    for a in soup.find_all("a"):
        a.replace_with(*a.contents)
    return soup


WHITELIST_TAGS = [
    "p",
    "hr",
    "strong",
    "em",
    "li",
    "ul",
    "br",
    "table",
    "tr",
    "th",
    "td",
]


def tidy_soup(soup: BeautifulSoup) -> None:
    for elem in [*soup.descendants]:
        if not isinstance(elem, Tag):
            continue
        elem.attrs = {}
        if elem.name not in WHITELIST_TAGS:
            if elem.parent == soup:
                elem.extract()
            else:
                elem.replace_with(*elem.contents)
        if elem.name == "br" and elem.parent and elem.parent.name in ["p", "li"]:
            following = []
            for sibling in [*elem.next_siblings]:
                following.append(sibling.extract())
            new_tag = soup.new_tag(name=elem.parent.name)
            new_tag.extend(following)
            elem.parent.insert_after(new_tag)
            elem.extract()

    for elem in soup.contents:
        if isinstance(elem, NavigableString):
            elem.extract()

    soup.smooth()
    for elem in [*soup.descendants]:
        if isinstance(elem, NavigableString):
            if not elem.strip(" \n"):
                elem.extract()
            else:
                elem.replace_with(elem.replace("\n", " "))

    for p in soup.find_all("p"):
        if not len(p.contents):
            p.extract()
            continue


def format_soup(soup: BeautifulSoup) -> str:
    for p in soup.find_all(["p", "li"]):
        assert isinstance(p, Tag)
        if not len(p.contents):
            p.extract()
            continue
        text = p.contents[0]
        if isinstance(text, NavigableString):
            if not text.strip():
                text.extract()
            text.replace_with(text.lstrip())
        text = p.contents[-1]
        if isinstance(text, NavigableString):
            if not text.strip():
                text.extract()
            text.replace_with(text.rstrip())
        p.insert_after("\n")
    for ul in soup.find_all("ul"):
        assert isinstance(ul, Tag)
        ul.insert(0, "\n")
        ul.insert_after("\n")
    for hr in soup.find_all("hr"):
        assert isinstance(hr, Tag)
        hr.insert_after("\n")
    text = str(soup)
    text = re.sub(r" {2,}", " ", text)
    return text


ACTION_SUBSTITUTION = [
    ("Reaction", "[reaction]"),
    ("Free Action", "[free-action]"),
    ("Single Action", "[one-action]"),
    ("Two Actions", "[two-actions]"),
    ("Three Actions", "[three-actions]"),
    ("or", "TO"),
    ("to", "TO"),
]

FILTER_TRAITS = [
    "uncommon",
    "rare",
    "positive",
    "negative",
    "metamagic",
]

NO_TITLE_UPPERCASE = [
    "a",
    "an",
    "the",
    "as",
    "and",
    "but",
    "for",
    "if",
    "its",
    "nor",
    "or",
    "at",
    "by",
    "in",
    "into",
    "of",
    "on",
]


def title_case(text: str) -> str:
    words = text.strip().lower().split(" ")
    title = " ".join(
        [(w if w in NO_TITLE_UPPERCASE else w.capitalize()) for w in words]
    )
    return "".join([title[0].upper(), *title[1:]])

REMOVED_PARAMETERS = [
    "Deity",
    "Deities",
    "Source",
    "Spell Lists",
]

RENAMED_PARAMETERS = {
    "Bloodlines": "Bloodline",
    "Deities": "Deity",
    "Domains": "Domain",
    "Lessons": "Lesson",
    "Mysteries": "Mystery",
    "Patron Theme": "Patron",
    "Patron Themes": "Patron",
    "Tradition": "Traditions",
    "Target": "Targets",
    "Saving Throw": "Defense"
}

COLLAPSED_PARAMETERS = [
    ("range", "targets"),
    ("range", "area"),
    ("defense", "duration")
]

FILTERED_PARAMETERS = [
    ("traditions", "traditions", "", (
        "arcane",
        "divine",
        "occult",
        "primal",
    )),
    ("domains", "domain", "cleric", (
        "air",
        "ambition",
        "cities",
        "confidence",
        "creation",
        "darkness",
        "death",
        "destruction",
        "dreams",
        "earth",
        "family",
        "fate",
        "fire",
        "freedom",
        "healing",
        "indulgence",
        "knowledge",
        "luck",
        "magic",
        "might",
        "moon",
        "nature",
        "nightmares",
        "pain",
        "passion",
        "perfection",
        "protection",
        "secrecy",
        "sun",
        "travel",
        "trickery",
        "truth",
        "tyranny",
        "undeath",
        "water",
        "wealth",
        "zeal",
    )),
    ("mysteries", "mystery", "oracle", (
        "ancestors",
        "battle",
        "bones",
        "cosmos",
        "flames",
        "life",
        "lore",
        "tempest",
    )),
    ("bloodlines", "bloodline", "sorcerer", (
        "aberrant",
        "angelic",
        "demonic",
        "diabolic",
        "draconic",
        "elemental",
        "fey",
        "hag",
        "imperial",
        "undead",
    )),
    ("lessons", "lesson", "witch", (
        "dreams",
        "elements",
        "life",
        "protection",
        "vengeance",
        "mischief",
        "shadow",
        "snow",
        "death",
        "renewal"
    )),
    ("patrons", "patron", "witch", (
        "Faith's Flamekeeper",
        "The Inscribed One",
        "The Resentment",
        "Silence in Snow",
        "Spinner of Threads",
        "Starless Shadow",
        "Wilding Steward",
    )),
]

def parse_parameter(soup: BeautifulSoup, p: Tag, key: Tag):
    if next_key := key.find_next_sibling("strong"):
        assert isinstance(next_key, Tag)
        siblings = [elem.extract() for elem in next_key.next_siblings]
        next_p = soup.new_tag("p")
        next_p.append(next_key.extract())
        next_p.extend(siblings)
        p.insert_after(next_p)
        parse_parameter(soup, next_p, next_key)
    value = key.next_sibling
    assert isinstance(value, NavigableString)
    if key.string in RENAMED_PARAMETERS:
        key.string = RENAMED_PARAMETERS[key.string]
    if key.string in REMOVED_PARAMETERS:
        p.extract()
    p.attrs["class"] = key.string.lower()


def parse_header(soup: BeautifulSoup, info: dict) -> None:
    for p in [*soup.contents]:
        if not isinstance(p, Tag) or p.name != "p" or not len(p.contents):
            break
        if p.find("strong", string="PFS Note"):
            p.extract()
            continue
        key = p.contents[0]
        if not isinstance(key, Tag) or key.name != "strong":
            break
        if not isinstance(key.next_sibling, NavigableString):
            break
        parse_parameter(soup, p, key)

    for left, right in COLLAPSED_PARAMETERS:
        left_tag = soup.find("p", class_=left)
        right_tag = soup.find("p", class_=right)
        if not isinstance(left_tag, Tag) or not isinstance(right_tag, Tag):
            continue
        elements = [e.extract() for e in [*right_tag.contents]]
        right_tag.extract()
        left_tag.extend(["; ", *elements])

    for attribute, name, trait, _ in FILTERED_PARAMETERS:
        tag = soup.find("p", class_=name)
        if not isinstance(tag, Tag):
            continue
        values = info[attribute]
        if not len(values) or (trait and trait not in info["traits"]):
            tag.extract()
            continue
        [*tag.children][1].replace_with(f" {', '.join(info[attribute])}")


def parse_entry(entry: dict):
    source = entry["primary_source"]
    if source not in SOURCES:
        return

    copyright = SOURCES[source]
    source = f"Pathfinder {source}"
    book = to_slug(source)
    title = title_case(entry["name"])
    entry_id = to_slug(title)

    book_dir = BASE_DIR / book
    os.makedirs(book_dir, exist_ok=True)
    path = book_dir / f"{entry_id}.yaml"
    if os.path.exists(path):
        pass

    actions = entry["actions"] if entry.get("actions_number", 60) < 7 else ""
    for src, dst in ACTION_SUBSTITUTION:
        actions = actions.replace(src, dst)

    traits = [x.lower() for x in entry["trait"]]
    traits = [x for x in traits if x not in FILTER_TRAITS]

    info = {
        "id": entry_id,
        "title": title,
        "actions": actions,
        "type": entry["spell_type"].lower(),
        "level": entry["level"],
        "rarity": entry["rarity"],
        "traits": traits,
        "traditions": [x.lower() for x in entry.get("tradition", [])],
        "domains": [x.lower() for x in entry.get("domain", [])],
        "mysteries": [x.lower() for x in entry.get("mystery", [])],
        "bloodlines": [x.lower() for x in entry.get("bloodline", [])],
        "lessons": [x.lower().replace("lesson of ", "") for x in entry.get("lesson", [])],
        "patrons": [x for x in entry.get("patron_theme", [])],
        "source": source,
        "copyright": copyright,
    }

    for attribute, _, _, values in FILTERED_PARAMETERS:
        info[attribute] = [x for x in info[attribute] if x in values]

    soup = text_to_soup(entry["markdown"])
    strip_element(soup, "title")
    strip_element(soup, "traits")
    tidy_soup(soup)
    parse_header(soup, info)

    if isinstance(soup.contents[0], Tag) and soup.contents[0].name == "hr":
        soup.contents[0].extract()

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(info, f)
        f.write("\n--- >\n")
        f.write(textwrap.indent(format_soup(soup), "  "))


def parse() -> None:
    with open(BASE_DIR / "scrape.json", "r", encoding="utf-8") as f:
        for entry in json.load(f):
            parse_entry(entry)


def download():
    target = BASE_DIR / "scrape.json"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if os.path.exists(target):
        return
    client = OpenSearch(
        hosts=[{"host": NETHYS_HOST, "port": NETHYS_PORT}],
        use_ssl=NETHYS_SSL
    )
    data = []
    total = 1
    query = {
        "bool": {
            "must": [
                {"term": {"category": "spell"}},
            ],
            "must_not": [
                {"exists": {"field": "item_child_id"}},
                {"term": {"exclude_from_search": True}},
                {"term": {"trait": "mythic"}},
            ]
        }
    }

    while len(data) < total:
        payload = {
            "from": len(data),
            "size": NETHYS_BATCH_SIZE,
            "query": query
        }
        result = client.search(index="aon", body=payload)
        total = result["hits"]["total"]["value"]
        data.extend([x["_source"] for x in result["hits"].get("hits", [])])

    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f)


if __name__ == "__main__":
    download()
    parse()
