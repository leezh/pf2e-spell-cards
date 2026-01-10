#!/usr/bin/env python

import json
import os
import pathlib
import re
import textwrap
import unicodedata
from collections.abc import Callable

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag
from markdown2 import markdown
from opensearchpy import OpenSearch


NETHYS_HOST = 'elasticsearch.aonprd.com'
NETHYS_PORT = 443
NETHYS_SSL = True
NETHYS_INDEX = 'aon'
NETHYS_BATCH_SIZE = 50


SOURCES = {
    "Core Rulebook": ("Pathfinder ", "2019 Paizo Inc.", "legacy"),
    "Advanced Player's Guide": ("Pathfinder ", "2020 Paizo Inc.", "legacy"),
    "Gamemastery Guide": ("Pathfinder ", "2019 Paizo Inc.", "legacy"),
    "Secrets of Magic": ("Pathfinder ", "2021 Paizo Inc.", "legacy"),
    "Player Core": ("Pathfinder ", "2023 Paizo Inc.", "remaster"),
    "Player Core 2": ("Pathfinder ", "2024 Paizo Inc.", "remaster"),
    "Guns & Gears": ("Pathfinder ", "2021 Paizo Inc.", "both"),
    "Book of the Dead": ("Pathfinder ", "2023 Paizo Inc.", "legacy"),
    "Dark Archive": ("Pathfinder ", "2022 Paizo Inc.", "legacy"),
    "Treasure Vault": ("Pathfinder ", "2023 Paizo Inc.", "both"),
    "Rage of Elements": ("Pathfinder ", "2023 Paizo Inc.", "remaster"),
    "Howl of the Wild": ("Pathfinder ", "2024 Paizo Inc.", "remaster"),
    "War of Immortals": ("Pathfinder ", "2024 Paizo Inc.", "remaster"),
    "Battlecry!": ("Pathfinder ", "2025 Paizo Inc.", "remaster"),
}

ACTION_SUBSTITUTION = {
    "Reaction": "[reaction]",
    "Free Action": "[free-action]",
    "Single Action": "[one-action]",
    "Two Actions": "[two-actions]",
    "Three Actions": "[three-actions]",
}

RENAMED_PARAMETERS = {
    "Bloodlines": "Bloodline",
    "Deities": "Deity",
    "Domains": "Domain",
    "Lessons": "Lesson",
    "Mysteries": "Mystery",
    "Patron Themes": "Patron",
    "Patron Theme": "Patron",
    "Tradition": "Traditions",
    "Target": "Targets",
    "Saving Throw": "Defense"
}

LOWERCASE_PARAMETERS = [
    "traditions",
    "domain",
    "mystery",
    "bloodline",
    "lesson",
    "patron",
]

HIDDEN_PARAMETERS = [
    "deity",
    "source",
    "spell-lists",
]

COLLAPSED_PARAMETERS = [
    ("range", "targets"),
    ("range", "area"),
    ("area", "targets"),
    ("defense", "duration")
]

CLASS_PARAMETERS = {
    "domain": "Cleric",
    "mystery": "Oracle",
    "bloodline": "Sorcerer",
    "lesson": "Witch",
    "patron": "Witch",
}

FILTERS = {
    "filters": {
        "Type": ["Cantrip", "Spell", "Focus"],
        "Level": {f"Level {level}": level for level in range(1, 11)},
        "Rarity": ["Common", "Uncommon", "Rare"],
    },
    "legacy": {
        "Traditions": ["No Tradition", "Arcane", "Divine", "Occult", "Primal", "Elemental"],
        "Traits": [],
        "Source": [f"{SOURCES[s][0]}{s}" for s in SOURCES if SOURCES[s][2] in ["legacy", "both"]],
    },
    "remaster": {
        "Traditions": ["No Tradition", "Arcane", "Divine", "Occult", "Primal"],
        "Traits": [],
        "Source": [f"{SOURCES[s][0]}{s}" for s in SOURCES if SOURCES[s][2] in ["remaster", "both"]],
    }
}

BASE_DIR = pathlib.Path(os.path.dirname(__file__)) / "data"

ADJUSTMENTS: list[Callable[[dict, BeautifulSoup], None]] = []


def to_slug(text: str) -> str:
    text = (
        unicodedata.normalize("NFKD", text)
        .lower()
        .replace(" ", "_")
        .encode("ASCII", "ignore")
        .decode("ASCII")
    )
    return "".join([c for c in text if c.isalnum() or c == "_"])


