"""
Clean up duplicate materials and geometry material configs.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.db.models.material import Material
from app.db.models.geometry_material_config import GeometryMaterialConfig

db = SessionLocal()

try:
    # ============================================
    # Clean up duplicate materials
    # ============================================
    print("=" * 60)
    print("Cleaning up duplicate materials")
    print("=" * 60)
    
    materials = db.query(Material).all()
    material_names = {}
    
    # Group materials by name
    for m in materials:
        if m.name not in material_names:
            material_names[m.name] = []
        material_names[m.name].append(m)
    
    materials_deleted = 0
    for name, material_list in material_names.items():
        if len(material_list) > 1:
            # Keep the first one, delete the rest
            for m in material_list[1:]:
                db.delete(m)
                materials_deleted += 1
            print(f"  Kept 1, deleted {len(material_list) - 1} copies of: {name}")
    
    db.commit()
    print(f"\nDeleted {materials_deleted} duplicate materials")
    
    # ============================================
    # Clean up duplicate geometry material configs
    # ============================================
    print("\n" + "=" * 60)
    print("Cleaning up duplicate geometry material configs")
    print("=" * 60)
    
    configs = db.query(GeometryMaterialConfig).all()
    config_keys = {}
    
    # Group configs by (geometry_id, size)
    for c in configs:
        key = (str(c.geometry_id), c.size)
        if key not in config_keys:
            config_keys[key] = []
        config_keys[key].append(c)
    
    configs_deleted = 0
    for key, config_list in config_keys.items():
        if len(config_list) > 1:
            # Keep the first one, delete the rest
            for c in config_list[1:]:
                db.delete(c)
                configs_deleted += 1
            print(f"  Kept 1, deleted {len(config_list) - 1} copies of: Geometry {key[0]}, Size {key[1]}")
    
    db.commit()
    print(f"\nDeleted {configs_deleted} duplicate configs")
    
    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE")
    print("=" * 60)
    print(f"Materials deleted: {materials_deleted}")
    print(f"Configs deleted: {configs_deleted}")
    
except Exception as e:
    db.rollback()
    print(f"\nError during cleanup: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
