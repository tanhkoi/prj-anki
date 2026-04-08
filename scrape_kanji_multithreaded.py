import requests
import threading
from bs4 import BeautifulSoup

# Function to fetch kanji data for a specific JLPT level
def fetch_kanji_data(level):
    url = f"https://kanjiapi.dev/v1/kanji/jlpt-{level}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch kanji data for JLPT level {level}: {response.status_code}")
        return []

# Function to scrape data for a specific kanji
def scrape_kanji_data(kanji):
    url = f"https://nhaikanji.com/{kanji}"
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        # Extract the first div with the specified class
        div = soup.find('div', class_="flex flex-col items-center space-y-2 p-4 min-[1366px]:items-start min-[1366px]:text-left")
        if div:
            return div.text  # Extract entire content of the div
        else:
            return response.text[:3000]  # Extract up to 3000 characters if div is not found
    else:
        print(f"Failed to fetch data for kanji {kanji}: {response.status_code}")
        return ""

# Worker function for multithreading
def worker(level, kanji_list, output_file):
    with open(output_file, 'a', encoding='utf-8') as file:
        for kanji in kanji_list:
            print(f"Processing kanji: {kanji}")
            data = scrape_kanji_data(kanji)
            if data:
                file.write(f"Kanji: {kanji}\n")
                file.write(data + "\n\n")

# Main function
def main():
    threads = []
    for level in range(5, 0, -1):  # Levels 5 to 1
        kanji_list = fetch_kanji_data(level)
        output_file = f"jlpt_level_{level}.txt"

        # Split kanji list into chunks for multithreading
        chunk_size = max(1, len(kanji_list) // 5)
        for i in range(0, len(kanji_list), chunk_size):
            chunk = kanji_list[i:i + chunk_size]
            thread = threading.Thread(target=worker, args=(level, chunk, output_file))
            threads.append(thread)
            thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()