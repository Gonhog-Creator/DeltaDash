interface PdfExportData {
  title: string;
  sheetId: string;
  compatText: string;
  selectedModel: string;
  imageUrl: string;
  sizes: string[];
  rows: string[][];
  area: string[];
  totals: string[];
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

function canvasRoundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
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

function loadImageFromUrl(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    if (!src) {
      reject(new Error('No image available'));
      return;
    }
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('Failed to load image'));
    image.src = src;
  });
}

function jpegToA4Pdf(jpegBytes: Uint8Array, width: number, height: number): Blob {
  const pageW = 595.28;
  const pageH = 841.89;

  const objects: (Uint8Array | string)[] = [];
  objects[1] = bytesToLatin1('<< /Type /Catalog /Pages 2 0 R >>');
  objects[2] = bytesToLatin1('<< /Type /Pages /Kids [3 0 R] /Count 1 >>');
  objects[3] = bytesToLatin1(
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageW} ${pageH}] ` +
    `/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`
  );

  const imageHeader = bytesToLatin1(
    `<< /Type /XObject /Subtype /Image /Width ${width} /Height ${height} ` +
    `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpegBytes.length} >>\nstream\n`
  );
  const imageFooter = bytesToLatin1('\nendstream');
  objects[4] = concatUint8Arrays([imageHeader, jpegBytes, imageFooter]);

  const content = `q\n${pageW} 0 0 ${pageH} 0 0 cm\n/Im0 Do\nQ`;
  const contentBytes = bytesToLatin1(content);
  objects[5] = concatUint8Arrays([
    bytesToLatin1(`<< /Length ${contentBytes.length} >>\nstream\n`),
    contentBytes,
    bytesToLatin1('\nendstream')
  ]);

  const header = bytesToLatin1('%PDF-1.4\n%\xFF\xFF\xFF\xFF\n');
  const chunks: Uint8Array[] = [header];
  const offsets = [0];
  let position = header.length;

  for (let i = 1; i <= 5; i++) {
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
  let xref = `xref\n0 6\n0000000000 65535 f \n`;
  for (let i = 1; i <= 5; i++) {
    xref += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`;
  }
  xref += `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  chunks.push(bytesToLatin1(xref));

  return new Blob(chunks as BlobPart[], { type: 'application/pdf' });
}

export async function exportGeometryPdf(data: PdfExportData): Promise<void> {
  const W = 1240;
  const H = 1754;
  const M = 70;
  const CW = W - M * 2;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;

  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, W, H);
  ctx.textBaseline = 'top';

  ctx.fillStyle = '#102a43';
  ctx.font = '800 38px Arial, sans-serif';
  ctx.fillText(data.title || 'GEOMETRAL', M, 48);

  ctx.fillStyle = '#667085';
  ctx.font = '600 20px Arial, sans-serif';
  ctx.fillText(`Codigo: ${data.sheetId || '---'}`, M, 96);

  ctx.fillStyle = '#1677ff';
  ctx.font = '800 21px Arial, sans-serif';
  ctx.fillText('MODELO', M, 136);
  ctx.fillStyle = '#172033';
  ctx.font = '700 21px Arial, sans-serif';
  ctx.fillText(data.selectedModel || 'No seleccionado', M + 105, 136);

  ctx.fillStyle = '#1677ff';
  ctx.font = '800 21px Arial, sans-serif';
  ctx.fillText('COMPATIBILIDAD', M, 171);
  ctx.fillStyle = '#172033';
  ctx.font = '500 18px Arial, sans-serif';
  const compatLines = wrapCanvasText(ctx, data.compatText, CW - 260);
  compatLines.slice(0, 2).forEach((line, i) => ctx.fillText(line, M + 260, 171 + i * 24));

  let imageBottom = 270;
  try {
    const img = await loadImageFromUrl(data.imageUrl);
    const maxW = CW;
    const maxH = 490;
    const ratio = img.width / img.height;
    let iw = maxW;
    let ih = iw / ratio;
    if (ih > maxH) {
      ih = maxH;
      iw = ih * ratio;
    }
    const ix = M + (CW - iw) / 2;
    const iy = 245 + (maxH - ih) / 2;

    ctx.fillStyle = '#f7f9fc';
    canvasRoundRect(ctx, M, 235, CW, maxH + 30, 14);
    ctx.fill();
    ctx.strokeStyle = '#d9e0ea';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.drawImage(img, ix, iy, iw, ih);
    imageBottom = 235 + maxH + 30;
  } catch {
    ctx.fillStyle = '#f7f9fc';
    ctx.fillRect(M, 235, CW, 180);
    ctx.fillStyle = '#667085';
    ctx.font = '500 20px Arial, sans-serif';
    ctx.fillText('Imagen no disponible para este geometral.', M + 25, 315);
    imageBottom = 415;
  }

  let tableY = imageBottom + 30;
  ctx.fillStyle = '#102a43';
  ctx.font = '800 27px Arial, sans-serif';
  ctx.fillText('TABLA DE MEDIDAS (mm)', M, tableY);
  tableY += 42;

  const sizes = data.sizes || [];
  const cols = 1 + sizes.length * 2;
  const firstColW = 95;
  const dataColW = (CW - firstColW) / Math.max(1, cols - 1);
  const rowH = 39;
  const rows = (data.rows || []).length + 4;

  ctx.fillStyle = '#102a43';
  ctx.fillRect(M, tableY, CW, rowH);
  ctx.fillStyle = '#ffffff';
  ctx.font = '800 16px Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Cota', M + firstColW / 2, tableY + 11);

  sizes.forEach((size, i) => {
    const x = M + firstColW + i * dataColW * 2;
    ctx.fillText(String(size), x + dataColW, tableY + 11);
  });

  tableY += rowH;

  ctx.fillStyle = '#173f5f';
  ctx.fillRect(M, tableY, CW, rowH);
  ctx.fillStyle = '#ffffff';
  ctx.font = '800 14px Arial, sans-serif';
  ctx.fillText('Medidas', M + firstColW / 2, tableY + 11);
  sizes.forEach((_, i) => {
    const x = M + firstColW + i * dataColW * 2;
    ctx.fillText('Frente', x + dataColW / 2, tableY + 11);
    ctx.fillText('Espalda', x + dataColW + dataColW / 2, tableY + 11);
  });

  ctx.textAlign = 'center';
  tableY += rowH;

  function drawDataRow(values: string[], fill: string, bold = false) {
    ctx.fillStyle = fill;
    ctx.fillRect(M, tableY, CW, rowH);
    ctx.strokeStyle = '#d9e0ea';
    ctx.lineWidth = 1;
    ctx.strokeRect(M, tableY, CW, rowH);

    ctx.fillStyle = '#172033';
    ctx.font = `${bold ? '800' : '500'} 14px Arial, sans-serif`;
    ctx.fillText(String(values[0] ?? '---'), M + firstColW / 2, tableY + 11);

    for (let j = 1; j < cols; j++) {
      const x = M + firstColW + (j - 1) * dataColW;
      ctx.fillText(String(values[j] ?? '---'), x + dataColW / 2, tableY + 11);
    }
    tableY += rowH;
  }

  (data.rows || []).forEach((row, i) => {
    drawDataRow(row, i % 2 ? '#f7f9fc' : '#ffffff');
  });

  const areaRow = ['Area (m2)', ...(data.area || [])];
  drawDataRow(areaRow, '#eef5ff', true);

  ctx.fillStyle = '#eaf3ff';
  ctx.fillRect(M, tableY, CW, rowH);
  ctx.strokeStyle = '#d9e0ea';
  ctx.strokeRect(M, tableY, CW, rowH);
  ctx.fillStyle = '#102a43';
  ctx.font = '800 14px Arial, sans-serif';
  ctx.fillText('Area total (m2)', M + firstColW / 2, tableY + 11);

  (data.totals || []).forEach((value, i) => {
    const x = M + firstColW + i * dataColW * 2;
    ctx.fillText(String(value || '---'), x + dataColW, tableY + 11);
  });

  ctx.strokeStyle = '#d9e0ea';
  ctx.lineWidth = 1;
  for (let j = 0; j <= cols; j++) {
    let x: number;
    if (j === 0) x = M;
    else if (j === 1) x = M + firstColW;
    else x = M + firstColW + (j - 1) * dataColW;
    ctx.beginPath();
    ctx.moveTo(x, tableY - rowH * rows);
    ctx.lineTo(x, tableY + rowH);
    ctx.stroke();
  }

  ctx.textAlign = 'left';

  ctx.fillStyle = '#667085';
  ctx.font = '500 14px Arial, sans-serif';
  ctx.fillText('Visor Tecnico - Geometrales de Chalecos', M, H - 45);
  ctx.textAlign = 'right';
  ctx.fillText('Pagina 1 - A4', W - M, H - 45);
  ctx.textAlign = 'left';

  const jpegDataUrl = canvas.toDataURL('image/jpeg', 0.92);
  const comma = jpegDataUrl.indexOf(',');
  const jpegBytes = base64ToBytes(jpegDataUrl.slice(comma + 1));
  const pdfBlob = jpegToA4Pdf(jpegBytes, canvas.width, canvas.height);

  const name = (data.title || 'geometral')
    .replace(/[^\w\-]+/g, '_')
    .replace(/^_+|_+$/g, '');
  const modelSuffix = data.selectedModel
    ? '_' + data.selectedModel.replace(/[^\w\-]+/g, '_').replace(/^_+|_+$/g, '')
    : '';

  const url = URL.createObjectURL(pdfBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `Geometral_${name}${modelSuffix}_A4.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
