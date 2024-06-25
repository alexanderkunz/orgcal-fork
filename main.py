import logging
import caldav
import datetime as dt

from utils import (
    setup_logging,
    read_config_file,
    parse_args,
    load_all_headings_from_mixed_list,
    parse_cutoff_date,
    force_timestamp,
)
from events import Event
from cache import check_cache_dir, read_cache_file, write_cache_file


def process_calendar(calendar: dict, delete_remote_events: bool = False) -> None:
    server_url = calendar['url']
    calendar_id = calendar['id']
    calendar_url = server_url + calendar_id

    logging.info(f'Processing calendar: {calendar_id}')
    cutoff_date = parse_cutoff_date(calendar['sync_cutoff'])
    logging.info(f'Sync cutoff date: {cutoff_date}')

    events = sorted(
        map(
            Event.from_org,
            load_all_headings_from_mixed_list(calendar['org_files'], cutoff_date),
        ),
        key=lambda event: force_timestamp(event.scheduled),
    )

    cache_filename = f'{calendar_id}.yaml'
    cache_file = read_cache_file(cache_filename)

    if not cache_file:
        write_cache_file(cache_filename, {'cache': {}})
        old_cache = {}
    else:
        old_cache = cache_file.get('cache', {})

    old_events = []
    for uid, event in old_cache.items():
        schedule_date = event.get('scheduled', None)
        if (
            schedule_date
            and dt.datetime.strptime(schedule_date, '%Y-%m-%d %H:%M:%S%z').date()
            >= cutoff_date
        ):
            old_events.append(uid)

    new_cache = {}

    if not delete_remote_events:
        new_cache = old_cache

    with caldav.DAVClient(
        url=server_url,
        username=calendar['username'],
        password=calendar['password'],
    ) as client:
        remote_calendar = client.calendar(url=calendar_url)

        if not remote_calendar:
            logging.error(f'Calendar not found: {calendar_id}')
            return

        for i, event in enumerate(events):
            time_str = f'{event.scheduled:%Y-%m-%d %H:%M}'
            if event.scheduled and event.duration:
                time_str += f'--{event.scheduled + event.duration:%H:%M}'

            status_string = f'[{i + 1:03}/{len(events):03}] [{time_str}] {event.title}'

            if event.uid in old_events:
                old_events.remove(event.uid)

            new_cache[event.uid] = {
                'title': event.title,
                'scheduled': event.scheduled,
                'duration': event.duration,
                'description': event.description,
            }

            if remote_event := Event.find_remote_event(remote_calendar, event.uid):
                if event.compare_with_ical(remote_event):
                    logging.debug(f'No changes for event: {event.title}')
                    prefix = '= '
                else:
                    logging.debug(f'Updating event: {event.title}')
                    event.update_remote_event(remote_event)
                    prefix = '~ '
            else:
                logging.debug(f'Creating event: {event.title}')
                event.save_to_calendar(remote_calendar)
                prefix = '+ '

            logging.info(prefix + status_string)

        if delete_remote_events:
            for uid in old_events:
                if remote_event := Event.find_remote_event(remote_calendar, uid):
                    logging.info(f'Removing cached event "{old_cache[uid]["title"]}".')
                    remote_event.delete()

        write_cache_file(
            cache_filename,
            {
                'cache': new_cache,
            },
        )


def main(
    config_file: str = 'config.yml',
    debug: bool = False,
    delete_remote_events: bool = False,
) -> None:
    try:
        if not (config := read_config_file(config_file)):
            return

        calendars = config.get('calendars', [])

        for calendar in calendars:
            process_calendar(calendar, delete_remote_events)

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
        main(args.config, args.debug, args.delete_remote)

    except KeyboardInterrupt:
        print()
        logging.info('Exited.')
