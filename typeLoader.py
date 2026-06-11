# Import Custom Types into Ghidra for More Efficient Bare Metal RE
#@author So11Deo6loria
#@category Bare Metal

import json
import os
import re
from collections import OrderedDict

import ghidra.app.script.GhidraScript
from ghidra.program.model.data import (
    CategoryPath,
    DataTypeConflictHandler,
    EnumDataType,
    StructureDataType,
    ByteDataType,
    UnsignedIntegerDataType,
    ArrayDataType,
    PointerDataType
)
from ghidra.util.task import TaskMonitor

class CreateCustomTypesScript(ghidra.app.script.GhidraScript):

    def __init__(self):
        self.category_path = CategoryPath("/CustomTypes")
        self.dataTypeManager = currentProgram.getDataTypeManager()
        self.createdEnums = []
        self.createdStructs = []
        self.customTypes = {}
        self.dataToCreate = {}

    def createEnum(self, enum_name, enum_data):
        enum_data_type = EnumDataType(self.category_path, enum_name, 4)

        for enum_key, enum_value in enum_data.items():
            try:
                if not isinstance(enum_value, dict):
                    print("Skipping malformed enum " + enum_key + " in " + enum_name)
                    continue

                if 'value' not in enum_value:
                    print("Skipping enum " + enum_key + " in " + enum_name + " (no value).")
                    continue

                value = int(enum_value['value'])
                comment = enum_value.get('comment', '')
                if comment is None:
                    comment = ""

                enum_data_type.add(enum_key, value, comment)
            except Exception as e:
                print("Error adding enum " + enum_key + " in " + enum_name + ": " + str(e))
                continue

        try:
            self.dataTypeManager.addDataType(enum_data_type, DataTypeConflictHandler.REPLACE_HANDLER)
            self.createdEnums.append(enum_name)
        except Exception as e:
            print("Error registering enum " + enum_name + ": " + str(e))

    def createPointer(self, pointed_to_data_type_name):
        pointed_to_data_type = None
        all_data_types = self.dataTypeManager.getAllDataTypes()
        for data_type in all_data_types:
            if data_type.getName() == pointed_to_data_type_name:
                pointed_to_data_type = data_type
                break

        if pointed_to_data_type is None:
            return PointerDataType(ByteDataType())  # fallback to byte pointer

        return PointerDataType(pointed_to_data_type)

    def createStruct(self, struct_name, struct_data):
        if 'struct' not in struct_data:
            print("Invalid struct definition for " + struct_name)
            return

        struct_fields = struct_data['struct']
        struct_data_type = StructureDataType(self.category_path, struct_name, 0)

        for field_name, field_info in struct_fields.items():
            try:
                if not isinstance(field_info, dict):
                    print("Skipping field " + field_name + " in " + struct_name + " (not a dict).")
                    continue

                data_type_str = field_info.get('type', 'uint32_t')
                comment = field_info.get('comment', '') or ""

                # Array handling: uint32_t[2]
                array_match = re.match(r'(\w+)\[(\d+)\]', data_type_str)
                if array_match:
                    base_type = array_match.group(1)
                    count = int(array_match.group(2))
                    struct_data_type.add(ArrayDataType(UnsignedIntegerDataType(), count, 4), field_name, comment)
                    continue

                # Pointer handling: void * or Type *
                if '*' in data_type_str:
                    base_type = data_type_str.replace('*', '').strip()
                    struct_data_type.add(self.createPointer(base_type), field_name, comment)
                    continue

                # Simple base types
                if data_type_str.startswith('uint') or data_type_str == 'int':
                    struct_data_type.add(UnsignedIntegerDataType(), field_name, comment)
                elif data_type_str in self.dataToCreate.get('enums', {}):
                    self.createEnum(data_type_str, self.dataToCreate['enums'][data_type_str])
                    struct_data_type.add(self.dataTypeManager.getDataType(self.category_path, data_type_str), field_name, comment)
                elif data_type_str in self.dataToCreate.get('structs', {}):
                    self.createStruct(data_type_str, self.dataToCreate['structs'][data_type_str])
                    struct_data_type.add(self.dataTypeManager.getDataType(self.category_path, data_type_str), field_name, comment)
                else:
                    struct_data_type.add(UnsignedIntegerDataType(), field_name, comment)

            except Exception as e:
                print("Error adding field " + field_name + " in struct " + struct_name + ": " + str(e))
                continue

        try:
            self.dataTypeManager.addDataType(struct_data_type, DataTypeConflictHandler.REPLACE_HANDLER)
            self.createdStructs.append(struct_name)
            self.customTypes[struct_name] = struct_data_type
        except Exception as e:
            print("Error registering struct " + struct_name + ": " + str(e))

    def run(self):
        script_directory = os.path.dirname(os.path.realpath(__file__))
        json_file_path = os.path.join(script_directory, "stmDataTypes.json")

        if not os.path.exists(json_file_path):
            print("JSON file not found at " + json_file_path)
            return

        with open(json_file_path, "r") as file:
            self.dataToCreate = json.loads(file.read(), object_pairs_hook=OrderedDict)

        # Create enums
        for enum_name, enum_def in self.dataToCreate.get("enums", {}).items():
            self.createEnum(enum_name, enum_def)

        # Create structs
        for struct_name, struct_def in self.dataToCreate.get("structs", {}).items():
            self.createStruct(struct_name, struct_def)

        print("Created Data Types:")
        print("\tEnums:")
        for e in self.createdEnums:
            print("\t\t" + e)
        print("\tStructs:")
        for s in self.createdStructs:
            print("\t\t" + s)


# Run script
createScript = CreateCustomTypesScript()
createScript.run()
