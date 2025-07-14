from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
from datetime import datetime
import base64
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import shutil
import requests
from time import sleep
import os
from config_telegram import TelegramSend
import re
import sys

load_dotenv()

CNPJ_BASE = os.getenv("CNPJ_BASE")
CNPJ_BASICO = os.getenv('CNPJ_BASICO')
CNPJ = os.getenv("CNPJ_SC")
CPF = os.getenv('CPF')
API_KEY = os.getenv("CHAVE_API")
ITOKEN = os.getenv("ITOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
BASE_PATH = os.getenv("BASE_PATH")
data_hoje = datetime.now().strftime('%d-%m-%Y')
telegram = TelegramSend("CND")
erro = TelegramSend("CND ERRO:")

meses = {'01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
         '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
         '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'}

pasta_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
ano_atual = datetime.now().strftime('%Y')
mes_atual = datetime.now().strftime('%m')
mes_extenso = meses[mes_atual]
pasta_mes = f"{mes_atual} - {mes_extenso}"

pasta_fgts = os.path.join(BASE_PATH, "CND_FGTS", ano_atual, pasta_mes)
pasta_municipal = os.path.join(BASE_PATH, "CND - Municipal", ano_atual, pasta_mes)
pasta_trabalhista = os.path.join(BASE_PATH, "CND - Trabalhista", ano_atual, pasta_mes)
pasta_divida_ativa = os.path.join(BASE_PATH, "CND - Divida Ativa", ano_atual, pasta_mes)

ANTICAPTCHA_CREATE_URL = "https://api.anti-captcha.com/createTask"
ANTICAPTCHA_RESULT_URL = "https://api.anti-captcha.com/getTaskResult"

def iniciar_selenium(download_path=None):
    options = Options()
    options.add_argument("--start-maximized")

    if download_path:
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True}
        options.add_experimental_option("prefs", prefs)
    navegador = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return navegador

def resolver_captcha_imagem(caminho_imagem, tentativas=3):
    with open(caminho_imagem, 'rb') as f:
        image_base64 = base64.b64encode(f.read()).decode('utf-8')

    url_create = ANTICAPTCHA_CREATE_URL
    url_result = ANTICAPTCHA_RESULT_URL

    for i in range(tentativas):
        payload = {
            "clientKey": API_KEY,
            "task": {
                "type": "ImageToTextTask",
                "body": image_base64}}

        response = requests.post(url_create, json=payload).json()

        if response.get('errorId') != 0:
            continue

        task_id = response.get('taskId')

        for tentativa in range(30):
            sleep(3)
            result = requests.post(url_result, json={
                "clientKey": API_KEY,
                "taskId": task_id}).json()

            if result.get('status') == 'ready':
                texto = result.get('solution', {}).get('text')
                return texto
    return None

def resolver_captcha_recaptcha(api_key, site_key, site_url, tentativas=3):
    url_create = ANTICAPTCHA_CREATE_URL
    url_result = ANTICAPTCHA_RESULT_URL

    for i in range(tentativas):
        payload = {
            "clientKey": api_key,
            "task": {
                "type": "NoCaptchaTaskProxyless",
                "websiteURL": site_url,
                "websiteKey": site_key}}

        response = requests.post(url_create, json=payload).json()

        if response.get('errorId') != 0:
            erro_desc = response.get('errorDescription', 'Erro desconhecido')
            erro.telegram_bot(f"Erro ao criar task no anti-captcha: {erro_desc}", ITOKEN, CHAT_ID)
            continue

        task_id = response.get('taskId')

        for tentativa in range(10):
            sleep(3)
            res = requests.post(url_result, json={
                "clientKey": api_key,
                "taskId": task_id}).json()

            if res.get('status') == 'ready':
                token = res.get('solution', {}).get('gRecaptchaResponse')
                return token
    erro.telegram_bot("Captcha não foi resolvido após várias tentativas.", ITOKEN, CHAT_ID)
    return None

