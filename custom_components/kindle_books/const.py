"""Constants for the Kindle Books integration."""

from datetime import timedelta

DOMAIN = "kindle_books"

CONF_USER_ID = "user_id"
CONF_READ_SHELF = "read_shelf"
CONF_READING_SHELF = "reading_shelf"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MAX_BOOKS = "max_books"

DEFAULT_READ_SHELF = "read"
DEFAULT_READING_SHELF = "currently-reading"
DEFAULT_SCAN_INTERVAL = 60  # minutes
DEFAULT_MAX_BOOKS = 20

MIN_SCAN_INTERVAL = timedelta(minutes=15)
