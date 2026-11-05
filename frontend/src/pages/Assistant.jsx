import { useRef, useState } from 'react'
import { assistant } from '../api/resources'
import { extractErrorMessage } from '../components/DataState'

const SUGERENCIAS = [
  '¿Cuántas vulnerabilidades críticas tenemos?',
  '¿Qué hallazgos están vencidos?',
  '¿Cuál es el activo más vulnerable?',
  '¿Cómo vamos en cumplimiento ISO 27001?',
  '¿Cuál es nuestro nivel de riesgo?',
  '¿Hay aprobaciones pendientes?',
  '¿Qué vulnerabilidades se están explotando activamente?',
]

/**
 * HU26: preguntas en lenguaje natural. El agente responde solo con los
 * datos ya recolectados y lo dice explícitamente cuando no tiene datos
 * suficientes (no inventa).
 */
export default function Assistant() {
  const [mensajes, setMensajes] = useState([
    { de: 'agente', texto: 'Hola. Pregúntame sobre los hallazgos, el cumplimiento, el riesgo, las aprobaciones o los incidentes de la clínica.' },
  ])
  const [pregunta, setPregunta] = useState('')
  const [pensando, setPensando] = useState(false)
  const fin = useRef(null)

  async function enviar(texto) {
    const q = (texto ?? pregunta).trim()
    if (!q) return
    setPregunta('')
    setMensajes((m) => [...m, { de: 'yo', texto: q }])
    setPensando(true)
    try {
      const { data } = await assistant.ask(q)
      setMensajes((m) => [...m, { de: 'agente', texto: data.respuesta, sinDatos: !data.datos_suficientes, fuentes: data.fuentes, motor: data.motor }])
    } catch (err) {
      setMensajes((m) => [...m, { de: 'agente', texto: extractErrorMessage(err), sinDatos: true }])
    } finally {
      setPensando(false)
      setTimeout(() => fin.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Asistente</h1>
        <p>Preguntas en lenguaje natural sobre los datos que ya recolectó el agente</p>
      </div>
      <div className="panel pb" style={{ maxWidth: 860 }}>
        <div className="chat">
          {mensajes.map((m, i) => (
            <div key={i} className={`burbuja ${m.de} ${m.sinDatos ? 'sin-datos' : ''}`}>
              {m.texto}
              {m.de === 'agente' && m.motor && (
                <small>{m.sinDatos ? 'Sin datos suficientes · ' : ''}Fuentes: {m.fuentes?.join(', ') || '—'} · motor: {m.motor}</small>
              )}
            </div>
          ))}
          {pensando && <div className="burbuja agente muted">Consultando los datos…</div>}
          <div ref={fin} />
        </div>
        <div className="row-actions" style={{ margin: '12px 0' }}>
          {SUGERENCIAS.map((s) => <button key={s} className="btn sm" onClick={() => enviar(s)} disabled={pensando}>{s}</button>)}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); enviar() }} className="row-actions">
          <input value={pregunta} onChange={(e) => setPregunta(e.target.value)} placeholder="Escribe tu pregunta…" maxLength={500} style={{ flex: 1, minWidth: 220 }} />
          <button className="btn pri" disabled={pensando || !pregunta.trim()}>Preguntar</button>
        </form>
      </div>
    </div>
  )
}
