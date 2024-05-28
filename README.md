# Orgcal
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
      password: PASSWORD
      sync_cutoff: thisweek
      org_files:
          - /path/to/file.org
```

For a Nextcloud CalDAV server, the url should be in the format `https://SERVER-URL/remote.php/dav/calendars/USERNAME/`, where `USERNAME` is the username of the user in the server. As this may be different for other implementations, the provided user name for authentication is not used to construct the url.

The `sync_cutoff` key can be set to "now" or "thisweek" to synchronize only events that are scheduled in the current week. Alternatively, a date in the format "YYYY-MM-DD" can be provided. No item with a scheduled date before this date will be synchronized.

The org_files key has to be a list of org files or directories containing org files. If a directory is provided, all org files within will be added to the list. This does not work recursively.

## Testing
This tool has only be tested with a Nextcloud CalDAV server. If you are using another implementation and are experiencing problems, please create an issue on GitHub and I can take a look.

## License
This program is licensed under the MIT license.
