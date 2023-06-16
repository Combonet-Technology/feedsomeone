from selenium import webdriver

browser = webdriver.Firefox()
browser.get('http://localhost:8000')
assert 'FEEDSOMEONE | eradicating hunger and poverty' in browser.title
