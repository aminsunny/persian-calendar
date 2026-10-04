from datetime import date, timedelta
from pathlib import Path
import json
import re
import requests
import jdatetime

MONTHS = ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"]
WEEKDAYS = ["دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه","یکشنبه"]
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

IMAN_ICS = "https://raw.githubusercontent.com/imanabrisham/Persian-calendar/main/calendar.ics"
ALIREZA_JSON = "https://raw.githubusercontent.com/alirezadesh/jalali_calendar/main/{jy}_data.json"
HOLIDAY_JSON = "https://raw.githubusercontent.com/iyazdanicharati/IranHollidaysJSON/main/{jy}.json"


def fa(n):
    return str(n).translate(FA)


def esc(s):
    return (str(s).replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n"))


def event(uid, d, summary, desc=""):
    return ("BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\nDTSTAMP:{date.today():%Y%m%d}T000000Z\r\n"
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}\r\n"
            f"DTEND;VALUE=DATE:{(d + timedelta(days=1)):%Y%m%d}\r\n"
            f"SUMMARY:{esc(summary)}\r\n"
            + (f"DESCRIPTION:{esc(desc)}\r\n" if desc else "")
            + "TRANSP:TRANSPARENT\r\nEND:VEVENT\r\n")


def all_days(jyear):
    d = jdatetime.date(jyear, 1, 1).togregorian()
    end = jdatetime.date(jyear + 1, 1, 1).togregorian()
    while d < end:
        yield d
        d += timedelta(days=1)


def parse_ics(text):
    # Unfold RFC 5545 continuation lines.
    text = re.sub(r"\r?\n[ \t]", "", text)
    records = {}
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        fields = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.split(";", 1)[0]
            fields[key] = value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
        dt = fields.get("DTSTART")
        if not dt:
            continue
        try:
            d = date(int(dt[:4]), int(dt[4:6]), int(dt[6:8]))
        except Exception:
            continue
        records[d] = fields
    return records


def load_iman_events():
    try:
        r = requests.get(IMAN_ICS, timeout=30)
        r.raise_for_status()
        events = parse_ics(r.text)
        info = {}
        for d, item in events.items():
            uid = item.get("UID", "")
            if "jalali-info-" in uid:
                info[d] = item
        print(f"Loaded {len(info)} daily occasion entries from Iman Abrisham source")
        return info
    except Exception as e:
        print("Iman source unavailable:", e)
        return {}


def load_json_events(jy):
    try:
        r = requests.get(ALIREZA_JSON.format(jy=jy), timeout=30)
        r.raise_for_status()
        data = r.json()
        result = {}
        for item in data:
            try:
                d = date.fromisoformat(item["date_latin"])
            except Exception:
                continue
            events = item.get("events") or []
            names = [str(e.get("description", "")).strip() for e in events if e.get("description")]
            result[d] = names
        print(f"Loaded {sum(bool(v) for v in result.values())} days with occasions for {jy}")
        return result
    except Exception as e:
        print(f"Fallback occasion source unavailable for {jy}:", e)
        return {}


