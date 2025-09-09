import uuid
import hashlib
import logging
import caldav
import datetime as dt

from utils import (
    setup_logging,
    read_config_file,
    parse_args,
    load_all_headings_from_mixed_list,
    force_timestamp,
)
from events import Event
from cache import check_cache_dir, read_cache_file, write_cache_file


def process_calendar(calendar: dict) -> None:
    server_url = calendar['url']
    calendar_id = calendar['id']
    calendar_url = server_url + calendar_id

    logging.info(f'Processing calendar: {calendar_id}')

    events = sorted(
        [event for generator in map(
            Event.from_org,
            load_all_headings_from_mixed_list(calendar['org_files']),
        ) for event in generator],
        key=lambda event: hash(event.scheduled),
    )

    cache_filename = f'{calendar_id}.bin'
    cache_file = read_cache_file(cache_filename)

    if not cache_file:
        write_cache_file(cache_filename, {'cache': {}})
        old_cache = {}
    else:
        old_cache = cache_file.get('cache', {})

    old_events = list(old_cache.keys())
    new_cache = {}

    # optionally read password from file
    file_prefix = "file="
    if calendar['password'].startswith("file="):
        try:
            with open(calendar['password'][len(file_prefix):], "r") as password_file:
                calendar['password'] = password_file.read().strip()
        except:
            pass

    with caldav.DAVClient(
        url=server_url,
        username=calendar['username'],
        password=calendar['password'],
    ) as client:
        remote_calendar = client.calendar(url=calendar_url)

        if not remote_calendar:
            logging.error(f'Calendar not found: {calendar_id}')
            return

        processed_uids = set()
        for i, event in enumerate(events):
            try:
                # generate ID if event has none attached
                if event.uid is None:
                    hash_str = \
                        f"{calendar_id}\0{event.title}\0{event.scheduled}\0" \
                        f"{event.recurrence_freq}\0{event.recurrence_interval}\0{event.recurrence_count}"
                    hash_val = int(hashlib.sha256(hash_str.encode("utf-8")).hexdigest(), 16)
                    event.uid = str(uuid.UUID(int=hash_val & ((1 << 128) - 1), version=4))

                # prevent duplicate IDs
                if event.uid in processed_uids:
                    continue
                processed_uids.add(event.uid)

                # build new cache
                new_cache[event.uid] = {
                    'title': event.title,
                    'scheduled': event.scheduled,
                    'duration': event.duration,
                    'description': event.description,
                    'recurrence_freq': event.recurrence_freq,
                    'recurrence_interval': event.recurrence_interval,
                    'recurrence_count': event.recurrence_count,
                    'tags': event.tags,
                }

                # search in old events
                skip = False
                if event.uid in old_events:
                    old_events.remove(event.uid)

                    # skip when matching
                    old_event = old_cache[event.uid]
                    if old_cache[event.uid] == new_cache[event.uid]:
                        continue

                # update event
                if remote_event := Event.find_remote_event(remote_calendar, event.uid):
                    if event.compare_with_ical(remote_event):
                        prefix = '= '
                    else:
                        event.update_remote_event(remote_event)
                        prefix = '~ '
                else:
                    event.save_to_calendar(remote_calendar)
                    prefix = '+ '

                # announce status
                time_str = f'{event.scheduled:%Y-%m-%d %H:%M}'
                if event.scheduled and event.duration:
                    time_str += f'--{event.scheduled + event.duration:%H:%M}'
                status_string = f'[{i + 1:03}/{len(events):03}] [{time_str}] {event.title}'
                logging.info(prefix + status_string)

            except Exception as e:

                # log event and exception
                logging.error(event)
                logging.error(e)

        # delete old elements
        for uid in old_events:
            if remote_event := Event.find_remote_event(remote_calendar, uid):
                logging.info(f'Removing cached event "{old_cache[uid]["title"]}".')
                remote_event.delete()

        # persist cache
        write_cache_file(
            cache_filename,
            {
                'cache': new_cache,
            },
        )


def main(
    config_file: str = 'config.yml',
    debug: bool = False,
) -> None:
    try:
        # read config
        if not (config := read_config_file(config_file)):
            return

        # process all calendars
        calendars = config.get('calendars', [])
        for calendar in calendars:
            process_calendar(calendar)

    except Exception as ex:
        if debug:
            logging.exception(ex)
        else:
            logging.error(ex)


if __name__ == '__main__':
    try:
        args = parse_args()
        setup_logging(args.debug)
        check_cache_dir()
        main(args.config, args.debug)

    except KeyboardInterrupt:
        print()
        logging.info('Exited.')
