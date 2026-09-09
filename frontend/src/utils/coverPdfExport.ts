interface CoverResumenData {
  title: string;
  coverCode: string;
  geometryName: string;
  fabricType: string;
  fabricWeight: string;
  layerCount: string;
  color: string;
  weightG: string;
  constructionDescription: string;
  availableSizes: string[];
  compatibleVestTypes: string[];
  hasMolle: boolean;
  hasQuickRelease: boolean;
  quickReleaseType: string;
  hasBadana: boolean;
  hasEscudo: boolean;
  hasHombreras: boolean;
  finHeightMm: string;
  finWidthMm: string;
  notes: string;
  frontImageUrl: string;
  backImageUrl: string;
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
    fetch(src)
      .then(res => {
        if (!res.ok) throw new Error('Failed to fetch image');
        return res.blob();
      })
      .then(blob => {
        const reader = new FileReader();
        reader.onload = () => {
          const image = new Image();
          image.onload = () => resolve(image);
          image.onerror = () => reject(new Error('Failed to load image'));
          image.src = reader.result as string;
        };
        reader.onerror = () => reject(new Error('Failed to read image blob'));
        reader.readAsDataURL(blob);
      })
      .catch(() => reject(new Error('Failed to load image')));
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

export async function exportCoverResumenPdf(data: CoverResumenData): Promise<void> {
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

  // Title
  ctx.fillStyle = '#102a43';
  ctx.font = '800 38px Arial, sans-serif';
  ctx.fillText(data.title || 'COVER', M, 48);

  // Cover code
  ctx.fillStyle = '#667085';
  ctx.font = '600 20px Arial, sans-serif';
  ctx.fillText(`Codigo: ${data.coverCode || '---'}`, M, 96);

  // Images section (front and back side by side)
  let contentY = 140;
  const imgBoxH = 300;
  const imgW = (CW - 20) / 2;

  ctx.fillStyle = '#1677ff';
  ctx.font = '800 21px Arial, sans-serif';
  ctx.fillText('IMAGENES', M, contentY);
  contentY += 30;

  const drawImage = async (url: string, label: string, x: number, y: number, maxW: number, maxH: number) => {
    ctx.fillStyle = '#f7f9fc';
    canvasRoundRect(ctx, x, y, maxW, maxH, 14);
    ctx.fill();
    ctx.strokeStyle = '#d9e0ea';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = '#667085';
    ctx.font = '600 16px Arial, sans-serif';
    ctx.fillText(label, x + 10, y + 8);

    try {
      const img = await loadImageFromUrl(url);
      const pad = 35;
      const availW = maxW - pad * 2;
      const availH = maxH - pad * 2 - 20;
      const ratio = img.width / img.height;
      let iw = availW;
      let ih = iw / ratio;
      if (ih > availH) {
        ih = availH;
        iw = ih * ratio;
      }
      const ix = x + (maxW - iw) / 2;
      const iy = y + 25 + (availH - ih) / 2;
      ctx.drawImage(img, ix, iy, iw, ih);
    } catch {
      ctx.fillStyle = '#667085';
      ctx.font = '500 18px Arial, sans-serif';
      ctx.fillText('No disponible', x + maxW / 2 - 60, y + maxH / 2 - 10);
    }
  };

  await drawImage(data.frontImageUrl, 'Frente', M, contentY, imgW, imgBoxH);
  await drawImage(data.backImageUrl, 'Espalda', M + imgW + 20, contentY, imgW, imgBoxH);
  contentY += imgBoxH + 30;

  // Specs table
  ctx.fillStyle = '#102a43';
  ctx.font = '800 27px Arial, sans-serif';
  ctx.fillText('ESPECIFICACIONES', M, contentY);
  contentY += 42;

  const specs: [string, string][] = [
    ['Geometria', data.geometryName || '---'],
    ['Tipo de Tela', data.fabricType || '---'],
    ['Peso de Tela (g/m2)', data.fabricWeight || '---'],
    ['Numero de Capas', data.layerCount || '---'],
    ['Color', data.color || '---'],
    ['Peso Total (g)', data.weightG || '---'],
    ['Tallas Disponibles', data.availableSizes.join(', ') || '---'],
    ['Tipos de Chaleco Compatible', data.compatibleVestTypes.join(', ') || '---'],
    ['MOLLE', data.hasMolle ? 'Si' : 'No'],
    ['Quick Release', data.hasQuickRelease ? `Si (${data.quickReleaseType || '---'})` : 'No'],
    ['Badana', data.hasBadana ? 'Si' : 'No'],
    ['Escudo', data.hasEscudo ? 'Si' : 'No'],
    ['Hombreras', data.hasHombreras ? 'Si' : 'No'],
    ['Altura de Aleta (mm)', data.finHeightMm || '---'],
    ['Ancho de Aleta (mm)', data.finWidthMm || '---'],
  ];

  const labelColW = 380;
  const valueColW = CW - labelColW;
  const rowH = 36;

  // Header row
  ctx.fillStyle = '#102a43';
  ctx.fillRect(M, contentY, CW, rowH);
  ctx.fillStyle = '#ffffff';
  ctx.font = '800 16px Arial, sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('Campo', M + 12, contentY + 9);
  ctx.fillText('Valor', M + labelColW + 12, contentY + 9);
  contentY += rowH;

  specs.forEach((spec, i) => {
    const fill = i % 2 ? '#f7f9fc' : '#ffffff';
    ctx.fillStyle = fill;
    ctx.fillRect(M, contentY, CW, rowH);
    ctx.strokeStyle = '#d9e0ea';
    ctx.lineWidth = 1;
    ctx.strokeRect(M, contentY, CW, rowH);

    ctx.fillStyle = '#172033';
    ctx.font = '500 15px Arial, sans-serif';
    ctx.fillText(spec[0], M + 12, contentY + 9);
    ctx.font = '700 15px Arial, sans-serif';
    ctx.fillText(spec[1], M + labelColW + 12, contentY + 9);
    contentY += rowH;
  });

  // Construction description
  if (data.constructionDescription) {
    contentY += 20;
    ctx.fillStyle = '#102a43';
    ctx.font = '800 21px Arial, sans-serif';
    ctx.fillText('DESCRIPCION DE CONSTRUCCION', M, contentY);
    contentY += 30;
    ctx.fillStyle = '#172033';
    ctx.font = '500 16px Arial, sans-serif';
    const descLines = wrapCanvasText(ctx, data.constructionDescription, CW);
    descLines.forEach(line => {
      ctx.fillText(line, M, contentY);
      contentY += 24;
    });
  }

  // Notes
  if (data.notes) {
    contentY += 20;
    ctx.fillStyle = '#102a43';
    ctx.font = '800 21px Arial, sans-serif';
    ctx.fillText('NOTAS', M, contentY);
    contentY += 30;
    ctx.fillStyle = '#172033';
    ctx.font = '500 16px Arial, sans-serif';
    const noteLines = wrapCanvasText(ctx, data.notes, CW);
    noteLines.forEach(line => {
      ctx.fillText(line, M, contentY);
      contentY += 24;
    });
  }

  // Footer
  ctx.fillStyle = '#667085';
  ctx.font = '500 14px Arial, sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('Visor Tecnico - Covers de Chalecos', M, H - 45);
  ctx.textAlign = 'right';
  ctx.fillText('Pagina 1 - A4', W - M, H - 45);
  ctx.textAlign = 'left';

  const jpegDataUrl = canvas.toDataURL('image/jpeg', 0.92);
  const comma = jpegDataUrl.indexOf(',');
  const jpegBytes = base64ToBytes(jpegDataUrl.slice(comma + 1));
  const pdfBlob = jpegToA4Pdf(jpegBytes, canvas.width, canvas.height);

  const name = (data.title || 'cover')
    .replace(/[^\w\-]+/g, '_')
    .replace(/^_+|_+$/g, '');

  const url = URL.createObjectURL(pdfBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `Cover_${name}_Resumen_A4.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