def resolver_captcha_anticaptcha(navegador, tentativas=3):
    captcha_element = navegador.find_element(By.XPATH, '//*[@id="captchaImage"]/img')
    captcha_path = os.path.join(os.getcwd(), 'captcha.png')
    captcha_element.screenshot(captcha_path)

    with open(captcha_path, "rb") as img_file:
        b64_string = base64.b64encode(img_file.read()).decode()

    url_create = ANTICAPTCHA_CREATE_URL
    url_result = ANTICAPTCHA_RESULT_URL
    headers = {"Content-Type": "application/json"}

    for i in range(tentativas):
        payload = {
            "clientKey": API_KEY,
            "task": {
                "type": "ImageToTextTask",
                "body": b64_string}}

        response = requests.post(url_create, json=payload, headers=headers).json()

        if response.get('errorId') != 0:
            continue

        task_id = response.get('taskId')
        for tentativa in range(30):
            sleep(3)
            res = requests.post(url_result, json={
                "clientKey": API_KEY,
                "taskId": task_id}, headers=headers).json()

            if res.get('status') == 'ready':
                solution = res.get('solution', {}).get('text')
                os.remove(captcha_path)
                return solution

    os.remove(captcha_path)
    erro.telegram_bot("Timeout: captcha não foi resolvido na certidão municipal.", ITOKEN, CHAT_ID)
    navegador.quit()
    sys.exit()

def cnd_divida_ativa():
    url_site = 'https://www.dividaativa.pge.sp.gov.br/sc/pages/home/home_novo.jsf'
    navegador = iniciar_selenium()
    navegador.get(url_site)
    sleep(3)

    try:
        navegador.find_element(By.XPATH, '//*[@id="modalPanelDebIpvaIDContentDiv"]/div').click()
        sleep(1)
    except:
        pass

    navegador.find_element(By.XPATH, '//*[@id="menu:j_id99_span"]').click()
    sleep(1)

    try:
        wait = WebDriverWait(navegador, 10)
        elemento = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="menu:itemMenu3649:anchor"]')))
        elemento.click()
    except Exception as e:
        erro.telegram_bot(f"Erro ao clicar no menu: {str(e)}", ITOKEN, CHAT_ID)
        navegador.quit()
        return
    try:
        wait = WebDriverWait(navegador, 10)
        campo_cnpj = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="emitirCrda:crdaInputCnpjBase"]')))
        campo_cnpj.send_keys(CNPJ_BASE)
    except:
        erro.telegram_bot("Campo CNPJ não encontrado na dívida ativa.", ITOKEN, CHAT_ID)
        navegador.quit()
        return
    try:
        site_key = navegador.find_element(By.XPATH, '//*[@id="recaptcha"]').get_attribute('data-sitekey')
    except:
        erro.telegram_bot("Não foi possível capturar o sitekey do reCAPTCHA.", ITOKEN, CHAT_ID)
        navegador.quit()
        return

    token = resolver_captcha_recaptcha(API_KEY, site_key, url_site)

    if not token:
        navegador.quit()
        return

    try:
        navegador.execute_script("""
            document.getElementById("g-recaptcha-response").style.display = 'block';
            document.getElementById("g-recaptcha-response").value = arguments[0];
            document.getElementById("g-recaptcha-response").innerHTML = arguments[0];""", token)
        sleep(2)

        navegador.find_element(By.XPATH, '//*[@id="emitirCrda:j_id78_body"]/div[2]/input[2]').click()
        sleep(2)
        screenshot_path = os.path.join(os.getcwd(), f"print_divida_ativa_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png")
        navegador.save_screenshot(screenshot_path)
        os.makedirs(pasta_divida_ativa, exist_ok=True)

        arquivos_encontrados = False

        for arquivo in os.listdir(pasta_downloads):
            if arquivo.endswith(".pdf") and "crda" in arquivo.lower():                                                                                                           
                caminho_origem = os.path.join(pasta_downloads, arquivo)
                nome_novo = f"{os.path.splitext(arquivo)[0]}_validade_{data_hoje}.pdf"
                caminho_final = os.path.join(pasta_divida_ativa, nome_novo)
                try:
                    shutil.move(caminho_origem, caminho_final)
                    mensagem = f"Divida Ativa gerada com sucesso!\n\nArquivo salvo em:\n\n{caminho_final}"
                    telegram.telegram_bot_image(mensagem, ITOKEN, CHAT_ID, screenshot_path)

                    arquivos_encontrados = True
                    break
                except Exception as move_error:
                    erro.telegram_bot(f"Erro ao mover arquivo PDF: {str(move_error)}", ITOKEN, CHAT_ID)

        if not arquivos_encontrados:
            erro.telegram_bot("Nenhum arquivo PDF com 'crda' encontrado na pasta de downloads.", ITOKEN, CHAT_ID)

    except Exception as e:
        erro.telegram_bot(f"Erro ao gerar certidão: {str(e)}", ITOKEN, CHAT_ID)

    navegador.quit()

