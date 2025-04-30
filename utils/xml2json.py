import xmltodict
import json
import argparse
import sys
import os

def convert_xml_to_json(input_file, output_file=None):
    try:
        # Check if input file exists
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file '{input_file}' not found")

        # Load and read the XML file
        with open(input_file, "r", encoding="utf-8") as file:
            xml_content = file.read()

        # Convert XML to Python dictionary
        data_dict = xmltodict.parse(xml_content)

        # Convert dictionary to formatted JSON string
        json_output = json.dumps(data_dict, indent=2)

        # Determine output filename if not provided
        if output_file is None:
            output_file = os.path.splitext(input_file)[0] + ".json"

        # Save to a .json file
        with open(output_file, "w", encoding="utf-8") as json_file:
            json_file.write(json_output)

        print(f"✅ Conversion complete. Output saved to {output_file}")
        return True

    except FileNotFoundError as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Error during conversion: {str(e)}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description='Convert XML file to JSON')
    parser.add_argument('input_file', help='Path to the input XML file')
    parser.add_argument('-o', '--output', help='Path to the output JSON file (optional)')
    
    args = parser.parse_args()
    
    success = convert_xml_to_json(args.input_file, args.output)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
