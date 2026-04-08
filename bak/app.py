import requests

def extract_all_contexts(kanji, window=3000):
    url = f"https://nhaikanji.com/{kanji}"
    
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(url, headers=headers)
    if res.status_code != 200:
        print("Request failed")
        return

    text = res.text
    contexts = []

    start = 0
    while True:
        index = text.find(kanji, start)
        if index == -1:
            break

        # cắt đoạn xung quanh
        s = max(0, index - window)
        e = min(len(text), index + len(kanji) + window)
        snippet = text[s:e]

        contexts.append(snippet)

        # tiếp tục tìm sau vị trí này
        start = index + 1

    return contexts


def find_best_match(contexts):
    for ctx in contexts:
        # lọc đoạn có chứa dữ liệu bạn cần
        if "flex flex-col items-center space-y-2 p-4 min-[1366px]:items-start min-[1366px]:text-left" in ctx:
            print("✅ Found candidate:\n")
            print(ctx)
            return ctx

    print("❌ Không tìm thấy đoạn phù hợp")


def save_to_file(data, filename):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(data + "\n")

def crawl_kanji_data():
    levels = ["5", "4", "3", "2", "1"]

    for level in levels:
        output_file = f"kanji_data_n{level}.txt"
        print(f"🔄 Crawling JLPT N{level} kanji...")
        url = f"https://kanjiapi.dev/v1/kanji/jlpt-{level}"
        response = requests.get(url)

        if response.status_code != 200:
            print(f"❌ Failed to fetch kanji for JLPT N{level}")
            continue

        kanji_list = response.json()

        for kanji in kanji_list:
            print(f"🔍 Processing kanji: {kanji}")
            contexts = extract_all_contexts(kanji)

            if not contexts:
                print(f"❌ No contexts found for kanji: {kanji}")
                continue

            best_match = find_best_match(contexts)

            if best_match:
                save_to_file(best_match, output_file)

    print("✅ Data saved to respective files for each JLPT level.")

if __name__ == "__main__":
    crawl_kanji_data()