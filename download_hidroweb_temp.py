#%%
import pandas as pd
import geopandas as gpd
import os
from typing import List

AUTOMATIC_GAUGES = 'https://raw.githubusercontent.com/anagovbr/dados-estacoes-hidro/main/dados'
CONVENTIONAL_GAUGES = 'https://raw.githubusercontent.com/anagovbr/hidro-dados-estacoes-convencionais/main'
INVENTORY_URL = 'https://raw.githubusercontent.com/anagovbr/dados-estacoes-hidro/main/Inventario_EstacoesHidrologicas_04082023.csv'


def download_from_list(stations_list:List[str], date_limits:List[str]=[], path_dir:str=None,
                       automatic_stations:bool=True, data_type:str='vazao',
                       hidrologic_variable:str='fluviometrica') -> None:
    for station_id in stations_list:
        print('Download data to the station: ', station_id)
        
        if automatic_stations:
            station_url = f'{AUTOMATIC_GAUGES}/{station_id}.csv'
            dates_col = ['Data Hora']
        else:
            station_url = f'{CONVENTIONAL_GAUGES}/{hidrologic_variable}/{station_id}/{station_id}_{data_type}.csv'
            dates_col = ['Data']
            
        try:
            station_data = pd.read_csv(station_url,
                                       delimiter=';',
                                       decimal=',',
                                       thousands='.',
                                       na_values=[-99999, '//////', '/////'],
                                       parse_dates=dates_col,
                                       dayfirst=True,
                                       index_col=dates_col)
            
            if len(date_limits):
                station_data = station_data.loc[date_limits[0]:date_limits[1]]
                
            if not path_dir:
                path_dir = os.getcwd()
            
            if not os.path.exists(path_dir):
                os.makedirs(path_dir)
            
            outputfile = f'{path_dir}/{station_id}.csv'
            station_data.to_csv(outputfile)
        except Exception as e:
            print("A error ocurried. This was the Error obtained.")
            print(e)
    
    print(f'Finished downlaod to the station: {station_id}.\n')


def download_from_shape(shape: str, date_limits: List[str]=[], path_dir: str=None,
                        station_type:bool=True, data_type:str='vazao',
                        hidrologic_variable:str='fluviometrica') -> None:
    """
    This function automates the download of all gauges that are within a given 
    shapefile.
    
    Args:
        shape (str): The path of the shapefile that will be used to select the stations.
        date_limits (List[str], optional): A list with the start and end dates 
                                           that you want to obtain from the gauges 
                                           in the YYYY-MM-dd format. Defaults to [].
        path_dir (str, optional): The path of the directory where the downloaded
                                  files will be storaged. Defaults to None. If None
                                  it will download the files into the main directory
                                  of the user.
        station_type (bool, optional): If True it will download data from the automatic
                                      stations, if False it will downaload data from
                                      the conventional stations. The automatic 
                                      stations contains data just from 2023-01-01 
                                      until present. The conventional stations 
                                      contains all the historic time series available.
        data_type (str, optional): The type of data you want to download. In 
                                    fluviometric stations this can be: vazao or
                                    cotas.
        hidrologic_variable (str, optional): If you are trying to download data
                                             from the conventional stations you
                                             have to determine if you want data
                                             from pluviometric (pluviometrica) of
                                             fluviometric (fluviometric) stations.
                                             In 2923-10-25 to conventional station
                                             is available just data of fluviometric
                                             stations.
    """
    # This reads the inventory of gauges operated by ANA.
    inventory = pd.read_csv(INVENTORY_URL, delimiter=';')
    
    # Reads the shapefile of the study area into a GeoDataFrame.
    gdf_shape = gpd.read_file(shape)
    
    # Creates a GeoDataFrame with the inventory. This contains the location of
    # each gauge operated by ANA.
    gdf_inventory = gpd.GeoDataFrame(inventory,
                                     geometry=gpd.points_from_xy(inventory['Longitude'],
                                                                 inventory['Latitude']),
                                     crs=gdf_shape.crs)
    
    # Selects only the stations that are inside the provided shapefile.
    stations_in = gpd.sjoin(gdf_inventory,
                            gdf_shape,
                            op='within')
    
    # Gets a list with the id of each station.
    stations_list = stations_in['Codigo'].to_list()
    
    # Realizes the download of the selected stations data.
    download_from_list(stations_list, date_limits=date_limits, path_dir=path_dir,
                       station_type=station_type, hidrologic_variable=hidrologic_variable,
                       data_type=data_type)
