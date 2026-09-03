interface Recommendation {
  composition: string;
  vest_type: string;
  total_layers: number;
  source: string;
  source_detail: string;
  predicted_mean_bfd_mm: number;
  predicted_max_bfd_mm: number;
  predicted_min_bfd_mm: number;
  max_perforation_probability: number;
  extrapolation_warning: boolean;
  out_of_range_features: string[];
  ci_width_mm: number;
  feature_space_distance: number;
  comparable_training_shots: number;
  scores: {
    uncertainty: number;
    distance: number;
    sparsity: number;
    practical: number;
    composite: number;
  };
  reason: string;
  layers: Array<{
    material_id: string;
    material_name: string;
    material_class: string | null;
    layer_count: number;
    layer_index: number;
  }>;
  prediction_summary: {
    mean_bfd_mm: number | null;
    max_bfd_mm: number | null;
    min_bfd_mm: number | null;
    std_bfd_mm: number | null;
  };
}

interface RecommendTestsResponse {
  recommendations: Recommendation[];
  summary: {
    total_candidates_generated: number;
    total_candidates_scored: number;
    returned: number;
    model_version: string;
    protocol_id: string;
  };
}

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
  const jpegDataUrl = canvas.toDataURL('image/jpeg', 0.92);
  const comma = jpegDataUrl.indexOf(',');
  const jpegBytes = base64ToBytes(jpegDataUrl.slice(comma + 1));

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

    const content = `q\n${renderW} 0 0 ${drawH * scale} 0 0 cm\n/Im${p} Do\nQ`;
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

export async function exportRecommendationsPdf(results: RecommendTestsResponse): Promise<void> {
  const recs = results.recommendations;
  if (!recs || recs.length === 0) return;

  const W = 1240;
  const M = 50;
  const CW = W - M * 2;
  const headerH = 90;
  const colWidths = [40, 320, 70, 60, 130, 80, 70, 200, 70];
  const colNames = ['#', 'Composition', 'Type', 'Layers', 'Pred. BFD (mm)', 'Perf. Prob', 'Test Value', 'Why?', 'Source'];
  const rowH = 50;
  const headerRowH = 40;

  const tableH = headerRowH + recs.length * rowH;
  const footerH = 60;
  const totalH = headerH + tableH + footerH + 40;

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
  ctx.fillText('Test Recommendations', M, 30);

  ctx.fillStyle = '#667085';
  ctx.font = '500 16px Arial, sans-serif';
  ctx.fillText(
    `${results.summary.total_candidates_generated} generated → ${results.summary.total_candidates_scored} scored → ${results.summary.returned} shown | Model: ${results.summary.model_version}`,
    M, 68
  );

  // Table header
  let y = headerH;
  ctx.fillStyle = '#102a43';
  ctx.fillRect(M, y, CW, headerRowH);

  ctx.fillStyle = '#ffffff';
  ctx.font = '700 14px Arial, sans-serif';
  ctx.textAlign = 'left';
  let x = M;
  for (let i = 0; i < colNames.length; i++) {
    ctx.fillText(colNames[i], x + 6, y + 12);
    x += colWidths[i];
  }
  y += headerRowH;

  // Table rows
  for (let r = 0; r < recs.length; r++) {
    const rec = recs[r];
    const isEven = r % 2 === 0;
    ctx.fillStyle = isEven ? '#ffffff' : '#f7f9fc';
    ctx.fillRect(M, y, CW, rowH);

    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;
    ctx.strokeRect(M, y, CW, rowH);

    x = M;
    ctx.font = '600 13px Arial, sans-serif';
    ctx.fillStyle = '#102a43';
    ctx.fillText(String(r + 1), x + 6, y + 8);
    x += colWidths[0];

    // Composition (monospace, wrapped)
    ctx.font = '500 12px monospace';
    ctx.fillStyle = '#172033';
    const compLines = wrapCanvasText(ctx, rec.composition, colWidths[1] - 12);
    compLines.slice(0, 2).forEach((line, i) => ctx.fillText(line, x + 6, y + 6 + i * 16));
    x += colWidths[1];

    // Type
    ctx.font = '500 13px Arial, sans-serif';
    ctx.fillStyle = '#667085';
    ctx.fillText(rec.vest_type, x + 6, y + 8);
    x += colWidths[2];

    // Layers
    ctx.fillStyle = '#172033';
    ctx.fillText(String(rec.total_layers), x + 6, y + 8);
    x += colWidths[3];

    // Pred BFD
    ctx.fillStyle = '#172033';
    ctx.font = '600 13px Arial, sans-serif';
    ctx.fillText(`${rec.predicted_mean_bfd_mm?.toFixed(1)} mean`, x + 6, y + 6);
    ctx.font = '400 11px Arial, sans-serif';
    ctx.fillStyle = '#667085';
    ctx.fillText(`${rec.predicted_min_bfd_mm?.toFixed(1)}–${rec.predicted_max_bfd_mm?.toFixed(1)}`, x + 6, y + 24);
    x += colWidths[4];

    // Perf Prob
    const perfPct = (rec.max_perforation_probability * 100).toFixed(1);
    ctx.font = '600 13px Arial, sans-serif';
    ctx.fillStyle = rec.max_perforation_probability > 0.5 ? '#dc2626' : '#667085';
    ctx.fillText(`${perfPct}%`, x + 6, y + 8);
    x += colWidths[5];

    // Test Value (composite score)
    const score = rec.scores.composite;
    ctx.font = '700 13px Arial, sans-serif';
    if (score >= 0.7) ctx.fillStyle = '#dc2626';
    else if (score >= 0.5) ctx.fillStyle = '#ea580c';
    else if (score >= 0.3) ctx.fillStyle = '#ca8a04';
    else ctx.fillStyle = '#16a34a';
    ctx.fillText(score.toFixed(3), x + 6, y + 8);
    x += colWidths[6];

    // Why? (with extrapolation icon)
    let whyX = x + 6;
    if (rec.extrapolation_warning) {
      ctx.fillStyle = '#ea580c';
      ctx.font = '700 12px Arial, sans-serif';
      ctx.fillText('⚠', whyX, y + 6);
      whyX += 16;
    }
    ctx.font = '400 11px Arial, sans-serif';
    ctx.fillStyle = '#667085';
    const whyLines = wrapCanvasText(ctx, rec.reason, colWidths[7] - 12 - (rec.extrapolation_warning ? 16 : 0));
    whyLines.slice(0, 2).forEach((line, i) => ctx.fillText(line, whyX, y + 6 + i * 16));
    x += colWidths[7];

    // Source
    ctx.font = '400 12px Arial, sans-serif';
    ctx.fillStyle = '#9ca3af';
    const sourceLabel = rec.source === 'material_swap' ? 'Swap' : rec.source === 'layer_count_variation' ? 'Layers' : 'Custom';
    ctx.fillText(sourceLabel, x + 6, y + 8);

    y += rowH;
  }

  // Footer
  y += 20;
  ctx.fillStyle = '#667085';
  ctx.font = '500 13px Arial, sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('DeltaDash — Test Recommendations Report', M, y);
  ctx.textAlign = 'right';
  ctx.fillText(`Generated ${new Date().toLocaleDateString()}`, W - M, y);
  ctx.textAlign = 'left';

  // Generate PDF (A4 portrait)
  const pageW = 595.28;
  const pageH = 841.89;
  const pdfBlob = canvasToPdfPages(canvas, pageW, pageH);

  const url = URL.createObjectURL(pdfBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `Test_Recommendations_${results.summary.model_version || 'latest'}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
