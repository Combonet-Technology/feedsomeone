import unittest

from selenium import webdriver


class NewVisitorTest(unittest.TestCase):

    def setUp(self) -> None:
        self.host = 'http://localhost:8000'
        super().setUp()
        self.browser = webdriver.Firefox()

    def tearDown(self) -> None:
        super().tearDown()
        self.browser.quit()

    def test_view_homepage_details(self):
        # user opens the website via a browser or social media or google link
        self.browser.get(self.host)
        self.assertIn('FEEDSOMEONE | eradicating hunger and poverty', self.browser.title)
        # self.fail('Incomplete test...')


if __name__ == '__main__':
    unittest.main(warnings='ignore')
