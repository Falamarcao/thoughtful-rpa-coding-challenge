from RPA.Robocorp.WorkItems import WorkItems

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException

import os
import re
from lxml import html
from httpx import Client
import polars as pl

class Gothamist:
    def __init__(self, search_query: str):
        self.search_query = search_query
        self.driver = webdriver.Chrome()
        self.action_chains = ActionChains(driver=self.driver)

        self.client = Client()

    def fetch(self):
        url = f"https://gothamist.com/search?q={self.search_query}"
        self.driver.get(url)

        load_more_button = self.driver.find_element(
            By.XPATH,
            "/html/body/div[1]/div/div/main/div[2]/div/section[2]/div/div[1]/div[2]/button",
        )
        while True:

            self.driver.execute_script(
                "arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });",
                load_more_button,
            )
            self.action_chains.click(load_more_button).perform()

            try:
                load_more_button = self.driver.find_element(
                    By.XPATH,
                    "/html/body/div[1]/div/div/main/div[2]/div/section[2]/div/div[1]/div[2]/button",
                )

            except NoSuchElementException:
                break

            break  # TODO: REMOVE ME

        return self.driver.page_source

    @staticmethod
    def contains_money(text):
        # Define regex pattern to match different money formats
        pattern = r"\$[\d,]+(?:\.\d+)?|\b\d+\s*(?:dollars?|usd)\b"

        # Check if the text contains any money format
        return bool(re.search(pattern, text))

    def count_occurences(self, text: str):
        return text.lower().count(self.search_query.lower())

    def download_image(self, src: str):

        image_filename = src.split("images/")[1].split("/fill")[0] + ".webp"
        folder_path = os.path.join("output", "images")
        
        os.makedirs(folder_path, exist_ok=True)
        
        image_path = os.path.join(folder_path, image_filename)

        response = self.client.get(src)

        # Handles redirect used by the image Web API
        redirect_url = response.headers.get("Location")

        response = self.client.get(redirect_url)

        if response.status_code == 200:
            with open(image_path, "wb") as file:
                file.write(response.content)
            
            return image_filename

    def scrape(self, content):
        tree = html.fromstring(content)

        div_list = tree.xpath(
            "/html/body/div[1]/div/div/main/div[2]/div/section[2]/div/div[1]/div[2]/div",
        )

        data = []
        for element in div_list:
            title = element.xpath(".//div/div[2]/div[1]/a/div")[0].text_content()
            description = element.xpath(".//div/div[2]/div[2]/p")[0].text_content()
            image = element.xpath(".//div/div[1]/figure[2]/div/div/a/div/img/@src")[0]

            image_filename = self.download_image(image)

            data.append(
                {
                    "title": title,
                    "description": description,
                    "image": image,
                    "image_filename": image_filename,
                    "money": self.contains_money(f"{title} {description}"),
                    "count_search_query": self.count_occurences(text=f"{title} {description}"),
                }
            )

        return data


def save_data_to_excel(data, filename):
    # Convert the dictionary to a Polars DataFrame
    df = pl.DataFrame(data)
    # Save the DataFrame to an Excel file
    df.write_excel(f"output/{filename}")


def run_task():
    wi = WorkItems()
    wi.get_input_work_item()
    search_query = wi.get_work_item_variable("search_query")

    gothamist = Gothamist(search_query=search_query)
    content = gothamist.fetch()
    data = gothamist.scrape(content)
    save_data_to_excel(data, "output.xlsx")

if __name__ == "__main__":
    run_task()
