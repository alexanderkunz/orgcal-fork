# Orgcal-Fork

## Fork
Personalized custom late evening fork of [orccal](https://github.com/tkreuziger/orgcal) with opinionated changes for fast one-way syncing.
I run this script on a server in the background within a folder change detection watcher script to synchronize a dedicated calendar.
At the time of writing, this fork differs to the original by:

### Additions
- Support for repeating events
- Support for deadlines (separate event)
- Support date ranges and multi-day events
- Support for tags as categories (with inheritance)
- Support for TODO/DONE as categories (no custom words yet)
- Automatically generate missing node identifiers
- Use `ripgrep` to pre-filter parsed files
- Use offline cache to complete instantly when nothing changed
- Binary cache using pickle for better date management
- Read passwords that start with `file=` from file
- Ignore end time if it matches with the start time

### Changes in Behavior
- No requirement to add IDs to events
- Always delete removed events remotely
- No more cutoff time setting
- Requires `rg` to be found in $PATH (install `ripgrep`)

### Missing
- persistent connection or threading to make adding multiple events faster

## Original Introduction

This is a small program to synchronize your `org-mode` files with a CalDAV server. Headings that have a `SCHEDULED` timestamp are handled as events in a calendar. Multiple calendars and org files can be handled via a config file. For more details about its creation and some thoughts behind it, you can read my blog post about it [here](https://tkreuziger.com/posts/2024-01-10-writing_my_own_calendar_syncing_solution/).
## Usage
To set up a working environment for the script, run the following command:

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install -r requirements.txt
```

The script can then be run with the following command:

```bash
python3 main.py --config config.yml
```

If the `--config` argument is omitted, a file with the name `config.yml` in the current directory will be used. Absolute or relative paths can be provided. Optionally, a `--debug` argument can be passed to see more detailed output.

Alternatively, it can easily be built with PyInstaller into a single executable that can be put anywhere. To do this, run the following command:

```bash
./venv/bin/pyinstaller -F main.py
```

Afterwards you can put the final executable from `dist` wherever you like. There is also a Makefile that does the same thing.

## Cofiguration
The config file is in YAML format. The file has the following structure:

```yaml
# config.yml
calendars: # this key has to be the root
    - url: SERVER-URL
      id: CALENDAR-ID
      username: USERNAME
      password: PASSWORD (or file=/path/to/file)
      org_files:
          - /path/to/file.org
          - /path/to/directory
```

For a Nextcloud CalDAV server, the url should be in the format `https://SERVER-URL/remote.php/dav/calendars/USERNAME/`, where `USERNAME` is the username of the user in the server. As this may be different for other implementations, the provided user name for authentication is not used to construct the url.

The org_files key has to be a list of org files or directories containing org files. If a directory is provided, all org files within will be added to the list. ~~This does not work recursively.~~

## Testing
This tool has only been tested with a Nextcloud CalDAV server and Radicale. ~~If you are using another implementation and are experiencing problems, please create an issue on GitHub and I can take a look.~~

## Known issues / bugs / limitations
- Archiving: ~~Similar to deletion, the event simply vanishes from the point of view of the software, when it is moved to a dedicated archive file. Usually, this will simply lead to the software ignoring the event and any further changes to it. The easiest solution is to include the archive files in the org files to synchronize with the server.~~ Archived events not in *.org files or not specified will be deleted on the remote server.
- (Outdated?) Deleting events: Deleting events on the calendar can cause issues with ids, as the software may try to create a new id with an existing (although deleted) id. The original motivation was to only support one-way syncing, so deletion was always supposed to only happen in the org files. A more stable solution would be to keep track of the ids and how they are used. A workaround for now is to simply delete an entry in the org file first, then in the calendar.
- (Outdated?) Timestamps: Sometimes timestamps are not updated correctly, especially if one switches from all-day event to one with a specific timestamp. This is being investigated.

## License
This program is licensed under the MIT license.
