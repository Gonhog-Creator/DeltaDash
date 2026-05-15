from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.db.models import TestSession as TestSessionModel, ShotData as ShotDataModel
from app.services.excel_parser import ExcelParser, ExcelParseError


def create_sessions_from_excel_data(
    db: Session,
    excel_file_path: str,
    test_name: str,
    location_name: Optional[str],
    operator: Optional[str],
    protocol: Optional[str],
    test_date: Optional[str],
    temperature: Optional[float],
    humidity: Optional[float],
    is_full_path: bool = False,
) -> List[TestSessionModel]:
    """Create test sessions from Excel file data."""
    import os
    from app.core.config import settings
    
    full_path = excel_file_path if is_full_path else os.path.join(settings.MATERIAL_DOCS_DIR, excel_file_path)
    parser = ExcelParser(full_path)
    conditioning_size = parser.parse_conditioning_and_size(parser.sheet['A1'].value if parser.sheet['A1'].value else '')
    multiple_tests = parser.detect_multiple_tests()
    shot_data, _, _ = parser.parse()
    
    if multiple_tests:
        parent_session = TestSessionModel(
            name=test_name,
            lab_name=location_name,
            operator=operator,
            protocol=protocol,
            test_date=test_date,
            ambient_temperature_c=temperature,
            humidity_percent=humidity,
            excel_file_path=excel_file_path,
        )
        db.add(parent_session)
        db.commit()
        db.refresh(parent_session)
        
        created_sessions = []
        for i, test_info in enumerate(multiple_tests):
            test_conditioning = test_info.get('conditioning')
            test_size = test_info.get('size')
            
            db_test_session = TestSessionModel(
                name=f"{test_name} - Vest {test_info['vest_number']}",
                lab_name=location_name,
                operator=operator,
                protocol=protocol,
                test_date=test_date,
                ambient_temperature_c=temperature,
                humidity_percent=humidity,
                conditioning=test_conditioning,
                size=test_size,
                ballistic_limit=False,
                parent_test_group_id=parent_session.id,
                excel_file_path=excel_file_path,
            )
            db.add(db_test_session)
            db.commit()
            db.refresh(db_test_session)
            
            test_rows = {item['row'] for item in test_info['data']}
            for shot in shot_data:
                if shot.get('row') in test_rows:
                    shot_copy = {k: v for k, v in shot.items() if k != 'row'}
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
            operator=operator,
            protocol=protocol,
            test_date=test_date,
            ambient_temperature_c=temperature,
            humidity_percent=humidity,
            conditioning=conditioning_size.get('conditioning'),
            size=conditioning_size.get('size'),
            ballistic_limit=conditioning_size.get('ballistic_limit', False),
            excel_file_path=excel_file_path,
        )
        db.add(db_test_session)
        db.commit()
        db.refresh(db_test_session)
        
        for shot in shot_data:
            shot_data_db = ShotDataModel(
                test_session_id=db_test_session.id,
                **shot
            )
            db.add(shot_data_db)
        
        db.commit()
        db.refresh(db_test_session)
        return [db_test_session]
