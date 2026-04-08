import os
import json

# Directory containing JSON files
input_dir = "json_results"
output_file = "converted_results.txt"

def process_json_file(file_path):
    """Process a single JSON file and return the converted lines."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    lines = []
    for item in data:
        # Extract values, replace empty strings with "", and join with |
        values = [str(value) if value != "" else "" for value in item.values()]
        lines.append("|".join(values))

    return lines

def main():
    # Ensure the input directory exists
    if not os.path.exists(input_dir):
        print(f"Input directory '{input_dir}' does not exist.")
        return

    all_lines = []

    # Process each JSON file in the directory
    for file_name in os.listdir(input_dir):
        if file_name.endswith('.json'):
            file_path = os.path.join(input_dir, file_name)
            print(f"Processing file: {file_name}")
            all_lines.extend(process_json_file(file_path))
            # Write the results to the output file
            output_file = f"{os.path.splitext(file_name)[0]}_converted.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(all_lines))
            all_lines = []


    print(f"Conversion complete. Results saved to '{output_file}'.")

if __name__ == "__main__":
    main()