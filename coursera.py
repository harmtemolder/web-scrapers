from bs4 import BeautifulSoup
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import warnings
import yaml

# Prepare a list of URLs to scrape and a dict to hold results
base_url = 'https://www.coursera.org/learn/astro/home/week/'
urls = ['{}{}'.format(base_url, i) for i in range(5, 11)]
results = {}

# Set up the webdriver using my Firefox profile so Buster will run
options = Options()
# options.headless = True
profile_path = str(Path('firefox-profile').resolve())
profile = webdriver.FirefoxProfile()  # profile_path)
# profile.add_extension('buster_captcha_solver_for_humans-1.0.1-an+fx.xpi')
# https://addons.mozilla.org/en-US/firefox/addon/buster-captcha-solver/
# profile.set_preference(
#     'security.fileuri.strict_origin_policy', False)
# profile.set_preference('extensions.buster.currentVersion', '1.8.4')
# profile.update_preferences()
driver = webdriver.Firefox(options=options, firefox_profile=profile)
driver.install_addon(
    str(Path('buster_captcha_solver_for_humans-1.0.1-an+fx.xpi').resolve()))

# Enable `Simulate user input` for Buster
# driver.get('moz-extension://9709e690-477f-104a-affd-147d39aa4d37/src/options/index.html')

# Log in to Coursera
with open('credentials.yml', 'r') as credentials_file:
    credentials = yaml.load(credentials_file, Loader=yaml.FullLoader)['coursera']

login_url = 'https://www.coursera.org/?authMode=login'
driver.get(login_url)

try:
    submit_button = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-js=submit]')))
except TimeoutException:
    raise

username_field = driver.find_element_by_name('email')
username_field.send_keys(credentials['username'])

password_field = driver.find_element_by_name('password')
password_field.send_keys(credentials['password'])

submit_button.click()

# Use Buster to solve the captcha
captcha_frame = driver.find_element_by_css_selector(
    'iframe[src^="https://www.google.com/recaptcha/api2/bframe"]')
driver.switch_to.frame(captcha_frame)

try:
    solve_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'solver-button')))
    solve_button.click()
except TimeoutException as e:
    warnings.warn(
        'Could not solve captcha, please do it yourself ({}). Then '
        'press Enter in the Python console to continue'.format(e))
    input()

driver.switch_to.default_content()

# Render all URLs in the list and store their soups in a dict
for url in urls:
    driver.get(url)

    week_title_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'card-headline-text')))

    page_length = driver.execute_script(
        'window.scrollTo(0, document.body.scrollHeight);'
        'var lenOfPage = document.body.scrollHeight;'
        'return lenOfPage;')

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    results[url] = soup

driver.quit()

for url, soup in results.items():
    page_title = soup.title
    module_titles = soup.find_all(class_='module-title')

    pass
pass
