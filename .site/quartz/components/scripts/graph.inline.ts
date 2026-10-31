import type { ContentDetails } from "../../plugins/emitters/contentIndex"
import {
  SimulationNodeDatum,
  SimulationLinkDatum,
  Simulation,
  forceSimulation,
  forceManyBody,
  forceCenter,
  forceLink,
  forceCollide,
  forceRadial,
  zoomIdentity,
  select,
  drag,
  zoom,
} from "d3"
import { Text, Graphics, Application, Container, Circle, RendererType } from "pixi.js"
// Pixi's CSP adapter replaces generated functions with interpreted implementations.
import "pixi.js/unsafe-eval"
import { Group as TweenGroup, Tween as Tweened } from "@tweenjs/tween.js"
import { registerEscapeHandler, removeAllChildren } from "./util"
import { FullSlug, SimpleSlug, getFullSlug, resolveRelative, simplifySlug } from "../../util/path"
import { D3Config } from "../Graph"
import { renderSvgGraph } from "./graph-svg"

type GraphicsInfo = {
  color: string
  gfx: Graphics
  alpha: number
  active: boolean
}

type NodeData = {
  id: SimpleSlug
  text: string
  tags: string[]
} & SimulationNodeDatum

type SimpleLinkData = {
  source: SimpleSlug
  target: SimpleSlug
}

type LinkData = {
  source: NodeData
  target: NodeData
} & SimulationLinkDatum<NodeData>

type LinkRenderData = GraphicsInfo & {
  simulationData: LinkData
}

type NodeRenderData = GraphicsInfo & {
  simulationData: NodeData
  label: Text
}

const localStorageKey = "graph-visited"
function getVisited(): Set<SimpleSlug> {
  try {
    const visited: unknown = JSON.parse(localStorage.getItem(localStorageKey) ?? "[]")
    return new Set(
      Array.isArray(visited)
        ? visited.filter((slug): slug is SimpleSlug => typeof slug === "string")
        : [],
    )
  } catch {
    return new Set()
  }
}

function addToVisited(slug: SimpleSlug) {
  const visited = getVisited()
  visited.add(slug)
  try {
    localStorage.setItem(localStorageKey, JSON.stringify([...visited]))
  } catch {
    return
  }
}

let graphDataRequest: Promise<Record<string, ContentDetails>> | undefined

function loadGraphData(fullSlug: FullSlug, retry: boolean) {
  if (retry) {
    const root = resolveRelative(fullSlug, "/" as SimpleSlug).replace(/\/$/, "")
    graphDataRequest = fetch(
      new URL(`${root}/static/contentIndex.json`, window.location.href),
    ).then((response) => {
      if (!response.ok) throw new Error(`Graph data request failed (${response.status})`)
      return response.json()
    })
  }
  return (graphDataRequest ??= fetchData)
}

type TweenNode = {
  update: (time: number) => void
  stop: () => void
}

