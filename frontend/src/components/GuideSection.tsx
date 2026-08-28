import { useState } from 'react';

interface GuideContent {
  title: string;
  sections: {
    heading: string;
    body: string[];
    bullets?: string[];
  }[];
}

const guideData: GuideContent[] = [
    {
      title: 'Dashboard',
      sections: [
        {
          heading: 'Overview',
          body: [
            'The Dashboard is the home page of DeltaDash. It shows summary stats (total vests, materials, test sessions, shots) and quick links to other pages.',
            'Admin users see additional controls: Database Sync, Reset, Backup/Restore, and Alembic Migration Management.',
          ],
        },
        {
          heading: 'Admin Actions',
          body: [
            'Sync Database: Pulls data from the remote Excel-based source and previews changes (new, updated, deleted records) before applying them.',
            'Backup/Restore: Download a full backup of the database and storage files, or restore from a previous backup.',
            'Alembic Management: Run pending database migrations, fix multiple heads, or execute custom SQL.',
          ],
        },
      ],
    },
    {
      title: 'Test Sessions',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Test Sessions are the core data unit in DeltaDash. Each session represents a ballistic testing event where a vest is shot with specific ammunition under a defined protocol.',
            'Sessions can be official (certification) or informal (R&D). Official sessions require a certification number and lab name.',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'To create a test session you need:',
          ],
          bullets: [
            'A vest (must exist in the Vests tab first)',
            'A protocol (defines shot pattern, distances, and pass/fail criteria)',
            'A location (testing lab or facility)',
            'A date and name for the session',
          ],
        },
        {
          heading: 'Data flow',
          body: [
            'Test Session -> Shots -> Ballistic Results. Each session contains individual shot records with velocity, depth, BFS, and pass/fail status.',
            'Shot data is imported from Excel files created by the team. These Excel files are formatted to match the DeltaDash import template.',
          ],
        },
        {
          heading: 'Limit points',
          body: [
            'Limit points define the acceptable range for a measurement (e.g., BFS depth must be between 0 and 44mm). These are set per protocol and per threat level.',
            'When adding limit points, specify the measurement type, min value, max value, and the unit. Shots outside these limits are flagged as failures.',
          ],
        },
      ],
    },
    {
      title: 'Official Certifications',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Official Certifications are formal homologation records. They represent a vest model that has been certified against a specific standard (e.g., NIJ, VPAM, UNE).',
            'Each certification links to the test sessions that produced the certification data.',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'To create a certification you need:',
          ],
          bullets: [
            'A vest (must exist first)',
            'A certification number (issued by the certifying body)',
            'The standard/protocol used',
            'The certifying lab and date',
            'Linked test session(s) with passing results',
          ],
        },
      ],
    },
    {
      title: 'Materials',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Materials are the ballistic fabrics and hard plates used in vest construction. Each material has properties like areal weight, thickness, material class, and supplier info.',
            'Materials are referenced by vest layers -- a vest is built up from multiple layers of different materials.',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'To create a material you need:',
          ],
          bullets: [
            'A unique name',
            'Material class (e.g., UHMWPE, Aramid, Steel, Ceramic)',
            'Areal weight (g/m2)',
            'Thickness (mm)',
          ],
        },
        {
          heading: 'Data flow',
          body: [
            'Materials -> Vest Layers -> Vests. A vest is composed of layers, each layer references a material and specifies how many layers of that material are used.',
          ],
        },
      ],
    },
    {
      title: 'Vests',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Vests are the product models. Each vest has technical specifications: vest code, type (soft/hard/hybrid), threat level, layer composition, sizes, weight, and more.',
            'Vests also support document management -- you can upload technical datasheets, composition specs, and other documents.',
          ],
        },
        {
          heading: 'Catalog Model flag',
          body: [
            'The "Catalog Model" checkbox determines whether a vest appears in the Geometries compatibility dropdown and in AI matching.',
            'Test vests, prototypes, and experimental vests should NOT be flagged as catalog models. Only official product models should be checked.',
            'To change it: edit a vest, check/uncheck the "Catalog Model" box, and save.',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'To create a vest you need:',
          ],
          bullets: [
            'A unique vest code (e.g., "STOP II", "MDS III")',
            'Vest type (soft, hard, or hybrid)',
            'Threat level (e.g., IIIA, III, IV)',
            'Layers (add materials and layer counts)',
          ],
        },
        {
          heading: 'Data flow',
          body: [
            'Vests -> Test Sessions (a vest is tested) -> Shots (results recorded).',
            'Vests -> Geometries compatibility (catalog vests appear in the compatibility dropdown).',
            'Vests -> Fabric Estimation (vest composition drives fabric calculations).',
          ],
        },
      ],
    },
    {
      title: 'Geometries',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Geometries (geometrales) define the physical panel shapes and dimensions for each vest size. Each geometry has surface areas, size measurements, and a compatibility list of vest models.',
            'Geometries can be imported/exported via a master Excel file. The Excel has a master sheet (metadata) and per-geometry detail sheets (measurements by size).',
          ],
        },
        {
          heading: 'Compatibility tab',
          body: [
            'The Geometry Compatibility tab shows which vest models are compatible with each geometry.',
            'The "Modelo compatible" dropdown is filtered to only show models listed in the selected geometry\'s compatibility text.',
            'Only vests flagged as "Catalog Model" appear in this dropdown. Make sure to check the catalog flag on vests in the Vests tab first.',
            'You can upload and manage technical documents for each model from this tab.',
          ],
        },
        {
          heading: 'Adding a new geometry',
          body: [
            'To add a new geometry via Excel:',
          ],
          bullets: [
            'Export the current geometries Excel (from the Geometries tab)',
            'Add a new row to the "Geometries" master sheet with name, description, vest_type, compatibility, etc.',
            'Create a detail sheet with the same name as the geometry, including a "Size" header row and measurement columns (Front A, Back A, etc.)',
            'Leave the image_url blank -- you can attach the image later from the UI',
            'Upload the Excel file -- the new geometry will appear',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'Each geometry needs:',
          ],
          bullets: [
            'A unique name (e.g., "GEOMETRAL D")',
            'Available sizes (e.g., SMALL, MEDIUM, LARGE)',
            'Surface areas per size (front, back, total in m2)',
            'Size measurements per size (front/back dimensions in mm)',
            'Compatibility text (e.g., "Compatible con: STOP II - STOP III")',
          ],
        },
      ],
    },
    {
      title: 'Ammunition',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Ammunition records define the projectiles used in ballistic testing. Each ammunition has a caliber, type, mass, and reference velocity.',
            'Ammunition is referenced by test session shots to record what was fired at the vest.',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'To create ammunition you need:',
          ],
          bullets: [
            'A unique name (e.g., "9mm FMJ", ".44 MAG SJHP")',
            'Caliber',
            'Mass (grams)',
            'Reference velocity (m/s)',
          ],
        },
      ],
    },
    {
      title: 'Fabric Estimation',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Fabric Estimation calculates how much ballistic fabric is needed to produce a vest, based on its geometry, layer composition, and size curve.',
            'It uses the geometry surface areas, the vest layer counts, and the production size curve to estimate total fabric consumption.',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'To use fabric estimation you need:',
          ],
          bullets: [
            'A vest with defined layers (materials and layer counts)',
            'A geometry with surface areas per size',
            'A size curve (how many units of each size to produce)',
          ],
        },
        {
          heading: 'Data flow',
          body: [
            'Vest (layers) + Geometry (surface areas) + Size Curve (quantities) -> Fabric Estimation (total m2 per material).',
          ],
        },
      ],
    },
    {
      title: 'Analytics',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Analytics provides visual dashboards and charts for ballistic test data. You can filter by vest, material, ammunition, date range, and more.',
            'Charts include shot distribution, BFS depth histograms, velocity trends, and pass/fail rates.',
          ],
        },
        {
          heading: 'Data flow',
          body: [
            'Analytics reads from Test Sessions and Shot Data. No direct input required -- just select filters and view the charts.',
          ],
        },
      ],
    },
    {
      title: 'Comparison',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Comparison lets you compare two or more vests side-by-side across all their technical specifications, test results, and certifications.',
            'Useful for evaluating different vest models against each other for procurement or R&D decisions.',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'Select two or more vests from the dropdown to compare. The vests must already exist with their data filled in.',
          ],
        },
      ],
    },
    {
      title: 'Predictions',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Predictions (Ballistic Testing) uses the trained AI model to predict ballistic performance for a vest configuration without physically testing it.',
            'You input vest parameters (layers, materials, geometry) and the model predicts BFS depth, penetration, and pass/fail probability.',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'To run a prediction you need:',
          ],
          bullets: [
            'A trained model (see Model Training tab)',
            'Vest parameters: layers with materials and counts',
            'Target ammunition and velocity',
            'Geometry (for surface area context)',
          ],
        },
        {
          heading: 'Data flow',
          body: [
            'Model Training (trains on historical test data) -> Predictions (uses trained model to predict new configurations).',
          ],
        },
      ],
    },
    {
      title: 'Protocols (Admin)',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Protocols define the testing standards and procedures. Each protocol specifies shot count, shot pattern, distances, velocities, and pass/fail criteria.',
            'Protocols are referenced by test sessions to determine how the testing should be conducted.',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'To create a protocol you need:',
          ],
          bullets: [
            'A unique name (e.g., "NIJ 0101.06 Level IIIA")',
            'Shot count and pattern definition',
            'Velocity requirements per shot',
            'Pass/fail criteria (BFS limits, penetration limits)',
          ],
        },
      ],
    },
    {
      title: 'Model Training (Admin)',
      sections: [
        {
          heading: 'What it does',
          body: [
            'Model Training trains the AI prediction model using historical ballistic test data from the database.',
            'The model learns the relationship between vest configuration (materials, layers, geometry) and ballistic performance (BFS, penetration).',
          ],
        },
        {
          heading: 'Required inputs',
          body: [
            'To train a model you need:',
          ],
          bullets: [
            'Sufficient test data (test sessions with shot results)',
            'Vests with complete layer definitions',
            'Materials with properties (areal weight, thickness)',
            'Select training parameters (model type, features, train/test split)',
          ],
        },
        {
          heading: 'Data flow',
          body: [
            'Test Sessions + Shots + Vests + Materials -> Feature Engineering -> Model Training -> Trained Model -> Predictions.',
          ],
        },
      ],
    },
];

export function GuideSection() {
  const [activeTab, setActiveTab] = useState(0);

  const current = guideData[activeTab];

  return (
    <div className="mt-8 bg-white shadow rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-gray-900">
          User Guide
        </h2>
      </div>

      <div className="border-b border-gray-200 mb-4">
        <div className="flex flex-wrap gap-1">
          {guideData.map((guide, idx) => (
            <button
              key={idx}
              onClick={() => setActiveTab(idx)}
              className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === idx
                  ? 'border-indigo-600 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {guide.title}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-6">
        {current.sections.map((section, idx) => (
          <div key={idx}>
            <h3 className="text-sm font-semibold text-gray-900 mb-2">{section.heading}</h3>
            <div className="space-y-1.5">
              {section.body.map((paragraph, pIdx) => (
                <p key={pIdx} className="text-sm text-gray-600 leading-relaxed">{paragraph}</p>
              ))}
            </div>
            {section.bullets && (
              <ul className="mt-2 space-y-1">
                {section.bullets.map((bullet, bIdx) => (
                  <li key={bIdx} className="text-sm text-gray-600 flex items-start">
                    <span className="text-indigo-500 mr-2 mt-0.5">-</span>
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
