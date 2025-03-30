import requests
from bs4 import BeautifulSoup

class Component:
    def __init__(self):
        self.manufacturer = ""
        self.mpn = ""
        self.description = ""
        self.datasheet = ""
        self.lcsc_part_number = ""
        self.parameters = {}
        self.pins = {}

    def __str__(self):
        return f"Manufacturer: {self.manufacturer}\n" \
               f"MPN: {self.mpn}\n" \
               f"Description: {self.description}\n" \
               f"Datasheet: {self.datasheet}\n" \
               f"LCSC Part Number: {self.lcsc_part_number}\n" \
               f"Parameters: {self.parameters}\n" \
               f"Pins: {self.pins}\n"


def get_component_info(mpn):
    url = f"https://www.lcsc.com/search?q={mpn}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    print(soup)
    part_link = soup.find('a', class_='search-product-title')
    if not part_link:
        return None

    part_url = "https://www.lcsc.com" + part_link['href']
    part_page = requests.get(part_url)
    part_soup = BeautifulSoup(part_page.content, 'html.parser')

    component = Component()

    component.manufacturer = part_soup.find(
        'div', class_='product-manufacturer').text.strip()
    component.mpn = part_soup.find('div', class_='product-model').text.strip()
    component.description = part_soup.find(
        'div', class_='product-title').text.strip()
    component.datasheet = part_soup.find('a', class_='datasheet')['href']
    component.lcsc_part_number = part_soup.find('span', {
        'id': 'lcsc_part_no'
    }).text.strip()

    parameters = part_soup.find_all('li', class_='product-param-item')
    for param in parameters:
        param_name = param.find('span', class_='param-name').text.strip()
        param_value = param.find('span', class_='param-value').text.strip()
        component.parameters[param_name] = param_value

    pins = part_soup.find('div', class_='product-pin-description')
    if pins:
        pin_info = pins.find_all('tr')
        for pin in pin_info:
            pin_number = pin.find_all('td')[0].text.strip()
            pin_name = pin.find_all('td')[1].text.strip()
            component.pins[pin_number] = pin_name

    return component

if __name__ == "__main__":
    mpn = "CH334F"
    component_info = get_component_info(mpn)
    if component_info:
        print(component_info)
    else:
        print(f"No information found for MPN: {mpn}")
