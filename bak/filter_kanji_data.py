# Python program to process a file as per the user's requirements

def process_file(input_file, output_file):
    try:
        with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
            for line in infile:
                # Check if 'kanji\\' exists in the line
                if 'kanji\\' in line:
                    # Split and keep the part starting from 'kanji\\'
                    modified_line = line.split('kanji\\', 1)[1]
                    outfile.write(modified_line)
                else:
                    # If 'kanji\\' is not found, write the line as is
                    outfile.write(line)
        print(f"File processed successfully. Output saved to {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
if __name__ == "__main__":
    input_file = "kanji_data_n1.txt"  # Input file name
    output_file = "processed_kanji_data_n1.txt"  # Output file name
    process_file(input_file, output_file)