import { useEffect, useId, useRef, useState } from 'react'
import './Select.css'

/**
 * Desplegable con el estilo de la consola. El <select> nativo no deja
 * estilizar su lista (fondo negro, resaltado gris del sistema), así que
 * este componente dibuja la lista él mismo y mantiene el comportamiento
 * de teclado: flechas, Inicio/Fin, Enter/Espacio para elegir, Escape
 * para cerrar y escribir letras para saltar a una opción.
 *
 * Uso: <Select value={v} onChange={(valor) => …} options={[{ value, label }]} />
 */
export default function Select({ value, onChange, options, placeholder = 'Elige…', disabled = false, align = 'left', className = '', size, 'aria-label': ariaLabel }) {
  const [open, setOpen] = useState(false)
  const [hi, setHi] = useState(-1)
  const ref = useRef(null)
  const listRef = useRef(null)
  const typed = useRef({ text: '', at: 0 })
  const id = useId()

  const idx = options.findIndex((o) => String(o.value) === String(value))
  const current = idx >= 0 ? options[idx] : null

  function openList() {
    setHi(idx >= 0 ? idx : 0)
    setOpen(true)
  }

  useEffect(() => {
    if (!open) return undefined
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  useEffect(() => {
    if (!open || hi < 0) return
    listRef.current?.children[hi]?.scrollIntoView({ block: 'nearest' })
  }, [open, hi])

  function choose(i) {
    const opt = options[i]
    if (!opt || opt.disabled) return
    setOpen(false)
    if (String(opt.value) !== String(value)) onChange(opt.value)
  }

  function onKey(e) {
    if (disabled) return
    const move = (d) => {
      e.preventDefault()
      if (!open) return openList()
      let i = hi
      for (let k = 0; k < options.length; k++) {
        i = (i + d + options.length) % options.length
        if (!options[i].disabled) break
      }
      setHi(i)
    }
    switch (e.key) {
      case 'ArrowDown': return move(1)
      case 'ArrowUp': return move(-1)
      case 'Home': e.preventDefault(); return setHi(0)
      case 'End': e.preventDefault(); return setHi(options.length - 1)
      case 'Enter':
      case ' ':
        e.preventDefault()
        if (open) choose(hi)
        else openList()
        return
      case 'Escape':
        if (open) { e.preventDefault(); setOpen(false) }
        return
      case 'Tab':
        setOpen(false)
        return
      default: {
        if (e.key.length !== 1) return
        const now = Date.now()
        typed.current = { text: now - typed.current.at < 700 ? typed.current.text + e.key : e.key, at: now }
        const q = typed.current.text.toLowerCase()
        const found = options.findIndex((o) => String(o.label).toLowerCase().startsWith(q))
        if (found >= 0) {
          if (open) setHi(found)
          else choose(found)
        }
      }
    }
  }

  return (
    <div className={`sel ${open ? 'open' : ''} ${disabled ? 'disabled' : ''} ${size === 'sm' ? 'sm' : ''} align-${align} ${className}`} ref={ref}>
      <button
        type="button"
        className="sel-btn"
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={onKey}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-list`}
        aria-label={ariaLabel}
      >
        <span className={`sel-label ${current ? '' : 'placeholder'}`}>{current ? current.label : placeholder}</span>
        <svg className="sel-chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
      </button>
      {open && (
        <ul className="sel-pop" role="listbox" id={`${id}-list`} ref={listRef} aria-activedescendant={hi >= 0 ? `${id}-${hi}` : undefined}>
          {options.map((o, i) => (
            <li
              key={String(o.value)}
              id={`${id}-${i}`}
              role="option"
              aria-selected={i === idx}
              aria-disabled={o.disabled || undefined}
              className={`sel-opt ${i === idx ? 'selected' : ''} ${i === hi ? 'hi' : ''} ${o.disabled ? 'disabled' : ''}`}
              onMouseEnter={() => setHi(i)}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => choose(i)}
            >
              <span className="sel-opt-label">{o.label}</span>
              {i === idx && (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m5 12 5 5 9-10" /></svg>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
