#%%
import requests
import xml.etree.ElementTree as ET
import datetime
import calendar
import pandas as pd
import os


def extract_data(data, dataType):
    list_data = []
    list_consistenciaF = []
    list_month_dates = []

    for i in data.iter('SerieHistorica'):

        consistencia = i.find('NivelConsistencia').text
        date = i.find('DataHora').text
        date = datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
        last_day = calendar.monthrange(date.year, date.month)[1]
        month_dates = [date + datetime.timedelta(days=i) for i in range(last_day)]
        content = []
        list_consistencia = []

        for day in range(last_day):

            if dataType == 3:
                value = f'Vazao{day+1:02d}'
            if dataType == 2:
                value = f'Chuva{day+1:02d}'
            
            try:
                content.append(float(i.find(value).text))
                list_consistencia.append(int(consistencia))
            except TypeError:
                content.append(i.find(value).text)
                list_consistencia.append(int(consistencia))
            except AttributeError:
                content.append(None)
                list_consistencia.append(int(consistencia))
        
        list_data += content
        list_consistenciaF += list_consistencia
        list_month_dates += month_dates

    return list_data, list_consistenciaF, list_month_dates


def save_data(data, dates, consistency, station, dataType, path_folder):
    df = pd.DataFrame({'Date': dates, 
                        f'Consistence_{dataType}_{station}':consistency,
                        f'Data{dataType}_{station}': data})
    filename = f'{dataType}_{station}.csv'
    df.to_csv(f'{path_folder}/{filename}', index=False)
    print(f'Done --> {path_folder}/{filename}\n')

def download_hidroweb(station, startDate='', endDate='', dataType='', 
                      consistencyLevel='', path_folder=os.path.expanduser('~')):
    """
    Função para download de dados hidrológicos brasileiros. Extrai dados da mesma base
    do portal Hidroweb da Agência Nacional de Águas (ANA).

    Params:
        station (int) : Código da estação pluviométrica ou fluviométrica. Você pode baixar
                        a lista de estações disponíveis no seguinte endereço: http://telemetriaws1.ana.gov.br/EstacoesTelemetricas.aspx
        startDate (str) : Data inicial (YYYY-mm-dd) que deseja da série de dados.
                          Caso não seja fornecida uma startDate serão baixados os dados
                          deste o primeiro registro histórico da estação.
        endDate (str) : Data fimal (YYYY-mm-dd) que deseja da série de dados.
                        Caso não seja fornecida uma startDate serão baixados os dados
                        até o registro mais recente do histórico da estação.
        dataType (int) : Tipo de dados: 1-Cotas, 2-Chuvas ou 3-Vazões
        consistencyLevel (int) : Nível de consistência dos dados: 1-Bruto ou 2-Consistido.
                                Caso não seja informado serão baixados dados brutos e consistidos.
         path_folder (str) : Endereço onde deseja salvar os dados. Por padrão os dados são
                              na pasta home dos usuários de sistemas Linux. Caso utilize sistema
                              Windows será necessário especificar um endereço ou o script não
                              funcionará
    Output:
        Como saída o script gera um arquivo csv salvo no diretório informado em path_folder.
    """
    while dataType not in [2, 3]:
        print('Especifique o tipo de dado:\n2-Chuva\n3-Vazão')
        dataType = int(input())
    params = {'codEstacao':station, 'dataInicio':startDate, 'dataFim':endDate,
              'tipoDados':dataType, 'nivelConsistencia':consistencyLevel}
    server = 'http://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica'
    response = requests.get(server, params)

    tree = ET.ElementTree(ET.fromstring(response.content))
    root = tree.getroot()
    data, consistency, dates = extract_data(root, dataType)

    if len(data) > 0:
        save_data(data, dates, consistency, station, dataType, path_folder)