async function renderGraph(
  graph: HTMLElement,
  fullSlug: FullSlug,
  signal: AbortSignal,
  retry: boolean,
) {
  const slug = simplifySlug(fullSlug)
  const visited = getVisited()

  let {
    drag: enableDrag,
    zoom: enableZoom,
    depth,
    scale,
    repelForce,
    centerForce,
    linkDistance,
    fontSize,
    opacityScale,
    removeTags,
    showTags,
    focusOnHover,
    enableRadial,
  } = JSON.parse(graph.dataset["cfg"]!) as D3Config

  const data: Map<SimpleSlug, ContentDetails> = new Map(
    Object.entries<ContentDetails>(await loadGraphData(fullSlug, retry)).map(([k, v]) => [
      simplifySlug(k as FullSlug),
      v,
    ]),
  )
  signal.throwIfAborted()
  removeAllChildren(graph)
  const links: SimpleLinkData[] = []
  const tags: SimpleSlug[] = []
  const validLinks = new Set(data.keys())

  const tweens = new Map<string, TweenNode>()
  for (const [source, details] of data.entries()) {
    const outgoing = details.links ?? []

    for (const dest of outgoing) {
      if (validLinks.has(dest)) {
        links.push({ source: source, target: dest })
      }
    }

    if (showTags) {
      const localTags = details.tags
        .filter((tag) => !removeTags.includes(tag))
        .map((tag) => simplifySlug(("tags/" + tag) as FullSlug))

      tags.push(...localTags.filter((tag) => !tags.includes(tag)))

      for (const tag of localTags) {
        links.push({ source: source, target: tag })
      }
    }
  }

  const neighbourhood = new Set<SimpleSlug>()
  const wl: (SimpleSlug | "__SENTINEL")[] = [slug, "__SENTINEL"]
  if (depth >= 0) {
    while (depth >= 0 && wl.length > 0) {
      // compute neighbours
      const cur = wl.shift()!
      if (cur === "__SENTINEL") {
        depth--
        wl.push("__SENTINEL")
      } else {
        neighbourhood.add(cur)
        const outgoing = links.filter((l) => l.source === cur)
        const incoming = links.filter((l) => l.target === cur)
        wl.push(...outgoing.map((l) => l.target), ...incoming.map((l) => l.source))
      }
    }
  } else {
    validLinks.forEach((id) => neighbourhood.add(id))
    if (showTags) tags.forEach((tag) => neighbourhood.add(tag))
  }

  const nodes = [...neighbourhood].map((url) => {
    const text = url.startsWith("tags/") ? "#" + url.substring(5) : (data.get(url)?.title ?? url)
    return {
      id: url,
      text,
      tags: data.get(url)?.tags ?? [],
    }
  })
  const nodeByIdMap = new Map(nodes.map((node) => [node.id, node]))
  const graphData: { nodes: NodeData[]; links: LinkData[] } = {
    nodes,
    links: links
      .filter((l) => neighbourhood.has(l.source) && neighbourhood.has(l.target))
      .map((l) => ({
        source: nodeByIdMap.get(l.source)!,
        target: nodeByIdMap.get(l.target)!,
      })),
  }
  const degreeMap = new Map<SimpleSlug, number>()
  for (const link of graphData.links) {
    degreeMap.set(link.source.id, (degreeMap.get(link.source.id) ?? 0) + 1)
    if (link.target.id !== link.source.id) {
      degreeMap.set(link.target.id, (degreeMap.get(link.target.id) ?? 0) + 1)
    }
  }

  const width = graph.offsetWidth
  const height = Math.max(graph.offsetHeight, 1)

  // we virtualize the simulation and use pixi to actually render it
  const simulation: Simulation<NodeData, LinkData> = forceSimulation<NodeData>(graphData.nodes)
    .force("charge", forceManyBody().strength(-100 * repelForce))
    .force("center", forceCenter().strength(centerForce))
    .force("link", forceLink(graphData.links).distance(linkDistance))
    .force("collide", forceCollide<NodeData>((n) => nodeRadius(n)).iterations(3))

  const radius = (Math.min(width, height) / 2) * 0.8
  if (enableRadial) simulation.force("radial", forceRadial(radius).strength(0.2))

  // precompute style prop strings as pixi doesn't support css variables
  const cssVars = [
    "--secondary",
    "--tertiary",
    "--gray",
    "--light",
    "--lightgray",
    "--dark",
    "--darkgray",
    "--bodyFont",
  ] as const
  const computedStyleMap = cssVars.reduce(
    (acc, key) => {
      acc[key] = getComputedStyle(document.documentElement).getPropertyValue(key)
      return acc
    },
    {} as Record<(typeof cssVars)[number], string>,
  )

  // calculate color
  const color = (d: NodeData) => {
    const isCurrent = d.id === slug
    if (isCurrent) {
      return computedStyleMap["--secondary"]
    } else if (visited.has(d.id) || d.id.startsWith("tags/")) {
      return computedStyleMap["--tertiary"]
    } else {
      return computedStyleMap["--gray"]
    }
  }

  function nodeRadius(d: NodeData) {
    return 2 + Math.sqrt(degreeMap.get(d.id) ?? 0)
  }

  let hoveredNodeId: string | null = null
  let hoveredNeighbours: Set<string> = new Set()
  const linkRenderData: LinkRenderData[] = []
  const nodeRenderData: NodeRenderData[] = []
  function updateHoverInfo(newHoveredId: string | null) {
    hoveredNodeId = newHoveredId

    if (newHoveredId === null) {
      hoveredNeighbours = new Set()
      for (const n of nodeRenderData) {
        n.active = false
      }

      for (const l of linkRenderData) {
        l.active = false
      }
    } else {
      hoveredNeighbours = new Set()
      for (const l of linkRenderData) {
        const linkData = l.simulationData
        if (linkData.source.id === newHoveredId || linkData.target.id === newHoveredId) {
          hoveredNeighbours.add(linkData.source.id)
          hoveredNeighbours.add(linkData.target.id)
        }

        l.active = linkData.source.id === newHoveredId || linkData.target.id === newHoveredId
      }

      for (const n of nodeRenderData) {
        n.active = hoveredNeighbours.has(n.simulationData.id)
      }
    }
  }

  let dragStartTime = 0
  let dragging = false

  function renderLinks() {
    tweens.get("link")?.stop()
    const tweenGroup = new TweenGroup()

    for (const l of linkRenderData) {
      let alpha = 1

      // if we are hovering over a node, we want to highlight the immediate neighbours
      // with full alpha and the rest with default alpha
      if (hoveredNodeId) {
        alpha = l.active ? 1 : 0.2
      }

      l.color = l.active ? computedStyleMap["--gray"] : computedStyleMap["--lightgray"]
      tweenGroup.add(new Tweened<LinkRenderData>(l).to({ alpha }, 200))
    }

    tweenGroup.getAll().forEach((tw) => tw.start())
    tweens.set("link", {
      update: tweenGroup.update.bind(tweenGroup),
      stop() {
        tweenGroup.getAll().forEach((tw) => tw.stop())
      },
    })
  }

  function renderLabels() {
    tweens.get("label")?.stop()
    const tweenGroup = new TweenGroup()

    const defaultScale = 1 / scale
    const activeScale = defaultScale * 1.1
    for (const n of nodeRenderData) {
      const nodeId = n.simulationData.id

      if (hoveredNodeId === nodeId) {
        tweenGroup.add(
          new Tweened<Text>(n.label).to(
            {
              alpha: 1,
              scale: { x: activeScale, y: activeScale },
            },
            100,
          ),
        )
      } else {
        tweenGroup.add(
          new Tweened<Text>(n.label).to(
            {
              alpha: n.label.alpha,
              scale: { x: defaultScale, y: defaultScale },
            },
            100,
          ),
        )
      }
    }

    tweenGroup.getAll().forEach((tw) => tw.start())
    tweens.set("label", {
      update: tweenGroup.update.bind(tweenGroup),
      stop() {
        tweenGroup.getAll().forEach((tw) => tw.stop())
      },
    })
  }

  function renderNodes() {
    tweens.get("hover")?.stop()

    const tweenGroup = new TweenGroup()
    for (const n of nodeRenderData) {
      let alpha = 1

      // if we are hovering over a node, we want to highlight the immediate neighbours
      if (hoveredNodeId !== null && focusOnHover) {
        alpha = n.active ? 1 : 0.2
      }

      tweenGroup.add(new Tweened<Graphics>(n.gfx, tweenGroup).to({ alpha }, 200))
    }

    tweenGroup.getAll().forEach((tw) => tw.start())
    tweens.set("hover", {
      update: tweenGroup.update.bind(tweenGroup),
      stop() {
        tweenGroup.getAll().forEach((tw) => tw.stop())
      },
    })
  }

  function renderPixiFromD3() {
    renderNodes()
    renderLinks()
    renderLabels()
  }

  tweens.forEach((tween) => tween.stop())
  tweens.clear()

  const svgFallback = () => {
    simulation.stop()
    return renderSvgGraph(graph, graphData.nodes, graphData.links, {
      width,
      height,
      focused: graph.classList.contains("graph-container"),
      current: slug,
      visited,
      drag: enableDrag,
      zoom: enableZoom,
      scale,
      repelForce,
      centerForce,
      linkDistance,
      fontSize,
      radius: (node) => nodeRadius(node as NodeData),
      href: (node) => resolveRelative(fullSlug, node.id as SimpleSlug),
      navigate: (node) => {
        const target = resolveRelative(fullSlug, node.id as SimpleSlug)
        window.spaNavigate(new URL(target, window.location.href))
      },
    })
  }

  if (graphData.nodes.length > 500) return svgFallback()

  const app = new Application()
  let appDestroyed = false
  const destroyApp = () => {
    if (app.renderer && !appDestroyed) {
      appDestroyed = true
      app.destroy()
    }
  }
  const initialization = app.init({
    width,
    height,
    antialias: true,
    autoStart: false,
    autoDensity: true,
    backgroundAlpha: 0,
    preference: "webgpu",
    resolution: window.devicePixelRatio,
    eventMode: "static",
  })
  let initializationTimer: ReturnType<typeof setTimeout> | undefined
  let cancelInitialization = () => {}
  try {
    await Promise.race([
      initialization,
      new Promise<never>((_resolve, reject) => {
        initializationTimer = setTimeout(() => reject(new Error("Graph renderer timed out")), 8000)
        cancelInitialization = () => reject(signal.reason)
        signal.addEventListener("abort", cancelInitialization, { once: true })
      }),
    ])
  } catch (error) {
    simulation.stop()
    void initialization.then(destroyApp, () => {})
    signal.throwIfAborted()
    console.warn("Graph GPU initialization failed, using SVG", error)
    return svgFallback()
  } finally {
    clearTimeout(initializationTimer)
    signal.removeEventListener("abort", cancelInitialization)
  }
  if (signal.aborted) {
    simulation.stop()
    destroyApp()
    signal.throwIfAborted()
  }
  graph.dataset.renderer = "pixi"
  graph.appendChild(app.canvas)
  app.canvas.setAttribute("role", "img")
  app.canvas.setAttribute("aria-label", "Force-directed graph of linked research notes")

  const stage = app.stage
  stage.interactive = false

  const labelsContainer = new Container<Text>({ zIndex: 3, isRenderGroup: true })
  const nodesContainer = new Container<Graphics>({ zIndex: 2, isRenderGroup: true })
  const linkContainer = new Container<Graphics>({ zIndex: 1, isRenderGroup: true })
  stage.addChild(nodesContainer, labelsContainer, linkContainer)

  for (const n of graphData.nodes) {
    const nodeId = n.id

    const label = new Text({
      interactive: false,
      eventMode: "none",
      text: n.text,
      alpha: 0,
      anchor: { x: 0.5, y: 1.2 },
      style: {
        fontSize: fontSize * 15,
        fill: computedStyleMap["--dark"],
        fontFamily: computedStyleMap["--bodyFont"],
      },
      resolution: window.devicePixelRatio * 4,
    })
    label.scale.set(1 / scale)

    let oldLabelOpacity = 0
    const isTagNode = nodeId.startsWith("tags/")
    const gfx = new Graphics({
      interactive: true,
      label: nodeId,
      eventMode: "static",
      hitArea: new Circle(0, 0, nodeRadius(n)),
      cursor: "pointer",
    })
      .circle(0, 0, nodeRadius(n))
      .fill({ color: isTagNode ? computedStyleMap["--light"] : color(n) })
      .on("pointerover", (e) => {
        updateHoverInfo(e.target.label)
        oldLabelOpacity = label.alpha
        if (!dragging) {
          renderPixiFromD3()
        }
      })
      .on("pointerleave", () => {
        updateHoverInfo(null)
        label.alpha = oldLabelOpacity
        if (!dragging) {
          renderPixiFromD3()
        }
      })

    if (isTagNode) {
      gfx.stroke({ width: 2, color: computedStyleMap["--tertiary"] })
    }

    nodesContainer.addChild(gfx)
    labelsContainer.addChild(label)

    const nodeRenderDatum: NodeRenderData = {
      simulationData: n,
      gfx,
      label,
      color: color(n),
      alpha: 1,
      active: false,
    }

    nodeRenderData.push(nodeRenderDatum)
  }

  for (const l of graphData.links) {
    const gfx = new Graphics({ interactive: false, eventMode: "none" })
    linkContainer.addChild(gfx)

    const linkRenderDatum: LinkRenderData = {
      simulationData: l,
      gfx,
      color: computedStyleMap["--lightgray"],
      alpha: 1,
      active: false,
    }

    linkRenderData.push(linkRenderDatum)
  }

  let currentTransform = zoomIdentity
  if (enableDrag) {
    select<HTMLCanvasElement, NodeData | undefined>(app.canvas).call(
      drag<HTMLCanvasElement, NodeData | undefined>()
        .container(() => app.canvas)
        .subject(() => graphData.nodes.find((n) => n.id === hoveredNodeId))
        .on("start", function dragstarted(event) {
          if (!event.active) simulation.alphaTarget(1).restart()
          event.subject.fx = event.subject.x
          event.subject.fy = event.subject.y
          event.subject.__initialDragPos = {
            x: event.subject.x,
            y: event.subject.y,
            fx: event.subject.fx,
            fy: event.subject.fy,
          }
          dragStartTime = Date.now()
          dragging = true
        })
        .on("drag", function dragged(event) {
          const initPos = event.subject.__initialDragPos
          event.subject.fx = initPos.x + (event.x - initPos.x) / currentTransform.k
          event.subject.fy = initPos.y + (event.y - initPos.y) / currentTransform.k
        })
        .on("end", function dragended(event) {
          if (!event.active) simulation.alphaTarget(0)
          event.subject.fx = null
          event.subject.fy = null
          dragging = false

          // if the time between mousedown and mouseup is short, we consider it a click
          if (Date.now() - dragStartTime < 500) {
            const node = graphData.nodes.find((n) => n.id === event.subject.id) as NodeData
            const targ = resolveRelative(fullSlug, node.id)
            window.spaNavigate(new URL(targ, window.location.toString()))
          }
        }),
    )
  } else {
    for (const node of nodeRenderData) {
      node.gfx.on("click", () => {
        const targ = resolveRelative(fullSlug, node.simulationData.id)
        window.spaNavigate(new URL(targ, window.location.toString()))
      })
    }
  }

  if (enableZoom) {
    select<HTMLCanvasElement, NodeData>(app.canvas).call(
      zoom<HTMLCanvasElement, NodeData>()
        .extent([
          [0, 0],
          [width, height],
        ])
        .scaleExtent([0.25, 4])
        .on("zoom", ({ transform }) => {
          currentTransform = transform
          stage.scale.set(transform.k, transform.k)
          stage.position.set(transform.x, transform.y)

          // zoom adjusts opacity of labels too
          const scale = transform.k * opacityScale
          let scaleOpacity = Math.max((scale - 1) / 3.75, 0)
          const activeNodes = nodeRenderData.filter((n) => n.active).flatMap((n) => n.label)

          for (const label of labelsContainer.children) {
            if (!activeNodes.includes(label)) {
              label.alpha = scaleOpacity
            }
          }
        }),
    )
  }

  let stopAnimation = false
  let fallbackCleanup: (() => void) | undefined
  const canvas = app.canvas
  const handleContextLoss = (event?: Event) => {
    event?.preventDefault()
    if (stopAnimation || signal.aborted) return
    stopAnimation = true
    simulation.stop()
    canvas.removeEventListener("webglcontextlost", handleContextLoss)
    destroyApp()
    try {
      fallbackCleanup = svgFallback()
    } catch (error) {
      console.error("Graph SVG rendering failed", error)
      showGraphError(graph, () => graph.dispatchEvent(new Event("graph-retry")))
    }
  }
  canvas.addEventListener("webglcontextlost", handleContextLoss)
  if (app.renderer.type === RendererType.WEBGPU) {
    void (app.renderer as import("pixi.js").WebGPURenderer).gpu.device.lost.then(() => {
      handleContextLoss()
    })
  }
  function animate(time: number) {
    if (stopAnimation) return
    for (const n of nodeRenderData) {
      const { x, y } = n.simulationData
      if (!x || !y) continue
      n.gfx.position.set(x + width / 2, y + height / 2)
      if (n.label) {
        n.label.position.set(x + width / 2, y + height / 2)
      }
    }

    for (const l of linkRenderData) {
      const linkData = l.simulationData
      l.gfx.clear()
      l.gfx.moveTo(linkData.source.x! + width / 2, linkData.source.y! + height / 2)
      l.gfx
        .lineTo(linkData.target.x! + width / 2, linkData.target.y! + height / 2)
        .stroke({ alpha: l.alpha, width: 1, color: l.color })
    }

    tweens.forEach((t) => t.update(time))
    try {
      app.renderer.render(stage)
    } catch (error) {
      console.warn("Graph GPU rendering failed, using SVG", error)
      handleContextLoss()
      return
    }
    requestAnimationFrame(animate)
  }

  requestAnimationFrame(animate)
  return () => {
    stopAnimation = true
    simulation.stop()
    tweens.forEach((tween) => tween.stop())
    canvas.removeEventListener("webglcontextlost", handleContextLoss)
    fallbackCleanup?.()
    if (!fallbackCleanup) destroyApp()
  }
}

