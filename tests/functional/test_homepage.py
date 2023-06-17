import unittest

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By


class NewVisitorTest(unittest.TestCase):

    def setUp(self) -> None:
        self.title_text = 'FEEDSOMEONE | eradicating hunger and poverty'
        self.host = 'http://localhost:8000'
        self.google_tag = '//script[@src="https://www.googletagmanager.com/gtag/js?id=G-SN22VH6DM1"]'
        super().setUp()
        self.browser = webdriver.Firefox()

    def tearDown(self) -> None:
        super().tearDown()
        self.browser.quit()

    def test_view_homepage_details(self):
        # user opens the website via a browser or social media or google link
        self.browser.get(self.host)
        self.assertIn(self.title_text, self.browser.title)

        # check if there is google tag in header
        google_tag = self.browser.find_element(By.XPATH, self.google_tag)
        self.assertIsNotNone(google_tag)

        # check if all the links are returning 200
        links = self.browser.find_elements(By.TAG_NAME, 'a')
        for link in links:
            url = link.get_attribute('href')
            print(link.text)
            if url.startswith('http'):
                print(url)
                response = requests.head(url)
                self.assertIn(response.status_code, [200, 301, 999])

        # check if the h1 under hero__caption class contains "Save Many<br>Feed Someone"
        h1_element = self.browser.find_element(By.CSS_SELECTOR, '.hero__caption h1')
        self.assertEqual(h1_element.get_attribute('innerHTML'), 'Save Many<br>Feed Someone')


if __name__ == '__main__':
    unittest.main(warnings='ignore')