def cnd_fgts():
    navegador = iniciar_selenium()
    url_site = 'https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf'
    navegador.get(url_site)

    sleep(3)

    navegador.find_element(By.XPATH, '//*[@id="mainForm:txtInscricao1"]').send_keys(CNPJ_BASICO)
    sleep(1)

    navegador.find_element(By.XPATH, '//*[@id="mainForm:uf"]').click()
    navegador.find_element(By.XPATH, '//*[@id="mainForm:uf"]/option[26]').click()

    sleep(3)

    tentativas = 0
    sucesso = False

    while tentativas < 5 and not sucesso:
        tentativas += 1

        CAPTCHA_XPATH = '//*[@id="captchaImg_N2"]'
        captcha_element = navegador.find_element(By.XPATH, CAPTCHA_XPATH)

        navegador.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", captcha_element)
        sleep(1) 

        captcha_src = captcha_element.get_attribute("src")
        if captcha_src.strip() == "data:image/png;base64,":

            erro_captcha_path = os.path.abspath(f"captcha_quebrado_{datetime.now().strftime('%H%M%S')}.png")
            captcha_element.screenshot(erro_captcha_path)

            erro.telegram_bot_image("CAPTCHA não carregou corretamente (base64 vazio).\n\nO site pode estar fora do ar ou com erro de carregamento.", ITOKEN, CHAT_ID, erro_captcha_path)
            navegador.quit()
            return

        image_path = 'captcha_fgts.png'
        captcha_element.screenshot(image_path)

        captcha_resolvido = resolver_captcha_imagem(image_path)

        if captcha_resolvido and len(captcha_resolvido) >= 4:
            navegador.find_element(By.XPATH, '//*[@id="mainForm:txtCaptcha"]').clear()
            navegador.find_element(By.XPATH, '//*[@id="mainForm:txtCaptcha"]').send_keys(captcha_resolvido)
            sleep(1)

            navegador.find_element(By.ID, 'mainForm:btnConsultar').click()
            sleep(3)

            if "Código da imagem inválido" in navegador.page_source:
                navegador.find_element(By.XPATH, '//*[@id="mainForm:j_id98"]').click()
                sleep(2)
            else:
                sucesso = True
        else:
            navegador.find_element(By.XPATH, '//*[@id="mainForm:j_id98"]').click()
            sleep(2)

    if sucesso:
        try:
            navegador.find_element(By.XPATH, '//*[@id="mainForm:listaEstabelecimentos:0:linkAction1"]/span').click()
            sleep(2)

            navegador.find_element(By.XPATH, '//*[@id="mainForm:j_id51"]').click()
            sleep(2)

            navegador.find_element(By.XPATH, '//*[@id="mainForm:btnVisualizar"]').click()
            sleep(3)

            ele_validade = navegador.find_element(By.XPATH, '//*[@id="mainForm"]/table[2]/tbody/tr/td/table[2]/tbody/tr[12]')
            validade_emisao = ele_validade.text

            reg_val = re.search(
                r'Validade:\s*\d{2}/\d{2}/\d{4}\s*.\s*(\d{2}/\d{2}/\d{4})\s*Certificação Número:\s*(\d+)',
                validade_emisao.replace('\n', ' '))

            if reg_val:
                validade = reg_val.group(1).replace("/", "-")
                emissao = reg_val.group(2)
            else:
                validade = datetime.datetime.now().strftime("%Y-%m-%d")
                emissao = "sem_numero"

            nome_arquivo = f"print_validade_{validade}_cert_{emissao}.png"
            navegador.fullscreen_window()
            sleep(2)
            navegador.get_screenshot_as_file(nome_arquivo)

            screenshot_path = os.path.abspath(nome_arquivo)
            novo_caminho = os.path.join(pasta_fgts, nome_arquivo)
            shutil.move(screenshot_path, novo_caminho)

            telegram.telegram_bot_image(f"FGTS gerada com sucesso!\n\nValidade: {validade}\n\nNº: {emissao}\n\nArquivo salvo em:\n\n{novo_caminho}", ITOKEN, CHAT_ID, novo_caminho)

        except Exception as e:
            screenshot_path = os.path.abspath('erro_captura_certidao.png')
            navegador.get_screenshot_as_file(screenshot_path)
            erro.telegram_bot_image("Erro ao gerar certidão.", ITOKEN, CHAT_ID, screenshot_path)
    else:
        erro.telegram_bot("Não foi possível passar do captcha após 5 tentativas.", ITOKEN, CHAT_ID)

    sleep(5)
    navegador.quit()       