function showGraphError(graph: HTMLElement, retry: () => void) {
  const message = document.createElement("p")
  message.setAttribute("role", "alert")
  message.textContent = "Graph unavailable."
  const button = document.createElement("button")
  button.type = "button"
  button.textContent = "Retry graph"
  button.addEventListener("click", retry, { once: true })
  graph.replaceChildren(message, button)
  delete graph.dataset.renderer
}

function startGraph(graph: HTMLElement, fullSlug: FullSlug) {
  let controller: AbortController | undefined
  let cleanup: (() => void) | undefined
  let disposed = false
  const render = (retry = false) => {
    if (disposed) return
    controller?.abort()
    cleanup?.()
    cleanup = undefined
    const current = new AbortController()
    controller = current
    graph.setAttribute("aria-busy", "true")
    graph.textContent = "Loading graph…"
    void renderGraph(graph, fullSlug, current.signal, retry).then(
      (dispose) => {
        if (current.signal.aborted || !graph.isConnected) {
          dispose()
          return
        }
        cleanup = dispose
        graph.removeAttribute("aria-busy")
      },
      (error: unknown) => {
        if (current.signal.aborted || !graph.isConnected) return
        console.error("Graph rendering failed", error)
        graph.removeAttribute("aria-busy")
        showGraphError(graph, () => render(true))
      },
    )
  }
  const retry = () => render(true)
  graph.addEventListener("graph-retry", retry)
  render()
  return () => {
    disposed = true
    controller?.abort()
    cleanup?.()
    graph.removeEventListener("graph-retry", retry)
    graph.removeAttribute("aria-busy")
    removeAllChildren(graph)
  }
}

