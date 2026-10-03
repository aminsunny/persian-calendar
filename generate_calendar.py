from datetime import date, timedelta
from pathlib import Path
import json, requests, jdatetime

MONTHS = ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"]
WEEKDAYS = ["دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه","یکشنبه"]
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

def fa(n): return str(n).translate(FA)
def esc(s):
    return str(s).replace("\\","\\\\").replace(";","\\;").replace(",","\\,").replace("\n","\\n")

def event(uid, d, summary, desc=""):
    return ("BEGIN:VEVENT\r\n"
            f"UID:{uid}\r\nDTSTAMP:{date.today():%Y%m%d}T000000Z\r\n"
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}\r\n"
            f"DTEND;VALUE=DATE:{(d+timedelta(days=1)):%Y%m%d}\r\n"
            f"SUMMARY:{esc(summary)}\r\n"
            + (f"DESCRIPTION:{esc(desc)}\r\n" if desc else "")
            + "TRANSP:TRANSPARENT\r\nEND:VEVENT\r\n")

def all_days(jyear):
    d = jdatetime.date(jyear,1,1).togregorian()
    end = jdatetime.date(jyear+1,1,1).togregorian()
    while d < end:
        yield d
        d += timedelta(days=1)

def make_calendar(years):
    out = ["BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//AminSunny Persian Apple Calendar//FA//EN\r\n",
           "CALSCALE:GREGORIAN\r\nMETHOD:PUBLISH\r\nX-WR-CALNAME:☀️ تقویم شمسی\r\n",
           "X-WR-CALDESC:روز هفته و تاریخ شمسی\r\nX-WR-TIMEZONE:Asia/Tehran\r\n"]
    for jy in years:
        for d in all_days(jy):
            j = jdatetime.date.fromgregorian(date=d)
            out.append(event(f"weekday-{d.isoformat()}@aminsunny", d, WEEKDAYS[d.weekday()]))
            out.append(event(f"date-{d.isoformat()}@aminsunny", d, f"{fa(j.day)} {MONTHS[j.month-1]}"))
    out.append("END:VCALENDAR\r\n")
    Path("calendar.ics").write_text("".join(out), encoding="utf-8", newline="")

def find_holidays(obj, found=None):
    if found is None: found = []
    if isinstance(obj, dict):
        # Accept common schemas used by Iranian holiday datasets.
        if obj.get("isHoliday") is True or obj.get("is_holiday") is True:
            found.append(obj)
        for v in obj.values(): find_holidays(v, found)
    elif isinstance(obj, list):
        for v in obj: find_holidays(v, found)
    return found

def get_jalali_date(item):
    for key in ("shamsiDate","date","jalali","persianDate"):
        v = item.get(key)
        if isinstance(v, str):
            import re
            m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", v)
            if m: return tuple(map(int,m.groups()))
        if isinstance(v, list) and len(v) >= 3:
            try: return tuple(map(int, v[:3]))
            except: pass
    return None

def get_title(item):
    for key in ("holidayDesription","holidayDescription","description","event_name","title","name"):
        if item.get(key): return str(item[key])
    return "تعطیل رسمی"

def make_holidays(years):
    out = ["BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//AminSunny Iranian Holidays//FA//EN\r\n",
           "CALSCALE:GREGORIAN\r\nMETHOD:PUBLISH\r\nX-WR-CALNAME:🔴 تعطیلات رسمی ایران\r\n",
           "X-WR-CALDESC:تعطیلات رسمی ایران\r\nX-WR-TIMEZONE:Asia/Tehran\r\n"]
    for jy in years:
        url = f"https://raw.githubusercontent.com/iyazdanicharati/IranHollidaysJSON/main/{jy}.json"
        try:
            data = requests.get(url, timeout=20).json()
        except Exception as e:
            print("Holiday source unavailable for", jy, e)
            continue
        seen = set()
        for item in find_holidays(data):
            j = get_jalali_date(item)
            if not j or j[0] != jy: continue
            try: d = jdatetime.date(*j).togregorian()
            except Exception: continue
            if d in seen: continue
            seen.add(d)
            out.append(event(f"holiday-{d.isoformat()}@aminsunny", d, f"🔴 {get_title(item)}", "تعطیل رسمی ایران"))
    out.append("END:VCALENDAR\r\n")
    Path("holidays.ics").write_text("".join(out), encoding="utf-8", newline="")

if __name__ == "__main__":
    current = jdatetime.date.today().year
    years = [current-1, current, current+1]
    make_calendar(years)
    make_holidays(years)
