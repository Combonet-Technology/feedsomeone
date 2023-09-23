# from unittest.mock import Mock, patch
#
# from django.test import TestCase
# from django.urls import reverse
#
# from .models import Donor, TransactionHistory, UserProfile
# from .utils import handle_successful_transaction
#
#
# class DonateTestCase(TestCase):
#     def setUp(self):
#         self.user = UserProfile.objects.create_user(username='testuser', password='testpassword',
#                                                     email='test@example.com')
#         self.donor = Donor.objects.create(user=self.user)
#         self.handler = Mock()
#         self.handler.pay_once.return_value = {'data': {'link': 'test_link'}}
#         self.handler.pay_recurrent.return_value = {'data': {'link': 'test_link'}}
#         self.handler.verify_transaction.return_value = {'amount': 100}
#         self.patcher = patch('mainsite.views.RavePaymentHandler', return_value=self.handler)
#         self.patcher.start()
#
#     def test_donate_one_time(self):
#         response = self.client.post(reverse('mainsite:donate'), {
#             'amount': 100,
#             'currency': 'USD',
#             'full_name': 'Test User',
#             'email': 'test@example.com',
#             'donation_type': 'one_time',
#         })
#         print(response.__dict__)
#         # self.assertEqual(response.status_code, 302)  # Redirect
#         # self.assertRedirects(response, 'test_link')
#
#         transaction = TransactionHistory.objects.get(donor=self.donor)
#         self.assertEqual(transaction.tx_status, 'pending')
#         self.assertIsNone(transaction.subscription)  # Fix: Subscription should be None
#         self.handler.pay_once.assert_called_once_with(100, 'USD',
#                                                       {'full_name': 'Test User', 'email': 'test@example.com'},
#                                                       transaction.tx_ref)
#
#     @patch('mainsite.views.messages')
#     def test_one_time_donation_successful(self, mock_messages):
#         transaction = TransactionHistory.objects.create(
#             tx_ref='test_tx_ref',
#             amount=100,
#             donor=self.donor,
#             tx_status='pending'
#         )
#
#         response = self.client.get(reverse('mainsite:donate'), {
#             'status': 'successful',
#             'tx_ref': 'test_tx_ref',
#             'transaction_id': 'test_tr_id',
#         })
#         self.assertEqual(response.status_code, 200)  # Rendered thanks-donation.html
#
#         transaction.refresh_from_db()
#         self.assertEqual(transaction.tx_status, 'successful')
#         self.handler.verify_transaction.assert_called_once_with('test_tr_id')
#         mock_messages.info.assert_not_called()  # Fix: Should not be called for successful transaction
#
#     @patch('mainsite.views.messages')
#     def test_one_time_donation_failed(self, mock_messages):
#         transaction = TransactionHistory.objects.create(
#             tx_ref='test_tx_ref',
#             amount=100,
#             donor=self.donor,
#             tx_status='pending'
#         )
#
#         response = self.client.get(reverse('mainsite:donate'), {
#             'status': 'failed',
#             'tx_ref': 'test_tx_ref',
#             'transaction_id': 'test_tr_id',
#         })
#         self.assertEqual(response.status_code, 302)  # Redirect
#         self.assertRedirects(response, reverse('mainsite:donate'))
#
#         transaction.refresh_from_db()
#         self.assertEqual(transaction.tx_status, 'failed')
#         self.assertEqual(transaction.subscription.plan_status, 'cancelled')
#         self.handler.verify_transaction.assert_not_called()  # Fix: Should not be called for failed transaction
#         mock_messages.info.assert_called_once_with('PAYMENT UNSUCCESSFUL AND REVERSED')
#
#     # def test_donate_invalid_payment_type(self):
#     #     response = self.client.post(reverse('mainsite:donate'), {
#     #         'amount': 100,
#     #         'currency': 'USD',
#     #         'full_name': 'Test User',
#     #         'email': 'test@example.com',
#     #         'donation_type': 'invalid_type',
#     #     })
#     #     self.assertEqual(response.status_code, 200)  # Rendered donate-draft.html
#     #     self.assertIn(b'Invalid payment type', response.content)
#     #
#     # # Add more test cases as needed for different scenarios
#     #
#     # def test_donate_post_monthly(self):
#     #     response = self.client.post(reverse('mainsite:donate'), {
#     #         'amount': 100,
#     #         'currency': 'USD',
#     #         'full_name': 'Test User',
#     #         'email': 'test@example.com',
#     #         'donation_type': 'monthly',
#     #     })
#     #     self.assertEqual(response.status_code, 302)  # Redirect
#     #     self.assertRedirects(response, 'test_link')
#     #
#     #     transaction = TransactionHistory.objects.get(donor=self.donor)
#     #     self.assertEqual(transaction.tx_status, 'pending')
#     #     self.assertEqual(transaction.subscription.plan_status, 'created')
#     #     self.handler.pay_recurrent.assert_called_once_with(
#     #         100, 'USD', {'full_name': 'Test User', 'email': 'test@example.com'},
#     #         transaction.tx_ref, 'Test User', 'monthly'
#     #     )
#     #
#     #
#     def test_donate_get(self):
#         response = self.client.get(reverse('mainsite:donate'))
#         self.assertEqual(response.status_code, 200)
#
#     #
#     # def test_handle_successful_transaction_verified_amount_mismatch(self):
#     #     transaction = TransactionHistory.objects.create(
#     #         tx_ref='test_tx_ref',
#     #         amount=100,
#     #         donor=self.donor,
#     #         tx_status='pending',
#     #         subscription=self.subscription
#     #     )
#     #     self.handler.verify_transaction.return_value = {'amount': 50}
#     #
#     #     with self.assertRaises(AssertionError):
#     #         handle_successful_transaction(self.handler, transaction)
#     #
#     # def test_handle_successful_transaction_subscription_not_none(self):
#     #     transaction = TransactionHistory.objects.create(
#     #         tx_ref='test_tx_ref',
#     #         amount=100,
#     #         donor=self.donor,
#     #         tx_status='pending',
#     #         subscription=self.subscription
#     #     )
#     #     self.handler.verify_transaction.return_value = {'amount': 100}
#     #
#     #     handle_successful_transaction(self.handler, transaction)
#     #     transaction.refresh_from_db()
#     #     self.assertEqual(transaction.tx_status, 'successful')
#     #     self.assertEqual(transaction.subscription.plan_status, 'active')
#     #
#     # def test_handle_successful_transaction_subscription_none(self):
#     #     transaction = TransactionHistory.objects.create(
#     #         tx_ref='test_tx_ref',
#     #         amount=100,
#     #         donor=self.donor,
#     #         tx_status='pending',
#     #     )
#     #     self.handler.verify_transaction.return_value = {'amount': 100}
#     #
#     #     handle_successful_transaction(self.handler, transaction)
#     #     transaction.refresh_from_db()
#     #     self.assertEqual(transaction.tx_status, 'successful')
#     #     self.assertIsNone(transaction.subscription)
#
#     def tearDown(self):
#         self.patcher.stop()
