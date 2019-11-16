# pyHidroWeb
Download de dados pluviométricos e fluviométricos do novo portal HidroWeb da ANA.

# Bibliotecas necessárias
- pandas
- numpy
- selenium
- pylab
- scipy
- shapely
- glob
- fiona
- matplotlib

# Como utilizar
Nesta versão foi incorporado um menu interativo main.py para facilitar a utilização das funções da aplicação.
Ao executar o arquivo main.py será aberto um menu onde o usuário poderá escolher entre baixar dados do portal ou realizar
o cálculo da precipitação média pelo método de Thiessen (caso já tenha os dados disponíveis).

# Download de dados
Para o download de dados o usuário pode escolher entre duas opções:

1. por área

  Nesta opção o usuário deve passar o arquivo shapefile da área de interesse e serão baixados os dados de todas as estações
  contidas na área de interesse. 
   
2. por código de identificação.

  Nesta opção o usuário deve fornecer um arquivo com o código das estações que deseja obter os dados onde cada linha contém o ID de uma estação.

# Cálculo do Thiessen
_Em implementação_

Esta oção oferece funções para o usuário cálcular a precipitação média na área de estudo utilizando o método de Thiessen.
