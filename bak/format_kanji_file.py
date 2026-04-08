# Python program to format lines in a file

def format_file(input_file, output_file):
    keywords = [
        "Quy tắc chuyển âmÝ nghĩa",
        "Trình độ JLPT",
        "Số nét",
        "Âm Kun",
        "Âm On",
        "Cấu tạo từ các bộ thủ",
        "Gợi ý cách nhớ"
    ]

    try:
        with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
            for line in infile:
                try:
                    # Extract fields from the line
                    if ' ' not in line:
                        print(f"Skipping malformed line: {line.strip()}")
                        continue

                    kanji, details = line.split(' ', 1)
                    details = details.strip()

                    # Check if all required keywords are present
                    if not all(keyword + ':' in details for keyword in keywords[:-1]):
                        print(f"Skipping line with missing keywords: {line.strip()}")
                        continue

                    # Extract details based on keywords
                    meaning = details.split("Quy tắc chuyển âmÝ nghĩa:")[1].split("Trình độ JLPT:")[0].strip()
                    jlpt = details.split("Trình độ JLPT:")[1].split("Số nét:")[0].strip()
                    strokes = details.split("Số nét:")[1].split("Âm Kun:")[0].strip()
                    kun_reading = details.split("Âm Kun:")[1].split("Âm On:")[0].strip()
                    on_reading = details.split("Âm On:")[1].split("Gợi ý cách nhớ:")[0].strip()

                    # Check for "Cấu tạo từ các bộ thủ"
                    if "Cấu tạo từ các bộ thủ:" in details:
                        components = details.split("Cấu tạo từ các bộ thủ:")[1].split("Gợi ý cách nhớ:")[0].strip()
                        mnemonic = details.split("Gợi ý cách nhớ:")[1].strip()
                    else:
                        components = ""
                        mnemonic = "|| " + details.split("Gợi ý cách nhớ:")[1].strip()

                    # Format the output line
                    formatted_line = f"{kanji.strip()} | {meaning} | {jlpt} | {strokes} | {kun_reading} | {on_reading} | {components} | {mnemonic}\n"
                    outfile.write(formatted_line)
                except Exception as line_error:
                    print(f"Error processing line: {line.strip()} - {line_error}")

        print(f"File formatted successfully. Output saved to {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
if __name__ == "__main__":
    input_file = "jlpt_level_3.txt"  # Input file name
    output_file = "formatted_jlpt_level_3.txt"  # Output file name
    format_file(input_file, output_file)