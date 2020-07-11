from bs4 import BeautifulSoup
import numpy as np
from pathlib import Path
import scipy.interpolate as si
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, \
    NoSuchElementException, NoAlertPresentException, UnexpectedAlertPresentException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import warnings
import yaml


def element_exists(driver, by, value):
    """
    :param driver: A selenium `webdriver` object
    :param by: A selenium `By` object
    :param value: A string to search for
    :return: True or False, whether the element exists
    """
    try:
        driver.find_element(by, value)
        return True
    except NoSuchElementException:
        return False


def alert_exists(driver):
    """
    :param driver: A selenium `webdriver` object
    :return: True or False, whether an alert exists
    """
    try:
        driver.switch_to.alert()
        return True
    except NoAlertPresentException:
        return False


def get_credentials(credentials_yaml):
    """
    :param credentials_yaml: Path to a YAML file containing credentials
    :return: Tuple of username and password
    """
    with credentials_yaml.open(mode='r') as credentials_file:
        credentials = yaml.load(
            credentials_file, Loader=yaml.FullLoader)['coursera']

    return (credentials['username'], credentials['password'])


def solve_recaptcha(driver):
    """

    :param driver: A selenium `webdriver` object
    :return: True if solved, False if not
    """
    captcha_frame = driver.find_element_by_css_selector(
        'iframe[src^="https://www.google.com/recaptcha/api2/bframe"]')
    buster_counter = 0

    while buster_counter < 10 and not element_exists(driver, By.ID, 'logout-btn'):
        # if alert_exists(driver):
        #     driver.switch_to.alert().accept()

        driver.switch_to.frame(captcha_frame)

        try:
            solve_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'solver-button')))
            time.sleep(1)
            move_mouse_to(driver, solve_button, solve_button)
            solve_button.click()
            time.sleep(20)
        except TimeoutException:
            warnings.warn('Buster\'s solve button did not appear, retrying...')
        except UnexpectedAlertPresentException:
            driver.switch_to.alert().accept()

        buster_counter += 1
        driver.switch_to.default_content()

    if element_exists(driver, By.ID, 'logout-btn'):
        return True
    return False


def move_mouse_to(driver, from_element, to_element):
    points = np.array([[0, 0], [0, 2], [2, 3], [4, 0], [6, 3], [8, 2], [8, 0]])

    x = points[:, 0]
    y = points[:, 1]

    t = range(len(points))
    ipl_t = np.linspace(0.0, len(points) - 1, 100)

    x_tup = si.splrep(t, x, k=3)
    y_tup = si.splrep(t, y, k=3)

    x_list = list(x_tup)
    xl = x.tolist()
    x_list[1] = xl + [0.0, 0.0, 0.0, 0.0]

    y_list = list(y_tup)
    yl = y.tolist()
    y_list[1] = yl + [0.0, 0.0, 0.0, 0.0]

    x_i = si.splev(ipl_t, x_list)  # x interpolate values
    y_i = si.splev(ipl_t, y_list)  # y interpolate values

    action = ActionChains(driver)

    # Move to the `from_element`
    action.move_to_element(from_element)
    action.perform()

    # Then along the generated curve
    for mouse_x, mouse_y in zip(x_i, y_i):
        action.move_by_offset(mouse_x, mouse_y)
        action.perform()

    # And finally to the `to_element`
    action.move_to_element(to_element)
    action.perform()


# Prepare a list of URLs to scrape and a dict to hold results
base_url = 'https://www.coursera.org/learn/astro/home/week/'
urls = ['{}{}'.format(base_url, i) for i in range(5, 11)]
results = {}

# Set up the webdriver with the Buster add-on
options = Options()
# options.headless = True
driver = webdriver.Firefox(options=options)
driver.install_addon(
    str(Path('buster_captcha_solver_for_humans-1.0.1-an+fx.xpi').resolve()))

# Log in to Coursera
(username, password) = get_credentials(Path('credentials.yml').resolve())
driver.get('https://www.coursera.org/?authMode=login')

try:
    submit_button = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-js=submit]')))
except TimeoutException:
    raise

driver.find_element_by_name('email').send_keys(username)
driver.find_element_by_name('password').send_keys(password)
submit_button.click()

# Use Buster to solve the captcha
solve_recaptcha(driver)
input('Press [Enter] when the captcha has been solved and you are logged in')

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
