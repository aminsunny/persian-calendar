from datetime import date, timedelta
from pathlib import Path

J_MONTHS = ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"]
J_WEEKDAYS = ["دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه","یکشنبه"]

# Compact Gregorian <-> Jalali conversion, no external dependency.
def g2j(gy, gm, gd):
    g_d_m = [0,31,59,90,120,151,181,212,243,273,304,334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365*gy + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400 + gd + g_d_m[gm-1]
    jy = -1595 + 33*(days//12053)
    days %= 12053
    jy += 4*(days//1461)
    days %= 1461
    if days > 365:
        jy += (days-1)//365
        days = (days-1)%365
    if days < 186:
        jm = 1 + days//31
        jd = 1 + days%31
    else:
        jm = 7 + (days-186)//30
        jd = 1 + (days-186)%30
    return jy, jm, jd

def j2g(jy, jm, jd):
    jy += 1595
    days = -355668 + 365*jy + (jy//33)*8 + ((jy%33)+3)//4 + jd
    if jm < 7:
        days += (jm-1)*31
    else:
        days += (jm-7)*30 + 186
    gy = 400*(days//146097)
    days %= 146097
    if days > 36524:
        gy += 100*((days-1)//36524)
        days = (days-1)%36524
        if days >= 365: days += 1
    gy += 4*(days//1461)
    days %= 1461
    if days > 365:
        gy += (days-1)//365
        days = (days-1)%365
    gd = days + 1
    leap = (gy%4==0 and gy%100!=0) or (gy%400==0)
    mdays = [31,29 if leap else 28,31,30,31,30,31,31,30,31,30,31]
    gm = 1
    while gd > mdays[gm-1]:
        gd -= mdays[gm-1]; gm += 1
    return date(gy, gm, gd)

def esc(s):
    return str(s).replace('\\','\\\\').replace(';','\\;').replace(',','\\,').replace('\n','\\n')

def event(d):
    jy,jm,jd = g2j(d.year,d.month,d.day)
    title = f"☀️ {jd} {J_MONTHS[jm-1]} • {J_WEEKDAYS[d.weekday()]}"
    desc = f"تقویم شمسی: {jd} {J_MONTHS[jm-1]} {jy}\\nمیلادی: {d.isoformat()}"
    nxt = d + timedelta(days=1)
    return ("BEGIN:VEVENT\r\n" f"UID:jalali-{d.isoformat()}@persian-apple-calendar\r\n"
            f"DTSTAMP:{date.today():%Y%m%d}T000000Z\r\n"
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}\r\n"
            f"DTEND;VALUE=DATE:{nxt:%Y%m%d}\r\n"
            f"SUMMARY:{esc(title)}\r\nDESCRIPTION:{esc(desc)}\r\n"
            "TRANSP:TRANSPARENT\r\nEND:VEVENT\r\n")

today=date.today(); current_j=g2j(today.year,today.month,today.day)[0]
events=[]
for jy in range(current_j-1,current_j+2):
    d=j2g(jy,1,1); end=j2g(jy+1,1,1)
    while d < end:
        events.append(event(d)); d += timedelta(days=1)
ics=("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Persian Apple Calendar//FA//EN\r\n"
     "CALSCALE:GREGORIAN\r\nMETHOD:PUBLISH\r\nX-WR-CALNAME:تقویم شمسی ☀️\r\n"
     "X-WR-CALDESC:تقویم شمسی با روزهای هفته فارسی\r\nX-WR-TIMEZONE:Asia/Tehran\r\n" + ''.join(events) + "END:VCALENDAR\r\n")
Path('calendar.ics').write_text(ics,encoding='utf-8',newline='')
print(f'Generated {len(events)} days for Jalali years {current_j-1}-{current_j+1}')
