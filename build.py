#!/usr/bin/env python

import json
import os
import pathlib
import shutil

import yaml

BASE_DIR = pathlib.Path(os.path.dirname(__file__))
DATA_DIR = BASE_DIR / "data"
BUILD_DIR = BASE_DIR / "build"


def build():
    data = {}

    with open(DATA_DIR / "filters.json", "r", encoding="utf-8") as f:
        data.update(json.load(f))

    spells = []
    for book in os.listdir(DATA_DIR):
        if not os.path.isdir(DATA_DIR / book):
            continue
        for file in os.listdir(DATA_DIR / book):
            if not file.endswith(".yaml"):
                continue
            with open(DATA_DIR / book / file, "r", encoding="utf-8") as f:
                entry = [*yaml.safe_load_all(f)]
                entry = { **entry[0], "description": entry[1] }
            spells.append(entry)
            for edition in ["legacy", "remaster"]:
                if entry[edition]:
                    if entry["source"] not in data[edition]["Source"]:
                        data[edition]["Source"].append(entry["source"])
                    for trait in entry["traits"]:
                        if trait not in data[edition]["Traits"]:
                            data[edition]["Traits"].append(trait)
    data["spells"] = sorted(spells, key=lambda x: x["title"])
    for edition in ["legacy", "remaster"]:
        data[edition]["Traits"] = sorted(data[edition]["Traits"])

    os.makedirs(BUILD_DIR / "icons", exist_ok=True)
    for path in os.listdir(BASE_DIR / "data" / "icons"):
        shutil.copy(BASE_DIR / "data" / "icons" / path, BUILD_DIR / "icons" / path)

    os.makedirs(BUILD_DIR / "fonts", exist_ok=True)
    for path in os.listdir(BASE_DIR / "fonts"):
        shutil.copy(BASE_DIR / "fonts" / path, BUILD_DIR / "fonts" / path)

    for path in os.listdir(BASE_DIR / "web"):
        shutil.copy(BASE_DIR / "web" / path, BUILD_DIR / path)

    with open(BUILD_DIR / "data.json", "w", encoding="utf-8") as f:
        json.dump(data, f)


if __name__ == "__main__":
    build()
