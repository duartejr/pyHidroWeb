#%%
import pandas as pd
import geopandas as gpd
import os

DATA_URL = 'https://raw.githubusercontent.com/anagovbr/dados-estacoes-hidro/main/dados'
INVENTORY_URL = 'https://raw.githubusercontent.com/anagovbr/dados-estacoes-hidro/main/Inventario_EstacoesHidrologicas_04082023.csv'

def download_from_list(stations_list, date_limits=[], path_dir=None):
    for station_id in stations_list:
        print('Download data to the station: ', station_id)
        station_url = f'{DATA_URL}/{station_id}.csv'
        try:
            station_data = pd.read_csv(station_url,
                                       delimiter=';',
                                       decimal=',',
                                       thousands='.',
                                       na_values=[-99999, '//////', '/////'],
                                       parse_date=['Data Hora'],
                                       dayfirst=True,
                                       index_col=['Data Hora'])
            
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


def download_from_shape(shape, date_limits=[], path_dir=None):
    inventory = pd.read_csv(INVENTORY_URL,
                            delimiter=';')
    
    gdf_shape = gpd.read_file(shape)
    gdf_inventory = gpd.GeoDataFrame(inventory,
                                     geometry=gpd.points_from_xy(inventory['Longitude'],
                                                                 inventory['Latitude']),
                                     crs=gdf_shape.crs)
    
    stations_in = gpd.sjoin(gdf_inventory,
                            gdf_shape,
                            op='within')
    
    stations_list = stations_in['Codigo'].to_list()
    
    download_from_list(stations_list, date_limits=date_limits, path_dir=path_dir)
