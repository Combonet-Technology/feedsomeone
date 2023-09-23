import json
import os
import sys

import requests
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')))
from utils.enums import Currency, SubscriptionPlan  # noqa: E402

load_dotenv()
ENCRYPTION_KEY = os.environ.get("FLW_ENCRYPTION_KEY")
TEST_FLW_PUBLIC_KEY = os.environ.get("TEST_FLW_PUBLIC_KEY")
TEST_FLW_SECRET_KEY = os.environ.get("TEST_FLW_SECRET_KEY")
TEST_ENCRYPTION_KEY = os.environ.get("TEST_ENCRYPTION_KEY")
TEST_RAVE_WEBHOOK_URL = os.environ.get("TEST_RAVE_WEBHOOK_URL")
RAVE_REDIRECT_URL = os.environ.get("RAVE_REDIRECT_URL")

OEF_CUSTOMIZATION = {
    "title": "Oluwafemi Ebenezer Foundation",
    "logo": "https://oluwafemiebenezerfoundation.org/static/img/logo/logo.png"
}


class RavePaymentHandler:
    def __init__(self, private_key, public_key):
        self.FLW_SECRET_KEY = private_key
        self.RAVE_REDIRECT_URL = RAVE_REDIRECT_URL
        self.OEF_CUSTOMIZATION = OEF_CUSTOMIZATION
        self.filter = dict()
        self.headers = {
            "Authorization": f"Bearer {self.FLW_SECRET_KEY}",
            "Content-Type": "application/json"
        }

    def pay_once(self, amount: float, currency: Currency, customer_data, tx_ref_id: str):
        return self._generate_payment_link(amount, currency, customer_data, tx_ref_id)

    def pay_recurrent(self, amount, currency, customer_data, tx_ref_id,
                      subscription_name,
                      subscription_interval=SubscriptionPlan.MONTHLY):
        plan = self.create_subscription_plan(subscription_name, subscription_interval)

        if plan:
            plan_id = plan['data']['id']
            url = self._generate_payment_link(amount, currency, customer_data, tx_ref_id, plan_id)
            return url, plan_id
        else:
            return None

    def _generate_payment_link(self, amount, currency, customer_data, tx_ref_id,
                               plan_id=None):
        try:
            data = {
                "tx_ref": tx_ref_id,
                "amount": amount,
                "currency": currency,
                "redirect_url": self.RAVE_REDIRECT_URL,
                "meta": {
                    "consumer_id": 23,
                    "consumer_mac": "92a3-912ba-1192a"
                },
                "customer": customer_data,
                "customizations": self.OEF_CUSTOMIZATION
            }

            if plan_id:
                data['payment_plan'] = plan_id
            response = requests.post("https://api.flutterwave.com/v3/payments", headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print("An error occurred:", str(e))
            return None

    def get_subscription(self, filters=None):
        query_params = None
        if filters:
            query_params = {
                key: value
                for key, value in filters.__dict__.items()
                if value is not None
            }
        try:
            url = "https://api.flutterwave.com/v3/payment-plans"

            response = requests.get(url, headers=self.headers, params=query_params)

            if response.status_code == 200:
                print(json.dumps(response.json()['data'], indent=2))
                return response.json()
            else:
                print("Failed to retrieve subscription plans. Status code:", response.status_code)
                print("Response:", response.text)
                return None

        except Exception as e:
            print("An error occurred:", str(e))
            return None

    def create_subscription_plan(self, subscription_name, subscription_interval: SubscriptionPlan):
        try:
            url = "https://api.flutterwave.com/v3/payment-plans"
            data = {
                "name": subscription_name,
                "interval": subscription_interval,
            }

            response = requests.post(url, headers=self.headers, json=data)

            if response.status_code == 200:
                print(response.json())
                return response.json()
            else:
                print("Failed to create subscription plan. Status code:", response.status_code)
                print("Response:", response.text)
                return None

        except Exception as e:
            print("An error occurred:", str(e))
            return None

    def verify_transaction(self, tr_id):
        print('here')
        try:
            url = f'https://api.flutterwave.com/v3/transactions/{tr_id}/verify'

            response = requests.get(url, headers=self.headers)
            print(response.json())
            if response.status_code == 200:
                print(response.json())
                return response.json()['data']
            else:
                print("Failed to verify transaction. Status code:", response.status_code)
                print("Response:", response.text)
                return None

        except Exception as e:
            print("An error occurred:", str(e))
            return None

    def deactivate_plan(self, plan_ids):
        if isinstance(plan_ids, int):
            response = self._deactivate_single_plan(plan_ids)
            return response

        elif isinstance(plan_ids, list) and all(isinstance(id, int) for id in plan_ids):
            responses = []
            for id in plan_ids:
                response = self._deactivate_single_plan(id)
                responses.append(response)
            return responses

        else:
            raise ValueError("plan_ids should be either an integer or a list of integers")

    def _deactivate_single_plan(self, plan_id):
        try:
            url = f"https://api.flutterwave.com/v3/payment-plans/{plan_id}/cancel"
            headers = {
                "Authorization": f"Bearer {self.FLW_SECRET_KEY}",
                "Content-Type": "application/json"
            }

            response = requests.post(url, headers=headers)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            print("An error occurred during plan deactivation:", str(e))
            return None


if __name__ == '__main__':
    handler = RavePaymentHandler(os.environ.get("RAVE_SECRET_KEY"), os.environ.get("RAVE_PUBLIC_KEY"))
    print(f"Bearer {handler.FLW_SECRET_KEY}")
    # lnk = handler.get_subscription()
    # ids = [plan['id'] for plan in lnk['data']]
    # print(ids)
    # deleted = handler.deactivate_plan(ids)
    # print(deleted)
