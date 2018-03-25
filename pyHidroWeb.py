# -*- coding: utf-8 -*-
import re
import os
import wget
import time
from pyvirtualdisplay import Display
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import Select

home = os.path.expanduser('~')

def download_hidroweb(id_station, dir_out, var_cod="10"):

	display = Display(visible=0, size=(800,600))
	display.start()

	driver = webdriver.Firefox()
	url = 'http://www.snirh.gov.br/hidroweb/HidroWeb.asp?TocItem=1080&TipoReg=7&MostraCon=false&CriaArq=false&TipoArq=1&SerieHist=true'
	driver.get(url)
	
	driver.find_element_by_id("txtCodigo1").send_keys(id_station)
	driver.find_element_by_id("txtCodigo2").send_keys(id_station)
	
	driver.execute_script("javascript:mostrarCon(1080,7,true)")
	time.sleep(10)
	
	driver.execute_script("javascript:abrirEstacao("+id_station+")")
	time.sleep(10)
	
	window_before = driver.window_handles[0]
	window_after = driver.window_handles[1]
	driver.switch_to_window(window_after)
	
	Select(driver.find_element_by_name('cboTipoReg')).select_by_value(var_cod)
	
	driver.execute_script("javascript:criarArq("+id_station+",1)")
	time.sleep(10)
	
	html_source = driver.page_source
	web_soup = BeautifulSoup(html_source,'html.parser')
	link = web_soup.findAll('a', attrs={'href': re.compile("^ARQ/")})[0]['href']
	link = 'http://www.snirh.gov.br/hidroweb/'+link
	print link
	wget.download(link, out=dir_out)
	
	driver.close()
	driver.switch_to_window(window_before)
	driver.close()
	
	display.stop()

'''
var_cod examples:
'8'  -> cotas (cm)
'9'  -> vazão (m³/s)
'10' -> precipitação (mm)
'12' -> qualidade da água
'13' -> resumo de descarga
'15' -> curva de descarga
'16' -> perfil transversal
'''

download_hidroweb('12360000', home, "9")
download_hidroweb('02950013', home)
