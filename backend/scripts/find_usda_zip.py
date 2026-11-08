import re
import urllib.request

url = "https://fdc.nal.usda.gov/download-datasets"
with urllib.request.urlopen(url, timeout=40) as response:
    text = response.read().decode("utf-8", "ignore")
print("length", len(text))
hrefs = re.findall(r'href="([^"]+)"', text)
interesting = [href for href in hrefs if "zip" in href.lower() or "fdc-datasets" in href.lower() or "download" in href.lower()]
print("hrefs", len(hrefs), "interesting", len(interesting))
for href in interesting[:50]:
    print(href)
