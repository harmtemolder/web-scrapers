from bs4 import BeautifulSoup, NavigableString
import json
from pathlib import Path
import random
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, \
    NoSuchElementException, UnexpectedAlertPresentException, \
    NoAlertPresentException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tenacity import retry, retry_if_exception_type, stop_after_attempt
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


def get_credentials(credentials_yaml):
    """
    :param credentials_yaml: Path to a YAML file containing credentials
    :return: Tuple of username and password
    """
    with credentials_yaml.open(mode='r') as credentials_file:
        credentials = yaml.load(
            credentials_file, Loader=yaml.FullLoader)['coursera']

    return (credentials['username'], credentials['password'])


def alert_exists(driver):
    try:
        driver.switch_to.alert
        return True
    except NoAlertPresentException:
        return False


@retry(retry=retry_if_exception_type((
    TimeoutException,
    UnexpectedAlertPresentException,
    NoSuchElementException,
    StaleElementReferenceException)), stop=stop_after_attempt(5))
def solve_recaptcha(driver):
    """

    :param driver: A selenium `webdriver` object
    :return: True if solved, False if not
    """

    # Switch to the recaptcha iframe
    driver.switch_to.default_content()
    captcha_frame = driver.find_element_by_css_selector(
        'iframe[src^="https://www.google.com/recaptcha/api2/bframe"]')
    driver.switch_to.frame(captcha_frame)

    # Click the audio button
    if element_exists(driver, By.ID, 'recaptcha-audio-button'):
        audio_button = driver.find_element_by_id('recaptcha-audio-button')
        long_click(driver, audio_button)
        time.sleep(5)

    try:
        # Wait for the solve button and click it
        solve_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'solver-button')))
        time.sleep(1)
        long_click(driver, solve_button)
        time.sleep(20)

        # Accept the alert that might pop up
        if alert_exists(driver):
            driver.switch_to.alert.accept()
    except TimeoutException:
        warnings.warn('Buster\'s solve button did not appear, retrying...')
        raise
    except UnexpectedAlertPresentException:
        warnings.warn(
            'Some alert popped up, accepting that and retrying...')
        driver.switch_to.alert.accept()
        raise

    if not element_exists(driver, By.ID, 'logout-btn'):
        raise NoSuchElementException
    return True

def long_click(driver, element):
    """Clicks an `element` for a random amount of time

    :param driver:
    :param element:
    :return:
    """
    delay = random.randrange(100, 1000) / 1000.0

    action = ActionChains(driver)
    action.click_and_hold(element)
    action.perform()
    time.sleep(delay)
    action.release(element)
    action.perform()

@retry(stop=stop_after_attempt(5))
def get_soup(driver, url):
    """

    :param driver:
    :param url:
    :return:
    """
    try:
        driver.get(url)

        week_title_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'card-headline-text')))

        time.sleep(3)

        page_length = driver.execute_script(
            'window.scrollTo(0, document.body.scrollHeight);'
            'var lenOfPage = document.body.scrollHeight;'
            'return lenOfPage;')

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        return soup
    except Exception:
        pass
        raise


def scrape_contents(soup):
    """

    :param soup:
    :return dict: The contents of the soup that I want
    """
    module_section = soup.find(class_='rc-ModuleSection')

    contents = {
        'module_title': module_section.find(
            name='h3', class_='card-headline-text').text,
        'module_sections':[]}

    sections = module_section.find_all(class_='rc-NamedItemList')

    for section in sections:
        section_contents = {
            'section_title': list.find(class_='card-headline-text').text,
            'section_lessons': []
        }

        lessons = section.find_all(class_='rc-WeekItemName')
        for lesson in lessons:
            for part in lesson.contents:
                if isinstance(part, NavigableString):
                    section_contents['section_lessons'].append(str(part))
                    break

        contents['module_sections'].append(section_contents)

    return contents

if __name__ == '__main__':
    driver = None
    buster_id = None
    module_contents = {}

    try:
        # Prepare a list of URLs to scrape and a dict to hold results
        base_url = 'https://www.coursera.org/learn/astro/home/week/'
        urls = ['{}{}'.format(base_url, i) for i in range(5, 12)]
        results = {}

        # Set up the webdriver with the Buster add-on
        options = Options()
        # options.headless = True
        # profile_path = str(Path('~/Library/Application Support/Firefox/Profiles'
        #                         '/ghacks-user.js').expanduser())
        profile_path = str(Path('firefox-profile').resolve())
        profile = webdriver.FirefoxProfile(profile_path)
        driver = webdriver.Firefox(options=options, firefox_profile=profile)
        buster_id = driver.install_addon(
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
        # try:
        #     WebDriverWait(driver, 10).until(
        #         EC.presence_of_element_located((
        #             By.CSS_SELECTOR,
        #             'iframe[src^="https://www.google.com/recaptcha/api2/bframe"]')))
        # except TimeoutException:
        #     warnings.warn('Could not find ReCAPTCHA, skipping...')
        # else:
        #     solve_recaptcha(driver)

        input('Press [Enter] when the captcha has been solved and you are logged in')

        # Render all URLs in the list and store their soups in a dict
        for url in urls:
            results[url] = get_soup(driver, url)

        # Since Buster doesn't seem to like quiting, uninstall it first
        driver.uninstall_addon(buster_id)
        driver.quit()

        for url, soup in results.items():
            contents_as_dict = scrape_contents(soup)
            module_contents[url] = contents_as_dict

            pass

        json_path = Path('module_contents.json').resolve()
        with json_path.open(mode='w') as output_json:
            json.dump(output_json, module_contents)

        pass

    except Exception:
        if driver is not None:
            driver.quit()
        if buster_id is not None:
            # Uninstall Buster so it can be installed freshly on the next run
            driver.uninstall_addon(buster_id)
