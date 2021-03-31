# pyHidroWeb
Download de dados pluviométricos e fluviométricos do novo portal HidroWeb da ANA.

# Bibliotecas necessárias
- pandas
- os
- requests
- xml
- datetime
- calendar


# Como utilizar
Importar a função **download_hidroweb**

Exemplo1: download_hidroweb(47000, dataType=2)

Este exemplo realiza o download da série temporal da estação 47000 na pasta home

Para o **dataType** utilizar:

1: para cotas

2: para chuva

3: para vazão

O id da estação pode ser encontrado no inventario disponível para download no site do hidroweb.

Exemplo2: download_hidroweb(47000, dataType=2, path_folder='c:\usuarios\nomedousuario\')

Salva a série da estação 47000 na pasta **path_folder**

Também é possível especificar

**startDate** : Data de início da série de dados

**endDate** : Data de fim da série de dados

**consistencyLevel** : nível de consistência dos dados (1:dados brutos, 2:dados consistidos)
