import operator

from bs4 import BeautifulSoup, NavigableString
import json
import logging
from pathlib import Path
import pickle
import random
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, \
    NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import sys
from tenacity import retry, retry_if_exception_type, stop_after_attempt, \
    wait_exponential
import time
import yaml


class CourseraScraper:
    def __init__(self, profile_path, username, password):
        self.profile_path = profile_path
        self.username = username
        self.password = password

        self.addon_ids = {}
        self.driver = None

    def __enter__(self):
        self.create_driver()
        self.install_buster()
        self.login()

        return self

    def __exit__(self, e_type, e_value, e_traceback):
        if e_traceback is not None:  # i.e. if Exception
            pass

        self.driver.uninstall_addon(self.addon_ids['buster'])
        self.driver.quit()

    def create_driver(self):
        options = Options()
        profile = webdriver.FirefoxProfile(self.profile_path)
        self.driver = webdriver.Firefox(
            options=options,
            firefox_profile=profile)

    def install_buster(self):
        self.addon_ids['buster'] = self.driver.install_addon(str(
            Path('buster_captcha_solver_for_humans-1.0.1-an+fx.xpi').resolve()))
        self.driver.get('about:addons')
        input('Installed Buster. Go to `about:addons` and dis- and enable it '
              'for it to work correctly. Then press [Enter] here')

    def login(self):
        # Load the login page
        login_url = 'https://www.coursera.org/?authMode=login'
        self.driver.get(login_url)

        # Wait max 10 s for the submit button to appear, then login
        submit_button = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-js=submit]')))

        self.driver.find_element_by_name('email').send_keys(self.username)
        self.driver.find_element_by_name('password').send_keys(self.password)
        submit_button.click()

        # Try to solve the ReCAPTCHA with the Buster add-on
        try:
            self.solve_recaptcha()
        except Exception:
            logging.warning('Could not solve ReCAPTCHA automatically, ple'
                          'ase do so manually')

        # Ask the user to confirm that he is logged in
        input('Press [Enter] when the captcha has been solved and you a'
              're logged in')

    def element_exists(self, by, value):
        """
        :param by: A selenium `By` object
        :param value: A string to search for
        :return: True or False, whether the element exists
        """
        try:
            self.driver.find_element(by, value)
            return True
        except NoSuchElementException:
            return False

    def long_click(self, element):
        """Clicks an `element` for a random amount of time

        :param element:
        :return:
        """
        delay = random.randrange(100, 1000) / 1000.0

        action = ActionChains(self.driver)
        action.click_and_hold(element)
        action.perform()
        time.sleep(delay)
        action.release(element)
        action.perform()

    @retry(
        retry=retry_if_exception_type((NoSuchElementException)),
        wait=wait_exponential(),
        stop=stop_after_attempt(5))
    def solve_recaptcha(self):
        # Make sure driver is on the main page
        self.driver.switch_to.default_content()

        try:
            # Switch to the ReCAPTCHA iframe
            captcha_frame = self.driver.find_element_by_css_selector(
                'iframe[src^="https://www.google.com/recaptcha/api2/bframe"]')
            self.driver.switch_to.frame(captcha_frame)

            # Click the audio button
            if self.element_exists(By.ID, 'recaptcha-audio-button'):
                audio_button = self.driver.find_element_by_id(
                    'recaptcha-audio-button')
                self.long_click(audio_button)
                time.sleep(3)

            # Wait for the solve button and click it
            solve_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, 'solver-button')))

            time.sleep(1)
            self.long_click(solve_button)
            time.sleep(30)
        except Exception:
            raise
        finally:
            # Switch back to the main page
            self.driver.switch_to.default_content()

        # Check if logged in, otherwise raise (and retry)
        if not self.element_exists(By.ID, 'logout-btn'):
            raise NoSuchElementException
        return True

    @retry(
        retry=retry_if_exception_type((TimeoutException)),
        wait=wait_exponential(),
        stop=stop_after_attempt(10))
    def get_soup(self, url):
        """Get the entire soup of the module section for a given URL

        :param url:
        :return:
        """
        self.driver.get(url)

        # Wait max 10 s for the content to appear
        card_headline_text = WebDriverWait(self.driver, 30).until(
            EC.presence_of_element_located(
                (By.CLASS_NAME, 'card-headline-text')))

        # And wait some more
        time.sleep(3)

        # Scroll the entire page
        page_length = self.driver.execute_script(
            'window.scrollTo(0, document.body.scrollHeight);'
            'var lenOfPage = document.body.scrollHeight;'
            'return lenOfPage;')

        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        module_section = soup.find(class_='rc-ModuleSection')

        return module_section


