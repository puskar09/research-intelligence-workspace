import requests
from bs4 import BeautifulSoup

url = "https://example.com"
response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")
title=soup.find("body")


"""print(response.text)"""
print(title.get_text(strip=True))

