"""Optional, owner-scoped, read-only iCloud calendar integration."""
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from config import APP_TIMEZONE


def read_events(owner, start, end):
    from services.connection_service import icloud_config
    settings=icloud_config(owner)
    if not settings:return {"events":[],"status":"not_configured"}
    username,password=settings['username'],settings['password']
    import caldav
    events = []
    # Fixed trusted service URL; users cannot supply arbitrary network targets.
    with caldav.DAVClient(url="https://caldav.icloud.com/", username=username,
                          password=password, timeout=15) as client:
        for calendar in client.principal().calendars():
            for resource in calendar.search(start=start, end=end, event=True, expand=True):
                for component in resource.icalendar_instance.walk("VEVENT"):
                    if str(component.get("STATUS", "")) == "CANCELLED":
                        continue
                    begins = component.decoded("DTSTART")
                    all_day = isinstance(begins, date) and not isinstance(begins, datetime)
                    finishes = component.decoded("DTEND") if "DTEND" in component else begins + (
                        component.decoded("DURATION") if "DURATION" in component else
                        timedelta(days=1) if all_day else timedelta(0))
                    if not all_day:
                        zone = ZoneInfo(APP_TIMEZONE)
                        begins = begins.replace(tzinfo=zone) if begins.tzinfo is None else begins.astimezone(zone)
                        finishes = finishes.replace(tzinfo=zone) if finishes.tzinfo is None else finishes.astimezone(zone)
                    events.append({"id": str(component.get("UID", "")),
                                   "summary": str(component.get("SUMMARY", "(無標題)")),
                                   "description": str(component.get("DESCRIPTION", "")),
                                   "start": begins.isoformat(), "end": finishes.isoformat(),
                                   "is_all_day": all_day, "source": "icloud", "read_only": True})
    return {"events": events, "status": "connected"}
