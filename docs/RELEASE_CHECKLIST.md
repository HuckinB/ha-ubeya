# Publishing checklist

This is an unofficial integration using Ubeya's undocumented Crew endpoints.
Do not claim it is endorsed or supported by Ubeya.

## Before any public HACS release

- [x] Live phone-number OTP login tested by a user in Home Assistant.
- [x] Live calendar shifts displayed; state survives HA restart.
- [ ] Verify automatic cookie refresh after >75 minutes without reauth.
- [ ] Confirm reauth UX with genuinely expired/revoked credentials.
- [ ] Compare approved earnings/paid hours against the Crew Income screen.
- [ ] Exercise the new weekly, rolling-range and upcoming-shift sensors in HA.
- [ ] Verify diagnostics export contains no personal data or tokens.
- [ ] Run hassfest and HACS action on the intended GitHub repository.
- [x] Include local `brand/icon.png` and `brand/icon@2x.png` artwork.
- [ ] Add more translations and complete public-release support information.
- [ ] Check current Ubeya usage policies and document that this is unofficial.

## Publish when checks pass

1. Ensure the GitHub repo root contains `custom_components/ubeya`,
   `hacs.json`, `README.md` and `LICENSE` directly.
2. Confirm the repository's `manifest.json` version matches the planned tag.
3. Push the code to `main`. Once all three validation jobs pass, the CI
   workflow creates one GitHub prerelease for the manifest version. It skips
   the publication step if that version already has a release.
4. Add the repo as a custom integration repository in HACS for first testers.
5. Submit to the public listing only after meeting its current requirements.

## Security

- Never include phone numbers, OTPs, cookies, JWTs, HAR captures or raw API
  responses in bug reports or releases.
- Protect HA backups containing `.storage/core.config_entries`.
- Do not attempt to automate or bypass Ubeya's reCAPTCHA.
- The original community icon is not the official Ubeya company logo. Do not
  imply an affiliation, endorsement or formal API partnership.