def cnd_trabalhista(base_path):
    navegador = iniciar_selenium(base_path)

    url = 'https://cndt-certidao.tst.jus.br/inicio.faces'
    navegador.get(url)
    sleep(3)

    navegador.find_element(By.XPATH, '//*[@id="corpo"]/div/div[2]/input[1]').click()
    sleep(2)

    navegador.find_element(By.XPATH, '//*[@id="gerarCertidaoForm:cpfCnpj"]').send_keys(CNPJ)
    sleep(2)

    wait = WebDriverWait(navegador, 10)
    captcha_element = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="idImgBase64"]')))
    
    captcha_path = os.path.join(base_path, 'captcha_trabalhista.png')
    os.makedirs(base_path, exist_ok=True)
    captcha_element.screenshot(captcha_path)

    captcha_text = resolver_captcha_imagem(captcha_path)

    if not captcha_text or len(captcha_text.strip()) < 4:
        telegram.telegram_bot("Falha ao resolver o CAPTCHA da Certidão Trabalhista.", ITOKEN, CHAT_ID)
        navegador.quit()
        return

    navegador.find_element(By.XPATH, '//*[@id="idCampoResposta"]').send_keys(captcha_text)

    navegador.find_element(By.XPATH, '//*[@id="gerarCertidaoForm:btnEmitirCertidao"]').click()
    sleep(2)

    screenshot_path = os.path.join(os.getcwd(), f"print_Trabalhista{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png")
    navegador.save_screenshot(screenshot_path)

    navegador.quit()

    for arquivo in os.listdir(base_path):
        if "certidao" in arquivo.lower() and arquivo.lower().endswith(".pdf"):
            origem = os.path.join(base_path, arquivo)
            destino = os.path.join(pasta_trabalhista, arquivo)
            shutil.move(origem, destino)

            nome_arquivo = os.path.basename(destino)
            mensagem = f"PDF Trabalhista\n\n{nome_arquivo}\n\nmovido para a pasta {pasta_trabalhista}"
            telegram.telegram_bot_image(mensagem, ITOKEN, CHAT_ID, screenshot_path)

