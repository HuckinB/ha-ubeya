# Ubeya for Home Assistant

An **experimental, read-only** Home Assistant integration for employee shifts,
timesheets and earnings in Ubeya Crew.

> [!IMPORTANT]
> This is a **public beta candidate** (v0.5.0b1), not a stable release.
> release. A user has confirmed live SMS login, live calendar shifts and
> successful reconnect after a Home Assistant restart. Long-running access
> token renewal is still unverified, and this is an unofficial API integration.

This is a community project, not endorsed by or affiliated with Ubeya.
The Crew API is undocumented and may change without notice. Never share
verification codes, session cookies, JWTs or complete Home Assistant config
entries in issue reports.

## What currently works

- Native Home Assistant calendar with shift times, role, venue and notes.
- Upcoming shift, position, monthly shift and scheduled-hours sensors.
- Next shift location, estimated gross pay, and rolling seven-day shift totals.
- Weekly and last-30-day approved earnings summaries.
- Approved earnings and paid-hours sensors, using Ubeya's reported payroll
  `value` and `aggregatedHours` instead of guessing payslips.
- Upcoming gross pay estimate when a simple hourly rate is available; excludes
  unpaid breaks, multipliers and other payroll adjustments.
- Scheduled-on-shift binary sensor (does **not** assert actual clock-in).
- Historical shifts merged with booked shifts using stable shift IDs.
- Multiple hour and pay categories, with decimal arithmetic and UK DST handling.
- A live API client that handles cookie refresh on 401, coalesces concurrent
  refreshes, and retries once, storing rotated cookies between HA restarts.
- Demo and experimental live setup through **Settings → Devices & services → Add integration**.
- Privacy-safe aggregate diagnostics, excluding credentials, phone numbers,
  locations, notes, shift dates and individual pay amounts.
- Original two-colour shift-and-clock icon bundled locally for both light and
  dark Home Assistant UI themes (with standard light-image fallback).

## Install this development build

1. Copy `custom_components/ubeya/` into your Home Assistant configuration's
   `custom_components/ubeya/` directory.
2. Restart Home Assistant.
3. Add **Ubeya** in **Settings → Devices & services**, then choose:
   - **Demo** for synthetic shifts, which never calls the Ubeya API.
   - **Live** for the experimental real-account sign-in described below.

You can install this new code over an existing demo alpha without losing that
config entry. To switch to live data, add a **second Ubeya** configuration via
Add integration and select Live. After confirming it works, remove the demo
entry to eliminate the example calendar and sensors.

The `hacs.json` and repository layout are prepared for HACS/Marketplace, but
this alpha is not published or available from the catalog.

## Entities

| Entity type | Name |
| --- | --- |
| Calendar | Shifts |
| Sensor | Next shift |
| Sensor | Next position |
| Sensor | Next location |
| Sensor | Next shift estimated earnings |
| Sensor | Shifts next 7 days |
| Sensor | Confirmed shifts next 7 days |
| Sensor | Scheduled hours next 7 days |
| Sensor | Shifts this month |
| Sensor | Scheduled hours this month |
| Sensor | Approved shifts this month |
| Sensor | Approved hours this month |
| Sensor | Approved earnings this month |
| Sensor | Approved earnings this week |
| Sensor | Approved earnings last 30 days |
| Sensor | Approved earnings last month |
| Sensor | Approved earnings this year |
| Sensor | Estimated upcoming earnings this month |
| Sensor | Last sync |
| Binary sensor | Scheduled on shift |

Entity IDs are assigned by Home Assistant and may differ from the names above.

Earnings sensors refer to **employer-approved gross payroll values**, not
net pay, tax deductions or the date money reaches a bank account. Weekly totals
use Monday through Sunday according to Home Assistant's configured timezone.
The next-shift and upcoming monthly estimates are provisional hourly-rate
calculations; they cannot predict unpaid breaks, overtime or payroll changes.

## Live-account test (experimental)

