# Import Custom Types into Ghidra for More Efficient Bare Metal RE
#@author So11Deo6loria
#@category Bare Metal
#@runtime PyGhidra

import json
import os
import re
from collections import OrderedDict

from ghidra.program.model.data import (
    CategoryPath,
    DataTypeConflictHandler,
    EnumDataType,
    StructureDataType,
    ByteDataType,
    CharDataType,
    UnsignedCharDataType,
    UnsignedShortDataType,
    UnsignedIntegerDataType,
    IntegerDataType,
    ArrayDataType,
    PointerDataType,
)

# Match "uint32_t[2]" style array declarations.
ARRAY_RE = re.compile(r"([\w]+)\s*\[(\d+)\]")

# Friendly labels for the vendor type files, shown in the selection drop-down.
VENDOR_LABELS = {
    "stmDataTypes.json": "STMicroelectronics - STM32 HAL",
    "nxpDataTypes.json": "NXP - Kinetis / LPC / i.MX RT (MCUXpresso)",
    "microchipDataTypes.json": "Microchip / Atmel - SAM / PIC32",
    "nordicDataTypes.json": "Nordic - nRF52 / nRF53 (nrfx)",
    "tiDataTypes.json": "Texas Instruments - TM4C / Tiva (TivaWare)",
    "espressifDataTypes.json": "Espressif - ESP32 (ESP-IDF)",
    "renesasDataTypes.json": "Renesas - RA family (FSP)",
}

# Order the known vendors appear in the drop-down (unknown files follow, sorted).
VENDOR_ORDER = [
    "stmDataTypes.json",
    "nxpDataTypes.json",
    "microchipDataTypes.json",
    "nordicDataTypes.json",
    "tiDataTypes.json",
    "espressifDataTypes.json",
    "renesasDataTypes.json",
]

# Sentinel drop-down entry that drops back to the file picker.
BROWSE_LABEL = "Browse for a file..."

# Map C scalar type names to fixed-width Ghidra data types so register-block
# offsets (which depend on 1/2/4-byte field widths) stay correct.
SCALAR_TYPES = {
    "uint8_t": UnsignedCharDataType,
    "int8_t": CharDataType,
    "char": CharDataType,
    "uint16_t": UnsignedShortDataType,
    "int16_t": UnsignedShortDataType,
    "uint32_t": UnsignedIntegerDataType,
    "int32_t": IntegerDataType,
    "int": IntegerDataType,
}


def _coerce_int(raw):
    """Accept ints or C-style strings ("0x20", "0x20U", "12") and return an int."""
    if isinstance(raw, int):
        return raw
    text = str(raw).strip().rstrip("uUlL")
    return int(text, 0)


