from openpyxl import load_workbook
from typing import List, Dict, Optional, Tuple, Union
from decimal import Decimal
from pathlib import Path
import re
from datetime import datetime


class ExcelParseError(Exception):
    pass


class ExcelParser:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.workbook = load_workbook(file_path, data_only=True)
        self.sheet = self.workbook.active

    def parse(self) -> Union[Tuple[List[Dict], Optional[float], Optional[float]], Dict[str, Tuple[List[Dict], Optional[float], Optional[float]]]]:
        """Try to parse Excel with auto-detection of format
        
        Returns:
            For single-sheet files: (data, temperature, humidity)
            For multi-sheet files: {sheet_name: (data, temperature, humidity)}
        """
        # Try multi-sheet parsing first (for new standard format with multiple TALLE sheets)
        if len(self.workbook.sheetnames) > 1:
            try:
                return self._parse_multi_sheet()
            except ExcelParseError:
                pass
        
        # Fall back to single sheet parsing (legacy support)
        parsers = [
            self._parse_fie_format,  # FIE format (standard format)
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

    def extract_test_date(self) -> Dict[str, Optional[any]]:
        """Extract test date from filename or C2 cell, handling Spanish and English formats
        
        Returns:
            Dict with keys:
            - 'date': parsed date as ISO string (YYYY-MM-DD) or None
            - 'ambiguous': True if date is ambiguous (e.g., 01/02/25), False otherwise
            - 'source': 'filename' or 'cell' or None
        """
        result = {
            'date': None,
            'ambiguous': False,
            'source': None
        }
        
        # Try to extract from filename first
        filename = Path(self.file_path).stem
        filename_date = self._parse_date_from_string(filename)
        if filename_date:
            result.update(filename_date)
            result['source'] = 'filename'
            return result
        
        # Try to extract from C2 cell
        cell_c2 = self.sheet['C2'].value
        if cell_c2:
            # Handle datetime objects directly
            if isinstance(cell_c2, datetime):
                date_str = cell_c2.strftime('%Y-%m-%d')
                result['date'] = date_str
                result['ambiguous'] = False
                result['source'] = 'cell'
                return result
            else:
                cell_c2_str = str(cell_c2).strip()
                cell_date = self._parse_date_from_string(cell_c2_str)
                if cell_date:
                    result.update(cell_date)
                    result['source'] = 'cell'
                    return result
        
        return result

    def _parse_date_from_string(self, text: str) -> Optional[Dict[str, any]]:
        """Parse date from string, trying both Spanish (DD/MM/YY) and English (MM/DD/YY) formats
        
        Returns:
            Dict with keys:
            - 'date': parsed date as ISO string (YYYY-MM-DD) or None
            - 'ambiguous': True if date is ambiguous, False otherwise
        """
        if not text:
            return None
        
        # Common date patterns (including underscore separator)
        patterns = [
            # DD/MM/YY or DD/MM/YYYY
            r'(\d{1,2})/(\d{1,2})/(\d{2,4})',
            # DD-MM-YY or DD-MM-YYYY
            r'(\d{1,2})-(\d{1,2})-(\d{2,4})',
            # DD.MM.YY or DD.MM.YYYY
            r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})',
            # DD_MM_YY or DD_MM_YYYY
            r'(\d{1,2})_(\d{1,2})_(\d{2,4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                day, month, year = match.groups()
                
                # Normalize year (handle 2-digit years)
                if len(year) == 2:
                    year_int = int(year)
                    year = '20' + year if year_int < 50 else '19' + year
                
                day = int(day)
                month = int(month)
                year = int(year)
                
                # Check if date is ambiguous (both day and month <= 12)
                is_ambiguous = day <= 12 and month <= 12
                
                # Try Spanish format first (DD/MM)
                spanish_date = self._validate_and_format_date(day, month, year)
                
                # Try English format (MM/DD)
                english_date = self._validate_and_format_date(month, day, year)
                
                if spanish_date and english_date:
                    if is_ambiguous:
                        # Both valid and ambiguous - return both options
                        return {
                            'date': spanish_date,  # Default to Spanish
                            'ambiguous': True,
                            'spanish_date': spanish_date,
                            'english_date': english_date
                        }
                    else:
                        # Not ambiguous - use the one that's valid
                        return {
                            'date': spanish_date,
                            'ambiguous': False
                        }
                elif spanish_date:
                    return {
                        'date': spanish_date,
                        'ambiguous': False
                    }
                elif english_date:
                    return {
                        'date': english_date,
                        'ambiguous': False
                    }
        
        return None

    def _validate_and_format_date(self, day: int, month: int, year: int) -> Optional[str]:
        """Validate date and return as ISO string if valid"""
        try:
            datetime(year=year, month=month, day=day)
            return f"{year:04d}-{month:02d}-{day:02d}"
        except ValueError:
            return None

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

    def _parse_multi_sheet(self) -> Dict[str, List[Tuple[List[Dict], Optional[float], Optional[float], str]]]:
        """Parse multi-sheet Excel files (e.g., STOP FORCE HG II, Formulario de Ensayos Internos)
        
        Returns:
            Dict mapping sheet_name to list of (data, temperature, humidity, series_identifier) for each series in the sheet
        """
        sheets_data = {}
        
        # Skip non-certification sheets (like "Ensayo C" for COMPOLITE testing, "Punzocortante")
        skip_sheets = ['Ensayo C', 'Probetas', 'COMPOLITE', 'Punzocortante', 'Puntas y cuchillas']
        
        # Detect if this is a Formulario file by filename
        is_formulario_file = 'formulario' in self.file_path.lower()
        
        # Parse all sheets (for files with different sizes on different sheets like MDS files)
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
                
                # For MDS-style files with multiple series, split data by series
                # Check if we have multiple series by looking for "SERIE N°X" pattern in vest_number
                series_data = []
                current_series_data = []
                current_series_id = None
                current_conditioning = None
                
                for row in sheet_data:
                    if row.get('vest_number') and 'SERIE' in str(row['vest_number']).upper():
                        # Save previous series data if exists
                        if current_series_data:
                            series_data.append((current_series_data, sheet_temp, sheet_humidity, current_series_id, current_conditioning))
                        # Start new series
                        current_series_id = str(row['vest_number'])
                        current_series_data = [row]
                        # Parse conditioning from series_id
                        series_id_upper = str(row['vest_number']).upper()
                        if 'SECO' in series_id_upper or 'AMBIENT' in series_id_upper or 'DRY' in series_id_upper:
                            current_conditioning = 'ambient'
                        elif 'HUMEDO' in series_id_upper or 'WET' in series_id_upper:
                            current_conditioning = 'wet'
                        elif 'TUMBLED' in series_id_upper or 'TAMBALEADO' in series_id_upper or 'GIRADO' in series_id_upper:
                            current_conditioning = 'tumbled'
                        elif 'LIM BALISTICO' in series_id_upper or 'LIMITE BALISTICO' in series_id_upper or 'LIM BALÍSTICO' in series_id_upper or 'LIMITE BALÍSTICO' in series_id_upper:
                            current_conditioning = 'ballistic_limit'
                        else:
                            current_conditioning = None
                    else:
                        # Add to current series
                        current_series_data.append(row)
                
                # Don't forget the last series
                if current_series_data:
                    series_data.append((current_series_data, sheet_temp, sheet_humidity, current_series_id, current_conditioning))
                
                # If no series markers found, treat entire sheet as one series
                if not series_data and sheet_data:
                    series_data.append((sheet_data, sheet_temp, sheet_humidity, sheet_name, None))
                
                if series_data:
                    sheets_data[sheet_name] = series_data
            except ExcelParseError:
                continue
        
        if not sheets_data:
            raise ExcelParseError("No valid data found in any sheet")
        
        return sheets_data

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
                # Skip "-" values (no trauma measurement) - these are typically back side shots
                if trauma_str == '-' or trauma_str.lower() in ['none', 'n/a', '']:
                    # Skip this row entirely if it has no trauma data
                    continue
                else:
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
                    # Check adjacent cells for value (including current cell if it contains value)
                    for offset in [0, -1, 1, 2]:
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
                    # Check adjacent cells for value (including current cell if it contains value)
                    for offset in [0, -1, 1, 2]:
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
            # Require at least 2 of the main data columns to avoid label rows
            header_indicators = ['disparos', 'shot', 'nivel', 'calibre', 'trauma', 'velocidad', 'vo', 'id']
            matched_indicators = sum(1 for indicator in header_indicators if indicator in ' '.join(row_values))
            
            # Require at least 2 indicators to be considered a header row
            # This avoids matching label rows that only have "nivel" or a single indicator
            if matched_indicators >= 2:
                return row
        
        # Default to row 5 if no header found
        return 5 if self.sheet.max_row >= 5 else None

    def _map_columns(self, header_row: int) -> Dict[str, int]:
        """Map column names to column numbers based on header row"""
        mapping = {
            'vest_number': 1,  # Column A
            'side': 2,         # Column B
            'shot_number': 3,  # Column C
            'protection_level': None,  # Will be detected from "Nivel" header
            'caliber': None,      # Will be detected from "Calibre" header
            'trauma': None,       # Will be detected from "Trauma" header
            'velocity': None,     # Will be detected from "Velocidad" header
        }
        
        # Try to detect actual column positions from headers
        # Track if we've found the preferred trauma column
        found_trauma = False
        found_velocity = False
        
        for col in range(1, min(15, self.sheet.max_column + 1)):
            cell_value = self.sheet.cell(row=header_row, column=col).value
            if cell_value:
                cell_str = str(cell_value).lower()
                if 'disparo' in cell_str or 'shot' in cell_str:
                    if not mapping['shot_number']:
                        mapping['shot_number'] = col
                elif 'nivel' in cell_str:
                    if not mapping['protection_level']:
                        mapping['protection_level'] = col
                elif 'calibre' in cell_str or 'caliber' in cell_str:
                    if not mapping['caliber']:
                        mapping['caliber'] = col
                elif 'trauma' in cell_str and 'promedio' not in cell_str and not found_trauma:
                    # Prefer "Trauma (mm)" over "Trauma Promedio" etc.
                    # Only set if we haven't found a trauma column yet
                    mapping['trauma'] = col
                    found_trauma = True
                elif ('velocidad' in cell_str or 'vo' in cell_str or 'velocity' in cell_str) and not found_velocity:
                    mapping['velocity'] = col
                    found_velocity = True
        
        # Set fallback values if not detected
        if not mapping['protection_level']:
            mapping['protection_level'] = 4
        if not mapping['caliber']:
            mapping['caliber'] = 5
        if not mapping['trauma']:
            mapping['trauma'] = 6
        if not mapping['velocity']:
            mapping['velocity'] = 7
        
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
                # Skip "-" values (no trauma measurement)
                if trauma_str == '-' or trauma_str.lower() in ['none', 'n/a', '']:
                    # Skip this row entirely if it has no trauma data
                    continue
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
                trauma_str = str(trauma_mm).strip()
                # Skip "-" values (no trauma measurement)
                if trauma_str == '-' or trauma_str.lower() in ['none', 'n/a', '']:
                    # Skip this row entirely if it has no trauma data
                    continue
                # Skip "Average" rows
                if trauma_str.lower() == 'average' or trauma_str.lower() == 'promedio':
                    continue
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
