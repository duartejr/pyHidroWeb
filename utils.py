import os
import fiona
import datetime
import numpy as np
from fiona import collection
import matplotlib.path as mpltpath
from shapely.geometry import mapping, shape


def check_dir(path, typ, ext='.txt'):
    
    if typ == 'file':
        while path.split('.')[-1] != ext[1:]:
             path = input("Extensão inválida somente arquivos "+ext+':\n')

    while not os.path.exists(path):
        path = input("Caminho inválido tente novamente:\n")
    
    return path

def check_date():
    date = input("Data no formato DD/MM/AAAA:\n")
    try:
        datetime.datetime.strptime(date, '%d/%m/%Y')
    except ValueError:
        print("Data no formato incorreto tente novamente:\n")
        date = check_date()
    
    return date

def check_out(path):
    while not os.path.isabs(path):
        path = input("Caminho inválido. Tente novamente:\n")
    
    if not os.path.exists(path):
        os.makedirs(path)
    
    return path

def save_csv(dir_out, pr_med, date, basename):
    '''
    Salva arquivo .csv com a precipitação média.
    
    INPUT:
        dir_out (str): Diretório onde os arquivos serão salvos
        pr_med (float): Precipitação média
        date (str): Data no format DD/MM/AAAA
        basename (str): Nome base no arquivo de saída
    
    OUTPUT:
        Arquivo .csv salvo em dir_out com a estrutura:
            pr_thiessen_{basename}_{date}.csv
    '''
    
    if not os.path.exists(dir_out):
        os.makedirs(dir_out)
    
    outfile = 'pr_thiessen_{0}_{1}{2:02d}{3:02d}.csv'.format(basename,
                                                             date.year,
                                                             date.month,
                                                             date.day)
    out_file = os.path.join(dir_out, outfile)
    data_out = np.array([['{0:02d}/{1:02d}/{2}'.format(date.day, date.month,
                                                       date.year), pr_med]])
    np.savetxt(out_file, data_out, delimiter=',', fmt='%s')
    
    return None

def getvert(shp, poly, attr='basin', buffer=False):
    '''
    Extrai os vértices do poligo (poly) do shapefile (shp) informado
    
    INPUT:
        shp (str): Nome do shapefile com extensão .shp
        poly (str): Nome do poligono contido no shapefile informado
        attr (str)[opcional]: Nome do atributo para localização do poligono
        buffer (float)[opcional]: Valor do buffer desejado em graus
    
    OUTPUT:
        vertices (array): Array com os vertices do poligono
    '''

    if buffer:
        with collection(shp, "r") as input:
            schema = input.schema.copy()
            with collection( "with-shapely.shp", "w", "ESRI Shapefile", schema) as output:
                for f in input:
                    try:
                        # Make a shapely object from the dict.
                        geom = shape(f['geometry'])
                        geom = geom.buffer(buffer)
                        # Make a dict from the shapely object.
                        f['geometry'] = mapping(geom)
                        output.write(f)
        
                    except Exception as e:
                        # Writing uncleanable features to a different shapefile
                        # is another option.
                        print(e)
                        print("Error cleaning feature %s:", f['id'])
    
    if buffer:
        shpe = "with-shapely.shp"
    else:
        shpe = shp
    
    with fiona.open(shpe) as lines:  
        if len(lines) == 1:
            vertices = []
            for line in lines:
                for vert in line['geometry']['coordinates'][0]:
                    vertices.append(vert)
            vertices = np.array(vertices)
        
        else:
            for x, poligon in enumerate(lines):
                if poligon['properties'][attr] == poly:
                    vert = poligon['geometry']['coordinates']
                    vertices = np.asarray(vert)
                    
                    if len(vertices.shape) < 3:
                        verts2 = []
                        for m in vertices:
                            for x in m:
                                for k in x:
                                    verts2.append(k)
                        vertices = np.asarray(verts2)
            vertices = np.squeeze(vertices)

    return np.squeeze(vertices)

def isinpoly3(lon, lat, polig):
    """
    Encontra se os pontos com coordenadas lon e lat
    estão dentro ou fora de um poligono.

    :param lon: - array com a longitude dos pontos
    :param lat: - array com a latitude dos pontos
    :param polig: -  matriz com os pontos do polígono
    :return isin: - array booleano com o valor 0 para pontos fora do polígono, 1 para
                    pontos dentro do polígono. Pontos encima do polígono recebem 0.
    """
    coords = np.c_[lon, lat]

    pth = mpltpath.Path(polig,  closed=True)
    isin = pth.contains_points(coords)

    isin = np.array(isin)

    return isin