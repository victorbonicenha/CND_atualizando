import telebot
from dotenv import load_dotenv
import os

load_dotenv()

token=os.getenv("ITOKEN")
chat_id=os.getenv("CHAT_ID")

class TelegramSend:

    def __init__(self, name):
        self.name = name

    def telegram_bot(self, message, itoken, chat_id):
        """
        Telegram Bot
        :param message: Mensagem a ser enviada pelo telegram;
        :param itoken: Token do bot no Telegram;
        :param chat_id: ID do chat ou grupo;
        :return: Confirmação da mensagem enviada."""
        
        bot = telebot.TeleBot(itoken)
        texto = f"{self.name} {message}"
        bot.send_message(chat_id, texto)
        return {"status": "enviado", "mensagem": texto}

    def telegram_bot_image(self, message, itoken, chat_id, path_image):
        """
        Telegram Bot (imagem + mensagem)
        :param message: Mensagem a ser enviada;
        :param itoken: Token do bot;
        :param chat_id: ID do grupo ou usuário;
        :param path_image: Caminho da imagem;
        :return: Confirmação da mensagem e imagem enviada.
        """
        bot = telebot.TeleBot(itoken)

        with open(path_image, 'rb') as img:
            bot.send_photo(chat_id, img)

        texto = f"{self.name} {message}"
        bot.send_message(chat_id, texto)

        return {"status": "imagem+mensagem enviada", "mensagem": texto, "imagem": path_image}
    