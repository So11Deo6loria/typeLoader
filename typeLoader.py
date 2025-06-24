# Import Custom Types into Ghidra for More Efficient Bare Metal RE
#@author So11Deo6loria So11Deo6loria@proton.me
#@category Bare Metal

# Miscellaneous Imports
import json
import os
import re
from collections import OrderedDict

# Import the necessary Ghidra modules
import ghidra.app.script.GhidraScript
from ghidra.program.model.data import CategoryPath, DataTypeConflictHandler, EnumDataType, StructureDataType, ByteDataType, UnsignedIntegerDataType, ArrayDataType, PointerDataType
from ghidra.util.task import TaskMonitor

class CreateCustomTypesScript(ghidra.app.script.GhidraScript):
    def __init__( self ):
        self.category_path = CategoryPath("/CustomTypes")
        
        # Get the current program's dataTypeManager
        self.dataTypeManager = currentProgram.getDataTypeManager()
        self.createdEnums = []
        self.createdStructs = []
        self.customTypes = {}
        self.dataToCreate = {}

    def convertType( self, type ):
        typeConversion = {
            'uint8_t': ByteDataType()
        }

        if( type in typeConversion ):
            return typeConversion[type] 
        else: 
            return type 

    def createEnum( self, enum_name, enum_data ):
        # Create an EnumDataType
        enum_data_type = EnumDataType(self.category_path, enum_name, 1)  # 1-byte size
        
        # Add enumeration values
        for enum_key, enum_value in enum_data.items():
            enum_data_type.add(enum_key, enum_value['value'], enum_value['comment'])
        
        # Add the enum to the data type manager
        self.dataTypeManager.addDataType(enum_data_type, DataTypeConflictHandler.DEFAULT_HANDLER) 
        self.createdEnums.append(enum_name)

    def createPointer(self, pointer_name, pointed_to_data_type_name):
        # Check if the custom data type exists project-wide
        pointed_to_data_type = None
        all_data_types = self.dataTypeManager.getAllDataTypes()

        for data_type in all_data_types:
            if data_type.getName() == pointed_to_data_type_name:
                pointed_to_data_type = data_type
                break

        if pointed_to_data_type is None:
            print("Custom data type not found.")
            return

        # Create a pointer data type using the existing custom data type as the pointed-to type
        pointer_data_type = PointerDataType(pointed_to_data_type)
        return pointer_data_type

    def createStruct( self, struct_name, struct_data ):
        # Create a StructureDataType
        struct_data_type = StructureDataType(self.category_path, struct_name, 0)

        # Add fields to the structure
        for struct_key, struct_value in struct_data['struct'].items():
            data_type = struct_value['type']
            comment = struct_value['comment']
            
            # Arrays - TODO: Handle non-uint32_t arrays. 
            pattern = r'(\w+)\s*\[(\d+)\]'
            match = re.match(pattern, data_type)   
            if match:
                data_type = match.group(1)
                array_size = int(match.group(2))
                
                custom_data_type = ArrayDataType(UnsignedIntegerDataType(), array_size, 4)
                struct_data_type.add(custom_data_type, struct_key, comment)
            # Pointers
            elif( '*' in data_type ): 
                pattern = r'(.*?) \*'
                match = re.match(pattern, data_type)                
                point_to_data_type = match.group(1)
                if( point_to_data_type == 'void' ):
                     voidPointerDataType = PointerDataType(self.dataTypeManager.getDataType(self.category_path, "void"))
                     struct_data_type.add(voidPointerDataType, struct_key, comment)
                else:
                    #pointer_data_type = self.createPointer( data_type, point_to_data_type )                    
                    #struct_data_type.add(pointer_data_type, struct_key, comment)
                    pointer_data_type = self.createPointer(data_type, point_to_data_type)
                    if pointer_data_type is not None:
                        struct_data_type.add(pointer_data_type, struct_key, comment)
                    else:
                        pass
                        #print(f"Warning: Could not create pointer to type '{point_to_data_type}' for field '{struct_key}' in struct '{struct_name}'")

            else:
                if( struct_value['type'] == 'uint32_t' ):
                    struct_data_type.add(UnsignedIntegerDataType(), struct_key, comment)                        
                else:
                    if( data_type in self.customTypes ):                    
                        struct_data_type.add(self.customTypes[data_type], struct_key, comment)
                    else:
                        # If there is an unknown type make a new one
                        for typeCategory in self.dataToCreate:
                            if( data_type in self.dataToCreate[typeCategory] ):
                                if( typeCategory == 'enums' ):
                                    self.createEnum( data_type, self.dataToCreate[typeCategory][data_type] )   
                                elif( typeCategory == 'structs' ):
                                    self.createStruct( data_type, self.dataToCreate[typeCategory][data_type] )   
        
        # Add the structure to the data type manager
        self.dataTypeManager.addDataType(struct_data_type, DataTypeConflictHandler.DEFAULT_HANDLER)
        self.createdStructs.append(struct_name)
        self.customTypes[struct_name] = struct_data_type

    def run(self):
        # Get the directory where the script is located
        script_directory = os.path.dirname(os.path.realpath(__file__))

        # Specify the full path to the JSON file
        json_file_path = os.path.join(script_directory, 'stmDataTypes.json')

        # Check if the JSON file exists before opening it
        if not os.path.exists(json_file_path):
            print("JSON file " + json_file_path + " not found.")
            return

        # Open the JSON file
        with open(json_file_path, 'r') as file:
            json_data = file.read()
        
        self.dataToCreate = json.loads(json_data, object_pairs_hook=OrderedDict)

        for enum in self.dataToCreate['enums']:
            self.createEnum( enum, self.dataToCreate['enums'][enum] )        
        
        for struct in self.dataToCreate['structs']:
            self.createStruct( struct, self.dataToCreate['structs'][struct] )    
        
        print("Created Data Types: ")
        print("\tEnums: ")
        for enum in self.createdEnums: 
            print("\t\t" + enum)
        print("\tStructs: ")
        for struct in self.createdStructs: 
            print("\t\t" + struct)            

# Create an instance of the script and run it
createScript = CreateCustomTypesScript()
createScript.run()