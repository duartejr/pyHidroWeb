"""Custom exceptions for pyHidroWeb package."""


class PyHidroWebError(Exception):
    """Base exception for all pyHidroWeb errors."""

    pass


class InvalidDataTypeError(PyHidroWebError):
    """Raised when an invalid data type is specified."""

    pass


class InvalidDateFormatError(PyHidroWebError):
    """Raised when a date format is invalid."""

    pass


class InvalidDateRangeError(PyHidroWebError):
    """Raised when date range is invalid (start_date > end_date)."""

    pass


class InvalidStationCodeError(PyHidroWebError):
    """Raised when a station code is invalid."""

    pass


class InvalidOutputFormatError(PyHidroWebError):
    """Raised when an invalid output format is specified."""

    pass


class DownloadError(PyHidroWebError):
    """Raised when data download fails."""

    pass


class DataParsingError(PyHidroWebError):
    """Raised when data parsing fails."""

    pass


class MissingDependencyError(PyHidroWebError):
    """Raised when a required optional dependency is missing."""

    pass


class AuthenticationError(PyHidroWebError):
    """Raised when authentication against the ANA HidroWebService fails."""

    pass


class TokenExpiredError(AuthenticationError):
    """Raised when an ANA token is expired or too close to expiration."""

    pass


class ApiRequestError(DownloadError):
    """Raised when a request to the ANA HidroWebService fails."""

    pass


class ApiWindowError(PyHidroWebError):
    """Raised when a requested date window exceeds the API limits."""

    pass


class ChecksumMismatchError(DownloadError):
    """Raised when a downloaded file fails its integrity (SHA-256) check."""

    pass
