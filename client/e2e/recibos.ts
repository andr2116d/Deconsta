import { execFileSync } from 'node:child_process'
import { randomInt } from 'node:crypto'
import { fileURLToPath } from 'node:url'

const SERVER = fileURLToPath(new URL('../../server', import.meta.url))

const DIBUJAR = `
import io, sys
from PIL import Image, ImageDraw, ImageFont
lineas = sys.argv[1].split("|")
lienzo = Image.new("RGB", (1200, 760), "white")
dibujo = ImageDraw.Draw(lienzo)
fuente = ImageFont.load_default(size=36)
for i, linea in enumerate(lineas):
    dibujo.text((60, 60 + i * 90), linea, fill="black", font=fuente)
salida = io.BytesIO()
lienzo.save(salida, format="PNG")
sys.stdout.buffer.write(salida.getvalue())
`

/** Un recibo legible con números propios: cada uno es un documento distinto. */
export function reciboDeLuz(importe = '182.40'): Buffer {
  const lineas = [
    'HIDRANDINA S.A.  RUC 20132023540',
    `RECIBO N. S001-${randomInt(10_000_000, 99_999_999)}`,
    `Suministro: ${randomInt(10_000_000, 99_999_999)}`,
    'Titular: PRUEBA AUTOMATIZADA',
    'Periodo: SETIEMBRE 2026',
    'Fecha de vencimiento: 28/10/2026',
    `TOTAL A PAGAR S/ ${importe}`,
  ]
  return execFileSync('uv', ['run', 'python', '-c', DIBUJAR, lineas.join('|')], { cwd: SERVER })
}
