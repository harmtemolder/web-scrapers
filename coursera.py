from bs4 import BeautifulSoup
from requests_html import HTMLSession

# Log in to Coursera in your browser and paste the value of the `CAUTH` cookie:
cookies = {
    'CAUTH': 'DTaET90XJSdt9dKC71tbIK9CZy490YWED6u_03fWpewanaB6fimjilwhGaAy4_QoZmvi1_fp1-cKR9egBxF4wQ.CZOe4Otk4r3Y_T0_TLj5YQ.RKy0_bYnXn03RdUpf_1jThWFsRrdsB6NHQtrt7CbhP8HJB10gmjZuQrKTlCqvvk2jEcJzCr5LnSgudK5CKy5kd1BO352FDnbD6ooNthDjPMKyij0DgLUovVmyPMwNLflGqFDH4FvITq_mG5SBX0g6MmEzQAn3mzzN9mR_sTIGVRkg4Rtc3w_0fADcc3VJgCu'
}

# Prepare a list of URLs to scrape
base_url = 'https://www.coursera.org/learn/astro/home/week/'
urls = ['{}{}'.format(base_url, i) for i in range(5, 6)]

# Render all URLs
session = HTMLSession()
results = {}

for url in urls:
    results[url] = session.get(url, cookies=cookies)

session.close()

for url, result in results.items():
    soup = BeautifulSoup(result.html.html, 'html.parser')
    page_title = soup.title
    module_titles = soup.find_all(class_='module-title')

    pass

pass