class CreateCustomTypesScript(object):
    def __init__(self, program):
        self.program = program
        self.category_path = CategoryPath("/CustomTypes")
        self.dataTypeManager = program.getDataTypeManager()
        self.createdEnums = []
        self.createdStructs = []
        self.customTypes = {}
        self.dataToCreate = {}

    def createEnum(self, enum_name, enum_data):
        enum_data_type = EnumDataType(self.category_path, enum_name, 4, self.dataTypeManager)

        for enum_key, enum_value in enum_data.items():
            try:
                if not isinstance(enum_value, dict):
                    print("Skipping malformed enum " + enum_key + " in " + enum_name)
                    continue

                if "value" not in enum_value or enum_value["value"] is None:
                    print("Skipping enum " + enum_key + " in " + enum_name + " (no value).")
                    continue

                value = _coerce_int(enum_value["value"])
                comment = enum_value.get("comment", "") or ""

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
        pointed_to_data_type = self.dataTypeManager.getDataType(
            self.category_path, pointed_to_data_type_name
        )

        # Fixed-width scalars and JSON forward references (e.g. "uint8_t *").
        if pointed_to_data_type is None:
            pointed_to_data_type = self._resolve_base_type(pointed_to_data_type_name)

        if pointed_to_data_type is None:
            for data_type in self.dataTypeManager.getAllDataTypes():
                if data_type.getName() == pointed_to_data_type_name:
                    pointed_to_data_type = data_type
                    break

        if pointed_to_data_type is None:
            return PointerDataType(ByteDataType())  # fallback to byte pointer (e.g. "void *")

        return PointerDataType(pointed_to_data_type)

    def _resolve_base_type(self, type_name):
        """Resolve a (non-array, non-pointer) base type name to a Ghidra DataType.

        Handles fixed-width scalars, already-created custom types, and forward
        references to enums/structs in the JSON (created on demand). Returns
        None if the name cannot be resolved.
        """
        type_name = type_name.strip()

        if type_name in SCALAR_TYPES:
            return SCALAR_TYPES[type_name]()

        # Already-registered custom type?
        existing = self.dataTypeManager.getDataType(self.category_path, type_name)
        if existing is not None:
            return existing

        # Forward reference into the JSON: create it now, then look it up.
        if type_name in self.dataToCreate.get("enums", {}):
            self.createEnum(type_name, self.dataToCreate["enums"][type_name])
            return self.dataTypeManager.getDataType(self.category_path, type_name)
        if type_name in self.dataToCreate.get("structs", {}):
            self.createStruct(type_name, self.dataToCreate["structs"][type_name])
            return self.dataTypeManager.getDataType(self.category_path, type_name)

        return None

    def createStruct(self, struct_name, struct_data):
        if "struct" not in struct_data:
            print("Invalid struct definition for " + struct_name)
            return

        struct_fields = struct_data["struct"]
        struct_data_type = StructureDataType(self.category_path, struct_name, 0, self.dataTypeManager)

        for field_name, field_info in struct_fields.items():
            try:
                if not isinstance(field_info, dict):
                    print("Skipping field " + field_name + " in " + struct_name + " (not a dict).")
                    continue

                data_type_str = field_info.get("type", "uint32_t")
                comment = field_info.get("comment", "") or ""

                # Array handling: uint32_t[2], uint8_t[16], MyType[4]
                array_match = ARRAY_RE.match(data_type_str)
                if array_match:
                    base_name = array_match.group(1)
                    count = int(array_match.group(2))
                    element_type = self._resolve_base_type(base_name)
                    if element_type is None:
                        element_type = UnsignedIntegerDataType()
                    struct_data_type.add(
                        ArrayDataType(element_type, count), field_name, comment
                    )
                    continue

                # Pointer handling: void * or Type *
                if "*" in data_type_str:
                    base_type = data_type_str.replace("*", "").strip()
                    struct_data_type.add(self.createPointer(base_type), field_name, comment)
                    continue

                # Simple base types (fixed-width scalars, enums, structs).
                resolved = self._resolve_base_type(data_type_str)
                if resolved is not None:
                    struct_data_type.add(resolved, field_name, comment)
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

    def _script_directory(self):
        try:
            return os.path.dirname(os.path.realpath(__file__))
        except NameError:
            return None

    def _discover_type_files(self):
        """Return [(label, path)] for every *DataTypes.json next to the script.

        Files with a known vendor label are listed first (in VENDOR_ORDER);
        any other *DataTypes.json files follow alphabetically.
        """
        script_directory = self._script_directory()
        if not script_directory or not os.path.isdir(script_directory):
            return []

        present = {
            name
            for name in os.listdir(script_directory)
            if name.endswith("DataTypes.json")
        }

        ordered = []
        for name in VENDOR_ORDER:
            if name in present:
                ordered.append(name)
                present.discard(name)
        ordered.extend(sorted(present))

        return [
            (
                VENDOR_LABELS.get(name, name) + "  (" + name + ")",
                os.path.join(script_directory, name),
            )
            for name in ordered
        ]

    def _locate_json(self):
        # Prompt the user to pick the vendor type file for their micro from a
        # drop-down of the *DataTypes.json files shipped alongside the script.
        choices = self._discover_type_files()
        if choices:
            labels = [label for label, _ in choices]
            labels.append(BROWSE_LABEL)
            try:
                selection = str(
                    askChoice(  # noqa: F821
                        "typeLoader",
                        "Select the type file for your micro:",
                        labels,
                        labels[0],
                    )
                )
                if selection != BROWSE_LABEL:
                    for label, path in choices:
                        if label == selection:
                            return path
            except Exception:
                pass  # askChoice unavailable (headless) or cancelled -> fall through

        # Either the user chose "Browse..." or no files were discovered: open a
        # file picker so any JSON on disk can be selected.
        try:
            return str(
                askFile("Select vendor types JSON (e.g. nxpDataTypes.json)", "Load")  # noqa: F821
                .getAbsolutePath()
            )
        except Exception:
            pass

        # Headless fallback: load a *DataTypes.json sitting next to the script,
        # preferring stmDataTypes.json for backwards compatibility.
        script_directory = self._script_directory()
        if script_directory and os.path.isdir(script_directory):
            preferred = os.path.join(script_directory, "stmDataTypes.json")
            if os.path.exists(preferred):
                return preferred
            for name in sorted(os.listdir(script_directory)):
                if name.endswith("DataTypes.json"):
                    return os.path.join(script_directory, name)

        return None

    def run(self):
        json_file_path = self._locate_json()

        if not json_file_path or not os.path.exists(json_file_path):
            print("JSON file not found (select a *DataTypes.json, e.g. nxpDataTypes.json).")
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


# Run script. `currentProgram` is injected into the script namespace by Ghidra.
CreateCustomTypesScript(currentProgram).run()  # noqa: F821
