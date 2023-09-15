import os
from dataclasses import dataclass
from typing import Optional

import requests
from django.shortcuts import redirect
from rave_python import Rave

from utils.enums import SubscriptionPlan

# Replace with your Flutterwave API secret key
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY")
RAVE_WEBHOOK_URL = os.getenv("RAVE_WEBHOOK_URL")


@dataclass
class Customer:
    full_name: Optional[str]
    email: str
    phone_number: Optional[str]
    address: Optional[str]


# Example usage:
customer_data = Customer(
    full_name="John Doe",
    email="john@example.com",
    phone_number="123-456-7890",
    address="123 Main Street"
)
OEF_CUSTOMIZATION = {
    "title": "Oluwafemi Ebenezer Foundation",
    "logo": "https://www.combonettechnology.com/images/cbt.png"
}


def generate_payment_link(amount, currency, customer_data, tx_ref_id, payment_plan: Optional[str]):
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
        return redirect(response.json()['data']['link'])
    except Exception as e:
        print("An error occurred:", str(e))
        return None


def create_subscription_plan(duration: SubscriptionPlan):
    try:
        rave = Rave(os.getenv("FLW_PUBLIC_KEY"), os.getenv("FLW_SECRET_KEY"))
        res = rave.PaymentPlan.create({
            "name": f"{duration.capitalize()} Subscription Plan",
            "interval": duration
        })

        return res
    except Exception as e:
        print("An error occurred:", str(e))
        return None


# Example usage:
payment_url = generate_payment_link()
if payment_url:
    print("Payment plan created successfully.")

subscription_plan_result = create_subscription_plan("monthly")
if subscription_plan_result:
    print("Subscription plan created successfully.")
