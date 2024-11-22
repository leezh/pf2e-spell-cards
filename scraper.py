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

from build import build

BASE_DIR = pathlib.Path(os.path.dirname(__file__))

SOURCES = {
    "Player Core": "2023 Paizo Inc.",
    "Player Core 2": "2024 Paizo Inc.",
}


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


def read_header(soup: BeautifulSoup) -> dict:
    title = soup.find("title")
    if not isinstance(title, Tag):
        raise KeyError("Entry is missing <title>")

    actions = title.find("actions")
    actions = str(actions.extract()["string"]) if isinstance(actions, Tag) else ""
    for src, dst in ACTION_SUBSTITUTION:
        actions = actions.replace(src, dst)

    entry_type = title.attrs.get("right", " ").rsplit(" ", 1)
    level = int(entry_type[1])
    entry_type = entry_type[0].lower()

    title = title.extract()
    title = title_case(" ".join(title.stripped_strings))

    entry_id = unicodedata.normalize("NFKD", title).lower().replace(" ", "_")
    entry_id = entry_id.encode("ASCII", "ignore").decode("ASCII")
    entry_id = "".join([c for c in entry_id if c.isalnum() or c == "_"])

    traits = soup.find("traits")
    if isinstance(traits, Tag):
        traits = traits.extract()
        traits = [str(t["label"]).lower() for t in traits.find_all("trait")]
        traits.sort()
    else:
        traits = []

    rarity = "common"
    if "uncommon" in traits:
        traits.remove("uncommon")
        rarity = "uncommon"
    if "rare" in traits:
        traits.remove("rare")
        rarity = "rare"

    return {
        "id": entry_id,
        "title": title,
        "actions": actions,
        "type": entry_type,
        "level": level,
        "rarity": rarity,
        "traits": traits,
    }


FILTER_PATRONS = [
    "Faith's Flamekeeper",
    "The Inscribed One",
    "The Resentment",
    "Silence in Snow",
    "Spinner of Threads",
    "Starless Shadow",
    "Wilding Steward",
]
FILTER_LESSONS = [
    "dreams",
    "elements",
    "life",
    "protection",
    "vengeance",
    "mischief",
    "shadow",
    "snow",
    "death",
    "renewal",
]


def read_parameter(soup: BeautifulSoup, p: Tag, key: Tag, traits: list[str]) -> dict:
    result = {}
    if next_key := key.find_next_sibling("strong"):
        assert isinstance(next_key, Tag)
        siblings = [elem.extract() for elem in next_key.next_siblings]
        next_p = soup.new_tag("p")
        next_p.append(next_key.extract())
        next_p.extend(siblings)
        p.insert_after(next_p)
        result = read_parameter(soup, next_p, next_key, traits)
    value = key.next_sibling
    assert isinstance(value, NavigableString)
    match key.string:
        case "Source":
            source = value.split(" pg.", 1)[0].strip()
            p.extract()
            result["copyright"] = SOURCES[source]
            result["source"] = f"Pathfinder {source}"
        case "Tradition" | "Traditions":
            values = [t.strip().lower() for t in value.split(",")]
            values.sort()
            key.string = "Traditions"
            value.replace_with(f" {', '.join(values)}")
            result["traditions"] = values
        case "Domain" | "Domains":
            values = [t.strip().lower() for t in value.split(",")]
            values.sort()
            if "cleric" not in traits:
                p.extract()
            key.string = "Domain"
            value.replace_with(f" {', '.join(values)}")
            result["domains"] = values
        case "Mystery":
            values = [t.strip().lower() for t in value.split(",")]
            values.sort()
            if "oracle" not in traits:
                p.extract()
            key.string = "Mystery"
            value.replace_with(f" {', '.join(values)}")
            result["mysteries"] = values
        case "Bloodline" | "Bloodlines":
            values = [t.strip().lower() for t in value.split(",")]
            values.sort()
            if "sorcerer" not in traits:
                p.extract()
            key.string = "Bloodline"
            value.replace_with(f" {', '.join(values)}")
            result["bloodlines"] = values
        case "Patron Theme" | "Patron Themes":
            values = [t.strip() for t in value.split(",")]
            values.sort()
            for patron in [*values]:
                if patron not in FILTER_PATRONS:
                    values.remove(patron)
            if "witch" not in traits:
                p.extract()
            key.string = "Patron"
            value.replace_with(f" {', '.join(values)}")
            result["patrons"] = values
        case "Lesson":
            values = [t.strip().lower() for t in value.split(",")]
            for lesson in [*values]:
                values.remove(lesson)
                lesson = lesson.replace("lesson of the ", "")
                lesson = lesson.replace("lesson of ", "")
                if lesson not in FILTER_LESSONS:
                    continue
                values.append(lesson)
            values.sort()
            if not len(values) or "witch" not in traits:
                p.extract()
            key.string = "Lesson"
            value.replace_with(f" {', '.join(values)}")
            result["bloodlines"] = values
        case "Trigger" | "Requirements" | "Cast" | "Range" | "Area" | "Duration":
            pass
        case "Target" | "Targets":
            key.string = "Targets"
        case "Defense" | "Saving Throw":
            key.string = "Defense"
        case "Deity" | "Deities" | "Spell Lists":
            p.extract()
        case _:
            return result
    p.attrs["class"] = key.string.lower()
    return result


