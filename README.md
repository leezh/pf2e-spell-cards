# Pathfinder2E Spell Cards

An unofficial spell card generator for Pathfinder 2nd Edition
(Remastered).

The spells are formatted for tarrot card sizes (70mm x 120mm) which you
can find plastic card sleeves for online. The cards also have a 4mm
corner radius which is a common size for corner punches.

Once you have the cards you want you can then print them using the
browser's print functionality.

## Adding Spells

Spell data is stored as YAML files in `data/<book_name>/` in a
format like so:

```yaml
actions: '[two-actions]'
bloodlines: []
copyright: 2024 Example Inc.
domains: []
id: spell_id
lessons: []
level: 2
mysteries: []
patrons: []
rarity: common
source: Homebrew
title: Spell Title
traditions:
- arcane
traits:
- concentrate
- manipulate
type: spell

--- >
  <p>card 1 description</p>

--- >
  <p>card 2 description</p>

```

Once changes have been made you can rebuild the page with:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python build.py
```

To view the result you can go to the `build/` folder and use your
favourite static file server such as `python -m http.server`.

I have also included a script that cleans up JSON data from Archives of
Nethys and generates the spell files. Some manual tweaking is required
as it won't always convert the data cleanly and it won't split long
descriptions into multiple cards. Place the JSON files from the search
in the `scrape/` folder and run `scraper.py`. It won't overwrite
existing files so you need to remove the old one if you're regenerating.

## Pull Requests

You can submit pull requests to add spells to this repo - although until
a better source filtering is implemented, only Rulebook sources are
accepted.

## License

Copyright (C) 2024 Zoe Lee (lee.zh.92@gmail.com)

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or (at
your option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero
General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.


**Note**

Files in `data/` are under a separate license `data/LICENSE-ORC.md` from
Paizo.

Files in `fonts/` are under a separate license `fonts/LICENSE-OFL.md`
from The Mozilla Foundation.