def text_to_soup(text: str) -> BeautifulSoup:
    # Workaround for Markdown inside HTML tags
    soup = BeautifulSoup(text, "html.parser")
    for elem in soup.find_all(["p", "li", "td"]):
        html = markdown(str(elem), extras=["cuddled-lists"]).strip()
        elem_soup = BeautifulSoup(html, "html.parser")
        for p in [x for x in elem_soup.contents if isinstance(x, Tag) and x.name == "p"]:
            p.replace_with(*p.contents)
        elem.replace_with(elem_soup)
    html = markdown(str(soup), extras=["cuddled-lists"])
    soup = BeautifulSoup(html, "html.parser")
    for elem in [x for x in soup.descendants if isinstance(x, Tag)]:
        attrs = elem.attrs
        parent = elem.parent
        elem.attrs = {}
        match elem.name:
            case "title" | "traits" | "sup":
                elem.extract()
            case "li":
                if parent and parent.name == "p":
                    new_tag = soup.new_tag("p")
                    new_tag.extend([x.extract() for x in elem.next_siblings])
                    parent.insert_after(elem.extract())
                    parent.insert_after(new_tag)
            case "br":
                if parent and parent.name in ["li", "p"] and parent.parent:
                    new_tag = soup.new_tag("p")
                    if parent.name == "li":
                        new_tag.attrs["class"] = "indent"
                    elif "class" in parent.attrs:
                        new_tag.attrs["class"] = parent.attrs["class"]
                    new_tag.extend([x.extract() for x in elem.next_siblings])
                    parent.insert_after(new_tag)
                elem.extract()
            case "actions":
                elem.replace_with(ACTION_SUBSTITUTION[attrs["string"]])
            case "b" | "strong":
                elem.name = "strong"
            case "i" | "em":
                elem.name = "em"
            case "p":
                if parent and parent.name in ["li", "p"] and parent.parent:
                    new_tag = soup.new_tag("p")
                    if parent.name == "li":
                        new_tag.attrs["class"] = "indent"
                    elif "class" in parent.attrs:
                        new_tag.attrs["class"] = parent.attrs["class"]
                    new_tag.extend([x.extract() for x in elem.next_siblings])
                    parent.insert_after(new_tag)
                    elem.replace_with(*elem.contents)
            case "table" | "tr" | "td" | "hr":
                if parent and parent.name == "p":
                    parent.replace_with(elem)
            case _:
                elem.replace_with(*elem.contents)
    soup.smooth()
    for elem in [x for x in soup.descendants if isinstance(x, NavigableString)]:
        if not elem.strip(" \n"):
            elem.extract()
        else:
            elem.replace_with(elem.replace("\n", " "))
    soup.smooth()
    for elem in [*soup.contents]:
        if isinstance(elem, NavigableString):
            if str(elem).strip():
                new_tag = soup.new_tag("p", string=str(elem).strip())
                elem.insert_after(new_tag)
            elem.extract()
    for elem in soup.find_all("p"):
        if not len(elem.contents):
            elem.extract()
        elif elem.contents[0].name == "strong":
            current_class = elem.attrs.get("class", "")
            if isinstance(elem.previous_sibling, Tag):
                if elem.previous_sibling.name == "li":
                    current_class = "indent"
                if elem.previous_sibling.attrs.get("class", "").startswith("indent"):
                    current_class = "indent"
            elem.attrs["class"] = f"{current_class} hanging-indent".strip()
    return soup


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
    for hr in soup.find_all("hr"):
        assert isinstance(hr, Tag)
        hr.insert_after("\n")
    for strong in soup.find_all("strong"):
        if isinstance(strong.next_sibling, Tag) and strong.next_sibling.name == "em":
            strong.insert_after(" ")
    text = str(soup)
    text = re.sub(r" {2,}", " ", text)
    return text


def parse_parameter(soup: BeautifulSoup, p: Tag, key: Tag):
    if next_key := key.find_next_sibling("strong"):
        siblings = [elem.extract() for elem in next_key.next_siblings]
        next_p = soup.new_tag("p")
        next_p.append(next_key.extract())
        next_p.extend(siblings)
        p.insert_after(next_p)
        parse_parameter(soup, next_p, next_key)
    if key.string in RENAMED_PARAMETERS:
        key.string = RENAMED_PARAMETERS[key.string]
    value = key.next_sibling
    slug = key.string.lower().replace(" ", "-")
    if isinstance(value, NavigableString):
        text = value.rstrip(" ;")
        if slug in LOWERCASE_PARAMETERS:
            text = text.lower()
        if slug == "lesson":
            text = text.replace("lesson of the ", "")
            text = text.replace("lesson of ", "")
        value.replace_with(text)
    if slug in HIDDEN_PARAMETERS:
        p.extract()
    p.attrs["class"] = f"hanging-indent {slug}"


