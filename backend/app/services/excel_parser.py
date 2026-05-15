from openpyxl import load_workbook
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from pathlib import Path
import re


class ExcelParseError(Exception):
    pass


class ExcelParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.workbook = load_workbook(file_path, data_only=True)
        self.sheet = self.workbook.active

    def parse(self) -> Tuple[List[Dict], Optional[float], Optional[float]]:
        """Try to parse Excel with auto-detection of format"""
        # Try multi-sheet parsing first (for files like STOP FORCE HG II)
        if len(self.workbook.sheetnames) > 1:
            try:
                return self._parse_multi_sheet()
            except ExcelParseError:
                pass
        
        # Fall back to single sheet parsing
        parsers = [
            self._parse_fie_format,  # FIE format (MDS II, III, LIGHT II, STOP FORCE)
            self._parse_mds_format,  # Legacy MDS format
        ]
        
        for parser in parsers:
            try:
                data, temp, humidity = parser()
                if data:  # Only return if we got data
                    return data, temp, humidity
            except ExcelParseError:
                continue
        
        raise ExcelParseError("Could not detect Excel format")

    def get_test_session_metadata(self) -> Dict[str, Optional[str]]:
        """Extract test session metadata from Excel filename or content"""
        # Try to extract from filename first
        filename = Path(self.file_path).stem
        
        # Common patterns in ballistic test files
        metadata = {
            'name': filename,
            'lab_name': None,
            'operator': None,
            'protocol': None,
        }
        
        # Try to extract lab name from cell A1 or similar
        cell_a1 = self.sheet['A1'].value
        if cell_a1 and isinstance(cell_a1, str):
            # Check if it looks like a lab name
            if any(word in cell_a1.lower() for word in ['lab', 'laboratory', 'test', 'facility']):
                metadata['lab_name'] = cell_a1.strip()
        
        return metadata

    def parse_conditioning_and_size(self, cell_value: str) -> Dict[str, Optional[str]]:
        """Parse conditioning (seco/humedo), size (talle), and ballistic limit from cell value"""
        result = {
            'conditioning': None,
            'size': None,
            'ballistic_limit': False,
        }
        
        if not cell_value or not isinstance(cell_value, str):
            return result
        
        cell_lower = cell_value.lower()
        
        # Parse ballistic limit
        if 'lim ballistico' in cell_lower or 'limite balístico' in cell_lower:
            result['ballistic_limit'] = True
        
        # Parse conditioning
        if 'seco' in cell_lower:
            result['conditioning'] = 'dry'
        elif 'humedo' in cell_lower:
            result['conditioning'] = 'wet'
        
        # Parse size (talle)
        if 'talle' in cell_lower:
            # Look for size indicator after talle
            talle_idx = cell_lower.find('talle')
            remaining = cell_lower[talle_idx + 6:].strip()
            if remaining:
                size_char = remaining[0].upper()
                if size_char in ['S', 'M', 'L', 'XL', 'XXL']:
                    result['size'] = size_char
        
        return result

    def detect_multiple_tests(self) -> List[Dict[str, any]]:
        """Detect multiple tests in Excel (group front/back shots per vest)"""
        tests = []
        
        # Look for patterns that indicate separate tests
        # Check for vest numbers, conditioning changes, or size changes
        current_test_info = None
        current_side = None
        test_data = []
        
        for row in range(1, self.sheet.max_row + 1):
            cell_a_value = self.sheet[f'A{row}'].value
            cell_b_value = self.sheet[f'B{row}'].value if self.sheet.max_column >= 2 else None
            cell_c_value = self.sheet[f'C{row}'].value if self.sheet.max_column >= 3 else None
            
            if not cell_a_value and not cell_c_value:
                continue
            
            cell_a_str = str(cell_a_value).lower() if cell_a_value else ''
            cell_b_str = str(cell_b_value).lower() if cell_b_value else ''
            
            # Check if this row indicates a new test (SERIE header)
            # Look for vest numbers (e.g., "SERIE N°1", "SERIE N°2")
            vest_number = None
            if 'serie' in cell_a_str and any(char.isdigit() for char in cell_a_str):
                # Extract the first number as vest number
                import re
                numbers = re.findall(r'\d+', cell_a_str)
                if numbers:
                    vest_number = numbers[0]
            
            # Check for conditioning changes (seco/humedo/tumbled) - allowed values: ambient, wet, tumbled
            conditioning = None
            if 'seco' in cell_a_str or 'ambient' in cell_a_str:
                conditioning = 'ambient'
            elif 'humedo' in cell_a_str or 'wet' in cell_a_str:
                conditioning = 'wet'
            elif 'tumbled' in cell_a_str or 'tambaleado' in cell_a_str or 'girado' in cell_a_str:
                conditioning = 'tumbled'
            
            # Check for ballistic limit test
            if 'lim balistico' in cell_a_str or 'limite balistico' in cell_a_str or 'lim balístico' in cell_a_str or 'limite balístico' in cell_a_str:
                conditioning = 'ballistic_limit'
            
            # Check for size changes (talle)
            size = None
            if 'talle' in cell_a_str:
                talle_idx = cell_a_str.find('talle')
                remaining = cell_a_str[talle_idx + 6:].strip()
                if remaining:
                    size_char = remaining[0].upper()
                    if size_char in ['S', 'M', 'L', 'XL', 'XXL']:
                        size = size_char
            
            # Check for side changes (frente/espalda)
            side = None
            angle_degrees = None
            if 'frente' in cell_b_str or 'front' in cell_b_str:
                side = 'front'
            elif 'espalda' in cell_b_str or 'back' in cell_b_str:
                side = 'back'
            
            # Extract angle if present (e.g., "espalda 45°" -> 45)
            if side:
                import re
                angle_match = re.search(r'(\d+)\s*°', cell_b_str)
                if angle_match:
                    angle_degrees = float(angle_match.group(1))
            
            # Update current side if column B has a value
            if side:
                current_side = side
                current_angle = angle_degrees
            
            # If we found a vest number (SERIE header), consider this a new test group
            if vest_number:
                # Save previous test if exists
                if current_test_info and test_data:
                    tests.append({
                        'vest_number': current_test_info['vest_number'],
                        'conditioning': current_test_info.get('conditioning'),
                        'size': current_test_info.get('size'),
                        'data': test_data,
                    })
                    test_data = []
                
                current_test_info = {
                    'vest_number': vest_number,
                    'conditioning': conditioning,
                    'size': size,
                }
                current_side = side if side else None
                current_angle = angle_degrees if angle_degrees else None
            elif conditioning or size:
                # Update current test info if conditioning/size changed
                if current_test_info:
                    if conditioning:
                        current_test_info['conditioning'] = conditioning
                    if size:
                        current_test_info['size'] = size
            
            # Add row data if it looks like shot data
            # Check if column C has a shot number (numeric)
            if cell_c_value and isinstance(cell_c_value, (int, float)):
                test_data.append({'row': row, 'shot_number': cell_c_value, 'side': current_side, 'angle_degrees': current_angle})
        
        # Add last test
        if current_test_info and test_data:
            tests.append({
                'vest_number': current_test_info['vest_number'],
                'conditioning': current_test_info.get('conditioning'),
                'size': current_test_info.get('size'),
                'data': test_data,
            })
        
        # If no tests were detected but there's data, treat as single test
        if not tests and self.sheet.max_row > 1:
            tests.append({
                'vest_number': '1',
                'conditioning': None,
                'size': None,
                'data': [{'row': row, 'shot_number': self.sheet[f'C{row}'].value, 'side': None} for row in range(1, self.sheet.max_row + 1) if self.sheet.max_column >= 3 and isinstance(self.sheet[f'C{row}'].value, (int, float))],
            })
        
        return tests

    def _parse_multi_sheet(self) -> Tuple[List[Dict], Optional[float], Optional[float]]:
        """Parse multi-sheet Excel files (e.g., STOP FORCE HG II, Formulario de Ensayos Internos)"""
        all_data = []
        temperature = 22.0
        humidity = 50.0
        
        # Skip non-certification sheets (like "Ensayo C" for COMPOLITE testing, "Punzocortante")
        skip_sheets = ['Ensayo C', 'Probetas', 'COMPOLITE', 'Punzocortante', 'Puntas y cuchillas']
        
        # Detect if this is a Formulario file by filename
        is_formulario_file = 'formulario' in self.file_path.lower()
        
        for sheet_name in self.workbook.sheetnames:
            if any(skip_word in sheet_name.upper() for skip_word in skip_sheets):
                continue
            
            self.sheet = self.workbook[sheet_name]
            try:
                # Use Formulario format for Formulario files, FIE format otherwise
                if is_formulario_file:
                    sheet_data, sheet_temp, sheet_humidity = self._parse_formulario_interno_format()
                else:
                    sheet_data, sheet_temp, sheet_humidity = self._parse_fie_format()
                
                all_data.extend(sheet_data)
                # Use temperature/humidity from first valid sheet
                if temperature == 22.0 and sheet_temp:
                    temperature = sheet_temp
                if humidity == 50.0 and sheet_humidity:
                    humidity = sheet_humidity
            except ExcelParseError:
                continue
        
        if not all_data:
            raise ExcelParseError("No valid data found in any sheet")
        
        return all_data, temperature, humidity

    def _parse_fie_format(self) -> Tuple[List[Dict], Optional[float], Optional[float]]:
        """Parse FIE format (MDS II, III, LIGHT II, STOP FORCE)"""
        data = []
        
        # Extract temperature and humidity from row 2 (flexible position detection)
        temperature, humidity = self._extract_environmental_conditions()
        
        # Find header row (usually row 5, but detect dynamically)
        header_row = self._find_header_row()
        if not header_row:
            raise ExcelParseError("Could not find header row")
        
        # Map columns based on headers
        col_mapping = self._map_columns(header_row)
        
        # Track current side and angle across rows
        current_side = None
        current_angle = None
        
        # Parse data rows
        for row in range(header_row + 1, self.sheet.max_row + 1):
            vest_number = self.sheet.cell(row=row, column=col_mapping.get('vest_number', 1)).value
            side = self.sheet.cell(row=row, column=col_mapping.get('side', 2)).value
            shot_number = self.sheet.cell(row=row, column=col_mapping.get('shot_number', 3)).value
            protection_level = self.sheet.cell(row=row, column=col_mapping.get('protection_level', 4)).value
            caliber = self.sheet.cell(row=row, column=col_mapping.get('caliber', 5)).value
            trauma_mm = self.sheet.cell(row=row, column=col_mapping.get('trauma', 6)).value
            velocity_m_s = self.sheet.cell(row=row, column=col_mapping.get('velocity', 7)).value
            
            # Update current side if column B has a value
            if side:
                side_str = str(side).lower()
                # Normalize side values
                if 'frente' in side_str or 'front' in side_str:
                    current_side = 'front'
                elif 'espalda' in side_str or 'back' in side_str:
                    current_side = 'back'
                else:
                    current_side = side_str
                
                # Extract angle if present (e.g., "espalda 45°" -> 45)
                angle_match = re.search(r'(\d+)\s*°', side_str)
                if angle_match:
                    current_angle = float(angle_match.group(1))
                else:
                    current_angle = None
            
            # Skip empty rows
            if not vest_number and not shot_number:
                continue
            
            # Validate required fields
            if not shot_number:
                continue
            
            # Handle trauma: clean special characters, numeric values go to trauma_mm
            trauma_numeric = None
            trauma_qualitative = None
            if trauma_mm:
                trauma_str = str(trauma_mm).strip()
                # Remove arrows and other special characters
                trauma_clean = re.sub(r'[↑↓←→↔]', '', trauma_str)
                if trauma_clean.replace('.', '', 1).replace(',', '', 1).isdigit():
                    # Handle both decimal separators
                    trauma_clean = trauma_clean.replace(',', '.')
                    try:
                        trauma_numeric = Decimal(trauma_clean)
                    except:
                        pass
                elif trauma_clean.upper() in ['OK', 'PERFORO', 'PERFORACIÓN', 'PUNCTURED']:
                    trauma_qualitative = trauma_clean.upper()
            
            data.append({
                'row': row,
                'vest_number': str(vest_number) if vest_number else None,
                'side': current_side,
                'angle_degrees': current_angle,
                'shot_number': str(shot_number),
                'protection_level': str(protection_level) if protection_level else None,
                'caliber': str(caliber) if caliber else None,
                'trauma_mm': trauma_numeric,
                'trauma_qualitative': trauma_qualitative,
                'velocity_m_s': Decimal(str(velocity_m_s)) if velocity_m_s and str(velocity_m_s).replace('.', '', 1).replace(',', '', 1).isdigit() else None,
                'temperature_c': Decimal(str(temperature)),
                'humidity_percent': Decimal(str(humidity)),
            })
        
        if not data:
            raise ExcelParseError("No data found in Excel file")
        
        return data, temperature, humidity

    def _extract_environmental_conditions(self) -> Tuple[float, float]:
        """Extract temperature and humidity from row 2 with flexible position detection"""
        temperature = 22.0
        humidity = 50.0
        
        # Scan row 2 for temperature and humidity keywords
        for col in range(1, self.sheet.max_column + 1):
            cell_value = self.sheet.cell(row=2, column=col).value
            if cell_value:
                cell_str = str(cell_value).lower()
                # Look for temperature
                if 'temperatura' in cell_str or 'temp' in cell_str:
                    # Check adjacent cells for value
                    for offset in [-1, 1, 2]:
                        adjacent_col = col + offset
                        if 1 <= adjacent_col <= self.sheet.max_column:
                            adj_value = self.sheet.cell(row=2, column=adjacent_col).value
                            if adj_value:
                                adj_str = str(adj_value).strip()
                                # Extract numeric value (handles formats like "20°c", "20.5", "Amb. 20°c")
                                temp_match = re.search(r'(\d+\.?\d*)', adj_str)
                                if temp_match:
                                    try:
                                        temperature = float(temp_match.group(1))
                                    except:
                                        pass
                # Look for humidity
                if 'humedad' in cell_str or 'humidity' in cell_str:
                    # Check adjacent cells for value
                    for offset in [-1, 1, 2]:
                        adjacent_col = col + offset
                        if 1 <= adjacent_col <= self.sheet.max_column:
                            adj_value = self.sheet.cell(row=2, column=adjacent_col).value
                            if adj_value:
                                adj_str = str(adj_value).strip()
                                # Extract numeric value
                                humid_match = re.search(r'(\d+\.?\d*)', adj_str)
                                if humid_match:
                                    try:
                                        humidity = float(humid_match.group(1))
                                    except:
                                        pass
        
        return temperature, humidity

    def _find_header_row(self) -> Optional[int]:
        """Find the header row by looking for common column names"""
        for row in range(1, min(10, self.sheet.max_row + 1)):
            row_values = []
            for col in range(1, min(11, self.sheet.max_column + 1)):
                cell_value = self.sheet.cell(row=row, column=col).value
                if cell_value:
                    row_values.append(str(cell_value).lower())
            
            # Check if this row contains common header indicators
            header_indicators = ['disparos', 'shot', 'nivel', 'calibre', 'trauma', 'velocidad', 'vo', 'id']
            if any(indicator in ' '.join(row_values) for indicator in header_indicators):
                return row
        
        # Default to row 5 if no header found
        return 5 if self.sheet.max_row >= 5 else None

    def _map_columns(self, header_row: int) -> Dict[str, int]:
        """Map column names to column numbers based on header row"""
        mapping = {
            'vest_number': 1,  # Column A
            'side': 2,         # Column B
            'shot_number': 3,  # Column C
            'protection_level': 4,  # Column D
            'caliber': 5,      # Column E
            'trauma': 6,       # Column F
            'velocity': 7,     # Column G
        }
        
        # Try to detect actual column positions from headers
        for col in range(1, min(11, self.sheet.max_column + 1)):
            cell_value = self.sheet.cell(row=header_row, column=col).value
            if cell_value:
                cell_str = str(cell_value).lower()
                if 'disparo' in cell_str or 'shot' in cell_str:
                    mapping['shot_number'] = col
                elif 'nivel' in cell_str:
                    mapping['protection_level'] = col
                elif 'calibre' in cell_str or 'caliber' in cell_str:
                    mapping['caliber'] = col
                elif 'trauma' in cell_str:
                    mapping['trauma'] = col
                elif 'velocidad' in cell_str or 'vo' in cell_str or 'velocity' in cell_str:
                    mapping['velocity'] = col
        
        return mapping

    def _parse_formulario_interno_format(self) -> Tuple[List[Dict], Optional[float], Optional[float]]:
        """Parse Formulario de Ensayos Internos format (STOP II, MS II, DEF III)"""
        data = []
        
        # Extract temperature and humidity from row 2
        temperature, humidity = self._extract_environmental_conditions()
        
        # Find header row (usually row 6 for this format)
        header_row = 6  # Fixed for Formulario format
        if header_row > self.sheet.max_row:
            raise ExcelParseError("File has no data rows")
        
        # Use fixed column mapping for Formulario format
        col_mapping = {
            'material': 3,        # Column C - Comp.
            'shot_number': 5,     # Column E - Disparos
            'protection_level': 6, # Column F - Nivel
            'caliber': 7,         # Column G - Calibre
            'velocity': 8,        # Column H - Velocidad
            'trauma': 9,          # Column I - Trauma
        }
        
        # Track current side and material
        current_side = None
        current_material = None
        
        # Parse data rows
        for row in range(header_row + 1, self.sheet.max_row + 1):
            # Check for side/conditioning markers in column B
            cell_b = self.sheet.cell(row=row, column=2).value
            if cell_b and isinstance(cell_b, str):
                cell_b_str = cell_b.upper()
                
                # Detect side (even when combined with other text)
                if 'FRENTE' in cell_b_str or 'FRONT' in cell_b_str:
                    current_side = 'front'
                elif 'ESPALDA' in cell_b_str or 'BACK' in cell_b_str:
                    current_side = 'back'
                
                # Detect conditioning (even when combined with other text)
                if 'SECO' in cell_b_str or 'DRY' in cell_b_str:
                    current_conditioning = 'dry'
                elif 'HUMEDO' in cell_b_str or 'WET' in cell_b_str:
                    current_conditioning = 'wet'
            
            # Get material/composition from column C (only if present)
            cell_c = self.sheet.cell(row=row, column=3).value
            if cell_c and isinstance(cell_c, str) and cell_c.strip():
                current_material = cell_c.strip()
            
            # Get shot data
            shot_number = self.sheet.cell(row=row, column=col_mapping.get('shot_number', 5)).value
            protection_level = self.sheet.cell(row=row, column=col_mapping.get('protection_level', 6)).value
            caliber = self.sheet.cell(row=row, column=col_mapping.get('caliber', 7)).value
            velocity_m_s = self.sheet.cell(row=row, column=col_mapping.get('velocity', 8)).value
            trauma_mm = self.sheet.cell(row=row, column=col_mapping.get('trauma', 9)).value
            
            # Skip rows without shot numbers
            if not shot_number:
                continue
            
            # Handle trauma: clean special characters, handle ranges like "444 / 425"
            trauma_numeric = None
            if trauma_mm:
                trauma_str = str(trauma_mm).strip()
                # Remove arrows and special characters
                trauma_clean = re.sub(r'[↑↓←→↔/]', ' ', trauma_str)
                # Handle ranges - take first value
                trauma_values = trauma_clean.split()
                if trauma_values:
                    try:
                        trauma_numeric = Decimal(str(trauma_values[0]).replace(',', '.'))
                    except:
                        pass
            
            # Handle velocity ranges like "444 / 425"
            velocity_numeric = None
            if velocity_m_s:
                vel_str = str(velocity_m_s).strip()
                vel_clean = re.sub(r'[/]', ' ', vel_str)
                vel_values = vel_clean.split()
                if vel_values:
                    try:
                        velocity_numeric = Decimal(str(vel_values[0]).replace(',', '.'))
                    except:
                        pass
            
            data.append({
                'row': row,
                'vest_number': current_material,
                'side': current_side,
                'angle_degrees': None,
                'shot_number': str(shot_number),
                'protection_level': str(protection_level) if protection_level else None,
                'caliber': str(caliber) if caliber else None,
                'trauma_mm': trauma_numeric,
                'trauma_qualitative': None,
                'velocity_m_s': velocity_numeric,
                'temperature_c': Decimal(str(temperature)),
                'humidity_percent': Decimal(str(humidity)),
            })
        
        if not data:
            raise ExcelParseError("No data found in Excel file")
        
        return data, temperature, humidity

    def _map_columns_formulario(self, header_row: int) -> Dict[str, int]:
        """Map column names for Formulario de Ensayos Internos format"""
        mapping = {
            'material': 3,        # Column C - Comp.
            'shot_number': 5,     # Column E - Disparos
            'protection_level': 6, # Column F - Nivel
            'caliber': 7,         # Column G - Calibre
            'velocity': 8,        # Column H - Velocidad
            'trauma': 9,          # Column I - Trauma
        }
        
        # Try to detect actual column positions from headers - use first match
        for col in range(1, min(15, self.sheet.max_column + 1)):
            cell_value = self.sheet.cell(row=header_row, column=col).value
            if cell_value:
                cell_str = str(cell_value).lower()
                if 'comp.' in cell_str and mapping['material'] == 3:
                    mapping['material'] = col
                elif 'disparo' in cell_str or ('shot' in cell_str and mapping['shot_number'] == 5):
                    mapping['shot_number'] = col
                elif 'nivel' in cell_str and mapping['protection_level'] == 6:
                    mapping['protection_level'] = col
                elif 'calibre' in cell_str or ('caliber' in cell_str and mapping['caliber'] == 7):
                    mapping['caliber'] = col
                elif 'velocidad' in cell_str or ('vo' in cell_str and 'veloc' in cell_str and mapping['velocity'] == 8):
                    mapping['velocity'] = col
                elif 'trauma' in cell_str and 'mm' in cell_str and mapping['trauma'] == 9:
                    mapping['trauma'] = col
        
        return mapping

    def _parse_mds_format(self) -> Tuple[List[Dict], Optional[float], Optional[float]]:
        """Parse MDS II/III/LIGHT format"""
        data = []
        
        # Get temperature from F2, humidity from I2
        temp_cell = self.sheet['F2'].value
        humidity_cell = self.sheet['I2'].value
        
        temperature = float(temp_cell) if temp_cell else 22.0  # Default normal lab temp
        humidity = float(humidity_cell) if humidity_cell else 50.0  # Default normal humidity
        
        # Track current side (frente/espalda) across rows
        current_side = None
        current_angle = None
        
        # Start from row 3 (skip headers)
        for row in range(3, self.sheet.max_row + 1):
            vest_number = self.sheet[f'A{row}'].value
            side = self.sheet[f'B{row}'].value
            shot_number = self.sheet[f'C{row}'].value
            protection_level = self.sheet[f'D{row}'].value
            caliber = self.sheet[f'E{row}'].value
            trauma_mm = self.sheet[f'F{row}'].value
            velocity_m_s = self.sheet[f'G{row}'].value
            
            # Update current side if column B has a value
            if side:
                side_str = str(side).lower()
                # Normalize side values
                if 'frente' in side_str or 'front' in side_str:
                    current_side = 'front'
                elif 'espalda' in side_str or 'back' in side_str:
                    current_side = 'back'
                else:
                    current_side = side_str  # Keep original if not recognized
                
                # Extract angle if present (e.g., "espalda 45°" -> 45)
                import re
                angle_match = re.search(r'(\d+)\s*°', side_str)
                if angle_match:
                    current_angle = float(angle_match.group(1))
                else:
                    current_angle = None
            
            # Skip empty rows
            if not vest_number and not shot_number:
                continue
            
            # Validate required fields
            if not shot_number:
                raise ExcelParseError(f"Missing shot number in row {row}")
            
            # Handle trauma: numeric values go to trauma_mm, qualitative values go to trauma_qualitative
            trauma_numeric = None
            trauma_qualitative = None
            if trauma_mm:
                trauma_str = str(trauma_mm)
                if trauma_str.replace('.', '', 1).isdigit():
                    trauma_numeric = Decimal(trauma_str)
                else:
                    trauma_qualitative = trauma_str.upper() if trauma_str.upper() in ['OK', 'PERFORO'] else trauma_str

            data.append({
                'row': row,
                'vest_number': str(vest_number) if vest_number else None,
                'side': current_side,
                'angle_degrees': current_angle,
                'shot_number': str(shot_number),
                'protection_level': str(protection_level) if protection_level else None,
                'caliber': str(caliber) if caliber else None,
                'trauma_mm': trauma_numeric,
                'trauma_qualitative': trauma_qualitative,
                'velocity_m_s': Decimal(str(velocity_m_s)) if velocity_m_s and str(velocity_m_s).replace('.', '', 1).isdigit() else None,
                'temperature_c': Decimal(str(temperature)),
                'humidity_percent': Decimal(str(humidity)),
            })
        
        if not data:
            raise ExcelParseError("No data found in Excel file")
        
        return data, temperature, humidity
