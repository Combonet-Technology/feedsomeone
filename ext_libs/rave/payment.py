import os
from dataclasses import dataclass

import requests
from rave_python import Rave

from enum import Enum


class SubscriptionPlan(Enum):
    DAILY = {"interval": "daily"}
    WEEKLY = {"interval": "weekly"}
    MONTHLY = {"interval": "monthly"}
    QUARTERLY = {"interval": "quarterly"}
    ANNUALLY = {"interval": "annually"}


# Replace with your Flutterwave API secret key
FLW_SECRET_KEY = os.getenv("FLW_SECRET_KEY")
RAVE_WEBHOOK_URL = os.getenv("RAVE_WEBHOOK_URL")


@dataclass
class Customer:
    full_name: str
    email: str
    phone_number: str
    address: str  # You can add more fields as needed


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


def generate_payment_link(amount, currency, customer_data, tx_ref_id):
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

        response = requests.post("https://api.flutterwave.com/v3/payments", headers=headers, json=data)
        response.raise_for_status()

        return response.json()
    except Exception as e:
        print("An error occurred:", str(e))
        return None


def create_subscription_plan(duration):
    try:
        # Define the subscription plan details based on the duration
        subscription_plans = {
            "daily": {"amount": 500, "interval": "daily"},
            "weekly": {"amount": 2500, "interval": "weekly"},
            "monthly": {"amount": 10000, "interval": "monthly"},
            "quarterly": {"amount": 30000, "interval": "quarterly"},
            "annually": {"amount": 120000, "interval": "annually"}
        }

        if duration not in subscription_plans:
            raise ValueError("Invalid duration. Supported durations: daily, weekly, monthly, quarterly, annually")

        plan_details = subscription_plans[duration]

        # Create the subscription plan using the details
        rave = Rave(os.getenv("FLW_PUBLIC_KEY"), os.getenv("FLW_SECRET_KEY"))
        res = rave.PaymentPlan.create({
            "amount": plan_details["amount"],
            "name": f"{duration.capitalize()} Subscription Plan",
            "interval": plan_details["interval"]
        })

        return res
    except Exception as e:
        print("An error occurred:", str(e))
        return None


# Example usage:
payment_plan_result = create_payment_plan()
if payment_plan_result:
    print("Payment plan created successfully.")

subscription_plan_result = create_subscription_plan("monthly")
if subscription_plan_result:
    print("Subscription plan created successfully.")
