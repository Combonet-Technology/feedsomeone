from unittest.mock import Mock, patch

from django.contrib.auth.models import User
# from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from .models import Donor, TransactionHistory, UserProfile
from .utils import handle_successful_transaction

# from .views import donate, handle_donation_get, handle_donation_post


class DonateTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.user_profile = UserProfile.objects.create(user=self.user, email='test@example.com')
        self.donor = Donor.objects.create(user=self.user_profile)
        self.handler = Mock()
        self.handler.pay_once.return_value = {'data': {'link': 'test_link'}}
        self.handler.pay_recurrent.return_value = {'data': {'link': 'test_link'}}
        self.handler.verify_transaction.return_value = {'amount': 100}

    def test_donate_post_one_time(self):
        response = self.client.post(reverse('donate'), {
            'amount': 100,
            'currency': 'USD',
            'full_name': 'Test User',
            'email': 'test@example.com',
            'donation_type': 'one_time',
        })
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertRedirects(response, 'test_link')

        transaction = TransactionHistory.objects.get(donor=self.donor)
        self.assertEqual(transaction.tx_status, 'pending')
        self.assertIsNone(transaction.subscription)  # Fix: Subscription should be None
        self.handler.pay_once.assert_called_once_with(100, 'USD',
                                                      {'full_name': 'Test User', 'email': 'test@example.com'},
                                                      transaction.tx_ref)

    @patch('mainsite.views.messages')
    def test_donate_get_successful(self, mock_messages):
        transaction = TransactionHistory.objects.create(
            tx_ref='test_tx_ref',
            amount=100,
            donor=self.donor,
            tx_status='pending'
        )

        response = self.client.get(reverse('donate'), {
            'status': 'successful',
            'tx_ref': 'test_tx_ref',
            'transaction_id': 'test_tr_id',
        })
        self.assertEqual(response.status_code, 200)  # Rendered thanks-donation.html

        transaction.refresh_from_db()
        self.assertEqual(transaction.tx_status, 'successful')
        self.handler.verify_transaction.assert_called_once_with('test_tr_id')
        mock_messages.info.assert_not_called()  # Fix: Should not be called for successful transaction

    @patch('mainsite.views.messages')
    def test_donate_get_failed(self, mock_messages):
        transaction = TransactionHistory.objects.create(
            tx_ref='test_tx_ref',
            amount=100,
            donor=self.donor,
            tx_status='pending'
        )

        response = self.client.get(reverse('donate'), {
            'status': 'failed',
            'tx_ref': 'test_tx_ref',
            'transaction_id': 'test_tr_id',
        })
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertRedirects(response, reverse('donate'))

        transaction.refresh_from_db()
        self.assertEqual(transaction.tx_status, 'failed')
        self.assertEqual(transaction.subscription.plan_status, 'cancelled')
        self.handler.verify_transaction.assert_not_called()  # Fix: Should not be called for failed transaction
        mock_messages.info.assert_called_once_with('PAYMENT UNSUCCESSFUL AND REVERSED')

    def test_donate_invalid_payment_type(self):
        response = self.client.post(reverse('donate'), {
            'amount': 100,
            'currency': 'USD',
            'full_name': 'Test User',
            'email': 'test@example.com',
            'donation_type': 'invalid_type',
        })
        self.assertEqual(response.status_code, 200)  # Rendered donate-draft.html
        self.assertIn(b'Invalid payment type', response.content)

    # Add more test cases as needed for different scenarios

    def test_donate_get(self):
        response = self.client.get(reverse('donate'))
        self.assertEqual(response.status_code, 200)  # Rendered donate-draft.html

    # Add more test cases as needed for GET scenarios

    def test_donate_total_transaction(self):
        response = self.client.get(reverse('donate'))
        self.assertEqual(response.status_code, 200)  # Rendered donate-draft.html
        self.assertEqual(response.context['total_transaction'], 0)

    # Add more test cases as needed for context data

    # Add more test cases for handle_donation_post, handle_donation_get, and related functions

    def test_donate_post_monthly(self):
        response = self.client.post(reverse('donate'), {
            'amount': 100,
            'currency': 'USD',
            'full_name': 'Test User',
            'email': 'test@example.com',
            'donation_type': 'monthly',
        })
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertRedirects(response, 'test_link')

        transaction = TransactionHistory.objects.get(donor=self.donor)
        self.assertEqual(transaction.tx_status, 'pending')
        self.assertEqual(transaction.subscription.plan_status, 'created')
        self.handler.pay_recurrent.assert_called_once_with(
            100, 'USD', {'full_name': 'Test User', 'email': 'test@example.com'},
            transaction.tx_ref, 'Test User', 'monthly'
        )

    def test_donate_get_invalid_status(self):
        response = self.client.get(reverse('donate'), {
            'status': 'invalid_status',
            'tx_ref': 'test_tx_ref',
            'transaction_id': 'test_tr_id',
        })
        self.assertEqual(response.status_code, 200)  # Rendered donate-draft.html

    def test_donate_get_no_query_params(self):
        response = self.client.get(reverse('donate'))
        self.assertEqual(response.status_code, 200)  # Rendered donate-draft.html

    def test_handle_successful_transaction_verified_amount_mismatch(self):
        transaction = TransactionHistory.objects.create(
            tx_ref='test_tx_ref',
            amount=100,
            donor=self.donor,
            tx_status='pending',
            subscription=self.subscription
        )
        self.handler.verify_transaction.return_value = {'amount': 50}

        with self.assertRaises(AssertionError):
            handle_successful_transaction(self.handler, transaction)

    def test_handle_successful_transaction_subscription_not_none(self):
        transaction = TransactionHistory.objects.create(
            tx_ref='test_tx_ref',
            amount=100,
            donor=self.donor,
            tx_status='pending',
            subscription=self.subscription
        )
        self.handler.verify_transaction.return_value = {'amount': 100}

        handle_successful_transaction(self.handler, transaction)
        transaction.refresh_from_db()
        self.assertEqual(transaction.tx_status, 'successful')
        self.assertEqual(transaction.subscription.plan_status, 'active')

    def test_handle_successful_transaction_subscription_none(self):
        transaction = TransactionHistory.objects.create(
            tx_ref='test_tx_ref',
            amount=100,
            donor=self.donor,
            tx_status='pending',
        )
        self.handler.verify_transaction.return_value = {'amount': 100}

        handle_successful_transaction(self.handler, transaction)
        transaction.refresh_from_db()
        self.assertEqual(transaction.tx_status, 'successful')
        self.assertIsNone(transaction.subscription)
