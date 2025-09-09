from dataclasses import dataclass, replace
import orgparse
import datetime as dt
import caldav
import caldav.lib.error
import caldav.objects
import pytz
import logging
import re

from utils import get_datetime_from_org, clean_up_heading

_REPEAT_TO_FREQ = {
    "d": "DAILY",
    "w": "WEEKLY",
    "m": "MONTHLY",
    "y": "YEARLY",
}


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
    recurrence_freq : str | None = ""
    recurrence_interval : int | None = 0
    recurrence_count : int | None = 0
    tags : list | None = None

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
        self.tags = []
        tags = ical.get('CATEGORIES', None)
        if tags and hasattr(tags, "cats"):
            for cat in tags.cats:
                self.tags.append(str(cat))
        self.tags = sorted(filter(lambda e: len(e) > 0, self.tags))

        recurrence = ical.get('RRULE', None)
        if recurrence:
            self.recurrence_freq = recurrence["FREQ"]
            self.recurrence_interval = recurrence["INTERVAL"]
            try:
                self.recurrence_count = recurrence["COUNT"]
            except KeyError:
                self.recurrence_count = 0

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

        # event information
        self.uid = node.get_property('ID')
        self.title = clean_up_heading(node.heading)
        self.description = node.get_body()

        # properties
        self.created_at = get_datetime_from_org(
            node.get_property('CREATED_AT', ''), 'CREATED_AT'
        )
        self.last_modified_at = get_datetime_from_org(
            node.get_property('LAST_MODIFIED_AT', ''), 'LAST_MODIFIED_AT'
        )

        # get tags
        self.tags = list(filter(lambda e: len(e) > 0, node.tags))

        # mark as done
        if node.todo:
            self.tags.append(node.todo.strip().lower())
            if node.todo == "DONE":
                self.title = f"Done: {self.title}"

        # get effort
        effort_key = 'EFFORT' if 'EFFORT' in node.properties else 'Effort'
        effort = node.get_property(effort_key, 0)

        # check for schedule
        if node.scheduled:

            # base time
            self.scheduled = (
                pytz.timezone('Europe/Berlin').localize(node.scheduled.start)
                if isinstance(node.scheduled.start, dt.datetime)
                else node.scheduled.start
            )

            # get duration
            self.duration = self._get_duration(node, effort, node.scheduled, "SCHEDULED")

            # repeat
            if hasattr(node.scheduled, "_repeater"):
                self.recurrence_freq, self.recurrence_interval, self.recurrence_count = \
                    self._get_recurrence(node.scheduled._repeater)
            else:
                self.recurrence_freq = ""
                self.recurrence_interval = 0
                self.recurrence_count = 0

            # process
            self.tags.sort()
            yield self

        # check for deadline
        if node.deadline and node.scheduled != node.deadline:

            # clone
            self = replace(self)

            # override properties
            self.title = f"{self.title}!"
            self.tags.append("deadline")
            self.scheduled = (
                pytz.timezone('Europe/Berlin').localize(node.deadline.start)
                if isinstance(node.deadline.start, dt.datetime)
                else node.deadline.start
            )
            self.duration = self._get_duration(node, effort, node.deadline, "DEADLINE")

            # repeat
            if hasattr(node.deadline, "_repeater"):
                self.recurrence_freq, self.recurrence_interval, self.recurrence_count = \
                    self._get_recurrence(node.scheduled._repeater)
            else:
                self.recurrence_freq = ""
                self.recurrence_interval = 0
                self.recurrence_count = 0

            # process
            self.tags.sort()
            yield self

    @staticmethod
    def _get_duration(node, effort, time, prop):
        duration = None

        # check for start/end
        if (isinstance(time.end, dt.datetime)
            and isinstance(time.start, dt.datetime)):
            start = time.start
            end = time.end
            if end.hour < start.hour:
                end += dt.timedelta(days=1)
            duration = end - start
        else:

            # try scheduled range
            # workaround because orgparse scheduled end is set to None
            node_str = str(node)
            scheduled_match = re.search(f"{prop}: (<.*>--<.*>)", node_str)
            if scheduled_match:
                scheduled_str = scheduled_match.group(1)
                if scheduled_str:
                    date_list = orgparse.date.OrgDate.list_from_str(scheduled_str)
                    if date_list[0].start and date_list[0].end:
                        duration = date_list[0].end - date_list[0].start

            # try effort
            if duration is None:
                if isinstance(effort, int):
                    duration = dt.timedelta(minutes=effort)
                elif isinstance(effort, str) and ':' in effort:
                    duration = effort.strip().split(':')
                    duration = dt.timedelta(
                        hours=int(duration[0]), minutes=int(duration[1]))
        # done
        return duration

    @staticmethod
    def _get_recurrence(repeater):
        recurrence_freq = ""
        recurrence_interval = 0
        recurrence_count = 0
        if repeater and len(repeater) == 3:
            plus = False
            interval = False
            for char in repeater:
                if char == " ":
                    plus = False
                    interval = False
                elif interval:
                    try:
                        recurrence_freq = _REPEAT_TO_FREQ[char]
                    except KeyError:
                        recurrence_freq = ""
                        recurrence_interval = 0
                elif plus:
                    if isinstance(char, int):
                        recurrence_interval = char
                        interval = True
                else:
                    if char == "+":
                        plus = True

        # done
        return recurrence_freq, recurrence_interval, recurrence_count

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
            rrule = None
            if self.recurrence_freq and self.recurrence_interval:
                rrule = {"freq": self.recurrence_freq, "interval": self.recurrence_interval}
                if self.recurrence_count:
                    rrule["count"] = self.recurrence_count
            dtend = self.scheduled + self.duration if self.scheduled and self.duration else self.scheduled

            # do not add end time if time matches
            if self.scheduled == dtend:
                calendar.save_event(
                    uid=self.uid,
                    dtstart=self.scheduled,
                    summary=self.title,
                    description=self.description,
                    rrule=rrule,
                    categories=self.tags,
                )
            else:
                # both start and end time
                calendar.save_event(
                    uid=self.uid,
                    dtstart=self.scheduled,
                    dtend=dtend,
                    summary=self.title,
                    description=self.description,
                    rrule=rrule,
                    categories=self.tags,
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

            # base info
            ical['SUMMARY'] = self.title
            ical['DESCRIPTION'] = self.description
            if self.tags:
                ical['CATEGORIES'] = self.tags
            else:
                ical['CATEGORIES'] = []

            # start time
            ical['DTSTART'].dt = self.scheduled
            if isinstance(self.scheduled, dt.datetime):
                ical['DTSTART'].params['TZID'] = 'Europe/Berlin'
                if 'VALUE' in ical['DTSTART'].params:
                    del ical['DTSTART'].params['VALUE']
            elif isinstance(self.scheduled, dt.date):
                ical['DTSTART'].params['VALUE'] = 'DATE'
                if 'TZID' in ical['DTSTART'].params:
                    del ical['DTSTART'].params['TZID']

            # end time
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

            # filter same time
            if ical['DTSTART'] == ical['DTEND']:
                del ical['DTEND']

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
            and event1.recurrence_freq == event2.recurrence_freq
            and event1.recurrence_interval == event2.recurrence_interval
            and event1.recurrence_count == event2.recurrence_count
            and event1.tags == event2.tags
        )

    def compare_with_ical(self, remote_event: caldav.CalendarObjectResource) -> bool:
        return Event.compare_events(self, Event.from_ical(remote_event))
