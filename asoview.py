"""Read the public stock endpoint used by Asoview's ticket page."""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

PLAN = "ticket0000007351"
BOOKING_URL = f"https://www.asoview.com/item/ticket/{PLAN}/"


class ServiceError(Exception):
    pass


class HTTPStatusError(ServiceError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"HTTP {status}")


def request_json(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "SuzukaTicketMonitor/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read()
            try:
                return json.loads(body)
            except (ValueError, UnicodeError):
                content_type = response.headers.get_content_type()
                if not body.strip():
                    kind = "an empty response"
                elif content_type in ("text/html", "application/xhtml+xml"):
                    kind = "an HTML page"
                else:
                    kind = "invalid JSON"
                redirect = "; request was redirected" if response.geturl() != url else ""
                # Report metadata only: response bodies/URLs can contain credentials.
                raise ServiceError(
                    f"Service returned {kind} (HTTP {response.status}{redirect})"
                ) from None
    except urllib.error.HTTPError as error:
        # URLs can contain Telegram credentials. Never include them in errors.
        raise HTTPStatusError(error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ServiceError("Connection failed or timed out") from None


@dataclass(frozen=True)
class Slot:
    id: str
    start: str
    end: str
    remaining: int


def available_slots(courses, quantity):
    if not isinstance(courses, list):
        raise ServiceError("Unexpected Asoview response: expected a list of slots")
    slots = []
    for course in courses:
        required = {"id": str, "startTimeLabel": str, "endTimeLabel": str,
                    "stockStatus": str, "isClosed": bool, "isRequest": bool,
                    "remainReserveNumber": int, "minimumReservableQuantity": int,
                    "maximumReservableQuantity": int}
        if not isinstance(course, dict) or any(
            type(course.get(key)) is not kind for key, kind in required.items()
        ):
            raise ServiceError("Asoview slot format changed; availability is unknown")
        minimum = course["minimumReservableQuantity"]
        maximum = course["maximumReservableQuantity"]
        if (course["stockStatus"] == "REALTIME" and not course["isClosed"]
                and not course["isRequest"]
                and course["remainReserveNumber"] >= quantity
                and (minimum == 0 or quantity >= minimum)
                and (maximum == 0 or quantity <= maximum)):
            slots.append(Slot(course["id"], course["startTimeLabel"],
                              course["endTimeLabel"], course["remainReserveNumber"]))
    return slots


def fetch_slots(date, quantity):
    query = urllib.parse.urlencode({"planCode": PLAN, "channelCode": "asoview", "date": date})
    return available_slots(request_json(f"https://www.asoview.com/stocks/ticket/courses?{query}"), quantity)
