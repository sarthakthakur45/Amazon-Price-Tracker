import time
from selenium.webdriver.common.keys import Keys
from amazon_config import(
    get_web_driver_options,
    get_chrome_web_driver,
    set_ignore_certificate_error,
    set_browser_as_incognito,
    NAME,
    CURRENCY,
    FILTERS,
    BASE_URL,
    DIRECTORY
)
from selenium.common.exceptions import NoSuchElementException
import json
from datetime import datetime


class GenerateReport:
    def __init__(self, file_name, filters, base_link, currency, data):
        self.data = data
        self.file_name = file_name
        self.filters = filters
        self.base_link = base_link
        self.currency = currency
        report = {
            'title': self.file_name,
            'date': self.get_now(),
            'best_item': self.get_best_item(),
            'currency': self.currency,
            'filters': self.filters,
            'base_link': self.base_link,
            'products': self.data
        }
        print("Creating report...")
        with open(f'{DIRECTORY}/{file_name}.json', 'w') as f:
            json.dump(report, f)
        print("Done...")


    def get_best_item(self):
        try:
            return sorted(self.data, key=lambda k: k['price'])[0] 
            # sort the dictionary and return the lowest price value item
        except Exception as e:
            print(e)
            print("Problem with sorting items")
            return None


    def get_now(self):
        now = datetime.now()
        return now.strftime("%d/%m/%Y %H:%M:%S")


class AmazonAPI:
    def __init__(self, search_term, filters, base_url, currency):
        self.base_url = base_url
        self.search_term =search_term
        options = get_web_driver_options()
        set_ignore_certificate_error(options)
        set_browser_as_incognito(options)
        self.driver = get_chrome_web_driver(options)
        self.currency = currency
        self.price_filter = f"&rh=p_36%3A{filters['min']}00-{filters['max']}00"
        """ &rh=p_36%3A is the static part the 2 trailing zeros behind min and max are 
        bcoz amazon works in subunit (eg. paisa) and we pass in main unit (eg. Rs.)"""
        

    def run(self):
        print('Starting script...')
        print(f"Looking for {self.search_term} products...")
        links = self.get_products_links()
        time.sleep(1)
        if not links:
            print('Stopped script')
            return
        print(f"Got {len(links)} links to product")
        print("getting info about products...")
        products = self.get_products_info(links)
        print(f"Got info about {len(products)} products...")
        self.driver.quit()
        return products


    def get_products_info(self,links):
        asins = self.get_asins(links)
        products=[]
        for asin in asins[:8]:
            product = self.get_single_product_info(asin)
            if product:
                products.append(product)
        return products

    
    def get_single_product_info(self,asin):
        print(f"Product ID: {asin} - getting data...")
        product_short_url = self.shorten_url(asin)
        self.driver.get(f'{product_short_url}?language=en_GB') # also the language is changed to english
        time.sleep(2)
        title = self.get_title()
        seller = self.get_seller()
        price = self.get_price()
        if title and seller and price:
            product_info = {
                'asin': asin,
                'url': product_short_url,
                'title': title,
                'seller': seller,
                'price': price
            }
            return product_info
        return None


    def get_price(self):
        price = None
        try:
            price = self.driver.find_element_by_id('priceblock_ourprice').text # price available directly
            price = self.convert_price(price)
        except NoSuchElementException: #product available in stock but price is not given directly at the top
            try:
                availability = self.driver.find_element_by_id('availability').text
                if 'Available' in availability: # product available, price bottom
                    price = self.driver.find_element_by_class_name('olp-padding-right').text
                    price = price[price.find(self.currency):]
                    price = self.convert_price(price)
            except Exception as e:
                print(e) # not available
                print(f"Can't get price of a product - {self.driver.current_url}")
                return None
        except Exception as e:
            print(e)
            print(f"Can't get price of a product - {self.driver.current_url}")
            return None
        return price
    
    
    def get_seller(self):
        try:
            return self.driver.find_element_by_id('bylineInfo').text
        except Exception as e:
            print(e)
            print(f"Can't get a seller of a product - {self.driver.current_url}")
            return None


    def get_title(self):
        try:
            return self.driver.find_element_by_id('productTitle').text
        except Exception as e:
            print(e)
            print(f"Can't get a title of a product - {self.driver.current_url}")
            return None


    def convert_price(self,price):
        price = price.split(self.currency)[1] # splits on euro sign and stores the numeric part in variable
        try:
            price = price.split("\n")[0] + "." + price.split("\n")[1]
        except:
            Exception()
        try:
            price = price.split(",")[0] + price.split(",")[1]
        except:
            Exception()
        return float(price)


    def shorten_url(self, asin):
        """ We want only the base url and the id bcoz product name can change but id never changes in case of their database"""
        return self.base_url + 'dp/' + asin


    def get_asins(self, links):
        return [self.get_asin(link) for link in links]


    def get_asin(self, product_link):
        # Get me the thing between /dp/ and /ref
        # 4 is mentioned bcoz /dp/ is of 4 characters
        return product_link[product_link.find('/dp/') + 4:product_link.find('/ref')]


    def get_products_links(self):
        self.driver.get(self.base_url)
        element = self.driver.find_element_by_id('twotabsearchtextbox') #...
        element.send_keys(self.search_term) # send_keys --> it LITERALLY TYPES stuff in searchbar or any element for that matter
        element.send_keys(Keys.ENTER)
        time.sleep(2)
        self.driver.get(f'{self.driver.current_url}{self.price_filter}') #adds price filter to current url
        print(f"Our url: {self.driver.current_url}")
        time.sleep(2)
        result_list = self.driver.find_elements_by_class_name('s-result-list') #...
        # s-result-list is a class that has the complete list of the needed items
        links = []
        try:
            results = result_list[0].find_elements_by_xpath(
                "//div/span/div/div/div[2]/div[2]/div/div[1]/div/div/div[1]/h2/a") #... path for getting link inside a product
            links = [link.get_attribute('href') for link in results] # stores the links in this list
            return links
        except Exception as e:
            print("Didn't get any products...")
            print(e)
            return links

        

if __name__ == '__main__':
    print('Heyy!!!')
    amazon = AmazonAPI(NAME, FILTERS, BASE_URL, CURRENCY)
    data = amazon.run()
    GenerateReport(NAME, FILTERS, BASE_URL, CURRENCY, data)