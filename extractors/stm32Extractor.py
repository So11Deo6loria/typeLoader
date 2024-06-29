import re
import os

class STM32Extractor:
    def __init__( self, filename, directory, combined_struct ):
        self.filename = filename
        self.directory = directory
        self.combined_struct = combined_struct 
        if self.filename:
            self.process_file(self.filename, self.combined_struct)
        elif self.directory:
            self.process_directory(self.directory, self.combined_struct)
        else:
            print("ERROR: Initializing STM32Extractor")

    def find_typedefs(self, file_path):
        typedef_pattern = re.compile(
            r'typedef\s+(struct|enum)\s*(\w+)?\s*\{([^}]*)\}\s*(\w+)\s*;|typedef\s+([\w\s\*]+)\s+(\w+)\s*;',
            re.DOTALL
        )
        with open(file_path, 'r') as file:
            content = file.read()
        
        typedefs = typedef_pattern.findall(content)
        return typedefs

    def check_type(self, type):
        known_types = ['struct', 'enum', 'uint8_t', 'uint16_t', 'uint32_t']
        if type in known_types:
            return type
        else: 
            return 'unknown'
        
    def parse_enum_data(self, data):
        state_pattern_with_comment = re.compile(r'^\s*(.*?)\s*=\s*(0x[0-9A-Fa-f]+)U\s*,\s*/\*!<\s*(.*?)\s*\*/', re.DOTALL | re.MULTILINE)
        state_pattern_without_comment = re.compile(r'^\s*(.*?)\s*=\s*(0x[0-9A-Fa-f]+)U\s*,', re.MULTILINE)
        state_pattern_no_value = re.compile(r'^\s*(.*?)\s*,\s*/\*!<\s*(.*?)\s*\*/', re.DOTALL | re.MULTILINE)
        state_pattern_no_value_no_comment = re.compile(r'^\s*(.*?)\s*,', re.MULTILINE)
        state_pattern_last_no_value_no_comment = re.compile(r'^\s*(.*?)\s*}', re.MULTILINE)
        
        matches_with_comment = state_pattern_with_comment.findall(data)
        parsed_data = {}

        if matches_with_comment:
            for match in matches_with_comment:
                state, number, description = match
                description = re.sub(r'\s+', ' ', description.strip())  # Remove extra spaces and newlines
                parsed_data[state.strip()] = { 'value': number, 'description': description }
        else:
            matches_without_comment = state_pattern_without_comment.findall(data)
            for match in matches_without_comment:
                state, number = match
                parsed_data[state.strip()] = { 'value': number, 'description': None }
                
            matches_no_value = state_pattern_no_value.findall(data)
            for match in matches_no_value:
                state, description = match
                description = re.sub(r'\s+', ' ', description.strip())  # Remove extra spaces and newlines
                parsed_data[state.strip()] = { 'value': None, 'description': description }
                
            matches_no_value_no_comment = state_pattern_no_value_no_comment.findall(data)
            for match in matches_no_value_no_comment:
                state = match
                parsed_data[state.strip()] = { 'value': None, 'description': None }
                
            matches_last_no_value_no_comment = state_pattern_last_no_value_no_comment.findall(data)
            for match in matches_last_no_value_no_comment:
                state = match
                parsed_data[state.strip()] = { 'value': None, 'description': None }

        return parsed_data

    def parse_struct_data(self, data):
        field_pattern = re.compile(
            r'^\s*([\w\s\*\d]+?)\s+(\w+)\s*;\s*/\*!<\s*(.*?)\s*\*/', re.DOTALL | re.MULTILINE
        )

        matches = field_pattern.findall(data)
        parsed_data = {}

        for match in matches:
            field_type, name, description = match
            description = re.sub(r'\s+', ' ', description.strip())  # Remove extra spaces and newlines
            parsed_data[name.strip()] = { 'type': field_type.strip(), 'comment': description }

        return parsed_data

    def parse_fields(self, type, raw_data):
        if not re.search(r'[;,]', raw_data):
            return { 'name': raw_data }
        else:   
            if type == 'struct':
                parsed_data = self.parse_struct_data(raw_data)
                return { 'data': parsed_data }
            elif type == 'enum':
                parsed_data = self.parse_enum_data(raw_data)
                return { 'data': parsed_data }
            elif type == 'unknown':
                print("ERROR: Unknown Data Type")
            else: 
                pass

    def process_file(self, file_path, combined_struct):
        typedefs = self.find_typedefs(file_path)
        for typedef in typedefs:
            name = None
            known_type = None
            data = None
            for group in typedef:
                if group != '':
                    if known_type is None:
                        known_type = self.check_type(group)
                    else:
                        parsed_data = self.parse_fields(known_type, group)
                        if 'name' in parsed_data:
                            name = parsed_data['name']
                        elif 'data' in parsed_data:
                            data = parsed_data['data']
            if known_type and name:
                if known_type not in combined_struct:
                    combined_struct[known_type] = {}
                combined_struct[known_type][name] = data

    def process_directory(self, directory, combined_struct):
        for filename in os.listdir(directory):
            if filename.endswith(".h"):
                self.process_file(os.path.join(directory, filename), combined_struct)
