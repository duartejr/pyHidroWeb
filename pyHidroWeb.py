#%%
import requests
import xml.etree.ElementTree as ET
import datetime
import calendar
import pandas as pd
import os


def extract_data(data, data_type):
    """
    Extracts and processes hydrological data for a given month, returning detailed daily values.

    This function parses an XML-like structure containing historical series data. It extracts
    values for either rainfall or flow (depending on `data_type`), as well as their consistency levels
    and corresponding dates for each day of the month.

    Parameters:
        data (xml.etree.ElementTree.Element): The root element of the XML-like structure containing
                                              the hydrological data.
        data_type (int): Specifies the type of data to extract: 2 for rainfall, 3 for flow.

    Returns:
        tuple: A tuple containing three lists:
               - list_data (list): The extracted values (floats or None if data is missing) for each day.
               - list_consistency (list): Consistency levels (integers) for each corresponding value.
               - list_month_dates (list): List of datetime.date objects representing each day of the month.

    Raises:
        TypeError: If the provided `data_type` does not match expected values (2 or 3).
        AttributeError: If expected XML tags are missing in the data structure.

    Example:
        >>> root = ET.fromstring(your_xml_string)  # Assuming 'your_xml_string' is an XML string.
        >>> extract_data(root, 2)  # Example call for rainfall data extraction.
    """
    list_data = []
    list_consistency = []
    list_month_dates = []

    for i in data.iter('SerieHistorica'):
        consistencia = i.find('NivelConsistencia').text
        date = i.find('DataHora').text
        date = datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
        last_day = calendar.monthrange(date.year, date.month)[1]
        month_dates = [date + datetime.timedelta(days=k) for k in range(last_day)]
        content = []
        list_consistencia_day = []

        for day in range(last_day):
            if data_type == 3:
                value = f'Vazao{day+1:02d}'
            elif data_type == 2:
                value = f'Chuva{day+1:02d}'

            try:
                content.append(float(i.find(value).text))
                list_consistencia_day.append(int(consistencia))
            except TypeError:
                content.append(i.find(value).text)
                list_consistencia_day.append(int(consistencia))
            except AttributeError:
                content.append(None)
                list_consistencia_day.append(int(consistencia))

        list_data += content
        list_consistency += list_consistencia_day
        list_month_dates += month_dates

    return list_data, list_consistency, list_month_dates



def download_hidroweb_data(station, start_date='', end_date='', data_type='', 
                      consistency_level='', output_format=1):
    """
    Download Brazilian hydrological data from the Hidroweb portal of the National Water Agency (ANA).

    Parameters:
        station_code (int): Code of the pluviometric or fluviometric station. You can check
                            the available stations at: https://www.snirh.gov.br/hidroweb/serieshistoricas
        start_date (str, optional): Start date for the data series in YYYY-mm-dd format.
                                    If not provided, data will be downloaded from the earliest
                                    historical record of the station.
        end_date (str, optional): End date for the data series in YYYY-mm-dd format.
                                  If not provided, data will be downloaded up to the most
                                  recent historical record of the station.
        data_type (int): Type of data: 2 for Rainfall or 3 for Flow.
        consistency_level (int, optional): Level of data consistency: 1 for Raw or 2 for Consolidated.
                                           If not specified, both raw and consolidated data will be downloaded.
        output_format (int, optional): Specifies the output format: 0 for pandas DataFrame, 1 for xarray Dataset.

    Returns:
        Data in the requested format.

    Raises:
        ValueError: If the data_type is not 2 or 3, or if other specified parameters are not in the expected format.

    Example:
        >>> download_hidroweb_data(34879500, "2020-01-01", "2020-01-31", 3, 1)
    """
    
    if data_type not in [2, 3]:
        raise ValueError("Invalid data type specified. Use 2 for Rain or 3 for Flow.")
       
    name = {
        2: "rain_rate",
        3: "flow_rate",
    }
    
    units = {
        2: "mm$\,$h$^{-1}$",
        3: "m$^3\,$s$^{-1}$",
    }
    
    params = {'codEstacao':station, 'dataInicio':start_date, 'dataFim':end_date,
              'tipoDados':data_type, 'nivelConsistencia':consistency_level}
    server = 'http://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica'
    response = requests.get(server, params)

    tree = ET.ElementTree(ET.fromstring(response.content))
    root = tree.getroot()
    data, consistency, dates = extract_data(root, data_type)
    
    df = pd.DataFrame({'time': dates, 
                    f'{name[data_type]}_consistency_level':consistency,
                    name[data_type]: data})
    
    df = df.set_index("time")
    
    if output_format == 0:
        output_data = df
    elif output_format == 1:    
        ds = df.to_xarray()
        ds[name[data_type]].attrs["units"] = units[data_type]
        ds[name[data_type]].attrs["long_name"] = f"{name[data_type].replace('_', ' ')}"

        output_data = ds
    else:
        raise ValueError("Invalid output data type (output_format) specified. Use 0 for pandas.DataFrame or 1 for xarray.Dataset.")
    
    return output_data