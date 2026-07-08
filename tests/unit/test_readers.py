"""Tests for pyhydroweb.readers against the hydroDataBR fixtures.

The fixture files under tests/fixtures/ were copied verbatim from
hydrostat/hydroDataBR (tests/testthat/fixtures, MIT license), so these tests
validate the Python port against the same inputs the R package uses.
"""

from datetime import date
from pathlib import Path

import pytest

from pyhydroweb.exceptions import DataParsingError
from pyhydroweb.readers import (
    read_ana_json,
    read_ana_xml,
    read_hidroweb,
    read_hidroweb_cross_sections,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


class TestReadAnaXml:
    def test_fixture_consistency_merge(self):
        out = read_ana_xml(FIXTURES / "ana_daily.xml")
        # Fixture: two SerieHistorica records for 01/2020 (levels 1 and 2),
        # each with Cota01/Cota02 -> merged to one row per day, level 2 wins.
        assert len(out) == 2
        assert set(out["variable"]) == {"stage"}
        assert list(out["value"]) == [110.0, 111.0]
        assert set(out["consistency_level"]) == {"2"}
        assert out.iloc[0]["date"] == date(2020, 1, 1)
        assert out.iloc[1]["date"] == date(2020, 1, 2)
        assert out.iloc[0]["source"] == "ANA WebService XML"
        assert out.iloc[0]["station_code"] == "01234567"

    def test_fixture_without_merge(self):
        out = read_ana_xml(FIXTURES / "ana_daily.xml", merge_consistency=False)
        assert len(out) == 4  # 2 days x 2 consistency levels

    def test_status_columns_carried(self):
        out = read_ana_xml(FIXTURES / "ana_daily.xml")
        assert list(out["source_status"]) == ["2", "1"]

    def test_variable_filter(self):
        with pytest.raises(ValueError):
            # fixture has only stage; filtering to discharge leaves nothing
            read_ana_xml(FIXTURES / "ana_daily.xml", variables="discharge")

    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            read_ana_xml(FIXTURES / "does_not_exist.xml")


class TestReadAnaJson:
    def test_fixture_items_envelope(self):
        out = read_ana_json(FIXTURES / "ana_daily.json")
        # Fixture: items with Chuva01+Vazao01 at levels 1 and 2 -> one row per
        # variable after the consistency merge, decimal commas parsed.
        assert len(out) == 2
        by_variable = {row["variable"]: row for _, row in out.iterrows()}
        assert by_variable["rainfall"]["value"] == 7.0
        assert by_variable["discharge"]["value"] == 12.0
        assert set(out["consistency_level"]) == {"2"}
        assert out.iloc[0]["source"] == "ANA API JSON"

    def test_variable_filter(self):
        out = read_ana_json(FIXTURES / "ana_daily.json", variables="rainfall")
        assert set(out["variable"]) == {"rainfall"}
        assert out.iloc[0]["unit"] == "mm"


class TestReadHidroweb:
    def test_csv_fixture(self):
        out = read_hidroweb(FIXTURES / "hidroweb_discharge.csv")
        assert set(out["variable"]) == {"discharge"}
        assert out.iloc[0]["source"] == "HidroWeb CSV: hidroweb_discharge.csv"
        # January row exists at levels 1 and 2 -> merge keeps level 2
        january_first = out[out["date"] == date(2020, 1, 1)]
        assert len(january_first) == 1
        assert january_first.iloc[0]["value"] == 10.2
        # February 2020 has 29 days: Vazao30/Vazao31 of the 01/02/2020 row
        # (values 20,30/20,31) must be dropped as impossible dates.
        assert (out["date"] <= date(2020, 2, 29)).all()
        february = out[
            (out["date"] >= date(2020, 2, 1)) & (out["date"] <= date(2020, 2, 29))
        ]
        assert set(february["date"]) == {date(2020, 2, 1), date(2020, 2, 2)}

    def test_rainfall_csv_fixture(self):
        out = read_hidroweb(FIXTURES / "hidroweb_rainfall.csv")
        assert set(out["variable"]) == {"rainfall"}
        assert set(out["unit"]) == {"mm"}

    def test_zip_fixture(self):
        out = read_hidroweb(FIXTURES / "hidroweb_daily.zip")
        assert set(out["variable"]) == {"discharge", "rainfall"}
        assert out["source"].str.startswith("HidroWeb ZIP:").all()

    def test_zip_variable_filter(self):
        out = read_hidroweb(FIXTURES / "hidroweb_daily.zip", variables="rainfall")
        assert set(out["variable"]) == {"rainfall"}

    def test_header_detection_failure(self, tmp_path):
        bogus = tmp_path / "bogus.csv"
        bogus.write_text("no;header;here\n1;2;3\n", encoding="latin-1")
        with pytest.raises(DataParsingError):
            read_hidroweb(bogus)


class TestReadHidrowebCrossSections:
    def _write_fixture(self, tmp_path):
        content = (
            "Preamble line\n"
            "EstacaoCodigo;NivelConsistencia;Data;Hora;NumLevantamento;"
            "TipoSecao;NumVerticais;Vertical\n"
            "01234567;1;15/03/2019;10:30;2;1;3;0,100|1,5,98|3,95\n"
        )
        target = tmp_path / "PerfilTransversal.csv"
        target.write_bytes(content.encode("latin-1"))
        return target

    def test_sections_and_vertices(self, tmp_path):
        result = read_hidroweb_cross_sections(self._write_fixture(tmp_path))
        sections = result["sections"]
        vertices = result["vertices"]
        assert len(sections) == 1
        assert sections.iloc[0]["station_code"] == "01234567"
        assert sections.iloc[0]["survey_number"] == 2
        assert sections.iloc[0]["n_vertices"] == 3
        assert sections.iloc[0]["cross_section_id"] == "01234567_20190315103000_2_1"
        assert len(vertices) == 3
        # token "1,5,98": distance "1.5" (decimal comma re-joined), stage 98
        assert vertices.iloc[1]["vertex_distance_m"] == 1.5
        assert vertices.iloc[1]["vertex_stage_cm"] == 98.0
        assert vertices.iloc[0]["vertex_distance_m"] == 0.0
        assert vertices.iloc[0]["vertex_stage_cm"] == 100.0

    def test_missing_required_columns(self, tmp_path):
        bad = tmp_path / "PerfilTransversal.csv"
        bad.write_bytes(b"EstacaoCodigo;Data\n01234567;15/03/2019\n")
        with pytest.raises(DataParsingError):
            read_hidroweb_cross_sections(bad)

    def test_zip_member_lookup(self, tmp_path):
        import zipfile

        csv_path = self._write_fixture(tmp_path)
        zip_path = tmp_path / "station.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.write(csv_path, "01234567_PerfilTransversal.csv")
        result = read_hidroweb_cross_sections(zip_path)
        assert len(result["sections"]) == 1

    def test_zip_without_member(self, tmp_path):
        import zipfile

        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("other.csv", "a;b\n1;2\n")
        with pytest.raises(DataParsingError):
            read_hidroweb_cross_sections(zip_path)