let localGraphCleanups: (() => void)[] = []
let globalGraphCleanups: (() => void)[] = []

function cleanupLocalGraphs() {
  for (const cleanup of localGraphCleanups) {
    cleanup()
  }
  localGraphCleanups = []
}

function cleanupGlobalGraphs() {
  for (const cleanup of globalGraphCleanups) {
    cleanup()
  }
  globalGraphCleanups = []
}

document.addEventListener("nav", (e: CustomEventMap["nav"]) => {
  const slug = e.detail.url
  addToVisited(simplifySlug(slug))

  function renderLocalGraph() {
    cleanupLocalGraphs()
    const localGraphContainers = document.getElementsByClassName("graph-container")
    for (const container of localGraphContainers) {
      localGraphCleanups.push(startGraph(container as HTMLElement, slug))
    }
  }

  const handleThemeChange = () => {
    renderLocalGraph()
    if (containers.some((container) => container.classList.contains("active"))) renderGlobalGraph()
  }

  document.addEventListener("themechange", handleThemeChange)
  window.addCleanup(() => {
    document.removeEventListener("themechange", handleThemeChange)
  })

  const containers = [...document.getElementsByClassName("global-graph-outer")] as HTMLElement[]
  const dialogHost = document.createElement("div")
  dialogHost.className = "graph"
  dialogHost.append(...containers)
  document.body.append(dialogHost)
  window.addCleanup(() => dialogHost.remove())
  let previousFocus: HTMLElement | null = null
  function renderGlobalGraph() {
    if (!containers.some((container) => container.classList.contains("active"))) {
      previousFocus = document.activeElement as HTMLElement | null
    }
    cleanupGlobalGraphs()
    const slug = getFullSlug(window)
    for (const container of containers) {
      container.classList.add("active")
      const sidebar = container.closest(".sidebar") as HTMLElement
      if (sidebar) {
        sidebar.style.zIndex = "1"
      }

      const graphContainer = container.querySelector(".global-graph-container") as HTMLElement
      if (graphContainer) {
        globalGraphCleanups.push(startGraph(graphContainer, slug))
      }
      container.querySelector<HTMLButtonElement>(".close-graph")?.focus()
    }
  }

  function hideGlobalGraph() {
    const wasOpen = containers.some((container) => container.classList.contains("active"))
    cleanupGlobalGraphs()
    for (const container of containers) {
      container.classList.remove("active")
      const sidebar = container.closest(".sidebar") as HTMLElement
      if (sidebar) {
        sidebar.style.zIndex = ""
      }
    }
    if (wasOpen) previousFocus?.focus()
  }

  function shortcutHandler(e: HTMLElementEventMap["keydown"]) {
    if (e.key === "g" && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
      e.preventDefault()
      const anyGlobalGraphOpen = containers.some((container) =>
        container.classList.contains("active"),
      )
      anyGlobalGraphOpen ? hideGlobalGraph() : renderGlobalGraph()
    }
  }

  containers.forEach((container) => registerEscapeHandler(container, hideGlobalGraph))

  const containerIcons = document.getElementsByClassName("global-graph-icon")
  Array.from(containerIcons).forEach((icon) => {
    icon.addEventListener("click", renderGlobalGraph)
    window.addCleanup(() => icon.removeEventListener("click", renderGlobalGraph))
  })

  const mobileButton = document.createElement("button")
  mobileButton.type = "button"
  mobileButton.dataset.openGraph = ""
  mobileButton.textContent = "Graph view"
  mobileButton.setAttribute("aria-haspopup", "dialog")
  mobileButton.addEventListener("click", renderGlobalGraph)
  document.querySelector(".article-title")?.after(mobileButton)
  const updateMobileButton = () => {
    mobileButton.hidden = Array.from(containerIcons).some((icon) => {
      const bounds = icon.getBoundingClientRect()
      return (
        bounds.width > 0 &&
        bounds.left >= 0 &&
        bounds.right <= window.innerWidth &&
        getComputedStyle(icon).visibility === "visible"
      )
    })
  }
  updateMobileButton()
  window.addEventListener("resize", updateMobileButton)
  window.addCleanup(() => {
    window.removeEventListener("resize", updateMobileButton)
    mobileButton.removeEventListener("click", renderGlobalGraph)
    mobileButton.remove()
  })

  document.querySelectorAll(".close-graph").forEach((button) => {
    button.addEventListener("click", hideGlobalGraph)
    window.addCleanup(() => button.removeEventListener("click", hideGlobalGraph))
  })

  document.addEventListener("keydown", shortcutHandler)
  window.addCleanup(() => {
    document.removeEventListener("keydown", shortcutHandler)
    cleanupLocalGraphs()
    cleanupGlobalGraphs()
  })
  renderLocalGraph()
})
