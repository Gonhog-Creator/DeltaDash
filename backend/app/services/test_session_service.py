from typing import List, Dict, Optional, Union, Tuple, Set
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.db.models import TestSession as TestSessionModel, ShotData as ShotDataModel, Ammunition as AmmunitionModel
from app.services.excel_parser import ExcelParser, ExcelParseError


def normalize_caliber(caliber: str) -> str:
    """Normalize caliber string for intelligent matching."""
    if not caliber:
        return ''
    
    normalized = str(caliber).strip().lower()
    
    # Remove common suffixes from ammunition names
    suffixes_to_remove = ['fmj standard', 'standard', 'fmj', 'winchester', 'remington', 'magnum', 'mag']
    for suffix in suffixes_to_remove:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)].strip()
    
    # Remove spaces around numbers
    normalized = normalized.replace(' ', '')
    
    # Normalize decimal points
    normalized = normalized.replace(',', '.')
    
    # Remove leading/trailing dots
    normalized = normalized.strip('.')
    
    # Remove leading zeros from numbers (e.g., "0.357" -> ".357", "0.44" -> ".44")
    # But preserve the decimal point
    if normalized and normalized[0] == '0' and len(normalized) > 1 and normalized[1] == '.':
        normalized = normalized[1:]  # Remove leading zero, keep the dot
    
    # Common caliber aliases for matching
    caliber_aliases = {
        '9mm': '9x19mm',
        '9x19': '9x19mm',
        '357': '357mag',
        '44': '44mag',
        '308': '308win',
        '308win': '308winchester',
        '223': '223rem',
        '762x51mm': '7.62x51mm',
        '556x45mm': '5.56x45mm',
        '556nato': '5.56x45mm',
    }
    
    # For decimal-only calibers (like .357, .44), also try without the dot (357, 44)
    # This handles cases where database has "357" but Excel has ".357" or "0.357"
    if normalized and normalized[0] == '.' and normalized.replace('.', '').isdigit():
        # It's a decimal number like .357 - add version without dot to aliases
        caliber_aliases[normalized] = normalized[1:]  # ".357" -> "357"
    
    return caliber_aliases.get(normalized, normalized)


def get_standardized_caliber(db: Session, raw_caliber: str) -> Optional[str]:
    """Get the standardized caliber name from the database for a raw caliber string."""
    if not raw_caliber:
        return None
    
    # Filter out column header names
    excluded_names = {'calibre', 'caliber', 'calibres', 'calibers'}
    if raw_caliber.lower() in excluded_names:
        return None
    
    # Get all existing calibers from database
    # Try caliber column first, fall back to name column if caliber is empty
    caliber_ammo = db.query(AmmunitionModel.caliber).filter(
        AmmunitionModel.caliber.isnot(None),
        AmmunitionModel.caliber != ''
    ).all()
    
    if not caliber_ammo:
        # If caliber column is empty, use name column
        caliber_ammo = db.query(AmmunitionModel.name).filter(
            AmmunitionModel.name.isnot(None),
            AmmunitionModel.name != ''
        ).all()
    
    existing_calibers_normalized = {
        normalize_caliber(caliber[0]): caliber[0] for caliber in caliber_ammo
    }
    
    normalized_input = normalize_caliber(raw_caliber)
    
    # Try exact match first (normalized)
    if normalized_input in existing_calibers_normalized:
        return existing_calibers_normalized[normalized_input]
    
    # Try fuzzy matching for common variations
    for existing_norm in existing_calibers_normalized:
        # Check if one is a substring of the other (for cases like "9mm" vs "9 mm")
        if normalized_input in existing_norm or existing_norm in normalized_input:
            return existing_calibers_normalized[existing_norm]
        
        # Check for common variations (e.g., .357 vs .357 mag)
        # Remove dots, spaces, and "mag" for comparison
        input_stripped = normalized_input.replace('.', '').replace(' ', '').replace('mag', '')
        existing_stripped = existing_norm.replace('.', '').replace(' ', '').replace('mag', '')
        if input_stripped == existing_stripped:
            return existing_calibers_normalized[existing_norm]
    
    # No match found, return original
    return raw_caliber


