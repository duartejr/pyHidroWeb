'''
Conjunto de funções para processamento do Thiessen
'''
import os
import numpy as np
import pylab as pl
import pandas as pd
from glob import glob
from scipy.spatial import Voronoi
from utils import save_csv, getvert, isinpoly3
from shapely.geometry import Polygon, Point, LineString


def pre_process(hidroweb_dir, inventory):
    '''
    Pré processamento para obter a localização das estações
    
    INPUT:
        hidroweb_dir (str): Diretório contendo os dados das estações
        inventory (str): Arquivo .csv com o inventários das estações do Hidroweb
    
    OUTPUT:
        loc_stations (array): Localização das estações no formato:
                                [codigo, lat, lon]
    '''
    files = glob(os.path.join(hidroweb_dir, '*.csv'))
    df = pd.read_csv(inventory, sep=',', header=0, encoding='latin1')
    df = df[['RegistroID','Codigo','TipoEstacao','Latitude','Longitude']]
    loc_estations = []
    
    for file in files:
        ID = int(file.split('_')[-1][:-4])
        pos = df.Codigo.values == ID
        loc_estations.append([ID,float(df[pos].Latitude.values[0].replace(',','.')),
                                 float(df[pos].Longitude.values[0].replace(',','.'))])
    
    return np.array(loc_estations)

def open_files(list_IDS, hidroweb_dir, date):
    '''
    Abre os arquivos listados em list_IDS retornado o valor de precipitação
    observado para da data informada.
    
    INPUT:
        list_IDS (array): Lista com os códigos de indentificação das estações
        hidroweb_dir (str): Diretório contento os dados das estações do Hidroweb
        date (str): Data no formato datetime
    
    OUTPUT:
        output (array): Array contendo as coordenadas das estações selecionadas
                        e o valor de preciptação observado. formato [lat, lon, pr]
    '''
    output = []
    
    for ID in list_IDS:       
        file = glob(os.path.join(hidroweb_dir, '*'+str(int(ID[0]))+'*'))[0]
        
        # lista de colunos de interesse para processamento do thiessen
        cols=['Data','NivelConsistencia','Total','NumDiasDeChuva','TotalStatus']+\
        ['Chuva{0:02d}'.format(x) for x in range(1,32)]
        
        df = pd.read_csv(file, skiprows=10, sep=';', index_col=False, header=0,
                         usecols=cols, decimal=',')
        df = df.dropna(subset=['Total', 'NumDiasDeChuva']) # remove falhas da série
        df.Data = pd.to_datetime(df.Data, format='%d/%m/%Y')
        
        # seleciona valor de precipitação observado para a data informada
        pr_date = df.loc[(df.Data.dt.month == date.month) & (df.Data.dt.year == date.year)]
        
        # caso pr_date tenha valores consistidos e não consistidos
        if len(pr_date) > 1:
            consistency_level = 2 # valores consistidos
        else: # caso pr_date tenha apenas valores não consistidos
            consistency_level = 1 # não consistidos
        
        if not pr_date.empty:
            pr_date = pr_date[pr_date.NivelConsistencia == consistency_level]['Chuva{0:02d}'.format(date.day)].values[0]
            
            if not np.isnan(pr_date):
                output.append([ID[1],ID[2], pr_date])
    
    return np.array(output)

def thiessen(px, py, bacx, bacy, pr):
    '''
    Realiza o cálculo do Thiessen.
    
    INPUT:
        px (array): Longitude das estações
        py (array): Latitude das estações
        bacx (array): Longitudes do poligono
        bacy (array): Latitudes do poligonoe
        pr (array): Precipitação observada nas estações
    
    OUTPUT:
        pr_med (float): Precipitação média sengundo método de Thiessen
        
    '''
    alpha = voronoi(px, py, bacx, bacy)
    pr_med = np.sum(alpha*pr)
    return pr_med

def areaxy(x, y):
    """
    Calcula  a área de um polígono bidimensional
    formado pelos vértices com vetores de coordenadas x e y.
    O resultado é sensível à direção: a área é
    positiva se o contorno delimitador é antihorário
    e negativa se horário.

    Adaptado da versão em matlab de:
    Copyright (c) 1995 by Kirill K. Pankratov,
    kirill@plume.mit.edu.
    04/20/94, 05/20/95
    """
    # Calcula a integral de contorno Int -y*dx  (mesmo como Int x*dy).
    lx = len(x)-1
    x = x[1:lx+1]-x[0:lx]
    y = y[0:lx]+y[1:lx+1]
    a = -np.dot(x, y/2.)
    return a


