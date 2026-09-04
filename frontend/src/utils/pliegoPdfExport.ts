import { PliegoDocument } from '../api/pliego';

function base64ToBytes(base64: string): Uint8Array {
  const clean = base64.replace(/^data:.*;base64,/i, '').replace(/\s+/g, '');
  const binary = atob(clean);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function bytesToLatin1(text: string): Uint8Array {
  const out = new Uint8Array(text.length);
  for (let i = 0; i < text.length; i++) out[i] = text.charCodeAt(i) & 255;
  return out;
}

function concatUint8Arrays(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  parts.forEach(p => {
    out.set(p, offset);
    offset += p.length;
  });
  return out;
}

function wrapCanvasText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const words = String(text || '').split(/\s+/);
  const lines: string[] = [];
  let line = '';
  words.forEach(word => {
    const test = line ? line + ' ' + word : word;
    if (ctx.measureText(test).width <= maxWidth) {
      line = test;
    } else {
      if (line) lines.push(line);
      line = word;
    }
  });
  if (line) lines.push(line);
  return lines.length ? lines : [''];
}

function canvasToPdfPages(canvas: HTMLCanvasElement, pageW: number, pageH: number): Blob {
  const imgW = canvas.width;
  const imgH = canvas.height;
  const scale = Math.min(pageW / imgW, pageH / imgH);
  const renderW = imgW * scale;
  const renderH = imgH * scale;
  const numPages = Math.ceil(renderH / pageH);
  const sliceH = pageH / scale;

  const objects: (Uint8Array | string)[] = [];
  const kidRefs: string[] = [];

  let objIdx = 1;
  const catalogObj = objIdx++;
  const pagesObj = objIdx++;

  for (let p = 0; p < numPages; p++) {
    const pageObj = objIdx++;
    const contentObj = objIdx++;
    const imageObj = objIdx++;
    kidRefs.push(`${pageObj} 0 R`);

    const offsetY = p * pageH / scale;
    const drawH = Math.min(sliceH, imgH - offsetY);

    objects[pageObj] = bytesToLatin1(
      `<< /Type /Page /Parent ${pagesObj} 0 R /MediaBox [0 0 ${pageW} ${pageH}] ` +
      `/Resources << /XObject << /Im${p} ${imageObj} 0 R >> >> /Contents ${contentObj} 0 R >>`
    );

    const content = `q\n${renderW} 0 0 ${drawH * scale} 0 ${pageH - drawH * scale} cm\n/Im${p} Do\nQ`;
    const contentBytes = bytesToLatin1(content);
    objects[contentObj] = concatUint8Arrays([
      bytesToLatin1(`<< /Length ${contentBytes.length} >>\nstream\n`),
      contentBytes,
      bytesToLatin1('\nendstream')
    ]);

    const sliceCanvas = document.createElement('canvas');
    sliceCanvas.width = imgW;
    sliceCanvas.height = Math.ceil(drawH);
    const sliceCtx = sliceCanvas.getContext('2d')!;
    sliceCtx.fillStyle = '#ffffff';
    sliceCtx.fillRect(0, 0, sliceCanvas.width, sliceCanvas.height);
    sliceCtx.drawImage(canvas, 0, offsetY, imgW, drawH, 0, 0, imgW, drawH);

    const sliceJpeg = sliceCanvas.toDataURL('image/jpeg', 0.92);
    const sliceBytes = base64ToBytes(sliceJpeg.slice(sliceJpeg.indexOf(',') + 1));

    const imageHeader = bytesToLatin1(
      `<< /Type /XObject /Subtype /Image /Width ${sliceCanvas.width} /Height ${sliceCanvas.height} ` +
      `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${sliceBytes.length} >>\nstream\n`
    );
    objects[imageObj] = concatUint8Arrays([imageHeader, sliceBytes, bytesToLatin1('\nendstream')]);
  }

  objects[catalogObj] = bytesToLatin1(`<< /Type /Catalog /Pages ${pagesObj} 0 R >>`);
  objects[pagesObj] = bytesToLatin1(`<< /Type /Pages /Kids [${kidRefs.join(' ')}] /Count ${numPages} >>`);

  const totalObjects = objIdx - 1;
  const header = bytesToLatin1('%PDF-1.4\n%\xFF\xFF\xFF\xFF\n');
  const chunks: Uint8Array[] = [header];
  const offsets: number[] = [0];
  let position = header.length;

  for (let i = 1; i <= totalObjects; i++) {
    if (!objects[i]) continue;
    const obj = concatUint8Arrays([
      bytesToLatin1(`${i} 0 obj\n`),
      objects[i] as Uint8Array,
      bytesToLatin1('\nendobj\n')
    ]);
    offsets[i] = position;
    chunks.push(obj);
    position += obj.length;
  }

  const xrefOffset = position;
  let xref = `xref\n0 ${totalObjects + 1}\n0000000000 65535 f \n`;
  for (let i = 1; i <= totalObjects; i++) {
    if (objects[i]) {
      xref += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`;
    } else {
      xref += `0000000000 65535 f \n`;
    }
  }
  xref += `trailer\n<< /Size ${totalObjects + 1} /Root ${catalogObj} 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  chunks.push(bytesToLatin1(xref));

  return new Blob(chunks as BlobPart[], { type: 'application/pdf' });
}

interface Labels {
  title: string;
  documentName: string;
  date: string;
  extractedRequirements: string;
  summary: string;
  certifiedVests: string;
  matched: string;
  topScore: string;
  coverageGaps: string;
  recommendedVests: string;
  rank: string;
  vestCode: string;
  type: string;
  threatLevel: string;
  layers: string;
  weight: string;
  thickness: string;
  matchScore: string;
  certifications: string;
  gaps: string;
  properties: string;
  sizes: string;
  flexibility: string;
  panelSewn: string;
  catalogModel: string;
  femaleFit: string;
  composition: string;
  protectionClass: string;
  noMatches: string;
  noGaps: string;
  footer: string;
  generated: string;
  threatLevelLabel: string;
  vestTypeLabel: string;
  protectionClassLabel: string;
  maxWeightLabel: string;
  requiredSizesLabel: string;
  ammunitionLabel: string;
  maxBackfaceLabel: string;
  traumaAmmoLabel: string;
  flexibilityReqLabel: string;
  panelSewnReqLabel: string;
  femaleReqLabel: string;
  maxThicknessLabel: string;
  stitchPatternLabel: string;
  notesLabel: string;
  rawSummaryLabel: string;
}

function getLabels(lang: 'en' | 'es'): Labels {
  if (lang === 'es') {
    return {
      title: 'Informe de Análisis de Pliego Técnico',
      documentName: 'Documento',
      date: 'Fecha',
      extractedRequirements: 'Requisitos Extraídos',
      summary: 'Resumen',
      certifiedVests: 'Chalecos Certificados',
      matched: 'Coincidencias',
      topScore: 'Mejor Puntuación',
      coverageGaps: 'Brechas de Cobertura',
      recommendedVests: 'Chalecos Recomendados',
      rank: '#',
      vestCode: 'Código de Chaleco',
      type: 'Tipo',
      threatLevel: 'Nivel de Amenaza',
      layers: 'Capas',
      weight: 'Peso',
      thickness: 'Grosor',
      matchScore: 'Puntuación',
      certifications: 'Certificaciones',
      gaps: 'Brechas',
      properties: 'Propiedades',
      sizes: 'Tallas',
      flexibility: 'Flexibilidad',
      panelSewn: 'Paneles Cosidos',
      catalogModel: 'Modelo de Catálogo',
      femaleFit: 'Ajuste Femenino',
      composition: 'Composición',
      protectionClass: 'Clase de Protección',
      noMatches: 'No se encontraron chalecos certificados que coincidan.',
      noGaps: 'Sin brechas identificadas.',
      footer: 'DeltaDash — Informe de Pliego Técnico',
      generated: 'Generado',
      threatLevelLabel: 'Nivel de Amenaza',
      vestTypeLabel: 'Tipo de Chaleco',
      protectionClassLabel: 'Clase de Protección',
      maxWeightLabel: 'Peso Máximo',
      requiredSizesLabel: 'Tallas Requeridas',
      ammunitionLabel: 'Munición',
      maxBackfaceLabel: 'Deformación Máx.',
      traumaAmmoLabel: 'Munición Trauma',
      flexibilityReqLabel: 'Flexibilidad',
      panelSewnReqLabel: 'Paneles Cosidos',
      femaleReqLabel: 'Ajuste Femenino',
      maxThicknessLabel: 'Grosor Máximo',
      stitchPatternLabel: 'Patrón de Costura',
      notesLabel: 'Notas',
      rawSummaryLabel: 'Resumen',
    };
  }
  return {
    title: 'RFP Analysis Report',
    documentName: 'Document',
    date: 'Date',
    extractedRequirements: 'Extracted Requirements',
    summary: 'Summary',
    certifiedVests: 'Certified Vests',
    matched: 'Matched',
    topScore: 'Top Score',
    coverageGaps: 'Coverage Gaps',
    recommendedVests: 'Recommended Vests',
    rank: '#',
    vestCode: 'Vest Code',
    type: 'Type',
    threatLevel: 'Threat Level',
    layers: 'Layers',
    weight: 'Weight',
    thickness: 'Thickness',
    matchScore: 'Match Score',
    certifications: 'Certifications',
    gaps: 'Gaps',
    properties: 'Properties',
    sizes: 'Sizes',
    flexibility: 'Flexibility',
    panelSewn: 'Panel Sewn',
    catalogModel: 'Catalog Model',
    femaleFit: 'Female Fit',
    composition: 'Composition',
    protectionClass: 'Protection Class',
    noMatches: 'No certified vests matched the extracted requirements.',
    noGaps: 'No coverage gaps identified.',
    footer: 'DeltaDash — RFP Analysis Report',
    generated: 'Generated',
    threatLevelLabel: 'Threat Level',
    vestTypeLabel: 'Vest Type',
    protectionClassLabel: 'Protection Class',
    maxWeightLabel: 'Max Weight',
    requiredSizesLabel: 'Required Sizes',
    ammunitionLabel: 'Ammunition',
    maxBackfaceLabel: 'Max Backface',
    traumaAmmoLabel: 'Trauma Ammo',
    flexibilityReqLabel: 'Flexibility',
    panelSewnReqLabel: 'Panel Sewn',
    femaleReqLabel: 'Female Fit',
    maxThicknessLabel: 'Max Thickness',
    stitchPatternLabel: 'Stitch Pattern',
    notesLabel: 'Notes',
    rawSummaryLabel: 'Summary',
  };
}

export async function exportPliegoReportPdf(doc: PliegoDocument, lang: 'en' | 'es' = 'en'): Promise<void> {
  const L = getLabels(lang);
  const reqs = doc.extracted_requirements;
  const results = doc.match_results;

  const W = 1240;
  const M = 50;
  const CW = W - M * 2;

  // Build content height dynamically
  let y = 0;
  const sections: { y: number; h: number }[] = [];

  // Header
  const headerH = 90;
  y = headerH;

  // Requirements section
  const reqEntries: Array<{ label: string; value: string }> = [];
  if (reqs) {
    if (reqs.raw_summary) reqEntries.push({ label: L.rawSummaryLabel, value: reqs.raw_summary });
    if (reqs.threat_level) reqEntries.push({ label: L.threatLevelLabel, value: reqs.threat_level });
    if (reqs.vest_type) reqEntries.push({ label: L.vestTypeLabel, value: reqs.vest_type });
    if (reqs.protection_class) reqEntries.push({ label: L.protectionClassLabel, value: reqs.protection_class });
    if (reqs.max_weight_g) reqEntries.push({ label: L.maxWeightLabel, value: `${reqs.max_weight_g}g` });
    if (reqs.required_sizes?.length) reqEntries.push({ label: L.requiredSizesLabel, value: reqs.required_sizes.join(', ') });
    if (reqs.ammunition_calibers?.length) reqEntries.push({ label: L.ammunitionLabel, value: reqs.ammunition_calibers.join(', ') });
    if (reqs.trauma_homologation?.backface_max_mm) reqEntries.push({ label: L.maxBackfaceLabel, value: `${reqs.trauma_homologation.backface_max_mm}mm` });
    if (reqs.trauma_homologation?.ammunition) reqEntries.push({ label: L.traumaAmmoLabel, value: reqs.trauma_homologation.ammunition });
    if (reqs.flexibility_required !== null && reqs.flexibility_required !== undefined) reqEntries.push({ label: L.flexibilityReqLabel, value: reqs.flexibility_required ? 'Required' : lang === 'es' ? 'No requerido' : 'Not required' });
    if (reqs.panel_sewn_required !== null && reqs.panel_sewn_required !== undefined) reqEntries.push({ label: L.panelSewnReqLabel, value: reqs.panel_sewn_required ? 'Required' : lang === 'es' ? 'No requerido' : 'Not required' });
    if (reqs.is_female_required !== null && reqs.is_female_required !== undefined) reqEntries.push({ label: L.femaleReqLabel, value: reqs.is_female_required ? 'Required' : lang === 'es' ? 'No requerido' : 'Not required' });
    if (reqs.max_thickness_mm) reqEntries.push({ label: L.maxThicknessLabel, value: `${reqs.max_thickness_mm}mm` });
    if (reqs.stitch_pattern) reqEntries.push({ label: L.stitchPatternLabel, value: reqs.stitch_pattern });
    if (reqs.additional_notes) reqEntries.push({ label: L.notesLabel, value: reqs.additional_notes });
  }

  const reqSectionH = 40 + Math.ceil(reqEntries.length / 2) * 30;
  sections.push({ y, h: reqSectionH });
  y += reqSectionH + 20;

  // Summary section
  const summaryH = 80;
  sections.push({ y, h: summaryH });
  y += summaryH + 20;

  // Gaps section
  const gaps = results?.gaps || [];
  const gapsH = gaps.length > 0 ? 40 + gaps.length * 25 : 60;
  sections.push({ y, h: gapsH });
  y += gapsH + 20;

  // Vest recommendations
  const recs = results?.recommendations || [];
  const colWidths = [40, 180, 100, 120, 60, 80, 80, 100];
  const colNames = [L.rank, L.vestCode, L.type, L.threatLevel, L.layers, L.weight, L.thickness, L.matchScore];
  const headerRowH = 40;
  const rowH = 50;
  const tableH = recs.length > 0 ? headerRowH + recs.length * rowH : 60;
  sections.push({ y, h: tableH });
  y += tableH + 50;

  // Certifications detail for each vest — 2 columns
  const colGap = 30;
  const colW = (CW - colGap) / 2;
  const measureCanvas = document.createElement('canvas');
  const measureCtx = measureCanvas.getContext('2d')!;
  let certH = 0;
  const vestBlockHeights: number[] = [];
  if (recs.length > 0) {
    certH = 40;
    for (const vest of recs) {
      let bh = 25; // header line
      if (vest.certifications.length > 0) {
        bh += 22; // "Certifications:" label
        measureCtx.font = '400 12px Arial, sans-serif';
        for (const cert of vest.certifications) {
          const certText = `${cert.name}${cert.lab_name ? ' — ' + cert.lab_name : ''}${cert.certification_number ? ' (#' + cert.certification_number + ')' : ''}${cert.test_date ? ' — ' + new Date(cert.test_date).toLocaleDateString() : ''}`;
          const certLines = wrapCanvasText(measureCtx, certText, colW - 60);
          bh += certLines.length * 20;
        }
      }
      if (vest.match_gaps.length > 0) {
        bh += 22; // "Gaps:" label
        for (const gap of vest.match_gaps) {
          const gapLines = wrapCanvasText(measureCtx, `• ${gap}`, colW - 60);
          bh += gapLines.length * 20;
        }
      }
      bh += 15; // spacing after each vest block
      vestBlockHeights.push(bh);
    }
    // Split into 2 columns
    const halfCount = Math.ceil(recs.length / 2);
    let leftH = 0, rightH = 0;
    for (let i = 0; i < recs.length; i++) {
      if (i < halfCount) leftH += vestBlockHeights[i];
      else rightH += vestBlockHeights[i];
    }
    certH += Math.max(leftH, rightH);
  }
  if (certH > 0) {
    sections.push({ y, h: certH });
    y += certH + 20;
  }

  // Footer
  const footerH = 60;
  y += footerH + 40;

  const totalH = y;

  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = totalH;
  const ctx = canvas.getContext('2d')!;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, W, totalH);
  ctx.textBaseline = 'top';

  // Header
  ctx.fillStyle = '#102a43';
  ctx.font = '800 32px Arial, sans-serif';
  ctx.fillText(L.title, M, 30);

  ctx.fillStyle = '#667085';
  ctx.font = '500 16px Arial, sans-serif';
  ctx.fillText(
    `${L.documentName}: ${doc.original_name || doc.filename}  |  ${L.date}: ${new Date(doc.created_at).toLocaleDateString()}`,
    M, 68
  );

  // Requirements section
  y = headerH;
  ctx.fillStyle = '#102a43';
  ctx.font = '700 20px Arial, sans-serif';
  ctx.fillText(L.extractedRequirements, M, y);
  y += 35;

  if (reqEntries.length === 0) {
    ctx.fillStyle = '#9ca3af';
    ctx.font = '400 14px Arial, sans-serif';
    ctx.fillText(lang === 'es' ? 'Sin requisitos específicos extraídos.' : 'No specific requirements extracted.', M, y);
  } else {
    ctx.font = '500 14px Arial, sans-serif';
    for (let i = 0; i < reqEntries.length; i++) {
      const col = i % 2;
      const row = Math.floor(i / 2);
      const x = M + col * (CW / 2);
      const ry = y + row * 30;
      ctx.fillStyle = '#667085';
      ctx.font = '500 13px Arial, sans-serif';
      ctx.fillText(reqEntries[i].label + ':', x, ry);
      ctx.fillStyle = '#172033';
      ctx.font = '600 13px Arial, sans-serif';
      const valLines = wrapCanvasText(ctx, reqEntries[i].value, CW / 2 - 120);
      ctx.fillText(valLines[0], x + 110, ry);
    }
  }

  // Summary section
  y = sections[1].y;
  ctx.fillStyle = '#102a43';
  ctx.font = '700 20px Arial, sans-serif';
  ctx.fillText(L.summary, M, y);
  y += 35;

  if (results) {
    const summaryItems = [
      { label: L.certifiedVests, value: String(results.summary.total_certified_vests), color: '#102a43' },
      { label: L.matched, value: String(results.summary.total_matched), color: '#4f46e5' },
      { label: L.topScore, value: `${results.summary.top_score.toFixed(0)}%`, color: '#16a34a' },
    ];
    const itemW = CW / 3;
    for (let i = 0; i < summaryItems.length; i++) {
      const x = M + i * itemW;
      ctx.fillStyle = summaryItems[i].color;
      ctx.font = '800 28px Arial, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(summaryItems[i].value, x + itemW / 2, y);
      ctx.fillStyle = '#667085';
      ctx.font = '500 14px Arial, sans-serif';
      ctx.fillText(summaryItems[i].label, x + itemW / 2, y + 35);
    }
    ctx.textAlign = 'left';
  }

  // Gaps section
  y = sections[2].y;
  ctx.fillStyle = '#102a43';
  ctx.font = '700 20px Arial, sans-serif';
  ctx.fillText(L.coverageGaps, M, y);
  y += 35;

  if (gaps.length === 0) {
    ctx.fillStyle = '#16a34a';
    ctx.font = '500 14px Arial, sans-serif';
    ctx.fillText(`✓ ${L.noGaps}`, M, y);
  } else {
    ctx.fillStyle = '#ea580c';
    ctx.font = '400 14px Arial, sans-serif';
    for (const gap of gaps) {
      const gapLines = wrapCanvasText(ctx, `• ${gap}`, CW);
      for (const line of gapLines) {
        ctx.fillText(line, M, y);
        y += 22;
      }
    }
  }

  // Vest recommendations table
  y = sections[3].y;
  ctx.fillStyle = '#102a43';
  ctx.font = '700 20px Arial, sans-serif';
  ctx.fillText(`${L.recommendedVests} (${recs.length})`, M, y);
  y += 35;

  if (recs.length === 0) {
    ctx.fillStyle = '#9ca3af';
    ctx.font = '400 14px Arial, sans-serif';
    ctx.fillText(L.noMatches, M, y);
  } else {
    // Table header
    ctx.fillStyle = '#102a43';
    ctx.fillRect(M, y, CW, headerRowH);
    ctx.fillStyle = '#ffffff';
    ctx.font = '700 14px Arial, sans-serif';
    let x = M;
    for (let i = 0; i < colNames.length; i++) {
      ctx.fillText(colNames[i], x + 6, y + 12);
      x += colWidths[i];
    }
    y += headerRowH;

    // Table rows
    for (let r = 0; r < recs.length; r++) {
      const vest = recs[r];
      const isEven = r % 2 === 0;
      ctx.fillStyle = isEven ? '#ffffff' : '#f7f9fc';
      ctx.fillRect(M, y, CW, rowH);
      ctx.strokeStyle = '#e5e7eb';
      ctx.lineWidth = 1;
      ctx.strokeRect(M, y, CW, rowH);

      x = M;
      ctx.font = '600 13px Arial, sans-serif';
      ctx.fillStyle = '#102a43';
      ctx.fillText(String(r + 1), x + 6, y + 14);
      x += colWidths[0];

      ctx.font = '600 13px Arial, sans-serif';
      ctx.fillStyle = '#4f46e5';
      ctx.fillText(vest.vest_code, x + 6, y + 14);
      x += colWidths[1];

      ctx.font = '500 13px Arial, sans-serif';
      ctx.fillStyle = '#667085';
      ctx.fillText(vest.vest_type || '—', x + 6, y + 14);
      x += colWidths[2];

      ctx.fillStyle = '#172033';
      ctx.fillText(vest.threat_level || '—', x + 6, y + 14);
      x += colWidths[3];

      ctx.fillText(String(vest.total_layers || '—'), x + 6, y + 14);
      x += colWidths[4];

      ctx.fillText(vest.weight_g ? `${vest.weight_g}g` : '—', x + 6, y + 14);
      x += colWidths[5];

      ctx.fillText(vest.total_thickness_mm ? `${vest.total_thickness_mm}mm` : '—', x + 6, y + 14);
      x += colWidths[6];

      // Match score with color
      const score = vest.match_score;
      ctx.font = '700 14px Arial, sans-serif';
      ctx.fillStyle = score >= 80 ? '#16a34a' : score >= 50 ? '#ca8a04' : '#dc2626';
      ctx.fillText(`${score.toFixed(0)}%`, x + 6, y + 14);

      y += rowH;
    }
  }

  // Certifications & gaps detail — 2 columns
  if (sections.length > 4 && recs.length > 0) {
    y = sections[4].y;
    ctx.fillStyle = '#102a43';
    ctx.font = '700 20px Arial, sans-serif';
    ctx.fillText(`${L.certifications} & ${L.gaps}`, M, y);
    y += 35;

    const halfCount = Math.ceil(recs.length / 2);
    const leftX = M;
    const rightX = M + colW + colGap;
    let leftY = y;
    let rightY = y;

    for (let i = 0; i < recs.length; i++) {
      const vest = recs[i];
      const isLeft = i < halfCount;
      const colX = isLeft ? leftX : rightX;
      let cy = isLeft ? leftY : rightY;

      ctx.fillStyle = '#4f46e5';
      ctx.font = '700 15px Arial, sans-serif';
      ctx.fillText(`${vest.vest_code} — ${L.matchScore}: ${vest.match_score.toFixed(0)}%`, colX, cy);
      cy += 25;

      // Certifications
      if (vest.certifications.length > 0) {
        ctx.fillStyle = '#16a34a';
        ctx.font = '600 13px Arial, sans-serif';
        ctx.fillText(`✓ ${L.certifications}:`, colX + 20, cy);
        cy += 22;
        ctx.font = '400 12px Arial, sans-serif';
        ctx.fillStyle = '#667085';
        for (const cert of vest.certifications) {
          const certText = `${cert.name}${cert.lab_name ? ' — ' + cert.lab_name : ''}${cert.certification_number ? ' (#' + cert.certification_number + ')' : ''}${cert.test_date ? ' — ' + new Date(cert.test_date).toLocaleDateString() : ''}`;
          const certLines = wrapCanvasText(ctx, certText, colW - 60);
          for (const line of certLines) {
            ctx.fillText(line, colX + 40, cy);
            cy += 20;
          }
        }
      }

      // Gaps
      if (vest.match_gaps.length > 0) {
        ctx.fillStyle = '#ea580c';
        ctx.font = '600 13px Arial, sans-serif';
        ctx.fillText(`⚠ ${L.gaps}:`, colX + 20, cy);
        cy += 22;
        ctx.font = '400 12px Arial, sans-serif';
        ctx.fillStyle = '#667085';
        for (const gap of vest.match_gaps) {
          const gapLines = wrapCanvasText(ctx, `• ${gap}`, colW - 60);
          for (const line of gapLines) {
            ctx.fillText(line, colX + 40, cy);
            cy += 20;
          }
        }
      }

      cy += 15;
      if (isLeft) leftY = cy;
      else rightY = cy;
    }
  }

  // Footer
  y = totalH - footerH - 20;
  ctx.fillStyle = '#667085';
  ctx.font = '500 13px Arial, sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText(L.footer, M, y);
  ctx.textAlign = 'right';
  ctx.fillText(`${L.generated} ${new Date().toLocaleDateString()}`, W - M, y);
  ctx.textAlign = 'left';

  // Generate PDF (A4 portrait)
  const pageW = 595.28;
  const pageH = 841.89;
  const pdfBlob = canvasToPdfPages(canvas, pageW, pageH);

  const url = URL.createObjectURL(pdfBlob);
  const a = document.createElement('a');
  a.href = url;
  const langSuffix = lang === 'es' ? 'ES' : 'EN';
  a.download = `RFP_Report_${langSuffix}_${doc.original_name || doc.filename}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