def make_calendar(years):
    iman = load_iman_events()
    fallback = {}
    out = [
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n",
        "PRODID:-//AminSunny Persian Apple Calendar//FA//EN\r\n",
        "CALSCALE:GREGORIAN\r\nMETHOD:PUBLISH\r\n",
        "X-WR-CALNAME:☀️ تقویم شمسی\r\n",
        "X-WR-CALDESC:روز هفته، تاریخ شمسی و مناسبت‌های ایرانی\r\n",
        "X-WR-TIMEZONE:Asia/Tehran\r\n",
        "X-PUBLISHED-TTL:PT12H\r\n",
    ]

    for jy in years:
        if not any(jdatetime.date.fromgregorian(date=d).year == jy for d in iman):
            fallback[jy] = load_json_events(jy)
        for d in all_days(jy):
            j = jdatetime.date.fromgregorian(date=d)
            weekday = WEEKDAYS[d.weekday()]
            occasion_names = []
            desc = ""

            if d in iman:
                info = iman[d]
                summary = info.get("SUMMARY", "").strip()
                if summary:
                    # Keep the weekday from our own converter (consistent Persian spelling).
                    parts = summary.split(" - ", 1)
                    occasion_names = [parts[1]] if len(parts) == 2 and parts[1].strip() else []
                raw_desc = info.get("DESCRIPTION", "").strip()
                if raw_desc and "مناسبت ثبت شده ای" not in raw_desc:
                    desc = raw_desc
                    occasion_names = [x.strip() for x in raw_desc.splitlines()[1:] if x.strip()]
            else:
                occasion_names = fallback.get(jy, {}).get(d, [])
                desc = "مناسبت‌های این روز:\n" + "\n".join(occasion_names) if occasion_names else ""

            # De-duplicate while preserving order.
            seen = set()
            occasion_names = [x for x in occasion_names if not (x in seen or seen.add(x))]
            first = occasion_names[0] if occasion_names else ""
            weekday_summary = f"{weekday} - {first}" if first else weekday

            # Two visible rows in Apple Calendar: weekday/occasion + Persian date.
            out.append(event(f"weekday-{d.isoformat()}@aminsunny", d, weekday_summary, desc))
            out.append(event(f"date-{d.isoformat()}@aminsunny", d, f"{fa(j.day)} {MONTHS[j.month - 1]}"))

    out.append("END:VCALENDAR\r\n")
    Path("calendar.ics").write_text("".join(out), encoding="utf-8", newline="")


def find_holidays(obj, found=None):
    if found is None:
        found = []
    if isinstance(obj, dict):
        if obj.get("isHoliday") is True or obj.get("is_holiday") is True:
            found.append(obj)
        for v in obj.values():
            find_holidays(v, found)
    elif isinstance(obj, list):
        for v in obj:
            find_holidays(v, found)
    return found


def get_jalali_date(item):
    for key in ("shamsiDate", "date", "jalali", "persianDate"):
        v = item.get(key)
        if isinstance(v, str):
            m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", v)
            if m:
                return tuple(map(int, m.groups()))
        if isinstance(v, list) and len(v) >= 3:
            try:
                return tuple(map(int, v[:3]))
            except Exception:
                pass
    return None


def get_title(item):
    for key in ("holidayDesription", "holidayDescription", "description", "event_name", "title", "name"):
        if item.get(key):
            return str(item[key])
    return "تعطیل رسمی"


def make_holidays(years):
    out = [
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n",
        "PRODID:-//AminSunny Iranian Holidays//FA//EN\r\n",
        "CALSCALE:GREGORIAN\r\nMETHOD:PUBLISH\r\n",
        "X-WR-CALNAME:🌸 تعطیلات رسمی ایران\r\n",
        "X-WR-CALDESC:تعطیلات رسمی ایران\r\n",
        "X-WR-TIMEZONE:Asia/Tehran\r\n",
    ]
    for jy in years:
        url = HOLIDAY_JSON.format(jy=jy)
        try:
            data = requests.get(url, timeout=20).json()
        except Exception as e:
            print("Holiday source unavailable for", jy, e)
            continue
        seen = set()
        for item in find_holidays(data):
            j = get_jalali_date(item)
            if not j or j[0] != jy:
                continue
            try:
                d = jdatetime.date(*j).togregorian()
            except Exception:
                continue
            if d in seen:
                continue
            seen.add(d)
            out.append(event(
                f"holiday-{d.isoformat()}@aminsunny",
                d,
                f"🌸 {get_title(item)}",
                "تعطیل رسمی ایران"
            ))
    out.append("END:VCALENDAR\r\n")
    Path("holidays.ics").write_text("".join(out), encoding="utf-8", newline="")


if __name__ == "__main__":
    current = jdatetime.date.today().year
    years = [current - 1, current, current + 1]
    print("Generating Jalali years:", years)
    make_calendar(years)
    make_holidays(years)