def cnd_municipal():
    navegador = iniciar_selenium()
    url_site = 'https://portal.diadema.sp.gov.br/certidao-negativa-mobiliaria-e-imobiliaria-de-debitos/'
    navegador.get(url_site)

    try:
        navegador.find_element(By.CLASS_NAME, 'eicon-close').click()
    except NoSuchElementException:
        pass

    navegador.find_element(By.XPATH, '//*[@id="page"]/div/section[2]/div/div/div/div/div/p[4]/a/b').click()
    sleep(1)

    navegador.find_element(By.XPATH, '//*[@id="vCPFSOLICITANTE"]').send_keys(CPF)
    navegador.find_element(By.XPATH, '//*[@id="vNOMESOLICITANTE"]').send_keys('Alex Sandro Correia')
    navegador.find_element(By.XPATH, '//*[@id="vTIPOFILTRO"]').click()
    navegador.find_element(By.XPATH, '//*[@id="vTIPOFILTRO"]/option[3]').click()
    navegador.find_element(By.XPATH, '//*[@id="vNRFILTRO"]').send_keys(CNPJ)
    navegador.find_element(By.XPATH, '//*[@id="Rowfinalidade"]/td[2]').click()
    navegador.find_element(By.XPATH, '//*[@id="vMIAID"]/option[17]').click()
    navegador.find_element(By.XPATH, '//*[@id="TABLECONTRIBUINTE"]/tbody/tr[29]/td[2]').click()
    sleep(2)

    captcha_text = resolver_captcha_anticaptcha(navegador)
    navegador.find_element(By.XPATH, '//*[@id="_cfield"]').send_keys(captcha_text)
    navegador.find_element(By.XPATH, '//*[@id="TABLE3"]/tbody/tr/td[1]/input').click()

    try:
        WebDriverWait(navegador, 3).until(EC.presence_of_element_located((By.XPATH, '//*[@id="divMensagem"]/div')))
        captcha_text = resolver_captcha_anticaptcha(navegador)
        navegador.find_element(By.XPATH, '//*[@id="_cfield"]').clear()
        navegador.find_element(By.XPATH, '//*[@id="_cfield"]').send_keys(captcha_text)
        navegador.find_element(By.XPATH, '//*[@id="TABLE3"]/tbody/tr/td[1]/input').click()
    except:
        pass
    sleep(3)

    try:
        navegador.get('https://portaldeservicos.diadema.sp.gov.br/eagata/servlet/hwvdocumentos_v3')
        navegador.fullscreen_window()
        sleep(2)

        navegador.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(1.5)
    except:
        pass
    try:
        validade_extracao = navegador.find_element(By.XPATH, '//*[@id="TXTDSP"]/table/tbody/tr[3]/td/table/tbody/tr[6]/td[2]/p[2]')
        validade_regex = validade_extracao.text
        print(f"[DEBUG] Texto extraído para validade: {validade_regex}")
        
        validade_valor = re.search(r'Validade:\s*(\d{2}/\d{2}/\d{4})', validade_regex)
        
        if validade_valor:
            validade = validade_valor.group(1)
            print(f"[DEBUG] Validade encontrada: {validade}")
        else:
            validade = "NÃO ENCONTRADA"
            erro.telegram_bot("Não foi possível extrair a validade da certidão municipal (regex falhou).", ITOKEN, CHAT_ID)

        emissao_extracao = navegador.find_element(By.XPATH, '//*[@id="TXTDSP"]/table/tbody/tr[3]/td/table/tbody/tr[1]/td/h2[2]/span')
        emissao_regex = emissao_extracao.text
        print(f"[DEBUG] Texto extraído para emissão: {emissao_regex}")

        emissao_valor = re.search(r'Nº:\s*(\d+/\d+)', emissao_regex)

        if emissao_valor:
            emissao = emissao_valor.group(1)
        else:
            emissao = "NÃO ENCONTRADA"
            erro.telegram_bot("Não foi possível extrair o número de emissão da certidão municipal (regex falhou).", ITOKEN, CHAT_ID)

        navegador.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(2)

        screenshot_path = f"cnd_municipal_{datetime.now().strftime('%d-%m-%Y')}.png"
        navegador.save_screenshot(screenshot_path)
 
        os.makedirs(pasta_municipal, exist_ok=True)
        destino_final = os.path.join(pasta_municipal, screenshot_path)
        shutil.move(screenshot_path, destino_final)

        mensagem = f"Certidão Municipal gerada com sucesso\n\nValidade: {validade}\n\nEmissão: {emissao}\n\nArquivo salvo em: {destino_final}"
        telegram.enviar_imagem(destino_final, mensagem, ITOKEN, CHAT_ID)

    except Exception as e:
        erro.telegram_bot(f"Erro ao extrair a certidão municipal: {e}", ITOKEN, CHAT_ID)
        navegador.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        sleep(2)

        screenshot_path = f"cnd_municipal_{datetime.now().strftime('%d-%m-%Y')}.png"
        navegador.save_screenshot(screenshot_path)

        os.makedirs(pasta_municipal, exist_ok=True)
        destino_final = os.path.join(pasta_municipal, screenshot_path)
        shutil.move(screenshot_path, destino_final)

        mensagem = f"Certidão Municipal gerada com sucesso\n\n Validade:{validade}\n\n Arquivo salvo em: {destino_final}"
        telegram.enviar_imagem(destino_final, mensagem, ITOKEN, CHAT_ID)
        
    except Exception as e:
        erro.telegram_bot("Erro ao extrair a certidão municipal.", ITOKEN, CHAT_ID)

    navegador.quit()

if __name__ == "__main__":
    try:
        cnd_divida_ativa()
    except Exception as erro_Divida_Ativa:
        print(erro_Divida_Ativa)

    sleep(3)
    try:
        cnd_fgts()
    except Exception as erro_FGTS:
        print(erro_FGTS)
    sleep(3)

    try:
        cnd_trabalhista(os.path.join(os.getcwd(), 'CND - Trabalhista'))
    except Exception as erro_trabalhista:
        erro.telegram_bot(f'o erro é: {erro_trabalhista}', ITOKEN, CHAT_ID)
    sleep(3)
    try:
        cnd_municipal()
    except Exception as erro_municipal:
        print(str(erro_municipal))
    sleep(3)