1. Add integration → Ubeya → **Live Ubeya Crew account**.
2. Enter your phone number, including country code, e.g. `447xxxxxxxxx`.
3. In a **private/incognito browser window**, go to the official
   [Ubeya Crew website](https://crew.ubeya.com/), enter the same phone number,
   and request a new SMS code. Complete Ubeya's own reCAPTCHA as normal.
4. **Do not submit the SMS code on Ubeya's website.** Enter it on the Home
   Assistant Ubeya OTP screen instead. Codes expire quickly.
5. Home Assistant tries the known `/user/login` endpoint and checks the
   resulting cookies with `GET /auth/me`. If successful, it fetches the five
   read-only endpoints and creates the same calendar/sensor entities as demo.

This does **not** bypass or automate reCAPTCHA. Ubeya has not documented this
login handoff as an official integration method. If Ubeya rejects the code,
report only the visible HA error and a **redacted** log message; never share
your OTP, account cookies, access token, or refresh token. There is currently
no reliable automatic way for the HA flow to issue the initial SMS itself.

Tokens are stored in Home Assistant's config entry storage (normally
`.storage/core.config_entries`) and may appear in HA backups, which must be
protected accordingly. They are not transmitted to any service other than
Ubeya's HTTPS API hosts. Never upload raw HA config entries to bug reports.

## Architecture

- `models.py` normalises bookings, locations, positions, timesheets and payroll.
- `demo.py` provides small, synthetic API-shaped data for testing.
- `coordinator.py` shares one snapshot among all entities, updated every 15 min.
- `calendar.py`, `sensor.py`, `binary_sensor.py` expose standard HA platforms.
- `auth.py` isolates cookie storage for each live Ubeya account.
- `api.py` manages the known Ubeya authentication and read-only API calls.
- `config_flow.py` offers demo setup, experimental human-assisted SMS linking,
  and a reauthentication flow on expired refresh credentials.
- `diagnostics.py` exports only anonymous record counts and connection mode.
- `brand/icon.png` and `brand/icon@2x.png` are the local integration icons.

### Community artwork

The original blue-and-teal U/clock symbol was created for this **unofficial**
integration. It is not the official Ubeya company logo. The generated source
is in `branding/ubeya-community-icon-source.png` and the appropriately sized
production assets are in `custom_components/ubeya/brand/`.

Home Assistant 2026.3+ loads custom integration branding directly from the
integration's own `brand/` directory; no separate Brands repository PR is
necessary. This package includes 256 × 256 and 512 × 512 PNG icons.

### Validate token refresh before public release

After successful login, leave Home Assistant running for at least 75–90 minutes
and confirm that **Ubeya Last Sync** remains recent and the shifts still appear.
On authentication failure the integration should start a reauthentication flow
instead of silently returning empty data. A successful restart confirms stored
cookies, but **does not** independently prove one-hour token renewal.

### Documented employee API mapping (subject to change)

| Endpoint | Purpose |
| --- | --- |
| `GET /bookings` | Booked shifts and hourly estimates |
| `GET /positions` | Position name lookup (`slug`) |
| `GET /locations` | Shift venue and timezone |
| `GET /timesheets/history` | Past/future timesheet details |
| `GET /payroll` | Employer-approved earnings |

Always prefer `booking.locationId` to `booking.project.locationId`, since
individual shifts can override the event's default location. `wage.hourlyWage`
at the top level of a booking is the effective estimated rate; the nested
`employeeSlot.wage` may contain zeros.

### Authentication research

Crew uses phone-number SMS verification:

- `POST https://auth.api.ubeya.com/user/signup` with phone, isVoice and an
  `x-recaptcha-token` obtained through the legitimate Ubeya challenge.
- `POST https://auth.api.ubeya.com/user/login` with phone and code.
- Cookies named `user_access_token` and `user_refresh_token` on `.ubeya.com`,
  both HttpOnly.
- On HTTP 401, the Crew frontend sends an empty-body
  `POST https://auth.api.ubeya.com/user/refresh` using its cookies, then
  retries the request once.

**Still needs verification:** cross-client OTP acceptance, rate limiting,
session cookie rotation and revocation over time, recovery from reauth, and
API payload changes. The client never generates, bypasses, or scrapes CAPTCHA
tokens. No captured cookies, JWTs, OTPs, phone numbers, screenshots, or private
Ubeya exports are included in this repository.

## Testing

The normalization logic runs without Home Assistant installed:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components/ubeya
```

Before a public HACS release, test in a real Home Assistant 2026.10+ environment,
verify one-hour automatic refresh and reauthentication, run hassfest and HACS
validation, verify local branding display and translation coverage,
and validate API changes without sharing credentials in logs or issues. The
repository layout is HACS-compatible, but it is **not** registered in the public
HACS catalog, and no GitHub release has been published by this project.

## License and affiliation

This repository is an independent, unofficial integration and is not endorsed
by Ubeya. All trademarks belong to their respective owners.
