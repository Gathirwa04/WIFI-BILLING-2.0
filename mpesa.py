import requests
import json
import base64
from datetime import datetime

class MpesaClient:
    def __init__(self, consumer_key, consumer_secret, business_shortcode, passkey, callback_url):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.business_shortcode = business_shortcode
        self.passkey = passkey
        self.callback_url = callback_url
        self.base_url = "https://sandbox.safaricom.co.ke"

    def get_access_token(self):
        api_url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        response = requests.get(api_url, auth=(self.consumer_key, self.consumer_secret))
        if response.status_code == 200:
            return response.json()['access_token']
        else:
            raise Exception("Failed to get access token")

    def get_password(self, timestamp):
        data_to_encode = f"{self.business_shortcode}{self.passkey}{timestamp}"
        encoded_string = base64.b64encode(data_to_encode.encode())
        return encoded_string.decode('utf-8')

    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        access_token = self.get_access_token()
        api_url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = self.get_password(timestamp)
        
        # M-PESA phone number validation (must start with 254)
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif phone_number.startswith('+254'):
            phone_number = phone_number[1:]
            
        payload = {
            "BusinessShortCode": self.business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": self.business_shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": self.callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc
        }
        
        response = requests.post(api_url, json=payload, headers=headers)
        return response.json()