def validate_calibers_exist(db: Session, calibers: Set[str]) -> Set[str]:
    """Check if all calibers exist in the ammunition database. Returns missing calibers."""
    if not calibers:
        return set()
    
    # Filter out column header names and empty strings
    excluded_names = {'calibre', 'caliber', 'calibres', 'calibers'}
    calibers_to_check = {c for c in calibers if c and c.lower() not in excluded_names}
    
    if not calibers_to_check:
        return set()
    
    # Get all existing calibers from database with their IDs
    # Try caliber column first, fall back to name column if caliber is empty
    caliber_ammo = db.query(AmmunitionModel.caliber).filter(
        AmmunitionModel.caliber.isnot(None),
        AmmunitionModel.caliber != ''
    ).all()
    
    if not caliber_ammo:
        # If caliber column is empty, use name column
        caliber_ammo = db.query(AmmunitionModel.name).filter(
            AmmunitionModel.name.isnot(None),
            AmmunitionModel.name != ''
        ).all()
    
    existing_calibers_normalized = {
        normalize_caliber(caliber[0]): caliber[0] for caliber in caliber_ammo
    }
    
    # Normalize input calibers and check which are missing
    missing_calibers = set()
    for caliber in calibers_to_check:
        normalized_input = normalize_caliber(caliber)
        
        # Try exact match first (normalized)
        if normalized_input in existing_calibers_normalized:
            continue
        
        # Try fuzzy matching for common variations
        found_match = False
        for existing_norm in existing_calibers_normalized:
            # Check if one is a substring of the other (for cases like "9mm" vs "9 mm")
            if normalized_input in existing_norm or existing_norm in normalized_input:
                found_match = True
                break
            
            # Check for common variations (e.g., .357 vs .357 mag)
            # Remove dots, spaces, and "mag" for comparison
            input_stripped = normalized_input.replace('.', '').replace(' ', '').replace('mag', '')
            existing_stripped = existing_norm.replace('.', '').replace(' ', '').replace('mag', '')
            if input_stripped == existing_stripped:
                found_match = True
                break
        
        if not found_match:
            missing_calibers.add(caliber)
    
    return missing_calibers


