from config_telegram import TelegramSend
from dotenv import load_dotenv
from datetime import datetime
import pyodbc
import os

load_dotenv()

erro = TelegramSend("Banco")

def registrar_log(certidao, sucesso):
    try:
        conexao = pyodbc.connect(
            rf"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={os.getenv('DB_HOST')};"
            f"DATABASE={os.getenv('DB_NAME')};"
            f"UID={os.getenv('DB_USER')};"
            f"PWD={os.getenv('DB_PASS')};")
        cursor = conexao.cursor()

        data_hoje = datetime.now().date()

        cursor.execute("""
            SELECT tentativas, resultado FROM dbo.cnd_testes
            WHERE nome_certidao = ? AND CAST(data_execucao AS DATE) = ?""", (certidao, data_hoje))
        resultado_bd = cursor.fetchone()

        if resultado_bd:
            tentativas_atual, resultado_atual = resultado_bd
            nova_tentativa = tentativas_atual + 1
            novo_resultado = 1 if sucesso == 1 else resultado_atual

            cursor.execute("""
                UPDATE dbo.cnd_testes
                SET tentativas = ?, resultado = ?
                WHERE nome_certidao = ? AND CAST(data_execucao AS DATE) = ?""", (nova_tentativa, novo_resultado, certidao, data_hoje))
        else:
            data_execucao = datetime.now()
            cursor.execute("""
                INSERT INTO dbo.cnd_testes (nome_certidao, data_execucao, tentativas, resultado)
                VALUES (?, ?, ?, ?)""", (certidao, data_execucao, 0, sucesso))

        conexao.commit()
        conexao.close()

    except Exception as e:
        erro.telegram_bot(f"Erro ao registrar no banco: {e}", os.getenv("ITOKEN"), int(os.getenv("CHAT_ID")))
        print(f"Erro ao registrar no banco: {e}")


def pode_tentar(certidao, data_hoje):
    try:
        conexao = pyodbc.connect(
            rf"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={os.getenv('DB_HOST')};"
            f"DATABASE={os.getenv('DB_NAME')};"
            f"UID={os.getenv('DB_USER')};"
            f"PWD={os.getenv('DB_PASS')};")
        cursor = conexao.cursor()

        query = """
            SELECT COUNT(*) FROM dbo.cnd_testes
            WHERE nome_certidao = ?
            AND CAST(data_execucao AS DATE) = ?
            AND (
                resultado = 1 OR
                (tentativas >= 3 AND resultado = 0))"""
        cursor.execute(query, (certidao, data_hoje))
        resultado = cursor.fetchone()[0]
        conexao.close()
        return resultado < 1 

    except Exception as e:
        erro.telegram_bot(f"Erro ao consultar tentativas no banco: {e}", os.getenv("ITOKEN"), int(os.getenv("CHAT_ID")))
        print(f"Erro ao consultar tentativas no banco: {e}")
        return False
