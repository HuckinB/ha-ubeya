# Changelog

## 0.5.0b1 — First public beta candidate

- Package the verified live shift and pay sensors, local branding, and
  human-assisted OTP login as a prerelease.
- Add CI-gated beta publishing from the public GitHub repository.
- **Known limitation:** automatic refresh beyond one hour is not confirmed.
- **Known limitation:** Ubeya's API is undocumented and may change.

## 0.4.0 — Local branding release candidate

- Add original, community-designed 256 px and 512 px Ubeya Crew connector icons
  inside `custom_components/ubeya/brand/` for Home Assistant 2026.3+.
- Preserve the full-resolution generated source in `branding/`.
- Add brand dimension tests and clarify the local-brand requirements.
- The icon is original and is **not** Ubeya's official trademarked logo.
- **Still unverified:** access-token refresh after one hour.

## 0.3.0 — Development release candidate

- Add next venue, next shift gross-pay estimate, upcoming seven-day shift and
  scheduled-hour totals, and seven-day confirmation count.
- Add weekly and rolling 30-day approved gross-earnings sensors.
- Use Home Assistant's configured timezone for month and week boundaries.
- Add anonymous aggregate Home Assistant diagnostics.
- Enable README rendering in HACS metadata and install test dependencies in CI.
- Add regression coverage for pay ranges, shift windows and diagnostic privacy.
- **Still unverified:** automatic refresh after one-hour access-token expiry.

## 0.2.0 — Experimental live authentication

- Add human-assisted SMS login using OTP requested on Ubeya's official website.
- Store isolated HTTP-only session tokens in Home Assistant config-entry data.
- Add cookie renewal, reauthentication and read-only live data polling.
- Keep the original demo integration available.

## 0.1.0 — Demo alpha

- Add synthetic calendar, shift and approved gross-pay sensors.
- Normalize bookings, positions, locations, timesheets and payroll responses.
- Add base API and normalization tests.
