'''
Conjunto de funções para processamento do Thiessen
'''
from functions import pre_process, getvert, isinpoly3, open_files
import pandas as pd
from functions import thiessen, save_csv
import os
import datetime

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

def calc_thiessen():
    print("*************************************************************")
    print("* Cálculo da precipitação média usando o método de Thiessen *")
    print("*************************************************************")
    hidroweb_dir = check_dir(input("Informe o diretório com os dados das estações do Hidroweb:\n"),'dir')
    inventory = check_dir(input("Caminho completo para o inventário das estações:\n"),'file',ext='.csv')
    shp = check_dir(input("Shapefile com o traçado da bacia hidrográfica:\n"),'file',ext='.shp')
    poly = input("Nome do polígono da bacia hidrodráfica:\n")
    attr = input("Nome do atributo para seleção do polígono:\n")
    buffer = input("Valor do buffer:\n")
    date = check_date()
    dir_out = check_out(input("Informe o diretório de saída:\n"))
    
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

print("######################################")
print("#   Bem vindo ao PyHidroweb v. 0.0.2 #")
print("######################################")
print("\n")