def voronoi(px, py, bacx, bacy, fign=False, cont=False):
    """
    Calculo dos pesos de cada ponto.

    verifica os pontos que estão dentro da bacia
    e retorna os coeficientes de influencia de cada um deles.

    :param px: - longitude dos pontos ( ex: lon dos postos)
    :param py: - latitude dos pontos ( ex: lat dos postos)
    :param bacx: - longitude do polígono ( ex: lon das bacias)
    :param bacy: - latitude do polígono ( ex: lat das bacias)
    :param fign: - nome da figura, opcional
    :param cont: - número da figura, opcional
    :return alpha: - retorna os pesos de cada ponto
    """

    # Cálculo do Thiessen
    mnx = np.min(np.append(px, bacx))
    mny = np.min(np.append(py, bacy))

    mxx = np.max(np.append(px, bacx))
    mxy = np.max(np.append(py, bacy))

    lx = mxx - mnx
    ly = mxy - mny

    # Definindo os limites da area de contorno
    mnx = mnx - 10*lx
    mny = mny - 10*ly
    mxx = mxx + 10*lx
    mxy = mxy + 10*ly

    mdx = (mnx + mxx)/2.
    mdy = (mny + mxy)/2.

    # Descomente a linha abaixo para plotar
    # o gráfico da bacias com os pontos
    if fign:
        pl.plot(px, py, 'r^', bacx, bacy, 'b-')

    px = np.append(px, np.array([[mnx], [mdx], [mxx], [mdx]]))
    py = np.append(py, np.array([[mdy], [mxy], [mdy], [mny]]))

    vorpt = np.column_stack([px,py])

    # Gerar voronoi
    vor = Voronoi(vorpt)

    # formatar vetor de polígonos
    bacv = np.column_stack([bacx, bacy])

    area = np.empty(0)

    for region_idx in vor.point_region:
        region = vor.regions[region_idx]

        # Se a região é finita
        if region and -1 not in region:
            coords = np.empty(0)

            # Obtém coordenadas dos vértices
            for vertex_idx in region:

                coords = np.append(coords, vor.vertices[vertex_idx])

            # Intersecção do posto com o polígono
            coords = coords.reshape(len(coords)//2, 2)

            intersc = Polygon(coords).intersection(Polygon(bacv))

            if isinstance(intersc, Polygon):

                # Extrair lat, lon
                lat, lon = np.array(intersc.exterior.xy)

                # Caso do posto selecionado não ter área de intersecção com a bacia
                if lat.shape[0] == 0:
                    area = np.append(area, 0)
                else:
                    area = np.append(area, areaxy(lat, lon))
                    # Descomente a linha abaixo para plotar
                    # o gráfico da bacias com os pontos
                    if fign:
                        pl.plot(lat, lon, 'b-')
            else:
                aux = 0.

                # Identifica Multipolígono
                for i in range(len(intersc.geoms)):

                    if isinstance(intersc[i], Point) or \
                            isinstance(intersc[i], LineString):
                        continue

                    lat, lon = np.array(intersc[i].exterior.xy)

                    if lat.shape[0] == 0:
                        aux = 0

                    else:
                        aux = aux + areaxy(lat, lon)
                        # Descomente a linha abaixo para plotar
                        # o gráfico da bacias com os pontos
                        if fign:
                            pl.plot(lat, lon, 'b-')

                area = np.append(area, aux)

    # Descomente a linha abaixo para plotar
    # o gráfico da bacias com os pontos
    if fign:
        fign = "{0}_{1}".format(cont, fign)
        pl.savefig(fign)
        pl.close()

    alpha = area/np.sum(area)

    return alpha


def calc_thiessen(hidroweb_dir, inventory, shp, poly, attr, buffer, date, dir_out):
    
    loc_stations = pre_process(hidroweb_dir, inventory)
    
    if not attr:
        attr = 'basiname' # nome padrão do atributo caso não informado
    
    if buffer:
        buffer = float(buffer)
    else:
        buffer = False # padrão caso não informado
    
    # extrai vertices do poligono (poly) do shape informado
    vertices = getvert(shp, poly, attr=attr, buffer=buffer)
    
    # verifica quais postos estão dentro do polígono
    isin = isinpoly3(loc_stations[:,2], loc_stations[:,1], vertices)
    
    # seleciona apenas postos dentro do polígono
    estations_in = loc_stations[isin,:]
    
    # converte date de string para datetime
    date = pd.to_datetime(date, format='%d/%m/%Y')
    
    # extrai precipitação dos postos dentro do polígono para a data informada
    pr_estations = open_files(estations_in, hidroweb_dir, date)
    
    # cálculo da precipitação média usando o método de thiessen
    pr_med = thiessen(pr_estations[:,1], pr_estations[:,0], vertices[:,0],
                      vertices[:,1], pr_estations[:,2])
    
    # salva a precipitação média no formato .csv
    save_csv(dir_out, pr_med, date, poly)
    
    return None
