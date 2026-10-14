// Click an image in a page to see it full screen. Wheel or +/- zooms at the cursor, drag pans, double-click toggles
// between fit and 2.5x, the arrow keys move between the page's images, and Esc, x or a click outside closes.

const MIN = 1
const MAX = 12

document.addEventListener("nav", () => {
  const images = Array.from(document.querySelectorAll<HTMLImageElement>("article img")).filter(
    (img) =>
      !img.closest(".popover") &&
      !img.closest("a[href]:not([href$='.png']):not([href$='.svg']):not([href$='.jpg'])"),
  )
  if (images.length === 0) return

  const overlay = document.createElement("div")
  overlay.className = "image-zoom"
  overlay.setAttribute("role", "dialog")
  overlay.setAttribute("aria-modal", "true")
  overlay.innerHTML = `
    <div class="image-zoom-stage"><img alt="" draggable="false" /></div>
    <div class="image-zoom-bar">
      <span class="image-zoom-caption"></span>
      <span class="image-zoom-count"></span>
      <button type="button" data-act="out" aria-label="Zoom out">-</button>
      <button type="button" data-act="fit" aria-label="Fit to screen">fit</button>
      <button type="button" data-act="in" aria-label="Zoom in">+</button>
      <a class="image-zoom-open" target="_blank" rel="noopener">open original</a>
      <button type="button" data-act="close" aria-label="Close">&times;</button>
    </div>`
  document.body.appendChild(overlay)
  const stage = overlay.querySelector<HTMLDivElement>(".image-zoom-stage")!
  const view = overlay.querySelector<HTMLImageElement>(".image-zoom-stage img")!
  const caption = overlay.querySelector<HTMLSpanElement>(".image-zoom-caption")!
  const count = overlay.querySelector<HTMLSpanElement>(".image-zoom-count")!
  const original = overlay.querySelector<HTMLAnchorElement>(".image-zoom-open")!

  let index = 0
  let scale = 1
  let x = 0
  let y = 0
  let drag: { px: number; py: number; x: number; y: number } | null = null
  let pressed: EventTarget | null = null
  let travel = 0

  const apply = () => {
    view.style.transform = `translate(${x}px, ${y}px) scale(${scale})`
    stage.classList.toggle("zoomed", scale > 1)
  }
  const fit = () => {
    scale = 1
    x = 0
    y = 0
    apply()
  }
  const zoomAt = (factor: number, cx: number, cy: number) => {
    const next = Math.min(MAX, Math.max(MIN, scale * factor))
    const rect = stage.getBoundingClientRect()
    const ox = cx - rect.left - rect.width / 2
    const oy = cy - rect.top - rect.height / 2
    x = ox - ((ox - x) * next) / scale
    y = oy - ((oy - y) * next) / scale
    scale = next
    if (scale === 1) {
      x = 0
      y = 0
    }
    apply()
  }
  const centre = () => {
    const rect = stage.getBoundingClientRect()
    return [rect.left + rect.width / 2, rect.top + rect.height / 2] as const
  }
  const show = (i: number) => {
    index = (i + images.length) % images.length
    const source = images[index]
    view.src = source.currentSrc || source.src
    view.alt = source.alt
    caption.textContent = source.alt || source.title || ""
    count.textContent = images.length > 1 ? `${index + 1} / ${images.length}` : ""
    original.href = view.src
    fit()
  }
  const open = (i: number) => {
    show(i)
    overlay.classList.add("active")
    document.documentElement.classList.add("image-zoom-lock")
  }
  const close = () => {
    overlay.classList.remove("active")
    document.documentElement.classList.remove("image-zoom-lock")
  }

  images.forEach((img, i) => {
    img.classList.add("image-zoomable")
    const onClick = (e: MouseEvent) => {
      e.preventDefault()
      e.stopPropagation()
      open(i)
    }
    img.addEventListener("click", onClick)
    window.addCleanup(() => img.removeEventListener("click", onClick))
  })

  const onBar = (e: MouseEvent) => {
    const act = (e.target as HTMLElement).closest<HTMLElement>("[data-act]")?.dataset.act
    if (!act) return
    const [cx, cy] = centre()
    if (act === "close") close()
    if (act === "fit") fit()
    if (act === "in") zoomAt(1.5, cx, cy)
    if (act === "out") zoomAt(1 / 1.5, cx, cy)
  }
  const onWheel = (e: WheelEvent) => {
    e.preventDefault()
    zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY)
  }
  const onDown = (e: PointerEvent) => {
    if (e.button !== 0) return
    pressed = e.target
    travel = 0
    if (e.target === stage && scale === 1) return
    drag = { px: e.clientX, py: e.clientY, x, y }
    stage.setPointerCapture(e.pointerId)
  }
  const onMove = (e: PointerEvent) => {
    if (!drag) return
    travel = Math.max(travel, Math.hypot(e.clientX - drag.px, e.clientY - drag.py))
    x = drag.x + e.clientX - drag.px
    y = drag.y + e.clientY - drag.py
    apply()
  }
  const onUp = () => {
    // Only a click that starts and ends on the backdrop, without dragging, closes.
    if (pressed === stage && travel < 4) close()
    drag = null
    pressed = null
  }
  const onDouble = (e: MouseEvent) => (scale > 1 ? fit() : zoomAt(2.5, e.clientX, e.clientY))
  const onKey = (e: KeyboardEvent) => {
    if (!overlay.classList.contains("active")) return
    if (e.key === "Escape") close()
    else if (e.key === "ArrowRight") show(index + 1)
    else if (e.key === "ArrowLeft") show(index - 1)
    else if (e.key === "+" || e.key === "=") zoomAt(1.5, ...centre())
    else if (e.key === "-") zoomAt(1 / 1.5, ...centre())
    else if (e.key === "0") fit()
    else return
    e.preventDefault()
  }

  overlay.querySelector(".image-zoom-bar")!.addEventListener("click", onBar as EventListener)
  stage.addEventListener("wheel", onWheel, { passive: false })
  stage.addEventListener("pointerdown", onDown)
  stage.addEventListener("pointermove", onMove)
  stage.addEventListener("pointerup", onUp)
  stage.addEventListener("dblclick", onDouble)
  document.addEventListener("keydown", onKey)
  window.addCleanup(() => {
    document.removeEventListener("keydown", onKey)
    document.documentElement.classList.remove("image-zoom-lock")
    overlay.remove()
  })
})
