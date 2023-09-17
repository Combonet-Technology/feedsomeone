import json
import os
import sys
from dataclasses import dataclass
from typing import Optional

import requests
from django.shortcuts import redirect
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


def generate_payment_link(amount, currency, customer_data, tx_ref_id, payment_plan: Optional[str] = None):
    try:
        headers = {
            "Authorization": f"Bearer {FLW_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "tx_ref": tx_ref_id,
            "amount": amount,
            "currency": currency,
            "redirect_url": RAVE_WEBHOOK_URL,
            "meta": {
                "consumer_id": 23,
                "consumer_mac": "92a3-912ba-1192a"
            },
            "customer": customer_data,
            "customizations": OEF_CUSTOMIZATION
        }

        if payment_plan:
            data['payment_plan'] = payment_plan

        response = requests.post("https://api.flutterwave.com/v3/payments", headers=headers, json=data)
        response.raise_for_status()
        print(response.json()['data']['link'])
        return redirect(response.json()['data']['link'])
    except Exception as e:
        print("An error occurred:", str(e))
        return None


def get_subscription(filters: Optional[SubscriptionFilter] = None):
    if not filters:
        filters = dict()
    try:
        url = "https://api.flutterwave.com/v3/payment-plans"
        headers = {
            "Authorization": f"Bearer {FLW_SECRET_KEY}",
        }

        # Use a dictionary comprehension to construct the query parameters
        query_params = {
            key: value
            for key, value in filter.__dict__.items()
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


def create_subscription_plan(duration: SubscriptionPlan):
    try:
        url = "https://api.flutterwave.com/v3/payment-plans"
        headers = {
            "Authorization": f"Bearer {FLW_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "name": f"{duration.capitalize()} Subscription Plan",
            "interval": duration,
            # "amount": 100000
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
    #
    # # Example usage:
    # payment_url = generate_payment_link()
    # if payment_url:
    #     print("Payment plan created successfully.")
    #
    # subscription_plan_result = create_subscription_plan("yearly")
    # if subscription_plan_result:
    #     print("Subscription plan created successfully.")
    # generate_payment_link(10000, 'NGN', customer_data.__dict__, '123werty-feed')
    get_subscription()