def collapse_parameters(soup: BeautifulSoup) -> None:
    range = soup.find("p", class_="range")
    targets = soup.find("p", class_="targets")
    area = soup.find("p", class_="area")
    defense = soup.find("p", class_="defense")
    duration = soup.find("p", class_="duration")

    if isinstance(range, Tag) and isinstance(targets, Tag):
        elements = [e.extract() for e in [*targets.contents]]
        targets.extract()
        range.extend(["; ", *elements])
    if isinstance(range, Tag) and isinstance(area, Tag):
        elements = [e.extract() for e in [*area.contents]]
        area.extract()
        range.extend(["; ", *elements])
    if isinstance(defense, Tag) and isinstance(duration, Tag):
        elements = [e.extract() for e in [*duration.contents]]
        duration.extract()
        defense.extend(["; ", *elements])


def parse_entry(entry: dict) -> dict:
    soup = text_to_soup(entry["markdown"])
    result = {
        **read_header(soup),
        "traditions": [],
        "domains": [],
        "mysteries": [],
        "bloodlines": [],
        "lessons": [],
        "patrons": [],
        "source": "",
        "copyright": "",
        "description": [],
    }
    tidy_soup(soup)

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
        result.update(read_parameter(soup, p, key, result["traits"]))

    collapse_parameters(soup)

    if isinstance(soup.contents[0], Tag) and soup.contents[0].name == "hr":
        soup.contents[0].extract()
    result["description"] = [format_soup(soup)]
    return result


def scrape() -> None:
    entries = {}
    entry_list = []
    for path in os.listdir(BASE_DIR / "scrape"):
        if not path.endswith(".json"):
            continue
        with open(BASE_DIR / "scrape" / path, "r", encoding="utf-8") as f:
            entry_list.extend(json.load(f))

    for entry in entry_list:
        if set(entry["source"]).isdisjoint(set(SOURCES.keys())):
            continue
        entry = parse_entry(entry)
        entries[entry["id"]] = entry

    for entry_id, entry in entries.items():
        book = entry["source"].lower().replace(" ", "_")
        book_dir = BASE_DIR / "data" / book
        os.makedirs(book_dir, exist_ok=True)
        path = book_dir / f"{entry_id}.yaml"
        if os.path.exists(path):
            continue
        with open(path, "w", encoding="utf-8") as f:
            entry = entry.copy()
            description = entry.pop("description")
            yaml.safe_dump(entry, f)
            for block in description:
                f.write("\n--- >\n")
                f.write(textwrap.indent(block, "  "))


if __name__ == "__main__":
    scrape()
