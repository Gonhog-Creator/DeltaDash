export interface Material {
  id: string;
  name: string;
  normalized_name: string | null;
  manufacturer: string | null;
  supplier: string | null;
  material_class: string | null;
  fiber_type: string | null;
  weave_type: string | null;
  coating: string | null;
  color: string | null;
  areal_density_g_m2: number | null;
  thickness_mm: number | null;
  density_g_cm3: number | null;
  tensile_strength_mpa: number | null;
  modulus_gpa: number | null;
  elongation_percent: number | null;
  notes: string | null;
  source_confidence: string | null;
  created_at: string;
  updated_at: string;
}
