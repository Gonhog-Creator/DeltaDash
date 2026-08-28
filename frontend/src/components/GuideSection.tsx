import { useState } from 'react';

type Lang = 'en' | 'es';

interface GuideContent {
  title: string;
  sections: {
    heading: string;
    body: string[];
    bullets?: string[];
  }[];
}

const guideData: Record<Lang, GuideContent[]> = {
  en: [
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
  ],
  es: [
    {
      title: 'Dashboard (Panel Principal)',
      sections: [
        {
          heading: 'Resumen',
          body: [
            'El Dashboard es la pagina de inicio de DeltaDash. Muestra estadisticas resumidas (chalecos totales, materiales, sesiones de prueba, disparos) y enlaces rapidos a otras paginas.',
            'Los usuarios administradores ven controles adicionales: Sincronizacion de Base de Datos, Reset, Backup/Restore, y Gestion de Migraciones Alembic.',
          ],
        },
        {
          heading: 'Acciones de Admin',
          body: [
            'Sincronizar Base de Datos: Extrae datos del origen remoto basado en Excel y muestra una vista previa de cambios (nuevos, actualizados, eliminados) antes de aplicarlos.',
            'Backup/Restore: Descarga un backup completo de la base de datos y archivos, o restaura desde un backup anterior.',
            'Gestion Alembic: Ejecuta migraciones pendientes, arregla multiples heads, o ejecuta SQL personalizado.',
          ],
        },
      ],
    },
    {
      title: 'Sesiones de Prueba',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'Las Sesiones de Prueba son la unidad central de datos en DeltaDash. Cada sesion representa un evento de prueba balistica donde se dispara a un chaleco con municion especifica bajo un protocolo definido.',
            'Las sesiones pueden ser oficiales (certificacion) o informales (I+D). Las oficiales requieren numero de certificacion y nombre del laboratorio.',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Para crear una sesion de prueba necesitas:',
          ],
          bullets: [
            'Un chaleco (debe existir primero en la pestana Vests)',
            'Un protocolo (define patron de disparos, distancias y criterios de aprobacion)',
            'Una ubicacion (laboratorio o instalacion de prueba)',
            'Una fecha y nombre para la sesion',
          ],
        },
        {
          heading: 'Flujo de datos',
          body: [
            'Sesion de Prueba -> Disparos -> Resultados Balisticos. Cada sesion contiene registros individuales de disparos con velocidad, profundidad, BFS y estado de aprobacion.',
            'Los datos de disparos se importan desde archivos Excel creados por el equipo. Estos archivos Excel estan formateados para coincidir con la plantilla de importacion de DeltaDash.',
          ],
        },
        {
          heading: 'Puntos limite',
          body: [
            'Los puntos limite definen el rango aceptable para una medicion (ej., la profundidad BFS debe estar entre 0 y 44mm). Se establecen por protocolo y por nivel de amenaza.',
            'Al agregar puntos limite, especifica el tipo de medicion, valor minimo, valor maximo y la unidad. Los disparos fuera de estos limites se marcan como fallidos.',
          ],
        },
      ],
    },
    {
      title: 'Certificaciones Oficiales',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'Las Certificaciones Oficiales son registros formales de homologacion. Representan un modelo de chaleco que ha sido certificado contra un estandar especifico (ej., NIJ, VPAM, UNE).',
            'Cada certificacion se vincula con las sesiones de prueba que produjeron los datos de certificacion.',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Para crear una certificacion necesitas:',
          ],
          bullets: [
            'Un chaleco (debe existir primero)',
            'Un numero de certificacion (emitido por el organismo certificador)',
            'El estandar/protocolo utilizado',
            'El laboratorio certificador y la fecha',
            'Sesion(es) de prueba vinculadas con resultados aprobatorios',
          ],
        },
      ],
    },
    {
      title: 'Materiales',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'Los Materiales son las telas balisticas y placas rigidas usadas en la construccion de chalecos. Cada material tiene propiedades como peso areal, espesor, clase de material e info de proveedor.',
            'Los materiales son referenciados por las capas del chaleco -- un chaleco se compone de multiples capas de diferentes materiales.',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Para crear un material necesitas:',
          ],
          bullets: [
            'Un nombre unico',
            'Clase de material (ej., UHMWPE, Aramida, Acero, Ceramica)',
            'Peso areal (g/m2)',
            'Espesor (mm)',
          ],
        },
        {
          heading: 'Flujo de datos',
          body: [
            'Materiales -> Capas de Chaleco -> Chalecos. Un chaleco se compone de capas, cada capa referencia un material y especifica cuantas capas de ese material se usan.',
          ],
        },
      ],
    },
    {
      title: 'Chalecos (Vests)',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'Los Chalecos son los modelos de producto. Cada chaleco tiene especificaciones tecnicas: codigo, tipo (blando/rigido/hibrido), nivel de amenaza, composicion de capas, tallas, peso y mas.',
            'Los chalecos tambien soportan gestion de documentos -- puedes subir fichas tecnicas, especificaciones de composicion y otros documentos.',
          ],
        },
        {
          heading: 'Flag de Modelo de Catalogo',
          body: [
            'El checkbox "Catalog Model" determina si un chaleco aparece en el dropdown de compatibilidad de Geometrias y en el matching de IA.',
            'Los chalecos de prueba, prototipos y experimentales NO deben marcarse como modelos de catalogo. Solo los modelos oficiales de producto deben marcarse.',
            'Para cambiarlo: edita un chaleco, marca/desmarca el checkbox "Catalog Model" y guarda.',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Para crear un chaleco necesitas:',
          ],
          bullets: [
            'Un codigo unico (ej., "STOP II", "MDS III")',
            'Tipo de chaleco (blando, rigido o hibrido)',
            'Nivel de amenaza (ej., IIIA, III, IV)',
            'Capas (agregar materiales y conteos de capas)',
          ],
        },
        {
          heading: 'Flujo de datos',
          body: [
            'Chalecos -> Sesiones de Prueba (se prueba un chaleco) -> Disparos (se registran resultados).',
            'Chalecos -> Compatibilidad de Geometrias (los chalecos de catalogo aparecen en el dropdown).',
            'Chalecos -> Estimacion de Tela (la composicion del chaleco alimenta los calculos de tela).',
          ],
        },
      ],
    },
    {
      title: 'Geometrias',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'Las Geometrias (geometrales) definen las formas y dimensiones fisicas de los paneles para cada talla de chaleco. Cada geometria tiene areas de superficie, mediciones por talla y una lista de compatibilidad de modelos.',
            'Las geometrias pueden importarse/exportarse via un archivo Excel maestro. El Excel tiene una hoja maestra (metadatos) y hojas de detalle por geometria (mediciones por talla).',
          ],
        },
        {
          heading: 'Pestana de Compatibilidad',
          body: [
            'La pestana de Compatibilidad de Geometria muestra que modelos de chaleco son compatibles con cada geometria.',
            'El dropdown "Modelo compatible" se filtra para mostrar solo los modelos listados en el texto de compatibilidad de la geometria seleccionada.',
            'Solo los chalecos marcados como "Catalog Model" aparecen en este dropdown. Asegurate de marcar el flag de catalogo en los chalecos primero.',
            'Puedes subir y gestionar documentos tecnicos para cada modelo desde esta pestana.',
          ],
        },
        {
          heading: 'Agregar una nueva geometria',
          body: [
            'Para agregar una geometria via Excel:',
          ],
          bullets: [
            'Exporta el Excel actual de geometrias (desde la pestana Geometries)',
            'Agrega una nueva fila a la hoja maestra "Geometries" con nombre, descripcion, vest_type, compatibility, etc.',
            'Crea una hoja de detalle con el mismo nombre que la geometria, incluyendo una fila de cabecera "Size" y columnas de medicion (Front A, Back A, etc.)',
            'Deja el image_url en blanco -- puedes adjuntar la imagen despues desde la UI',
            'Sube el archivo Excel -- la nueva geometria aparecera',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Cada geometria necesita:',
          ],
          bullets: [
            'Un nombre unico (ej., "GEOMETRAL D")',
            'Tallas disponibles (ej., SMALL, MEDIUM, LARGE)',
            'Areas de superficie por talla (frente, espalda, total en m2)',
            'Mediciones por talla (dimensiones frente/espalda en mm)',
            'Texto de compatibilidad (ej., "Compatible con: STOP II - STOP III")',
          ],
        },
      ],
    },
    {
      title: 'Municion',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'Los registros de Municion definen los proyectiles usados en las pruebas balisticas. Cada municion tiene calibre, tipo, masa y velocidad de referencia.',
            'La municion es referenciada por los disparos de las sesiones de prueba para registrar que se disparo contra el chaleco.',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Para crear municion necesitas:',
          ],
          bullets: [
            'Un nombre unico (ej., "9mm FMJ", ".44 MAG SJHP")',
            'Calibre',
            'Masa (gramos)',
            'Velocidad de referencia (m/s)',
          ],
        },
      ],
    },
    {
      title: 'Estimacion de Tela',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'La Estimacion de Tela calcula cuanta tela balistica se necesita para producir un chaleco, basado en su geometria, composicion de capas y curva de tallas.',
            'Usa las areas de superficie de la geometria, los conteos de capas del chaleco y la curva de tallas de produccion para estimar el consumo total de tela.',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Para usar la estimacion de tela necesitas:',
          ],
          bullets: [
            'Un chaleco con capas definidas (materiales y conteos de capas)',
            'Una geometria con areas de superficie por talla',
            'Una curva de tallas (cuantas unidades de cada talla producir)',
          ],
        },
        {
          heading: 'Flujo de datos',
          body: [
            'Chaleco (capas) + Geometria (areas) + Curva de Tallas (cantidades) -> Estimacion de Tela (total m2 por material).',
          ],
        },
      ],
    },
    {
      title: 'Analiticas',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'Las Analiticas proporcionan dashboards visuales y graficos para los datos de pruebas balisticas. Puedes filtrar por chaleco, material, municion, rango de fechas y mas.',
            'Los graficos incluyen distribucion de disparos, histogramas de profundidad BFS, tendencias de velocidad y tasas de aprobacion/falla.',
          ],
        },
        {
          heading: 'Flujo de datos',
          body: [
            'Las analiticas leen de Sesiones de Prueba y Datos de Disparos. No se requiere entrada directa -- solo selecciona filtros y visualiza los graficos.',
          ],
        },
      ],
    },
    {
      title: 'Comparacion',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'La Comparacion permite comparar dos o mas chalecos lado a lado en todas sus especificaciones tecnicas, resultados de pruebas y certificaciones.',
            'Util para evaluar diferentes modelos de chalecos entre si para decisiones de adquisicion o I+D.',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Selecciona dos o mas chalecos del dropdown para comparar. Los chalecos deben existir previamente con sus datos completos.',
          ],
        },
      ],
    },
    {
      title: 'Predicciones',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'Las Predicciones (Prueba Balistica) usan el modelo de IA entrenado para predecir el rendimiento balistico de una configuracion de chaleco sin probarlo fisicamente.',
            'Ingresas parametros del chaleco (capas, materiales, geometria) y el modelo predice profundidad BFS, penetracion y probabilidad de aprobacion/falla.',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Para ejecutar una prediccion necesitas:',
          ],
          bullets: [
            'Un modelo entrenado (ver pestana Model Training)',
            'Parametros del chaleco: capas con materiales y conteos',
            'Municion objetivo y velocidad',
            'Geometria (para contexto de area de superficie)',
          ],
        },
        {
          heading: 'Flujo de datos',
          body: [
            'Model Training (entrena con datos historicos) -> Predicciones (usa el modelo entrenado para predecir nuevas configuraciones).',
          ],
        },
      ],
    },
    {
      title: 'Protocolos (Admin)',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'Los Protocolos definen los estandares y procedimientos de prueba. Cada protocolo especifica conteo de disparos, patron de disparos, distancias, velocidades y criterios de aprobacion/falla.',
            'Los protocolos son referenciados por las sesiones de prueba para determinar como debe realizarse la prueba.',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Para crear un protocolo necesitas:',
          ],
          bullets: [
            'Un nombre unico (ej., "NIJ 0101.06 Level IIIA")',
            'Definicion de conteo y patron de disparos',
            'Requisitos de velocidad por disparo',
            'Criterios de aprobacion/falla (limites BFS, limites de penetracion)',
          ],
        },
      ],
    },
    {
      title: 'Entrenamiento de Modelo (Admin)',
      sections: [
        {
          heading: 'Que hace',
          body: [
            'El Entrenamiento de Modelo entrena el modelo de IA de prediccion usando datos historicos de pruebas balisticas de la base de datos.',
            'El modelo aprende la relacion entre la configuracion del chaleco (materiales, capas, geometria) y el rendimiento balistico (BFS, penetracion).',
          ],
        },
        {
          heading: 'Datos requeridos',
          body: [
            'Para entrenar un modelo necesitas:',
          ],
          bullets: [
            'Suficientes datos de prueba (sesiones con resultados de disparos)',
            'Chalecos con definiciones completas de capas',
            'Materiales con propiedades (peso areal, espesor)',
            'Seleccionar parametros de entrenamiento (tipo de modelo, features, division train/test)',
          ],
        },
        {
          heading: 'Flujo de datos',
          body: [
            'Sesiones de Prueba + Disparos + Chalecos + Materiales -> Ingenieria de Features -> Entrenamiento -> Modelo Entrenado -> Predicciones.',
          ],
        },
      ],
    },
  ],
};

export function GuideSection() {
  const [lang, setLang] = useState<Lang>('en');
  const [activeTab, setActiveTab] = useState(0);

  const guides = guideData[lang];
  const current = guides[activeTab];

  return (
    <div className="mt-8 bg-white shadow rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-medium text-gray-900">
          {lang === 'en' ? 'User Guide' : 'Guia de Usuario'}
        </h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">
            {lang === 'en' ? 'Language' : 'Idioma'}
          </span>
          <button
            onClick={() => setLang('en')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              lang === 'en'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            EN
          </button>
          <button
            onClick={() => setLang('es')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              lang === 'es'
                ? 'bg-indigo-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            ES
          </button>
        </div>
      </div>

      <div className="border-b border-gray-200 mb-4">
        <div className="flex flex-wrap gap-1">
          {guides.map((guide, idx) => (
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
