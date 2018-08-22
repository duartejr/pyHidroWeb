# -*- coding: utf-8 -*-
import time
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import os
import pandas_access
import numpy as np

home = os.path.expanduser('~')

def wait_load_items(driver, xpath):

	n = 1
	p = 1
	while p: 
		try:
			driver.find_element_by_xpath(xpath)
			p = 0
		except:
			print(n, xpath)
			time.sleep(1)
			n += 1
		if n == 300:
			print('Tempo de espera excedito. Processo encerrado.')
			exit()

def click_css_selector(driver, css_selector):
	n = 0
	p = 1
	while p:
		try:
			driver.find_element_by_css_selector(css_selector).click()
			p = 0
		except:
			time.sleep(1)
			n += 1

		if n == 300:
			print('Tempo de espera excedido. Processo encerrado.')
			exit()

def download_hidroweb(id_station, name_estation, dir_out):

	# display = Display(visible=0, size=(800,600))
	# display.start()

	fp = webdriver.FirefoxProfile()

	fp.set_preference("browser.download.folderList",2)
	fp.set_preference("browser.download.dir",dir_out)
	fp.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/msword, application/csv, application/ris, text/csv, image/png, application/pdf, text/html, text/plain, application/zip, application/x-zip, application/x-zip-compressed, application/download, application/octet-stream")
	fp.set_preference("browser.download.manager.showWhenStarting", False)
	fp.set_preference("browser.download.manager.focusWhenStarting", False)  
	fp.set_preference("browser.download.useDownloadDir", True)
	fp.set_preference("browser.helperApps.alwaysAsk.force", False)
	fp.set_preference("browser.download.manager.alertOnEXEOpen", False)
	fp.set_preference("browser.download.manager.closeWhenDone", True)
	fp.set_preference("browser.download.manager.showAlertOnComplete", False)
	fp.set_preference("browser.download.manager.useWindow", False)
	fp.set_preference("services.sync.prefs.sync.browser.download.manager.showWhenStarting", False)
	fp.set_preference("pdfjs.disabled", True)

	driver = webdriver.Firefox(firefox_profile=fp)
	url = 'http://www.snirh.gov.br/hidroweb/publico/apresentacao.jsf'
	driver.get(url)
	time.sleep(1)
	driver.get(url)
	n = 0
	p = 1
	while  p:
		try:
			driver.find_element_by_link_text('Séries Históricas').click()
			p = 0
		except:
			time.sleep(1)
			n += 1
		if n == 300:
			print('Tempo de espera excedido. Processo encerrado.')
	
	wait_load_items(driver, '//*[@id="form:fsListaEstacoes:codigoEstacao"]')
	driver.find_element_by_xpath('//*[@id="form:fsListaEstacoes:codigoEstacao"]').send_keys([id_station, Keys.ENTER])
	wait_load_items(driver, '//*[@id="form:fsListaEstacoes:nomeEstacao"]')
	driver.find_element_by_xpath('//*[@id="form:fsListaEstacoes:nomeEstacao"]').send_keys([name_estation, Keys.ENTER])
	click_css_selector(driver, '#form\\:fsListaEstacoes\\:bt')
	click_css_selector(driver, '#form\\:fsListaEstacoes\\:fsListaEstacoesC\\:j_idt179\\:table\\:0\\:ckbSelecionada')
	click_css_selector(driver, '#form\\:fsListaEstacoes\\:fsListaEstacoesC\\:radTipoArquivo-componente > div:nth-child(2) > div:nth-child(2)')
	click_css_selector(driver, '#form\\:fsListaEstacoes\\:fsListaEstacoesC\\:btBaixar')


ID_ESTACAO = '00047001'
NOME_ESTACAO = 'MARACANÃ'
download_hidroweb(ID_ESTACAO, NOME_ESTACAO, home)
