import unittest

import requests
from selenium import webdriver
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By


class HomePageTest(unittest.TestCase):
    def setUp(self):
        self.title_text = 'FEEDSOMEONE | eradicating hunger and poverty'
        self.host = 'http://localhost:8000'
        self.google_tag = '//script[@src="https://www.googletagmanager.com/gtag/js?id=G-SN22VH6DM1"]'
        super().setUp()
        self.browser = webdriver.Firefox()

    def tearDown(self):
        super().tearDown()
        self.browser.quit()

    def test_open_website(self):
        self.browser.get(self.host)
        self.assertIn(self.title_text, self.browser.title)

    def test_google_tag_exists(self):
        self.browser.get(self.host)
        google_tag = self.browser.find_element(By.XPATH, self.google_tag)
        self.assertIsNotNone(google_tag)

    def test_valid_links(self):
        self.browser.get(self.host)
        links = self.browser.find_elements(By.TAG_NAME, 'a')
        li_count = 0
        for link in links:
            url = link.get_attribute('href')
            pare = link.find_element(By.XPATH, './..')
            if pare.tag_name == 'li':
                li_count += 1
            if url:
                self.assertIsNotNone(url)
                if url.startswith('http'):
                    try:
                        response = requests.head(url)
                        self.assertIn(response.status_code, [200, 301, 999, 404])
                    except requests.exceptions.ConnectionError:
                        print("Can't connect to external URL")
                    # print(f'text: {link.text} url: {url} parent tag: {pare.tag_name} parent value: {pare.text}')
        print(f'Tested {li_count} links in total')

    def test_hero_caption_text(self):
        self.browser.get(self.host)
        h1_element = self.browser.find_element(By.CSS_SELECTOR, '.hero__caption h1')
        self.assertEqual(h1_element.get_attribute('innerHTML'), 'Save Many<br>Feed Someone')

    def test_newsletter_form(self):
        self.browser.get(self.host)
        newsletter = self.browser.find_element(By.ID, 'subscribenow')
        self.assertEqual(newsletter.get_attribute('action'), f'{self.host}/contact/subscribe/')
        self.assertEqual(newsletter.get_attribute('method'), 'post')
        self.assertEqual(newsletter.get_attribute('target'), '_blank')

        children = newsletter.find_elements(By.XPATH, '*')
        csrf, input_box, submit = children

        self.assertEqual(input_box.get_attribute('placeholder'), 'Enter your email')
        self.assertEqual(input_box.get_attribute('type'), 'email')
        self.assertEqual(input_box.get_attribute('name'), 'email')

        self.assertEqual(csrf.get_attribute('type'), 'hidden')
        self.assertEqual(csrf.get_attribute('name'), 'csrfmiddlewaretoken')

        self.assertEqual(submit.get_attribute('class'), 'primary-button')
        self.assertEqual(submit.text, 'Subscribe')

    def test_submit_newsletter_form(self):
        self.browser.get(self.host)
        newsletter = self.browser.find_element(By.ID, 'subscribenow')
        input_box = newsletter.find_element(By.XPATH, './/input[@name="email"]')
        input_box.send_keys(Keys.ENTER)

        # Switch to the new tab
        self.browser.switch_to.window(self.browser.window_handles[1])

        # Add assertions or checks for the form response page
        response_page_title = self.browser.title
        expected_title = 'Thank You for Subscribing'
        self.assertEqual(response_page_title, expected_title)

        # Switch back to the original tab
        self.browser.switch_to.window(self.browser.window_handles[0])


if __name__ == '__main__':
    unittest.main(warnings='ignore')
