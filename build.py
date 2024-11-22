#!/usr/bin/env python

import json
import os
import shutil
import yaml


def build():
    entries = {}
    spells_dir = os.path.join("data")
    os.makedirs(spells_dir, exist_ok=True)
    for book in os.listdir(spells_dir):
        if not os.path.isdir(os.path.join(spells_dir, book)):
            continue
        for file in os.listdir(os.path.join(spells_dir, book)):
            if not file.endswith(".yaml"):
                continue
            with open(os.path.join(spells_dir, book, file), "r", encoding="utf-8") as f:
                data = [*yaml.safe_load_all(f)]
            data[0]["description"] = data[1:]
            entries[data[0]["id"]] = data[0]
    entries = {k: entries[k] for k in sorted(entries.keys())}
    os.makedirs(os.path.join("build", "icons"), exist_ok=True)
    os.makedirs(os.path.join("build", "fonts"), exist_ok=True)
    for path in os.listdir(os.path.join("data", "icons")):
        shutil.copy(os.path.join("data", "icons", path), os.path.join("build", "icons", path))
    for path in os.listdir("fonts"):
        shutil.copy(os.path.join("fonts", path), os.path.join("build", "fonts", path))
    for path in os.listdir("web"):
        shutil.copy(os.path.join("web", path), os.path.join("build", path))
    with open(os.path.join("build", "data.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f)


if __name__ == "__main__":
    build()
