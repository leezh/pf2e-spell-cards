#!/usr/bin/env python

import json
import os
import pathlib
import shutil

import yaml

BASE_DIR = pathlib.Path(os.path.dirname(__file__))


def build():
    entries = {}
    spells_dir = BASE_DIR / "data"
    for book in os.listdir(spells_dir):
        if not os.path.isdir(spells_dir / book):
            continue
        for file in os.listdir(spells_dir / book):
            if not file.endswith(".yaml"):
                continue
            with open(spells_dir / book / file, "r", encoding="utf-8") as f:
                data = [*yaml.safe_load_all(f)]
            data[0]["description"] = data[1]
            entries[data[0]["id"]] = data[0]
    entries = {k: entries[k] for k in sorted(entries.keys())}

    build_dir = BASE_DIR / "build"

    os.makedirs(build_dir / "icons", exist_ok=True)
    for path in os.listdir(BASE_DIR / "data" / "icons"):
        shutil.copy(BASE_DIR / "data" / "icons" / path, build_dir / "icons" / path)

    os.makedirs(build_dir / "fonts", exist_ok=True)
    for path in os.listdir(BASE_DIR / "fonts"):
        shutil.copy(BASE_DIR / "fonts" / path, build_dir / "fonts" / path)

    for path in os.listdir(BASE_DIR / "web"):
        shutil.copy(BASE_DIR / "web" / path, build_dir / path)

    with open(build_dir / "data.json", "w", encoding="utf-8") as f:
        json.dump(entries, f)


if __name__ == "__main__":
    build()
