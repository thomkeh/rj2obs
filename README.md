# rj2obs - Roam JSON To Obsidian Converter

Converts Roam JSON export to Obsidian Markdown files.

I wrote this to convert my own roam export into an Obsidian friendly format.

Output has the following directory structure:

* `md/` : contains all normal Markdown files
* `md/daily/`: contains all daily notes

### Features:

* Daily note format is changed to YYYY-MM-DD
* roam's block IDs are appended (only) to blocks actually referenced
    * e.g. `* this block gets referenced  ^someroamid`
* Blockrefs, block mentions, block embeds are replaced by their content with an appended Obsidian blockref link
    * e.g. `this block gets referenced  [[orignote#^someblockid]]`

**Note:** Please run Obsidian's Markdown importer after this conversion. It will fix #tag links and formattings (todo syntax, highlights, etc).

I might make it more user friendly and less hardcoded later. It did the job, though.

# Install
No need to install. But you need python3. Google is your friend. 

To install the required python packages:

```bash
pip install -r requirements.txt
```

# Usage:
```bash
python r2o.py my-roam-export.json
bash other_fixes.sh
```

