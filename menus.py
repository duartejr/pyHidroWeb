'''
Interface com os menus para operação do programa
'''
import pandas as pd
from thiessen import calc_thiessen
from utils import check_dir, check_out, check_date
from download import download_from_id, download_from_shp


def menu_thiessen():
    print("*************************************************************")
    print("* Cálculo da precipitação média usando o método de Thiessen *")
    print("*************************************************************")
    hidroweb_dir = check_dir(input("Informe o diretório com os dados das estações do Hidroweb:\n"),'dir')
    inventory = check_dir(input("Caminho completo para o inventário das estações:\n"),'file',ext='.csv')
    shp = check_dir(input("Shapefile com o traçado da área de interesse:\n"),'file',ext='.shp')
    poly = input("Nome do polígono da área de interesse:\n")
    attr = input("Nome do atributo para seleção do polígono:\n")
    buffer = input("Valor do buffer:\n")
    date = check_date()
    dir_out = check_out(input("Informe o diretório de saída:\n"))
    calc_thiessen(hidroweb_dir, inventory, shp, poly, attr, buffer, date, dir_out)

def menu_download():
    print('Selecione tipo de download:')
    print('1: Por área')
    print('2: Por código de identificação')
    res = input('\n')
    
    if int(res) == 1:
        inventory = check_dir(input("Caminho completo para o inventário das estações:\n"),'file',ext='.csv')
        shp = check_dir(input("Shapefile com o traçado da área de interesse:\n"),'file',ext='.shp')
        poly = input("Nome do polígono da área de interesse:\n")
        attr = input("Nome do atributo para seleção do polígono:\n")
        buffer = input("Valor do buffer:\n")
        tp = input("Tipo de Estação:\n1: Fluviométrica\n2: Pluviométrica")
        
        while int(tp) != 1 and int(tp) != 2:
            tp = input("Opção inválida tente novamente:")
        
        dir_out = check_out(input('Informe diretório de saída:\n'))
        
        download_from_shp(shp, poly, attr, buffer, inventory, int(tp), dir_out)
        
    elif int(res) == 2:
        ids_file = check_dir(input('Informe endereço do arquivo com o ID das estações:\n'),'file',ext='.csv')
        IDS = pd.read_csv(ids_file, header=None)
        inventory = check_dir(input('Informe endereço do inventário das estações:\n'),'file',ext='.csv')
        dir_out = check_out(input('Informe diretório de saída:\n'))
        download_from_id(IDS, inventory, dir_out)
    else:
        print('Opção inválida')
