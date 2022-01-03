import requests
import json
import sys
import time
import random
import threading
import os
import tempfile
import locale
from selenium import webdriver
from selenium.common.exceptions import *
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from urllib3.exceptions import MaxRetryError, NewConnectionError


checkout_info = {
    'EMAIL': "",
    'FIRST_NAME': "",
    'LAST_NAME': "",
    'ADDRESS': "",
    'COUNTRY': "",
    'CITY': "",
    'POSTCODE': "",
    'STATE': "",
    'MOBILE': "",
    'CREDITCNUMBER': "",
    'CREDITCNAME': "",
    'CREDITCEXPIRY': "",      #ONLY NUMBERS
    'CREDITCSECCODE': ""
}

webdriver_path = r''               #ENTER PATH

def get_driver(headless=True, captcha_driver=False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument('--headless')
        options.add_argument('--start-maximized')
        options.add_argument('--log-level=3')
        options.add_argument("--no-sandbox")
    if captcha_driver:
        options.add_argument("--window-size=500,600")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-gpu')

    language = False
    try:
        language = locale.getdefaultlocale()[0].replace("_", "-")
        print(language)
    except Exception:
        pass
    if not language:
        language = "en-US"

    options.add_argument("--lang=%s" % language)
    user_data_dir = os.path.normpath(tempfile.mkdtemp())
    arg = "--user-data-dir=%s" % user_data_dir
    options.add_argument(arg)
    options.add_argument("profile-directory=Default")
    options.add_experimental_option('detach', True)

    return webdriver.Chrome(executable_path=webdriver_path, options=options)



def get_wait_time():
    with open('wait_time.txt', 'r') as file:
        text: str = file.read()

    try:
        return float(text)
    except:
        return 5


def rand_wait():
    return random.randint(0, 1)


def check_exists_by_class_name(class_name, driver):
    try:
        driver.find_element_by_class_name(class_name)
    except NoSuchElementException:
        return False
    return True


def check_exists_by_xpath(xpath, driver):
    try:
        driver.find_element_by_xpath(xpath)
    except NoSuchElementException:
        return False
    return True


def check_text(class_name, driver, text):
    try:
        button_text = driver.find_element_by_class_name(class_name).text
        if button_text.find(text) != -1:
            return True
    except:
        return False
    return False


def shopify_error_handler(driver):
    if check_exists_by_class_name('status-error.status-code-500', driver):
        return 'error'


class ShopB0t:

    def __init__(self, shop_site, item_keywords):
        self.shop_site = shop_site
        self.item_keywords = item_keywords.split(';')
        self.id_list = []
        self.inputted_domain = None                             
        self.pause_after_pre_checkout = False                    
        self.pre_load_cookies = False                            
        self.headless = False                                   

    def site_error_handler(self, driver):
        if check_exists_by_class_name('contains("template-404")', driver):
            return 'error'

    def wait_captcha(self, driver, hcaptcha, string):
        if hcaptcha:
            element = driver.find_element_by_class_name('h-captcha')
        else:
            element = driver.find_element_by_class_name('g-recaptcha')
        actions = ActionChains(driver)
        actions.move_to_element(element).perform()
        while True:
            if driver.find_element_by_xpath(string).get_attribute('value') != '':
                token = driver.find_element_by_xpath(string).get_attribute('value')
                driver.quit()
                return token
            time.sleep(1.5)

    def wait_captcha_2(self, driver, hcaptcha):
        if hcaptcha:
            element = driver.find_element_by_class_name('h-captcha')
            find_string = '//*[contains(@id, "h-captcha-response")]'
        else:
            element = driver.find_element_by_class_name('g-recaptcha')
            find_string = '//*[contains(@id, "g-recaptcha-response")]'
        actions = ActionChains(driver)
        actions.move_to_element(element).perform()
        while True:
            if driver.find_element_by_xpath(find_string).get_attribute('value')!= '':
                time.sleep(1.5)
            else:
                return

    def force_captcha(self, driver):
        driver.get(self.shop_site + '/checkpoint')
        try:
            WebDriverWait(driver, 4).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'g-recaptcha'))
            )
            self.new_captcha_solve(driver, checkpoint=True)
            print('Force captcha success.... Proceeding to pre-checkout')
        except TimeoutException:
            print('Force captcha failed.... Proceeding to pre-checkout')
        time.sleep(4)

    def stock_wait(self, shop_site, driver):
        get_one = shop_site + '/cart/checkout'
        get_two = shop_site + '/throttle/queue'
        counter = get_two
        while True:
            print('reloading -- stock problems')
            driver.get(counter)
            if driver.current_url.find('stock_problems') == -1:
                break
            time.sleep(get_wait_time())
            if driver.current_url.find('stock_problems') == -1:
                break
            if counter != get_one:
                counter = get_one
            else:
                counter = get_two

    def queue_wait(self, driver):
        print('Waiting on queue')
        while True:
            if driver.current_url.find('queue') == -1:
                break
            time.sleep(2)

    def clear_checkout(self, driver, url) -> None:
        driver.get(self.shop_site + '/cart/clear')
        time.sleep(1)
        driver.get(url)
        time.sleep(1)
        driver.get(self.shop_site + '/cart/checkout')

    def pre_get_random_item(self):
        r = requests.get(self.shop_site + '/products.json')
        try:
            products = json.loads((r.text))['products']
        except:
            time.sleep(10)
            return
        id_list = []
        for product in products:
            variant = product['variants']
            for size in variant:
                if size['available']:
                    id_list.append(size['id'])

        random_index = random.randint(0, len(id_list) - 1)
        return self.shop_site + '/cart/add/' + str(id_list[random_index])

    def product_url(self):
        if self.inputted_domain is not None:
            site = self.inputted_domain + '.json'
        else:
            site = self.shop_site + '/products.json'

        try:
            r = requests.get(site)
            print(r.status_code)
            if r.status_code == 404:
                print('Error Page not found in finding product--RETRYING')
                return
            elif r.status_code != 200:
                raise ConnectionError('Unknown error in finding product')
        except (ConnectionError, TimeoutError, MaxRetryError, NewConnectionError):
            print('Connection Error in finding product--RETRYING')
            time.sleep(20)
            return

        # SHOPIFY SITES
        # https://www.a-ma-maniere.com/collections/nike-lab/products.json
        # https://cncpts.com/collections/nike/products.json
        # https://kith.com/products.json
        # https://sneakerpolitics.com/collections/sneakers/products.json
        # https://shopnicekicks.com/collections/new-arrivals-1/products.json

        try:
            products = json.loads((r.text))['products']
            single_product = False
        except KeyError:
            products = json.loads((r.text))['product']
            single_product = True
        except:
            print('Error while finding product: [' + str(sys.exc_info()[0]) + '] Retrying....')
            return

        id_list = []

        if not single_product:
            for product in products:
                product_name = (product['title']).upper()
                for keyword in self.item_keywords:
                    if product_name.find(keyword) != -1:
                        variant = product['variants']
                        for size in variant:
                            id_list.append(size['id'])
                        return id_list

        else:
            variant = products['variants']
            for size in variant:
                id_list.append(size['id'])
            return id_list

    def threaded_monitor(self):
        INT_MAX = 1000000
        for i in range(0, INT_MAX):

            ids_list = self.product_url()

            if ids_list is not None:
                self.id_list = ids_list
                return
            else:
                time.sleep(get_wait_time())
        print('could not find item')
        # driver.quit()
        sys.exit()

    def find_product(self):
        INT_MAX = 1000000
        print('Waiting for monitor....')
        for i in range(0, INT_MAX):

            if len(self.id_list) != 0:
                print('found product')
                return self.get_random_addcart()
            else:
                time.sleep(.7)
        print('could not find item')
        # driver.quit()
        sys.exit()

    def get_random_addcart(self):
        random_index = random.randint(0, len(self.id_list) - 1)
        return self.shop_site + '/cart/add/' + str(self.id_list[random_index])

    def get_random_direct_checkout(self):
        random_index = random.randint(0, len(self.id_list) - 1)
        return self.shop_site + '/cart/' + str(self.id_list[random_index]) + ':1'

    def new_captcha_solve(self, driver, h_captcha=False, checkpoint=False):
        if h_captcha:
            find_string = '//*[contains(@id, "h-captcha-response")]'
        else:
            find_string = '//*[contains(@id, "g-recaptcha-response")]'
        try:
            captcha_element = driver.find_element_by_xpath(find_string)
        except (AttributeError, Exception):
            print('Same error with string')
            time.sleep(2)
            return
        if captcha_element.get_attribute('value') == '':
            captcha_driver = get_driver(False)
            captcha_driver.set_window_size(500, 600)
            if checkpoint:
                pass
            else:
                captcha_driver.get(self.shop_site)
                cookies = driver.get_cookies()
                for cookie in cookies:
                    captcha_driver.add_cookie(cookie)
            captcha_driver.get(driver.current_url)
            token = self.wait_captcha(captcha_driver, h_captcha, find_string)

            if h_captcha:
                # driver.execute_script("document.querySelector('body > main > form > fieldset > div > iframe').style.display = 'block';")
                driver.execute_script("arguments[0].style.display = 'block';", captcha_element)
                captcha_element.send_keys(token)
                time.sleep(.5)
                driver.execute_script("arguments[0].style.display = 'none';", captcha_element)
            else:
                driver.execute_script("document.querySelector('#g-recaptcha > iframe').style.display = 'block';")
                driver.execute_script("arguments[0].style.display = 'block';", captcha_element)
                captcha_element.send_keys(token)
                time.sleep(.5)
                driver.execute_script("arguments[0].style.display = 'none';", captcha_element)
                driver.execute_script("document.querySelector('#g-recaptcha > iframe').style.display = 'none';")
        else:
            time.sleep(2)

    def pre_bot(self, driver):
        if driver.current_url.find('checkouts') != -1:
            self.pre_checkout(driver, checkout_info)
            return
        elif driver.current_url == (self.shop_site + '/cart'):
            print('cart error')
            driver.delete_all_cookies()
            time.sleep(3)
            self.pre_generate_url(driver)
            return
        elif driver.current_url == self.shop_site:
            driver.delete_all_cookies()
            driver.get(self.pre_get_random_item())
            time.sleep(3)
            self.pre_checkout(driver, checkout_info)
            return
        elif driver.current_url.find('queue') != -1:
            print('Waiting on queue')
            self.queue_wait(driver)
            self.pre_bot(driver)
            return
        else:
            print('error in pre checkout--going to main checkout')
            return

    def bot(self, driver, url):
        if driver.current_url.find('stock_problems') != -1:
            self.stock_wait(self.shop_site, driver)
            print('recursion')
            self.bot(driver, url)
            return
        elif driver.current_url.find('checkouts') != -1:
            self.checkout(driver, url)
            return
        elif driver.current_url.find('checkpoint') != -1 and check_exists_by_class_name('g-recaptcha', driver):
            print('solving captcha')
            driver.maximize_window()
            if self.headless:
                self.new_captcha_solve(driver,False,True)
            else:
                self.wait_captcha_2(driver, False)
            for i in range(3):
                if check_exists_by_class_name('g-recaptcha', driver) or check_exists_by_class_name(
                        'h-captcha', driver):
                    try:
                        driver.find_element_by_class_name('ui-button.ui-button--primary.btn').click()
                    except:
                        time.sleep(1.5)
                else:
                    break
            self.bot(driver, url)
            return
        elif driver.current_url.find('checkpoint') != -1 and check_exists_by_class_name('h-captcha', driver):
            print('solving captcha')

            if self.headless:
                self.new_captcha_solve(driver, True, True)
            else:
                self.wait_captcha_2(driver, True)
            for i in range(3):
                try:
                    if check_exists_by_class_name('g-recaptcha', driver) or check_exists_by_class_name(
                            'h-captcha', driver):
                        driver.find_element_by_class_name('ui-button.ui-button--primary.btn').click()
                    else:
                        break
                except (ElementNotInteractableException, ElementClickInterceptedException, NoSuchElementException,
                        ElementNotVisibleException):
                    time.sleep(2.5)
                    pass
            self.bot(driver, url)
            return
        elif check_exists_by_class_name('g-recaptcha', driver):
            print('solving captcha')
            if self.headless:
                self.new_captcha_solve(driver, False, False)
            else:
                self.wait_captcha_2(driver, False)
            self.bot(driver, url)
            return
        elif check_exists_by_class_name('h-captcha', driver):
            if self.headless:
                self.new_captcha_solve(driver, True, False)
            else:
                self.wait_captcha_2(driver, True)
            time.sleep(1.5)
            self.bot(driver, url)
            return
        elif driver.current_url == (self.shop_site + '/cart'):
            print('cart error')
            while driver.current_url.find('/cart') != -1:
                time.sleep(5.5)
                driver.get(self.get_random_addcart())
                driver.get(self.shop_site + '/cart/checkout')
                time.sleep(2)
            self.checkout(driver, url)
            return
        elif driver.current_url == self.shop_site:
            self.clear_checkout(driver, url)
            self.checkout(driver, url)
            return
        elif driver.current_url.find('queue') != -1:
            print('Waiting on queue')
            self.queue_wait(driver)
            self.bot(driver, url)
            return
        elif check_exists_by_xpath('//span[@class="os-order-number"]', driver):
            print('checkoutt!!!')
            print(driver.find_element_by_xpath("//span[@class='os-order-number']").get_attribute('innerHTML'))
            return
        else:
            print('error in checkout')
            print(driver.current_url)
            time.sleep(10)
            self.checkout(driver, url)
            return

    def pre_checkout(self, driver, checkout_info):
        if check_exists_by_xpath('//*[@id="checkout_email"]', driver):
            if driver.find_element_by_xpath('//*[@id="checkout_email"]').get_attribute("value") == '':
                driver.find_element_by_xpath('//*[@id="checkout_email"]').send_keys(checkout_info['EMAIL'])
                time.sleep(0.5)
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_first_name"]').send_keys(
                    checkout_info['FIRST_NAME'])
                time.sleep(0.5)
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_last_name"]').send_keys(
                    checkout_info['LAST_NAME'])
                time.sleep(0.5)
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_address1"]').send_keys(
                    checkout_info['ADDRESS'])
                time.sleep(0.5)
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_city"]').send_keys(
                    checkout_info['CITY'])
                time.sleep(0.5)
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_zip"]').send_keys(
                    checkout_info['POSTCODE'])
                time.sleep(0.5)
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_phone"]').send_keys(
                    checkout_info['MOBILE'])
                time.sleep(0.5)
            if check_exists_by_class_name('g-recaptcha', driver):
                self.new_captcha_solve(driver)
            elif check_exists_by_class_name('h-captcha', driver):
                self.new_captcha_solve(driver, h_captcha=True)

            try:
                driver.find_element_by_xpath('//*[@id="continue_button"]').click()
            except ElementClickInterceptedException:
                try:
                    driver.find_element_by_xpath('//*[@id="btn-accept-address"]').click()
                except NoSuchElementException:
                    print('Error in checkout info page')
            except:
                pass

            try:
                WebDriverWait(driver, 4).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'section.section--shipping-method'))
                )
            except TimeoutException:
                try:
                    driver.find_element_by_xpath('//*[@id="btn-proceed-address"]').click()
                except:
                    pass
                print('Error in checkout info page. Retrying...')  # Try clicking choose original address
                self.pre_bot(driver)
                return

        if check_exists_by_class_name('section.section--shipping-method', driver):
            time.sleep(5)
            return
        else:
            print('Error in pre-checkout. Retrying...')
            time.sleep(5)
            self.pre_bot(driver)

    def checkout(self, driver, url):
        if check_exists_by_xpath('//*[@id="checkout_email"]', driver):
            if driver.find_element_by_xpath('//*[@id="checkout_email"]').get_attribute("value") == '':
                driver.find_element_by_xpath('//*[@id="checkout_email"]').send_keys(checkout_info['EMAIL'])
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_first_name"]').send_keys(
                    checkout_info['FIRST_NAME'])
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_last_name"]').send_keys(
                    checkout_info['LAST_NAME'])
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_address1"]').send_keys(
                    checkout_info['ADDRESS'])

                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_city"]').send_keys(
                    checkout_info['CITY'])
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_zip"]').send_keys(
                    checkout_info['POSTCODE'])
                driver.find_element_by_xpath('//*[@id="checkout_shipping_address_phone"]').send_keys(
                    checkout_info['MOBILE'])
            if check_exists_by_class_name('g-recaptcha', driver):
                self.new_captcha_solve(driver)
            elif check_exists_by_class_name('h-captcha', driver):
                self.new_captcha_solve(driver, h_captcha=True)

            try:
                driver.find_element_by_xpath('//*[@id="continue_button"]').click()
            except ElementClickInterceptedException:
                print('check the driver- an element is intercepted')
                time.sleep(3)
                try:
                    driver.find_element_by_xpath('//*[@id="btn-accept-address"]').click()
                    print("Problem fixed")
                except NoSuchElementException:
                    print('Error in shipping page')

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'section.section--shipping-method'))

                )
            except TimeoutException:
                print('Error in checkout info page. Retrying...')
                self.bot(driver, url)
                return

        if check_exists_by_class_name('section.section--shipping-method', driver):
            if check_exists_by_class_name('g-recaptcha', driver):
                self.new_captcha_solve(driver)
            elif check_exists_by_class_name('h-captcha', driver):
                self.new_captcha_solve(driver, h_captcha=True)
            time.sleep(1)
            for i in range(3):
                try:
                    if not check_exists_by_class_name('section.section--payment-method', driver):
                        javaScript = "document.querySelector('#continue_button').click();"
                        driver.execute_script(javaScript)
                        time.sleep(2.5)
                    else:
                        break
                except:
                    print('error')

            try:
                WebDriverWait(driver, 4).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'section.section--payment-method'))

                )
            except TimeoutException:

                print('Error in shipping page. Retrying...')
                self.bot(driver, url)
                return

        if check_exists_by_class_name('section.section--payment-method', driver):
            try:
                driver.find_element_by_id(
                    'checkout_different_billing_address_false').click()  # Same as shipping address
            except:
                pass
            driver.find_element_by_xpath(
                '//*[contains(@id, "checkout_payment_gateway_")]').click()  # Click by Credit Card
            print('Submitting payment info')
            driver.switch_to.frame(driver.find_element_by_xpath('//*[contains(@id, "card-fields-number-")]'))
            number_element = driver.find_element_by_id('number')
            if number_element.get_attribute('value') == '':

                number_element.send_keys(checkout_info['CREDITCNUMBER'][0:4])
                number_element.send_keys(checkout_info['CREDITCNUMBER'][4:8])
                number_element.send_keys(checkout_info['CREDITCNUMBER'][8:12])
                number_element.send_keys(checkout_info['CREDITCNUMBER'][12:16])

                driver.switch_to.parent_frame()

                driver.switch_to.frame(driver.find_element_by_xpath('//*[contains(@id, "card-fields-name-")]'))
                driver.find_element_by_id('name').send_keys(checkout_info['CREDITCNAME'])


                driver.switch_to.parent_frame()
                driver.switch_to.frame(driver.find_element_by_xpath('//*[contains(@id, "card-fields-expiry-")]'))
                expiry_element = driver.find_element_by_id('expiry')
                expiry_element.send_keys(checkout_info['CREDITCEXPIRY'][0:2])
                expiry_element.send_keys(checkout_info['CREDITCEXPIRY'][2:4])


                driver.switch_to.parent_frame()

                driver.switch_to.frame(
                    driver.find_element_by_xpath("//*[contains(@id, 'card-fields-verification_value-')]"))
                driver.find_element_by_id("verification_value").send_keys(checkout_info['CREDITCSECCODE'])


                driver.switch_to.parent_frame()

                try:
                    driver.find_element_by_xpath('//*[@id="i-agree__checkbox"]').click()
                except:
                    pass

                if check_exists_by_class_name('g-recaptcha', driver):
                    self.new_captcha_solve(driver)
                elif check_exists_by_class_name('h-captcha', driver):
                    self.new_captcha_solve(driver, h_captcha=True)

                driver.find_element_by_id('continue_button').click()

                print('Checking out....')
            else:
                driver.switch_to.parent_frame()
                try:
                    driver.find_element_by_xpath('//*[@id="i-agree__checkbox"]').click()
                except:
                    print(sys.exc_info()[0])
                    pass

                if check_exists_by_class_name('g-recaptcha', driver):
                    self.new_captcha_solve(driver)
                elif check_exists_by_class_name('h-captcha', driver):
                    self.new_captcha_solve(driver, h_captcha=True)

                driver.find_element_by_id('continue_button').click()
                print('Checking out....')
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, '//span[@class="os-order-number"]'))
                )
                print('checkout!!!')
            except TimeoutException:
                print('error in payment page')
                self.bot(driver, url)
                return

        if check_exists_by_xpath('//span[@class="os-order-number"]', driver):
            return
        else:
            time.sleep(2)
            self.bot(driver, url)

    def pre_generate_url(self, driver):
        driver.get(self.pre_get_random_item())

        checkoutDetails = (
                '?checkout[shipping_address][first_name]=' + checkout_info['FIRST_NAME'] +
                '&checkout[shipping_address][last_name]=' +
                checkout_info['LAST_NAME'] + '&checkout[email]=' + checkout_info['EMAIL'] +
                '&checkout[shipping_address][address1]='
                + checkout_info['ADDRESS'] + '&checkout[shipping_address][city]=' + checkout_info['CITY']
                + '&checkout[shipping_address][zip]='
                + checkout_info['POSTCODE'] + '&checkout[shipping_address][country_code]=' + checkout_info['COUNTRY'] +
                '&&checkout[shipping_address][province_code]=' + checkout_info['STATE'] +
                '&checkout[shipping_address][phone]=' + checkout_info['MOBILE'])

        driver.get(self.shop_site + '/cart/checkout'  + checkoutDetails)
        self.pre_checkout(driver, checkout_info)
        driver.get(self.shop_site + '/cart/clear')

    def create_task(self):
        window = get_driver(headless=self.headless)

        if self.headless:
            window.execute_cdp_cmd(
                "Network.setUserAgentOverride",
                {
                    "userAgent": window.execute_script(
                        "return navigator.userAgent"
                    ).replace("Headless", "")
                }
            )


        if self.pre_load_cookies:
            self.pre_generate_url(window)

        variant_url = self.find_product()

        window.get(variant_url)

        window.get(self.shop_site + '/cart/checkout')

        self.bot(window, variant_url)



print(r"""

                      ----------------------------
                              SHOPIFY BOT
                      ----------------------------

""")


class_instance = ShopB0t('REPLACE WITH SHOPIFY URL', "REPLACE WITH PRODUCT KEYWORDS. SEPARATE KEYWORDS WITH SEMICOLON")

class_instance.inputted_domain = None                              #Replace with shopify url to product if you have it
class_instance.pause_after_pre_checkout = 0                        #Replace with number to wait for monitor to start
class_instance.pre_load_cookies = False                            #Replace with True if you want to pre-checkout
class_instance.headless = False                                    #NOT RECOMMENDED replace with True if you want chrome to start in headless mode

tasks = 1                                                          #Replace with number of tasks
for i in range(tasks):
    threading.Thread(target=class_instance.create_task).start()

time.sleep(class_instance.pause_after_pre_checkout)

class_instance.threaded_monitor()