class CourseraParser:
    def __init__(self, soup):
        self.soup = soup
        self.contents = {}

    def parse(self):
        contents = {
            'module_title': self.soup.find(
                name='h3',
                class_='card-headline-text').text,
            'module_sections':[]}

        sections = self.soup.find_all(class_='rc-NamedItemList')

        for section in sections:
            section_contents = {
                'section_title': section.find(
                    class_='card-headline-text').text,
                'section_lessons': []}

            lessons = section.find_all(class_='rc-WeekItemName')

            for lesson in lessons:
                for part in lesson.contents:
                    if type(part) == NavigableString:
                        section_contents['section_lessons'].append(str(part))
                        break

            contents['module_sections'].append(section_contents)

        self.contents = contents
        return self.contents


def generate_urls(base_url, from_week, to_week):
    """Prepare a list of URLs of modules for the given weeks

    :param base_url str: The absolute URL preceding week numbers
    :param from_week int: Start counting from, inclusive
    :param to_week int: Stop counting at, inclusive
    :return list: URLs for the requested weeks
    """
    urls = ['{}{}'.format(base_url, i) for i in range(from_week, to_week + 1)]
    return urls


def get_credentials(credentials_yaml):
    """
    :param credentials_yaml: Path to a YAML file containing credentials
    :return: Tuple of username and password
    """
    with credentials_yaml.open(mode='r') as credentials_file:
        credentials = yaml.load(
            credentials_file, Loader=yaml.FullLoader)['coursera']

    return (credentials['username'], credentials['password'])

@retry(
    retry=retry_if_exception_type((RecursionError)),
    stop=stop_after_attempt(3)
)
def dump_to_pickle(pickle_path):
    with pickle_path.open(mode='wb') as pkl:
        try:
            pickle.dump(soups, pkl)
        except RecursionError:
            # Soups can go pretty deep, so try again with a higher limit
            sys.setrecursionlimit(sys.getrecursionlimit() * 10)
            raise


if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    # logging.basicConfig(level=logging.DEBUG)

    soups_pkl = Path('20200713-coursera-astro.pkl')
    result = {}

    # Generate URLs of pages to scrape
    urls = generate_urls(
        'https://www.coursera.org/learn/astro/home/week/',
        from_week=5, to_week=11)
    logging.info('Generated URLs to scrape')
    logging.debug('\t{}'.format('\n\t'.join(urls)))

    # Load an existing scrape or, if there is none, start a new one
    if soups_pkl.is_file():
        with soups_pkl.open(mode='rb') as pkl:
            try:
                soups = pickle.load(pkl)
                logging.info('Read `soups` from Pickle')
            except EOFError:
                soups = {}
                logging.warning('`soups` was an empty file, starting with an '
                                'empty dict')
    else:
        logging.info('`{}` does not exist, starting with an empty '
                     'dict'.format(soups_pkl))
        soups = {}

    # Only keep URLs that are not scraped yet
    urls = list(set(urls).difference(set(soups.keys())))

    if len(urls) > 0:
        logging.info('After checking for already scraped URLs, {} are '
                     'left'.format(len(urls)))
        logging.debug('\t{}'.format('\n\t'.join(urls)))

        (username, password) = get_credentials(
            Path('credentials.yml').resolve())

        try:
            with CourseraScraper(
                    profile_path=str(Path('firefox-profile').resolve()),
                    username=username,
                    password=password
            ) as scraper:
                for url in urls:
                    logging.info('Scraping `{}`'.format(url))
                    soups[url] = scraper.get_soup(url)
        except Exception as e:
            logging.exception(e)
            raise
        finally:
            # Save on both success and error
            logging.info('Saving scraped soups to `{}`'.format(soups_pkl))
            dump_to_pickle(soups_pkl)
    else:
        logging.info('After checking for already scraped URLs, none are '
                     'left')

    # Sort the soups by week number in the URL, descendingly
    soups = dict(sorted(
        soups.items(),
        key=lambda item: int(item[0].split('/')[-1]),
        reverse=True))

    # Parse the soups into meaningful content
    for url, soup in soups.items():
        logging.info('Parsing the soup for `{}`'.format(url))
        parser = CourseraParser(soup)
        module_contents = parser.parse()
        logging.debug('This is the result:\n{}'.format(
            json.dumps(module_contents)))
        result[url] = module_contents

    # Print the result to console for pasting in WorkFlowy
    logging.info('Printing the result as a list for pasting in WorkFlowy')
    for url, module in result.items():
        print('- {}. {}'.format(
            url.split('/')[-1],
            module['module_title']))

        for section in module['module_sections']:
            print('\t- {}'.format(section['section_title']))

            for lesson in section['section_lessons']:
                print('\t\t- {}'.format(lesson))