def parse_header(soup: BeautifulSoup, info: dict) -> None:
    for p in [x for x in soup.contents if isinstance(x, Tag)]:
        if p.name != "p":
            break
        if next(p.stripped_strings).startswith("PFS Note"):
            p.extract()
            continue
        key = p.contents[0]
        if not isinstance(key, Tag) or key.name != "strong":
            break
        parse_parameter(soup, p, key)

    for left, right in COLLAPSED_PARAMETERS:
        left_tag = soup.find("p", class_=f"hanging-indent {left}")
        right_tag = soup.find("p", class_=f"hanging-indent {right}")
        if not isinstance(left_tag, Tag) or not isinstance(right_tag, Tag):
            continue
        elements = [e.extract() for e in [*right_tag.contents]]
        right_tag.extract()
        left_tag.extend(["; ", *elements])

    for attribute, trait in CLASS_PARAMETERS.items():
        tag = soup.find("p", class_=f"hanging-indent {attribute}")
        if isinstance(tag, Tag) and trait not in info["traits"]:
            tag.extract()
            continue


def parse_entry(entry: dict) -> dict | None:
    source = entry["primary_source"]
    if source not in SOURCES:
        return None

    source = f"{SOURCES[source][0]}{source}"
    title = entry["name"]

    book_dir = BASE_DIR / to_slug(source)
    os.makedirs(book_dir, exist_ok=True)
    path = book_dir / f"{to_slug(title)}.yaml"
    if os.path.exists(path):
        pass

    actions = entry["actions"] if entry.get("actions_number", 60) < 7 else ""
    for src, dst in ACTION_SUBSTITUTION.items():
        actions = actions.replace(src, dst)

    rarity = entry["rarity"].title()
    traits = sorted(entry["trait_raw"])
    if rarity in traits:
        traits.remove(rarity)

    info = {
        "id": entry["id"],
        "title": title,
        "actions": actions,
        "type": entry["spell_type"],
        "level": entry["level"],
        "rarity": rarity,
        "traits": traits,
        "traditions": entry.get("tradition", []),
        "domain": entry.get("domain", []),
        "mystery": entry.get("mystery", []),
        "bloodline": entry.get("bloodline", []),
        "lesson": [x.replace("Lesson of ", "") for x in entry.get("lesson", [])],
        "patron": entry.get("patron_theme", []),
        "remaster": SOURCES[entry["primary_source"]][2] in ["remaster", "both"],
        "legacy": SOURCES[entry["primary_source"]][2] in ["legacy", "both"],
        "source": source,
        "copyright": SOURCES[entry["primary_source"]][1],
    }

    soup = text_to_soup(entry["markdown"])
    parse_header(soup, info)

    if isinstance(soup.contents[0], Tag) and soup.contents[0].name == "hr":
        soup.contents[0].extract()

    for func in ADJUSTMENTS:
        func(info, soup)

    description = format_soup(soup)

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(info, f)
        f.write("\n--- >\n")
        f.write(textwrap.indent(description, "  "))

    info["description"] = description
    return info


def parse() -> None:
    legacy_traits = set()
    remaster_traits = set()

    with open(BASE_DIR / "scrape.json", "r", encoding="utf-8") as f:
        for entry in json.load(f):
            info = parse_entry(entry)
            if not info:
                continue
            if info["legacy"]:
                legacy_traits.update(info["traits"])
            if info["remaster"]:
                remaster_traits.update(info["traits"])

    FILTERS["legacy"]["Traits"] = sorted(legacy_traits)
    FILTERS["remaster"]["Traits"] = sorted(remaster_traits)

    with open(BASE_DIR / "filters.json", "w", encoding="utf-8") as f:
        json.dump(FILTERS, f, indent=2)


@ADJUSTMENTS.append
def adjust_avatar(info: dict, soup: BeautifulSoup):
    if info["title"] != "Avatar":
        return
    for elem in [*soup.find("strong", string="Zon-Kuthon").parent.next_siblings]:
        elem.extract()


@ADJUSTMENTS.append
def adjust_table_headers(info: dict, soup: BeautifulSoup):
    for elem in soup.find_all("p"):
        children = [*elem.children]
        if len(children) == 1 and isinstance(children[0], NavigableString):
            text = str(children[0]).strip()
            if len(text.split(" ")) < 3:
                elem.extract()


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
