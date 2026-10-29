# Ubeya for Home Assistant — first public beta

An **unofficial, read-only** integration for the Ubeya Crew platform.

## Included

- Calendar of real and upcoming shifts, including position, venue and notes.
- Twenty Home Assistant entities for shifts, hours, earnings and sync status.
- SMS login using a verification code first requested on the **official**
  Ubeya Crew website, where the user completes its normal reCAPTCHA.
- Cookie-based authentication, restart persistence and automatic refresh logic.
- Local Home Assistant icon, reauthentication flow and privacy-safe diagnostics.

## What has been tested

- Successful real Ubeya Crew login and calendar data on Home Assistant.
- Approved earnings compared against Ubeya's Income tab.
- Session persistence after a Home Assistant restart.
- All twenty entities available and community branding displayed.

## Still experimental

- **Automatic token refresh after an hour has not yet been verified live.**
- This uses undocumented Ubeya endpoints, which may change or stop working.
- Estimated gross income ignores deductions, breaks and payroll adjustments.
- SMS verification cannot be requested automatically by Home Assistant because
  Ubeya requires a legitimate human-completed reCAPTCHA challenge.

## Installation

Add `HuckinB/ha-ubeya` as a **custom integration repository** in HACS, or
copy `custom_components/ubeya/` to Home Assistant and restart.

Do not include phone numbers, tokens, verification codes or private shift/pay
details in bug reports. The project is not affiliated with Ubeya.
