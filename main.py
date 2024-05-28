import logging
import caldav

from utils import (
    setup_logging,
    read_config_file,
    parse_args,
    load_all_headings_from_mixed_list,
    parse_cutoff_date,
    force_timestamp,
)
from events import Event


def process_calendar(calendar: dict) -> None:
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

    with caldav.DAVClient(
        url=server_url,
        username=calendar['username'],
        password=calendar['password'],
    ) as client:
        for i, event in enumerate(events):
            remote_calendar = client.calendar(url=calendar_url)

            if not remote_calendar:
                logging.error(f'Calendar not found: {calendar_id}')
                continue

            time_str = f'{event.scheduled:%Y-%m-%d %H:%M}'
            if event.scheduled and event.duration:
                time_str += f'--{event.scheduled + event.duration:%H:%M}'

            status_string = f'[{i + 1:03}/{len(events):03}] [{time_str}] {event.title}'

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


def main(config_file: str = 'config.yml', debug: bool = False):
    try:
        if not (config := read_config_file(config_file)):
            return

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
        main(args.config)

    except KeyboardInterrupt:
        print()
        logging.info('Exited.')