def create_sessions_from_excel_data(
    db: Session,
    excel_file_path: str,
    test_name: str,
    location_name: Optional[str],
    protocol: Optional[str],
    vest_id: Optional[str],
    test_date: Optional[str],
    temperature: Optional[float],
    humidity: Optional[float],
    is_full_path: bool = False,
    is_official: Optional[bool] = False,
) -> List[TestSessionModel]:
    """Create test sessions from Excel file data."""
    import os
    from app.core.config import settings
    
    full_path = excel_file_path if is_full_path else os.path.join(settings.material_docs_dir, excel_file_path)
    parser = ExcelParser(full_path)
    parsed_data = parser.parse()
    
    # Check if parser returned multi-sheet data (dict) or single-sheet data (tuple)
    if isinstance(parsed_data, dict):
        # Multi-sheet file - validate calibers first
        all_calibers = set()
        for sheet_name, series_list in parsed_data.items():
            for shot_data, _, _, _, _ in series_list:
                for shot in shot_data:
                    if shot.get('caliber'):
                        all_calibers.add(str(shot['caliber']).strip())
        
        missing_calibers = validate_calibers_exist(db, all_calibers)
        if missing_calibers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "missing_ammunition",
                    "message": f"The following calibers are not in the ammunition database and cannot be matched: {', '.join(missing_calibers)}",
                    "missing_calibers": list(missing_calibers)
                }
            )
        
        # Multi-sheet file - create separate test sessions for each sheet
        return _create_sessions_from_multi_sheet(
            db, parsed_data, test_name, location_name, protocol, vest_id, test_date, excel_file_path, is_official
        )
    else:
        # Single-sheet file - extract size from sheet name
        size = None
        sheet_name = parser.sheet.title
        sheet_name_upper = sheet_name.upper()
        # Look for TALLE or SIZE keyword
        for keyword in ['TALLE', 'SIZE']:
            if keyword in sheet_name_upper:
                parts = sheet_name_upper.split()
                for i, part in enumerate(parts):
                    if part == keyword and i + 1 < len(parts):
                        size = parts[i + 1]
                        break
                if size:
                    break
        
        conditioning_size = parser.parse_conditioning_and_size(parser.sheet['A1'].value if parser.sheet['A1'].value else '')
        # Override size from sheet name
        if size:
            conditioning_size['size'] = size
        
        multiple_tests = parser.detect_multiple_tests()
        shot_data, _, _ = parsed_data
        
        # Validate calibers exist in database
        all_calibers = set()
        for shot in shot_data:
            if shot.get('caliber'):
                all_calibers.add(str(shot['caliber']).strip())
        
        missing_calibers = validate_calibers_exist(db, all_calibers)
        if missing_calibers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "missing_ammunition",
                    "message": f"The following calibers are not in the ammunition database and cannot be matched: {', '.join(missing_calibers)}",
                    "missing_calibers": list(missing_calibers)
                }
            )
        
        if multiple_tests:
            parent_session = TestSessionModel(
                name=test_name,
                lab_name=location_name,
                protocol=protocol,
                test_date=test_date,
                ambient_temperature_c=temperature,
                humidity_percent=humidity,
                vest_id=vest_id,
                excel_file_path=excel_file_path,
                is_official=is_official,
            )
            db.add(parent_session)
            db.commit()
            db.refresh(parent_session)
            
            created_sessions = []
            for i, test_info in enumerate(multiple_tests):
                test_conditioning = test_info.get('conditioning')
                test_size = test_info.get('size')
                
                # Get shots for this test
                test_rows = {item['row'] for item in test_info['data']}
                test_shots = [shot for shot in shot_data if shot.get('row') in test_rows]
                
                # Skip test if all shots have no velocity, no trauma, and no caliber
                has_velocity = any(shot.get('velocity_m_s') for shot in test_shots)
                has_trauma = any(shot.get('trauma_mm') for shot in test_shots)
                has_caliber = any(shot.get('caliber') for shot in test_shots)
                
                if not has_velocity and not has_trauma and not has_caliber:
                    continue  # Skip this test
                
                db_test_session = TestSessionModel(
                    name=f"{test_name} - Vest {test_info['vest_number']}",
                    lab_name=location_name,
                    protocol=protocol,
                    test_date=test_date,
                    ambient_temperature_c=temperature,
                    humidity_percent=humidity,
                    conditioning=test_conditioning,
                    size=test_size,
                    ballistic_limit=False,
                    parent_test_group_id=parent_session.id,
                    vest_id=vest_id,
                    excel_file_path=excel_file_path,
                    is_official=is_official,
                )
                db.add(db_test_session)
                db.commit()
                db.refresh(db_test_session)
                
                for shot in test_shots:
                    shot_copy = {k: v for k, v in shot.items() if k != 'row'}
                    # Standardize caliber to match database value
                    if shot_copy.get('caliber'):
                        shot_copy['caliber'] = get_standardized_caliber(db, shot_copy['caliber'])
                    shot_data_db = ShotDataModel(
                        test_session_id=db_test_session.id,
                        **shot_copy
                    )
                    db.add(shot_data_db)
                
                db.commit()
                db.refresh(db_test_session)
                created_sessions.append(db_test_session)
            
            return created_sessions
        else:
            db_test_session = TestSessionModel(
                name=test_name,
                lab_name=location_name,
                protocol=protocol,
                test_date=test_date,
                ambient_temperature_c=temperature,
                humidity_percent=humidity,
                conditioning=conditioning_size.get('conditioning'),
                size=conditioning_size.get('size'),
                ballistic_limit=conditioning_size.get('ballistic_limit', False),
                vest_id=vest_id,
                excel_file_path=excel_file_path,
                is_official=is_official,
            )
            db.add(db_test_session)
            db.commit()
            db.refresh(db_test_session)
            
            for shot in shot_data:
                # Standardize caliber to match database value
                shot_copy = shot.copy()
                if shot_copy.get('caliber'):
                    shot_copy['caliber'] = get_standardized_caliber(db, shot_copy['caliber'])
                shot_data_db = ShotDataModel(
                    test_session_id=db_test_session.id,
                    **shot_copy
                )
                db.add(shot_data_db)
            
            db.commit()
            db.refresh(db_test_session)
            return [db_test_session]


