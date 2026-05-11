from icalendar import Calendar
from datetime import date, datetime
import pytz

def get_schedule(date_str: str) -> list:
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    events = []

    with open("data/calendar.ics", "rb") as f:
        cal = Calendar.from_ical(f.read())
        for component in cal.walk():
            if component.name == "VEVENT":
                start = component.get("dtstart").dt
                if hasattr(start, "date"):
                    start = start.date()
                if start == target:
                    events.append({
                        "summary": str(component.get("summary")),
                        "start": str(component.get("dtstart").dt),
                        "description": str(component.get("description", ""))
                    })
    return events