import os
import sys
from dataclasses import dataclass
from typing import Optional
import json

import requests
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')))
from utils.enums import SubscriptionPlan  # noqa: E402

load_dotenv()
FLW_SECRET_KEY = os.environ.get("RAVE_SECRET_KEY")
FLW_PUBLIC_KEY = os.environ.get("RAVE_PUBLIC_KEY")
ENCRYPTION_KEY = os.environ.get("FLW_ENCRYPTION_KEY")
print(FLW_PUBLIC_KEY, FLW_SECRET_KEY)
TEST_FLW_PUBLIC_KEY = 'FLWPUBK_TEST-1db61213ff9e3721f770e0697a9e60c5-X'
TEST_FLW_SECRET_KEY = 'FLWSECK_TEST-8017fa700f790646a835491cefd646c7-X'
TEST_ENCRYPTION_KEY = 'FLWSECK_TEST73746dfa2c5a'
TEST_RAVE_WEBHOOK_URL = 'https://dev.oluwafemiebenezer.foundation/webhooks'
RAVE_WEBHOOK_URL = TEST_RAVE_WEBHOOK_URL


@dataclass
class Customer:
    full_name: Optional[str]
    email: str
    phone_number: Optional[str]
    address: Optional[str]


@dataclass
class SubscriptionFilter:
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    page: Optional[int] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    interval: Optional[str] = None
    status: Optional[str] = None


# Example usage:
customer_data = Customer(
    full_name="John Doe",
    email="info@oluwafemiebenezerfoundation.org",
    phone_number="+234-456-7890",
    address="123 Main Street"
)
OEF_CUSTOMIZATION = {
    "title": "Oluwafemi Ebenezer Foundation",
    "logo": "https://oluwafemiebenezerfoundation.org/static/img/logo/logo.png"
}


class RavePaymentHandler:
    def __init__(self):
        self.FLW_SECRET_KEY = FLW_SECRET_KEY
        self.RAVE_WEBHOOK_URL = FLW_PUBLIC_KEY
        self.OEF_CUSTOMIZATION = OEF_CUSTOMIZATION
        self.filter = dict()

    def pay_once(self, amount, currency, customer_data, tx_ref_id):
        return self._generate_payment_link(amount, currency, customer_data, tx_ref_id)

    def pay_recurrent(self, amount, currency, customer_data, tx_ref_id, subscription_name, subscription_interval,
                      subscription_duration):
        plan = self.create_subscription_plan(subscription_name, subscription_interval, subscription_duration)
        if plan:
            return self._generate_payment_link(amount, currency, customer_data, tx_ref_id, plan.get('id'))
        else:
            return None

    def _generate_payment_link(self, amount, currency, customer_data, tx_ref_id, plan_id=None):
        try:
            headers = {
                "Authorization": f"Bearer {self.FLW_SECRET_KEY}",
                "Content-Type": "application/json"
            }

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

            response = requests.post("https://api.flutterwave.com/v3/payments", headers=headers, json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print("An error occurred:", str(e))
            return None

    def get_subscription(self, filters: SubscriptionFilter = None):
        if not filters:
            filters = self.filter
        try:
            url = "https://api.flutterwave.com/v3/payment-plans"
            headers = {
                "Authorization": f"Bearer {self.FLW_SECRET_KEY}",
            }

            # Use a dictionary comprehension to construct the query parameters
            query_params = {
                key: value
                for key, value in filters.__dict__.items()
                if value is not None
            }

            response = requests.get(url, headers=headers, params=query_params)

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
            headers = {
                "Authorization": f"Bearer {self.FLW_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            data = {
                "name": subscription_name,
                "interval": subscription_interval,
                "duration": subscription_duration if subscription_name else 1_000_000_000_000_000_000
            }

            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 200:
                return response.json()
            else:
                print("Failed to create subscription plan. Status code:", response.status_code)
                print("Response:", response.text)
                return None

        except Exception as e:
            print("An error occurred:", str(e))
            return None


if __name__ == '__main__':
    handler = RavePaymentHandler(
        secret_key="your_secret_key",
        webhook_url="your_webhook_url",
        customization="your_customization",
        filters=None  # Pass an instance of SubscriptionFilter here if needed
    )

    # Example: Pay once
    handler.pay_once(amount=100, currency="USD", customer_data={"name": "John Doe"}, tx_ref_id="12345")

    # Example: Pay recurrent
    handler.pay_recurrent(amount=50, currency="EUR", customer_data={"name": "Jane Smith"}, tx_ref_id="54321",
                          plan_id="your_plan_id")

    # Example: Get subscription plans
    subscription_plans = handler.get_subscription()

    # Example: Create a subscription plan
    new_plan = handler.create_subscription_plan("Silver Plan", "monthly", 12)
