import json

def process_jlpt_file_to_json(input_file, output_file):
    data = []

    with open(input_file, 'r', encoding='utf-8') as file:
        for line in file:
            # Skip empty lines
            if not line.strip():
                continue

            # Split the line by '|'
            parts = [part.strip() for part in line.split('|')]

            # Map parts to keys
            if len(parts) >= 9:
                entry = {
                    "Kanji": parts[0],
                    "Vietsino": parts[1],
                    "Meaning": parts[2],
                    "Level": parts[3],
                    "StrokeCount": parts[4],
                    "Kunyomi": parts[5],
                    "Onyomi": parts[6],
                    "Radicals": parts[7],
                    "Explanation": parts[8]
                }
            else:
                # Handle cases with missing fields
                entry = {
                    "Kanji": parts[0] if len(parts) > 0 else "",
                    "Vietsino": parts[1] if len(parts) > 1 else "",
                    "Meaning": parts[2] if len(parts) > 2 else "",
                    "Level": parts[3] if len(parts) > 3 else "",
                    "StrokeCount": parts[4] if len(parts) > 4 else "",
                    "Kunyomi": parts[5] if len(parts) > 5 else "",
                    "Onyomi": parts[6] if len(parts) > 6 else "",
                    "Radicals": parts[7] if len(parts) > 8 else "",
                    "Explanation": parts[7] if len(parts) > 7 else ""
                }

            data.append(entry)

    # Write to JSON file
    with open(output_file, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    input_file = "jlpt_level_1.txt"  # Change this to your input file
    output_file = "jlpt_level_1.json"  # Change this to your desired output file
    process_jlpt_file_to_json(input_file, output_file)
    print(f"Processed {input_file} and saved to {output_file}.")