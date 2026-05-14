export interface ArmorPanelLayer {
  id: string;
  panel_id: string;
  layer_index: number;
  material_id: string | null;
  orientation_degrees: number | null;
  layer_count: number;
  notes: string | null;
}

export interface ArmorPanel {
  id: string;
  panel_code: string;
  test_session_id: string | null;
  vest_type: string | null;
  panel_shape: string | null;
  panel_width_mm: number | null;
  panel_height_mm: number | null;
  panel_thickness_mm: number | null;
  total_layers: number | null;
  total_areal_density_g_m2: number | null;
  total_mass_g: number | null;
  construction_notes: string | null;
  stitch_pattern: string | null;
  curvature: string | null;
  backing_material: string | null;
  created_at: string;
  updated_at: string;
  layers: ArmorPanelLayer[];
}
