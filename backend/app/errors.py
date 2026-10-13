class YahooUnavailable(Exception):
    """Yahoo could not be reached or returned an unusable response."""


class YahooFormatError(YahooUnavailable):
    """Yahoo responded, but the payload did not have the expected shape."""
