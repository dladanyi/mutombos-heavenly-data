class YahooUnavailable(Exception):
    """Yahoo could not be reached or returned an unusable response."""


class YahooAccessDenied(YahooUnavailable):
    """Yahoo returned HTTP 403: this account can't read the resource (or the credential is bad)."""


class YahooFormatError(YahooUnavailable):
    """Yahoo responded, but the payload did not have the expected shape."""
