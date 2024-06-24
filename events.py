from dataclasses import dataclass
import datetime as dt
import caldav
import caldav.lib.error
import caldav.objects
import pytz
import logging

from utils import get_datetime_from_org, clean_up_heading


@dataclass
class Event:
    uid: str = ''
    title: str = ''
    description: str = ''
    scheduled: dt.datetime | None = None
    duration: dt.timedelta | None = None
    created_at: dt.datetime | dt.date | None = None
    last_modified_at: dt.datetime | dt.date | None = None
    remote_event: caldav.CalendarObjectResource | None = None

    @staticmethod
    def from_ical(remote_event: caldav.CalendarObjectResource) -> 'Event':
        if hasattr(remote_event, 'icalendar_component'):
            ical = getattr(remote_event, 'icalendar_component')
        else:
            raise RuntimeError(
                'remote_event does not have icalendar_component attribute'
            )

        self = Event()

        self.remote_event = remote_event
        self.uid = ical['UID']
        self.title = ical['SUMMARY']
        self.description = ical.get('DESCRIPTION', '')

        scheduled = ical.get('DTSTART', None)
        self.scheduled = scheduled.dt if scheduled else None

        dt_end = ical.get('DTEND', None)
        self.duration = (
            (dt_end.dt - self.scheduled) if dt_end and self.scheduled else None
        )

        created_at = ical.get('CREATED', None)
        self.created_at = created_at.dt if created_at else None

        last_modified_at = ical.get('LAST-MODIFIED', None)
        self.last_modified_at = last_modified_at.dt if last_modified_at else None

        return self

    @staticmethod
    def from_org(node) -> 'Event':
        self = Event()
        self.uid = node.get_property('ID')
        self.title = clean_up_heading(node.heading)
        self.description = node.get_body()

        self.scheduled = (
            pytz.timezone('Europe/Berlin').localize(node.scheduled.start)
            if isinstance(node.scheduled.start, dt.datetime)
            else node.scheduled.start
        )

        effort_key = 'EFFORT' if 'EFFORT' in node.properties else 'Effort'
        effort = node.get_property(effort_key, 0)

        if isinstance(effort, int):
            self.duration = dt.timedelta(minutes=effort)
        elif isinstance(effort, str) and ':' in effort:
            duration = effort.strip().split(':')
            self.duration = dt.timedelta(
                hours=int(duration[0]), minutes=int(duration[1])
            )
        else:
            self.duration = None

        self.created_at = get_datetime_from_org(
            node.get_property('CREATED_AT', ''), 'CREATED_AT'
        )

        self.last_modified_at = get_datetime_from_org(
            node.get_property('LAST_MODIFIED_AT', ''), 'LAST_MODIFIED_AT'
        )

        return self

    @staticmethod
    def find_remote_event(
        calendar: caldav.Calendar, uid: str
    ) -> caldav.CalendarObjectResource | None:
        try:
            return calendar.event_by_uid(uid)

        except caldav.lib.error.NotFoundError:
            return None

    @staticmethod
    def find_event(calendar: caldav.Calendar, uid: str) -> 'Event | None':
        remote_event = Event.find_remote_event(calendar, uid)
        return Event.from_ical(remote_event) if remote_event else None

    def save_to_calendar(self, calendar: caldav.Calendar) -> None:
        try:
            calendar.save_event(
                uid=self.uid,
                dtstart=self.scheduled,
                dtend=(
                    self.scheduled + self.duration
                    if self.scheduled and self.duration
                    else self.scheduled
                ),
                summary=self.title,
                description=self.description,
            )

        except caldav.lib.error.PutError as ex:
            logging.error(ex)

    def update_remote_event(self, remote_event: caldav.CalendarObjectResource) -> None:
        try:
            if hasattr(remote_event, 'icalendar_component'):
                ical = getattr(remote_event, 'icalendar_component')
            else:
                raise RuntimeError(
                    '\'remote_event\' does not have icalendar_component attribute.'
                )

            ical['SUMMARY'] = self.title
            ical['DTSTART'].dt = self.scheduled

            if isinstance(self.scheduled, dt.datetime):
                ical['DTSTART'].params['TZID'] = 'Europe/Berlin'
                if 'VALUE' in ical['DTSTART'].params:
                    del ical['DTSTART'].params['VALUE']

            elif isinstance(self.scheduled, dt.date):
                ical['DTSTART'].params['VALUE'] = 'DATE'
                if 'TZID' in ical['DTSTART'].params:
                    del ical['DTSTART'].params['TZID']

            ical['DTEND'].dt = (
                self.scheduled + self.duration
                if self.scheduled and self.duration
                else self.scheduled
            )

            if isinstance(self.scheduled, dt.datetime) and self.duration:
                ical['DTEND'].params['TZID'] = 'Europe/Berlin'
                if 'VALUE' in ical['DTEND'].params:
                    del ical['DTEND'].params['VALUE']

            elif isinstance(self.scheduled, dt.date):
                ical['DTEND'].params['VALUE'] = 'DATE'
                if 'TZID' in ical['DTEND'].params:
                    del ical['DTEND'].params['TZID']

            ical['DESCRIPTION'] = self.description

            remote_event.save()

        except caldav.lib.error.PutError as ex:
            logging.error(ex)

    @staticmethod
    def compare_events(event1: 'Event', event2: 'Event') -> bool:
        return (
            event1.title == event2.title
            and event1.scheduled == event2.scheduled
            and event1.duration == event2.duration
            and event1.description == event2.description
        )

    def compare_with_ical(self, remote_event: caldav.CalendarObjectResource) -> bool:
        return Event.compare_events(self, Event.from_ical(remote_event))
