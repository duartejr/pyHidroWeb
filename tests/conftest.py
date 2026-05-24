"""Pytest configuration and fixtures for pyHidroWeb tests."""

import pytest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch
from datetime import datetime


@pytest.fixture
def sample_xml_response():
    """Create a sample XML response from HidroWeb API."""
    xml_string = """
    <HidroSerieHistorica>
        <SerieHistorica>
            <NivelConsistencia>1</NivelConsistencia>
            <DataHora>2020-01-01 00:00:00</DataHora>
            <Vazao01>10.5</Vazao01>
            <Vazao02>11.2</Vazao02>
            <Vazao03></Vazao03>
            <Vazao04>12.0</Vazao04>
            <Vazao05>13.5</Vazao05>
            <Vazao06>14.2</Vazao06>
            <Vazao07>15.0</Vazao07>
            <Vazao08>16.1</Vazao08>
            <Vazao09>17.0</Vazao09>
            <Vazao10>18.3</Vazao10>
            <Vazao11>19.0</Vazao11>
            <Vazao12>20.1</Vazao12>
            <Vazao13>21.0</Vazao13>
            <Vazao14>22.0</Vazao14>
            <Vazao15>23.1</Vazao15>
            <Vazao16>24.0</Vazao16>
            <Vazao17>25.2</Vazao17>
            <Vazao18>26.0</Vazao18>
            <Vazao19>27.0</Vazao19>
            <Vazao20>28.1</Vazao20>
            <Vazao21>29.0</Vazao21>
            <Vazao22>30.0</Vazao22>
            <Vazao23>31.1</Vazao23>
            <Vazao24>32.0</Vazao24>
            <Vazao25>33.2</Vazao25>
            <Vazao26>34.0</Vazao26>
            <Vazao27>35.0</Vazao27>
            <Vazao28>36.1</Vazao28>
            <Vazao29>37.0</Vazao29>
            <Vazao30>38.0</Vazao30>
            <Vazao31>39.1</Vazao31>
        </SerieHistorica>
    </HidroSerieHistorica>
    """
    return ET.fromstring(xml_string)


@pytest.fixture
def sample_rainfall_xml():
    """Create a sample rainfall XML response."""
    xml_string = """
    <HidroSerieHistorica>
        <SerieHistorica>
            <NivelConsistencia>2</NivelConsistencia>
            <DataHora>2020-02-01 00:00:00</DataHora>
            <Chuva01>5.0</Chuva01>
            <Chuva02>3.5</Chuva02>
            <Chuva03></Chuva03>
            <Chuva04>0.0</Chuva04>
            <Chuva05>2.1</Chuva05>
            <Chuva06>1.5</Chuva06>
            <Chuva07>4.0</Chuva07>
            <Chuva08>6.2</Chuva08>
            <Chuva09>0.0</Chuva09>
            <Chuva10>3.3</Chuva10>
            <Chuva11>2.0</Chuva11>
            <Chuva12>1.1</Chuva12>
            <Chuva13>5.0</Chuva13>
            <Chuva14>0.0</Chuva14>
            <Chuva15>1.1</Chuva15>
            <Chuva16>2.0</Chuva16>
            <Chuva17>3.2</Chuva17>
            <Chuva18>0.0</Chuva18>
            <Chuva19>1.0</Chuva19>
            <Chuva20>2.1</Chuva20>
            <Chuva21>3.0</Chuva21>
            <Chuva22>0.0</Chuva22>
            <Chuva23>1.1</Chuva23>
            <Chuva24>2.0</Chuva24>
            <Chuva25>4.2</Chuva25>
            <Chuva26>0.0</Chuva26>
            <Chuva27>1.0</Chuva27>
            <Chuva28>2.1</Chuva28>
        </SerieHistorica>
    </HidroSerieHistorica>
    """
    return ET.fromstring(xml_string)


@pytest.fixture
def mock_api_response():
    """Create a mock API response."""
    response = MagicMock()
    response.status_code = 200
    xml_content = """
    <HidroSerieHistorica>
        <SerieHistorica>
            <NivelConsistencia>1</NivelConsistencia>
            <DataHora>2020-01-01 00:00:00</DataHora>
            <Vazao01>10.5</Vazao01>
            <Vazao02>11.2</Vazao02>
            <Vazao03></Vazao03>
            <Vazao04>12.0</Vazao04>
            <Vazao05>13.5</Vazao05>
            <Vazao06>14.2</Vazao06>
            <Vazao07>15.0</Vazao07>
            <Vazao08>16.1</Vazao08>
            <Vazao09>17.0</Vazao09>
            <Vazao10>18.3</Vazao10>
            <Vazao11>19.0</Vazao11>
            <Vazao12>20.1</Vazao12>
            <Vazao13>21.0</Vazao13>
            <Vazao14>22.0</Vazao14>
            <Vazao15>23.1</Vazao15>
            <Vazao16>24.0</Vazao16>
            <Vazao17>25.2</Vazao17>
            <Vazao18>26.0</Vazao18>
            <Vazao19>27.0</Vazao19>
            <Vazao20>28.1</Vazao20>
            <Vazao21>29.0</Vazao21>
            <Vazao22>30.0</Vazao22>
            <Vazao23>31.1</Vazao23>
            <Vazao24>32.0</Vazao24>
            <Vazao25>33.2</Vazao25>
            <Vazao26>34.0</Vazao26>
            <Vazao27>35.0</Vazao27>
            <Vazao28>36.1</Vazao28>
            <Vazao29>37.0</Vazao29>
            <Vazao30>38.0</Vazao30>
            <Vazao31>39.1</Vazao31>
        </SerieHistorica>
    </HidroSerieHistorica>
    """
    response.content = xml_content.encode("utf-8")
    return response
