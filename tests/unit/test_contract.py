"""Tests for pyhydroweb.contract (daily contract engine)."""

from datetime import date

import pandas as pd
import pytest

from pyhydroweb.contract import (
    DAILY_CONTRACT_COLUMNS,
    match_daily_variables,
    normalize_name,
    normalize_station_code,
    parse_ana_date,
    parse_ana_numeric,
    prefer_daily_rows,
    standardize_ana_daily_table,
    standardize_api_daily_items,
)


class TestParseAnaNumeric:
    def test_brazilian_decimal_comma(self):
        assert parse_ana_numeric("12,3") == 12.3

    def test_brazilian_thousands_and_decimal(self):
        assert parse_ana_numeric("1.234,56") == 1234.56

    def test_plain_number(self):
        assert parse_ana_numeric("10.5") == 10.5

    def test_missing_tokens(self):
        for token in ("", "NA", "NaN", "NULL", "null", "None", "none", None):
            assert parse_ana_numeric(token) is None

    def test_whitespace_stripped(self):
        assert parse_ana_numeric(" 1 234,5 ") == 1234.5


class TestParseAnaDate:
    def test_brazilian_format_first(self):
        assert parse_ana_date("01/02/2020") == date(2020, 2, 1)

    def test_iso_format(self):
        assert parse_ana_date("2020-02-01") == date(2020, 2, 1)

    def test_iso_with_time_and_zulu(self):
        assert parse_ana_date("2020-02-01T12:30:00.000Z") == date(2020, 2, 1)

    def test_missing(self):
        assert parse_ana_date("") is None
        assert parse_ana_date(None) is None

    def test_unparseable(self):
        assert parse_ana_date("not-a-date") is None


class TestNormalizers:
    def test_normalize_name_fuzzy(self):
        assert normalize_name("Código da Estação") == "codigodaestacao"
        assert normalize_name("codigo_estacao") == "codigoestacao"

    def test_normalize_station_code_trailing_float(self):
        assert normalize_station_code("1234567.0") == "1234567"

    def test_normalize_station_code_missing(self):
        assert normalize_station_code("null") is None


class TestMatchDailyVariables:
    def test_all_expands(self):
        assert match_daily_variables("all") == ["discharge", "stage", "rainfall"]

    def test_single(self):
        assert match_daily_variables("discharge") == ["discharge"]

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            match_daily_variables("temperature")


class TestStandardizeWideTable:
    def test_wide_explosion_and_leap_day_dropping(self):
        table = pd.DataFrame(
            {
                "EstacaoCodigo": ["01234567"],
                "NivelConsistencia": ["1"],
                "Data": ["01/02/2019"],  # February 2019: 28 days
                "Vazao28": ["5,0"],
                "Vazao29": ["6,0"],  # impossible day -> dropped
                "Vazao28Status": ["1"],
            }
        )
        out = standardize_ana_daily_table(table, "test")
        assert list(out.columns) == DAILY_CONTRACT_COLUMNS
        assert len(out) == 1
        assert out.iloc[0]["date"] == date(2019, 2, 28)
        assert out.iloc[0]["value"] == 5.0
        assert out.iloc[0]["unit"] == "m3/s"
        assert out.iloc[0]["source_status"] == "1"

    def test_consistency_preference(self):
        table = pd.DataFrame(
            {
                "EstacaoCodigo": ["01234567", "01234567"],
                "NivelConsistencia": ["1", "2"],
                "Data": ["01/01/2020", "01/01/2020"],
                "Cota01": ["100", "110"],
            }
        )
        out = standardize_ana_daily_table(table, "test", merge_consistency=True)
        assert len(out) == 1
        assert out.iloc[0]["value"] == 110.0  # consisted (2) wins
        assert out.iloc[0]["consistency_level"] == "2"
        assert out.iloc[0]["variable"] == "stage"
        assert out.iloc[0]["unit"] == "cm"

    def test_merge_consistency_false_keeps_both(self):
        table = pd.DataFrame(
            {
                "EstacaoCodigo": ["01234567", "01234567"],
                "NivelConsistencia": ["1", "2"],
                "Data": ["01/01/2020", "01/01/2020"],
                "Chuva01": ["5,0", "7,0"],
            }
        )
        out = standardize_ana_daily_table(table, "test", merge_consistency=False)
        assert len(out) == 2

    def test_underscore_day_columns(self):
        table = pd.DataFrame(
            {
                "EstacaoCodigo": ["01234567"],
                "Data": ["01/01/2020"],
                "Vazao_05": ["3,5"],
            }
        )
        out = standardize_ana_daily_table(table, "test")
        assert len(out) == 1
        assert out.iloc[0]["date"] == date(2020, 1, 5)


class TestPreferDailyRows:
    def test_non_missing_value_preferred_within_level(self):
        data = pd.DataFrame(
            {
                "station_code": ["1", "1"],
                "date": [date(2020, 1, 1), date(2020, 1, 1)],
                "variable": ["discharge", "discharge"],
                "value": [None, 9.0],
                "unit": ["m3/s", "m3/s"],
                "consistency_level": ["1", "1"],
                "source_status": [None, None],
                "source": ["a", "b"],
            }
        )
        out = prefer_daily_rows(data)
        assert len(out) == 1
        assert out.iloc[0]["value"] == 9.0


class TestStandardizeApiItems:
    def test_long_items_with_decimal_comma(self):
        items = {
            "items": [
                {
                    "CodEstacao": "01234567",
                    "Data": "2020-01-01",
                    "Vazao": "10,5",
                    "NivelConsistencia": "2",
                }
            ]
        }
        out = standardize_api_daily_items(items, "discharge")
        assert len(out) == 1
        assert out.iloc[0]["value"] == 10.5
        assert out.iloc[0]["source_status"] == "success"
        assert out.iloc[0]["unit"] == "m3/s"

    def test_invalid_variable_raises(self):
        with pytest.raises(ValueError):
            standardize_api_daily_items([], "temperature")
