import json
import os
import sys

import requests
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')))
from utils.enums import Currency, SubscriptionPlan  # noqa: E402

load_dotenv()
ENCRYPTION_KEY = os.environ.get("FLW_ENCRYPTION_KEY")
TEST_FLW_PUBLIC_KEY = 'FLWPUBK_TEST-1db61213ff9e3721f770e0697a9e60c5-X'
TEST_FLW_SECRET_KEY = 'FLWSECK_TEST-8017fa700f790646a835491cefd646c7-X'
TEST_ENCRYPTION_KEY = 'FLWSECK_TEST73746dfa2c5a'
TEST_RAVE_WEBHOOK_URL = 'https://dev.oluwafemiebenezer.foundation/webhooks'
RAVE_WEBHOOK_URL = TEST_RAVE_WEBHOOK_URL

OEF_CUSTOMIZATION = {
    "title": "Oluwafemi Ebenezer Foundation",
    "logo": "https://oluwafemiebenezerfoundation.org/static/img/logo/logo.png"
}


class RavePaymentHandler:
    def __init__(self, private_key, public_key):
        self.FLW_SECRET_KEY = private_key
        self.RAVE_WEBHOOK_URL = public_key
        self.OEF_CUSTOMIZATION = OEF_CUSTOMIZATION
        self.filter = dict()
        self.headers = {
            "Authorization": f"Bearer {self.FLW_SECRET_KEY}",
            "Content-Type": "application/json"
        }

    def pay_once(self, amount: float, currency: Currency, customer_data, tx_ref_id: str):
        return self._generate_payment_link(amount, currency, customer_data, tx_ref_id)

    def pay_recurrent(self, amount, currency, customer_data, tx_ref_id,
                      subscription_name, subscription_duration,
                      subscription_interval=SubscriptionPlan.MONTHLY):
        plan = self.create_subscription_plan(subscription_name, subscription_interval, subscription_duration)
        if plan:
            return self._generate_payment_link(amount, currency, customer_data, tx_ref_id, plan['data']['id'])
        else:
            return None

    def _generate_payment_link(self, amount, currency, customer_data, tx_ref_id,
                               plan_id=None):
        try:
            data = {
                "tx_ref": tx_ref_id,
                "amount": amount,
                "currency": currency,
                "redirect_url": self.RAVE_WEBHOOK_URL,
                "meta": {
                    "consumer_id": 23,
                    "consumer_mac": "92a3-912ba-1192a"
                },
                "customer": customer_data,
                "customizations": self.OEF_CUSTOMIZATION
            }

            if plan_id:
                data['payment_plan'] = plan_id
            print(data)
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

    def create_subscription_plan(self, subscription_name, subscription_interval: SubscriptionPlan,
                                 subscription_duration):
        try:
            url = "https://api.flutterwave.com/v3/payment-plans"
            data = {
                "name": subscription_name,
                "interval": subscription_interval,
                "duration": subscription_duration if subscription_name else 1_000_000_000_000_000_000
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


if __name__ == '__main__':
    handler = RavePaymentHandler()

    # Example: Pay once
    # handler.pay_once(amount=100, currency="USD", customer_data={"name": "John Doe"}, tx_ref_id="12345")

    # Example: Pay recurrent
    # test_sub = handler.pay_recurrent(amount=50, currency="EUR", customer_data={"name": "Jane Smith"},
#                                  tx_ref_id='coemhrnrehfgd1',
#                                  subscription_name="Trial Annual Test subscription", subscription_interval="annual",
#                                  subscription_duration=12)
    # print(test_sub)
    # Example: Get subscription plans
    # subscription_plans = handler.get_subscription()
    # print(subscription_plans)
    # Example: Create a subscription plan
    # new_plan = handler.create_subscription_plan("Silver Plan", "monthly", 12)
    # print(new_plan)
    lnk = handler._generate_payment_link(amount=50000, currency="NGN",
                                         customer_data={"name": "Jane Smith", "email": "test@mail.com"},
                                         tx_ref_id='coehfgd1', plan_id=108344)
    print(lnk)
