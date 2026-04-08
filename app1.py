import requests

def get_kanji_page(kanji):
    url = f"https://nhaikanji.com/{kanji}"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        # print(response.text)  # raw HTML
        output_file = f"html_crawl.txt"
        save_to_file(response.text, output_file)

    else:
        print(f"Failed: {response.status_code}")

def save_to_file(data, filename):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(data + "\n")

# example
get_kanji_page("先")