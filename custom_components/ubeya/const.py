"""Constants for the Ubeya integration."""

DOMAIN = "ubeya"
CONF_MODE = "mode"
CONF_PHONE = "phone"
CONF_COOKIES = "cookies"
CONF_FEED_ENABLED = "calendar_feed_enabled"
CONF_FEED_TOKEN = "calendar_feed_token"
CONF_FEED_URL = "calendar_feed_base_url"
CONF_FEED_INCLUDE_NOTES = "calendar_feed_include_notes"
CONF_FEED_INCLUDE_EARNINGS = "calendar_feed_include_earnings"
MODE_DEMO = "demo"
MODE_LIVE = "live"

ACCESS_COOKIE = "user_access_token"
REFRESH_COOKIE = "user_refresh_token"

CREW_API = "https://crew.api.ubeya.com"
AUTH_API = "https://auth.api.ubeya.com"

UPDATE_INTERVAL_MINUTES = 15

CONF_PAY_PERIOD_START = "pay_period_start"
CONF_PAYDAY_OFFSET_DAYS = "payday_offset_days"
PAY_PERIOD_DAYS = 14


# Fired once per newly seen rota change from the audit log (e.g. an admin moving a shift).
EVENT_SHIFT_CHANGED = "ubeya_shift_changed"
AUDIT_PAGE_SIZE = 50
