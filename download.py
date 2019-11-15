# -*- coding: utf-8 -*-
import time
import pandas as pd
from selenium import webdriver
from utils import getvert, isinpoly3
from selenium.webdriver.common.keys import Keys


def download_from_id(ids, inventory, dir_out):
    df_inventory = pd.read_csv(inventory, sep=',', header=0, encoding='latin1',
                               usecols=['Codigo','Nome'])
    df_inventory = df_inventory[['Codigo','ID']]
    df_download = df_inventory[df_inventory.Codigo.isin(ids.values.squeeze())]
    
    for ID, NOME in df_download.values:
        download_hidroweb(str(ID), NOME, dir_out)   

def download_from_shp(shp, poly, attr, buffer, inventory, tp, dir_out):
    if buffer:
        buffer = float(buffer)
    else:
        buffer = False # padrão caso não informado
    
    df_inventory = pd.read_csv(inventory, sep=',', header=0, encoding='latin1',
                               usecols=['TipoEstacao','Codigo','Nome','Latitude','Longitude'],
                               decimal=',')
    df_inventory = df_inventory[df_inventory.TipoEstacao == tp]
    # extrai vertices do poligono (poly) do shape informado
    vertices = getvert(shp, poly, attr=attr, buffer=buffer)
    
    isin = isinpoly3(df_inventory.Longitude.values, df_inventory.Latitude.values, vertices)
    
    estations_in = df_inventory[isin]
    
    for estation in estations_in.values:
        ID = str(estation[1])
        NOME = estation[2]
        download_hidroweb(ID, NOME, dir_out)
    
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
        if n == 60:
            print('Tempo de espera excedito. Processo encerrado.')
            break

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

        if n == 60:
            print('Tempo de espera excedido.')
            break

def download_hidroweb(id_station, name_estation, dir_out):
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
    fp.set_preference("browser.link.open_newwindow.override.external", True)

    driver = webdriver.Firefox(firefox_profile=fp)
    driver.minimize_window()
    url = 'http://www.snirh.gov.br/hidroweb/apresentacao'
    driver.get(url)
    time.sleep(1)
    driver.get(url)
    n = 0
    p = 1
    while  p:
        try:
            click_css_selector(driver, 'div.ng-star-inserted:nth-child(3) > mat-panel-title:nth-child(1) > div:nth-child(1) > a:nth-child(1)')
            p = 0
        except:
            time.sleep(1)
            n += 1
        if n == 50:
            print('Tempo de espera excedido. Processo encerrado.')
            p = 0
            break
    
    wait_load_items(driver, '//*[@id="mat-input-0"]')
    driver.find_element_by_xpath('//*[@id="mat-input-0"]').send_keys([id_station, Keys.ENTER])
    wait_load_items(driver, '//*[@id="mat-input-1"]')
    driver.find_element_by_xpath('//*[@id="mat-input-1"]').send_keys([name_estation, Keys.ENTER])
    click_css_selector(driver, 'button.mat-flat-button > span:nth-child(1)')
    wait_load_items(driver, '/html/body/app-root/mat-sidenav-container/mat-sidenav-content/ng-component/form/mat-tab-group/div/mat-tab-body[1]/div/ana-card/mat-card/mat-card-content/ana-dados-convencionais-list/div/div[1]/table/tbody/tr/td[1]/mat-checkbox/label/div')
    time.sleep(2)
    
    try:
        driver.find_element_by_xpath('/html/body/app-root/mat-sidenav-container/mat-sidenav-content/ng-component/form/mat-tab-group/div/mat-tab-body[1]/div/ana-card/mat-card/mat-card-content/ana-dados-convencionais-list/div/div[1]/table/tbody/tr/td[1]/mat-checkbox/label/div').click()
        click_css_selector(driver, '#mat-radio-4 > label:nth-child(1) > div:nth-child(1)')
        click_css_selector(driver, 'a.mat-raised-button > span:nth-child(1)')
    except Exception as e:
        print(e)
    
    driver.quit()