def _create_sessions_from_multi_sheet(
    db: Session,
    sheets_data: Dict[str, List[Tuple[List[Dict], Optional[float], Optional[float], str, Optional[str]]]],
    test_name: str,
    location_name: Optional[str],
    protocol: Optional[str],
    vest_id: Optional[str],
    test_date: Optional[str],
    excel_file_path: str,
    is_official: Optional[bool] = False,
) -> List[TestSessionModel]:
    """Create test sessions from multi-sheet Excel data (parent + child sessions per series per sheet)."""
    # Create parent session
    # Use temperature/humidity from first series of first sheet
    first_sheet_series = list(sheets_data.values())[0][0]
    _, temperature, humidity, _, _ = first_sheet_series
    
    parent_session = TestSessionModel(
        name=test_name,
        lab_name=location_name,
        protocol=protocol,
        test_date=test_date,
        ambient_temperature_c=temperature,
        humidity_percent=humidity,
        vest_id=vest_id,
        excel_file_path=excel_file_path,
        is_official=is_official,
    )
    db.add(parent_session)
    db.commit()
    db.refresh(parent_session)
    
    created_sessions = []
    
    # Create child session for each series in each sheet
    for sheet_name, series_list in sheets_data.items():
        # Extract size from sheet name (e.g., "TALLE S" -> "S", "SIZE M" -> "M")
        size = None
        sheet_name_upper = sheet_name.upper()
        for keyword in ['TALLE', 'SIZE']:
            if keyword in sheet_name_upper:
                parts = sheet_name_upper.split()
                for i, part in enumerate(parts):
                    if part == keyword and i + 1 < len(parts):
                        size = parts[i + 1]
                        break
                if size:
                    break
        
        for shot_data, sheet_temp, sheet_humidity, series_id, conditioning in series_list:
            # Skip series if all shots have no velocity, no trauma, and no caliber
            has_velocity = any(shot.get('velocity_m_s') for shot in shot_data)
            has_trauma = any(shot.get('trauma_mm') for shot in shot_data)
            has_caliber = any(shot.get('caliber') for shot in shot_data)
            
            if not has_velocity and not has_trauma and not has_caliber:
                continue  # Skip this series
            
            # Determine ballistic limit from conditioning
            ballistic_limit = conditioning == 'ballistic_limit'
            
            # Extract series number from series_id (e.g., "SERIE N°1" -> "1")
            series_number = None
            if series_id:
                import re
                match = re.search(r'N°\s*(\d+)', series_id.upper())
                if match:
                    series_number = match.group(1)
            
            # Format conditioning for display
            conditioning_display = conditioning.capitalize() if conditioning else 'N/A'
            
            # Create simplified name: "1 - S - Wet"
            name_parts = []
            if series_number:
                name_parts.append(series_number)
            if size:
                name_parts.append(size)
            if conditioning_display:
                name_parts.append(conditioning_display)
            
            child_name = ' - '.join(name_parts) if name_parts else series_id or 'Unknown'
            
            # Create child test session for this series
            db_test_session = TestSessionModel(
                name=child_name,
                lab_name=location_name,
                protocol=protocol,
                test_date=test_date,
                ambient_temperature_c=sheet_temp,
                humidity_percent=sheet_humidity,
                size=size,
                conditioning=conditioning,
                ballistic_limit=ballistic_limit,
                parent_test_group_id=parent_session.id,
                vest_id=vest_id,
                excel_file_path=excel_file_path,
                is_official=is_official,
            )
            db.add(db_test_session)
            db.commit()
            db.refresh(db_test_session)
            
            # Add shot data for this series
            for shot in shot_data:
                shot_copy = {k: v for k, v in shot.items() if k != 'row'}
                # Standardize caliber to match database value
                if shot_copy.get('caliber'):
                    shot_copy['caliber'] = get_standardized_caliber(db, shot_copy['caliber'])
                shot_data_db = ShotDataModel(
                    test_session_id=db_test_session.id,
                    **shot_copy
                )
                db.add(shot_data_db)
            
            db.commit()
            db.refresh(db_test_session)
            created_sessions.append(db_test_session)
    
    return created_sessions
