# telegram_bot.py
import requests

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}/"

    def set_webhook(self, url):
        method = "setWebhook"
        params = {"url": url}
        response = requests.get(self.api_url + method, params)
        if response.json().get('ok'):
            print("Webhook berhasil diatur.")
        else:
            print(f"Gagal mengatur webhook: {response.json()}")

    def send_message(self, chat_id, text):
        method = "sendMessage"
        params = {"chat_id": chat_id, "text": text}
        response = requests.post(self.api_url + method, data=params)
        return response.json()