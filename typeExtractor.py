import json
import argparse
from extractors import stm32Extractor

def save_dict_to_json(dictionary, file_path):
    with open(file_path, 'w') as json_file:
        json.dump(dictionary, json_file, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process vendor HAL header files.')
    parser.add_argument('-f', '--file', type=str, help='HAL Filename')
    parser.add_argument('-d', '--directory', type=str, help='HAL Files Directory')
    parser.add_argument('-v', '--vendor', type=str, help='HAL Vendor')
    parser.add_argument('-o', '--output', type=str, required=True, help='Output JSON file name')

    args = parser.parse_args()

    combined_struct = {}

    if( args.vendor == "ST" ):
        extractor = stm32Extractor.STM32Extractor(args.file, args.directory, combined_struct)

    save_dict_to_json(combined_struct, args.output)