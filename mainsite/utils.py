from mainsite.models import Donor, PaymentSubscription, TransactionHistory
from user.models import UserProfile
from utils.enums import PaymentPlanStatus, TransactionStatus


def get_or_create_user_profile(email, first_name, last_name):
    user_profile, created = UserProfile.objects.get_or_create(email=email)
    if not created:
        user_profile.first_name = first_name
        user_profile.last_name = last_name
        user_profile.save()
    return user_profile


def get_or_create_donor(user_profile):
    donor = Donor.objects.filter(user=user_profile).first()
    if not donor:
        donor = Donor.objects.create(user=user_profile)
    return donor


def handle_one_time_donation(handler, amount, currency, customer_data, tx_ref_id):
    response_data = handler.pay_once(amount, currency, customer_data, tx_ref_id)
    return response_data, None


def handle_recurrent_donation(handler, amount, currency, customer_data, tx_ref_id, full_name, donation_type):
    subscription_name = f'{full_name}-{donation_type}-pledge'
    response_data, payment_plan = handler.pay_recurrent(amount, currency, customer_data, tx_ref_id, subscription_name,
                                                        donation_type)
    subscription = PaymentSubscription.objects.create(
        plan_id=payment_plan,
        plan_status=PaymentPlanStatus.CREATED.value,
        plan_name=subscription_name,
    )
    return response_data, subscription


def create_transaction_history(tx_status, tx_ref_id, amount, donor, subscription, currency):
    tx_history = TransactionHistory.objects.create(
        tx_status=tx_status,
        tx_ref=tx_ref_id,
        amount=amount,
        donor=donor,
        tx_currency=currency
    )
    if subscription:
        tx_history.subscription = subscription
        tx_history.save()
    return tx_history


def handle_successful_transaction(handler, transaction):
    verified_amount = handler.verify_transaction(transaction.tr_id).get('amount')
    if verified_amount == transaction.amount:
        transaction.tx_status = TransactionStatus.SUCCESSFUL.value
    if transaction.subscription is not None:
        transaction.subscription.plan_status = PaymentPlanStatus.ACTIVE.value
        transaction.subscription.save()
    transaction.save()


def handle_failed_transaction(transaction):
    transaction.tx_status = 'failed'
    if transaction.subscription is not None:
        transaction.subscription.plan_status = 'cancelled'
        transaction.subscription.save()
    transaction.save()
