from bs4 import BeautifulSoup
import requests
import sys
import threading


FILTERS = ["all", "au", "bd", "br", "by", "ca", "co", "cz", "de", "do", "ec", "eg", "es", "fr", "gb", "gr", "hk",
           "id", "il", "in", "it", "jp", "kr", "md", "mx", "nl", "ph", "pk", "pl", "ps", "ro", "ru", "se", "sg",
           "sy", "th", "tr", "tw", "ua", "us", "uz", "ve", "vn", "ye", "za", "zm"]


class Proxy:
    def __init__(self, country_code="all", validate_proxies=True):

        self.session = requests.Session()

        country_code = country_code.lower()

        is_valid = False
        for code in FILTERS:
            if country_code == code:
                is_valid = True
                break

        if is_valid:
            self.filter = country_code
        else:
            print("bad filter given! country code: " + country_code + " is not valid!\ndefaulting to no filter")
            self.filter = "all"

        self.index = 0
        self.validindex = 0
        self.proxies = self.fetch_proxies(self.filter)
        if len(self.proxies) <= 0:
            print("no proxies found! try using the 'all' filter")
        else:
            self.proxy_count = len(self.proxies)
            self.proxy = self.format_proxy(self.proxies[self.index])

        #ready to be used with requests and validated.
        self.validproxylist = []
        self.validproxy = None
        self.lock = threading.Lock()
        #validate and fill up the list
        if validate_proxies:
            self.validate_proxies(chunksize=8)

    @staticmethod
    def fetch_proxies(country_="all"):
        country_ = country_.lower()

        is_valid = False
        for code in FILTERS:
            if country_ == code:
                is_valid = True
                break

        if not is_valid:
            print("bad filter given! country code: " + country_ + " is not valid!\ndefaulting to no filter")
            country_ = "all"

        print("fetching proxies...")
        url = "https://free-proxy-list.net/"
        page = requests.get(url)

        if page.status_code != 200:
            print("Couldn't fetch proxies list! received bad response with code: " + str(page.status_code))
            sys.exit(1)
        else:
            print("parsing data...")
            soup = BeautifulSoup(page.content, "html.parser")
            rows = soup.find_all("tr")

            proxies = []
            for row in rows:
                parts = row.find_all("td")
                if len(parts) == 8:
                    ip = parts[0].text
                    port = parts[1].text
                    country_code = parts[2].text
                    country = parts[3].text
                    provider = parts[4].text
                    google = parts[5].text
                    https = parts[6].text
                    last_checked = parts[7].text

                    if https == "yes" and (country_ == "all" or country_ == country_code.lower()):
                        proxies.append([ip, port, country_code, country, provider, google, https, last_checked])

            print("retrieved " + str(len(proxies)) + " proxies")
            return proxies

    def cycleValid(self):
        self.validproxy = self.format_proxy(self.validproxylist[self.validindex])
        self.validindex = self.validindex + 1
        if self.validindex >= len(self.validproxylist):
            self.validindex = 0

    def _thr_test(self, proxy_):
        res = self.test_proxy(proxy_)
        if res == 1:
            self.lock.acquire()
            try:
                self.validproxylist.append(proxy_)
            finally:
                self.lock.release()

    def _thr_multi_test(self, plist):
        for p in plist:
            self._thr_test(p)

    def validate_proxies(self, chunksize=8):
        self.validproxylist=[]
        def _chunks(l, n):
            for i in range(0, len(l), n):
                yield l[i:i+n]
        formatted_proxies = [self.format_proxy(p) for p in self.proxies]
        chunklist = list(_chunks(formatted_proxies, chunksize))
        tlist = []
        for i in range(0, len(chunklist)):
            task = threading.Thread(target=self._thr_multi_test, args=(chunklist[i], ))
            tlist.append(task)
        for t in tlist:
            t.start()
        for t in tlist:
            t.join()


    @staticmethod
    def format_proxy(proxy):
        http = "http://" + proxy[0] + ":" + proxy[1]
        https = "https://" + proxy[0] + ":" + proxy[1]
        proxy_dict = {
            "http": http,
            "https": https
        }
        return proxy_dict

    @staticmethod
    def test_proxy(proxy_):
        url = "https://www.iplocation.net/find-ip-address"
        print("testing proxy...")
        try:
            page = requests.get(url, proxies=proxy_)
            soup = BeautifulSoup(page.content, "html.parser")
            try:
                ip_tbl = soup.find("table", {"class": "iptable"})
                data = ip_tbl.find_all("td")

                ip = data[0].find("span").text
                location = data[1].text.split("[")[0]
                device = data[4].text + ", " + data[3].text
                os = data[5].text
                browser = data[6].text
                user_agent = data[7].text

                print("\n\nSuccess! Able to connect with proxy\nConnection Details:\nip: " + ip + "\nlocation: " + location)
                print("device: " + device + "\nos: " + os + "\nbrowser: " + browser + "\nuser agent: " + user_agent)
            except AttributeError:
                print("Something went wrong.")
            return 1
        except requests.exceptions.ProxyError:
            print("request caused a proxy error!")
            return 0
