export interface Ammunition {
  id: string;
  name: string;
  caliber: string | null;
  projectile_type: string | null;
  projectile_mass_grains: number | null;
  projectile_mass_grams: number | null;
  nominal_velocity_fps: number | null;
  nominal_velocity_m_s: number | null;
  manufacturer: string | null;
  lot_number: string | null;
  standard_reference: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}
