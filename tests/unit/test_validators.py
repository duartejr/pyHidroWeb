"""Tests for pyhydroweb.validators module."""

import pytest
from datetime import datetime

from pyhydroweb.validators import (
    validate_date_format,
    validate_date_range,
    validate_data_type,
    validate_consistency_level,
    validate_station_code,
    validate_output_format,
)
from pyhydroweb.exceptions import (
    InvalidDataTypeError,
    InvalidDateFormatError,
    InvalidDateRangeError,
    InvalidStationCodeError,
    InvalidOutputFormatError,
)


class TestValidateDateFormat:
    """Tests for validate_date_format function."""

    def test_valid_date_format(self):
        """Test validation of valid date."""
        result = validate_date_format("2020-01-15")
        assert isinstance(result, datetime)
        assert result.year == 2020
        assert result.month == 1
        assert result.day == 15

    def test_invalid_date_format(self):
        """Test rejection of invalid date format."""
        with pytest.raises(InvalidDateFormatError):
            validate_date_format("01-15-2020")

    def test_invalid_date_string(self):
        """Test rejection of invalid date values."""
        with pytest.raises(InvalidDateFormatError):
            validate_date_format("2020-13-45")

    def test_empty_date_string(self):
        """Test handling of empty date string."""
        result = validate_date_format("")
        assert result is None

    def test_none_date_string(self):
        """Test handling of None date string."""
        result = validate_date_format(None)
        assert result is None

    def test_custom_date_format(self):
        """Test validation with custom date format."""
        result = validate_date_format("01/15/2020", "%m/%d/%Y")
        assert result.year == 2020
        assert result.month == 1


class TestValidateDateRange:
    """Tests for validate_date_range function."""

    def test_valid_date_range(self):
        """Test validation of valid date range."""
        start, end = validate_date_range("2020-01-01", "2020-12-31")
        assert start.year == 2020
        assert end.year == 2020
        assert start < end

    def test_invalid_date_range(self):
        """Test rejection of invalid date range (start > end)."""
        with pytest.raises(InvalidDateRangeError):
            validate_date_range("2020-12-31", "2020-01-01")

    def test_empty_start_date(self):
        """Test with empty start date."""
        start, end = validate_date_range("", "2020-12-31")
        assert start is None
        assert end is not None

    def test_empty_end_date(self):
        """Test with empty end date."""
        start, end = validate_date_range("2020-01-01", "")
        assert start is not None
        assert end is None

    def test_both_empty_dates(self):
        """Test with both dates empty."""
        start, end = validate_date_range("", "")
        assert start is None
        assert end is None


class TestValidateDataType:
    """Tests for validate_data_type function."""

    def test_valid_rainfall_type(self):
        """Test validation of rainfall data type (2)."""
        validate_data_type(2)  # Should not raise

    def test_valid_flow_type(self):
        """Test validation of flow data type (3)."""
        validate_data_type(3)  # Should not raise

    def test_invalid_data_type_1(self):
        """Test rejection of invalid type 1."""
        with pytest.raises(InvalidDataTypeError):
            validate_data_type(1)

    def test_invalid_data_type_4(self):
        """Test rejection of invalid type 4."""
        with pytest.raises(InvalidDataTypeError):
            validate_data_type(4)

    def test_invalid_data_type_string(self):
        """Test rejection of string input."""
        with pytest.raises(InvalidDataTypeError):
            validate_data_type("3")


class TestValidateConsistencyLevel:
    """Tests for validate_consistency_level function."""

    def test_valid_raw_level(self):
        """Test validation of raw consistency level (1)."""
        validate_consistency_level(1)  # Should not raise

    def test_valid_consolidated_level(self):
        """Test validation of consolidated level (2)."""
        validate_consistency_level(2)  # Should not raise

    def test_invalid_consistency_level(self):
        """Test rejection of invalid consistency level."""
        with pytest.raises(InvalidDataTypeError):
            validate_consistency_level(3)

    def test_zero_consistency_level(self):
        """Test that zero (both levels) is accepted."""
        validate_consistency_level(0)  # Should not raise


class TestValidateStationCode:
    """Tests for validate_station_code function."""

    def test_valid_station_code(self):
        """Test validation of valid station code."""
        validate_station_code(34879500)  # Should not raise
        validate_station_code("34879500")  # Should not raise

    def test_invalid_station_code_empty(self):
        """Test rejection of empty station code."""
        with pytest.raises(InvalidStationCodeError):
            validate_station_code("")

    def test_invalid_station_code_string(self):
        """Test rejection of non-numeric string."""
        with pytest.raises(InvalidStationCodeError):
            validate_station_code("ABC123")

    def test_invalid_station_code_none(self):
        """Test rejection of None station code."""
        with pytest.raises(InvalidStationCodeError):
            validate_station_code(None)


class TestValidateOutputFormat:
    """Tests for validate_output_format function."""

    def test_valid_dataframe_format(self):
        """Test validation of DataFrame format (0)."""
        validate_output_format(0)  # Should not raise

    def test_valid_xarray_format(self):
        """Test validation of xarray format (1)."""
        validate_output_format(1)  # Should not raise

    def test_invalid_output_format(self):
        """Test rejection of invalid output format."""
        with pytest.raises(InvalidOutputFormatError):
            validate_output_format(2)

    def test_invalid_output_format_string(self):
        """Test rejection of string format."""
        with pytest.raises(InvalidOutputFormatError):
            validate_output_format("0")
