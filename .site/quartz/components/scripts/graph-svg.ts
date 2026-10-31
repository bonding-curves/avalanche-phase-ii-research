import {
  drag,
  dragEnable,
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  select,
  zoom,
  zoomIdentity,
  type SimulationNodeDatum,
} from "d3"

type SvgNode = SimulationNodeDatum & { id: string; text: string }
type SvgLink = { source: SvgNode; target: SvgNode }
type SvgOptions = {
  width: number
  height: number
  focused: boolean
  current: string
  visited: Set<string>
  drag: boolean
  zoom: boolean
  scale: number
  repelForce: number
  centerForce: number
  linkDistance: number
  fontSize: number
  radius: (node: SvgNode) => number
  href: (node: SvgNode) => string
  navigate: (node: SvgNode) => void
}

function labelLines(value: string, limit: number): string[] {
  const lines: string[] = []
  for (const word of value.split(/\s+/)) {
    const last = lines.length - 1
    if (last >= 0 && lines[last].length + word.length < limit) lines[last] += " " + word
    else lines.push(word)
  }
  return lines
}

export function renderSvgGraph(
  graph: HTMLElement,
  nodes: SvgNode[],
  links: SvgLink[],
  options: SvgOptions,
): () => void {
  const { width, height, focused } = options
  const large = nodes.length > 500
  let dragView: Window | undefined
  let zoomView: Window | undefined
  graph.replaceChildren()
  graph.dataset.renderer = "svg"
  const svg = select(graph)
    .append("svg")
    .attr("class", "graph-svg")
    .attr("width", "100%")
    .attr("height", height)
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("role", "group")
    .attr("aria-label", "Linked pages")
    .style("display", "block")
    .style("height", `${height}px`)
    .style("touch-action", "none")
  const viewport = svg.append("g")
  const world = viewport.append("g").attr("transform", `translate(${width / 2},${height / 2})`)
  const edges = world
    .append("g")
    .attr("aria-hidden", "true")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke", "var(--lightgray)")
    .attr("stroke-width", 1)
  const anchors = world
    .append("g")
    .selectAll<SVGAElement, SvgNode>("a")
    .data(nodes)
    .join((enter) => enter.append<SVGAElement>("a"))
    .attr("class", "graph-node")
    .attr("data-node-id", (node) => node.id)
    .attr("href", options.href)
    .attr("aria-label", (node) => node.text)
    .attr("tabindex", 0)
    .style("cursor", "pointer")
    .on("click", (event: MouseEvent, node) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
      event.preventDefault()
      options.navigate(node)
    })
  anchors.append("title").text((node) => node.text)
  anchors
    .append("circle")
    .attr("r", (node) => Math.max(focused ? 10 : 4, options.radius(node)))
    .attr("fill", (node) =>
      node.id === options.current
        ? "var(--secondary)"
        : options.visited.has(node.id)
          ? "var(--tertiary)"
          : "var(--gray)",
    )
    .attr("stroke", (node) => (node.id.startsWith("tags/") ? "var(--tertiary)" : "none"))
  const fontSize = Math.max(11, options.fontSize * 15)
  const labels = anchors
    .append("text")
    .attr("text-anchor", "middle")
    .attr("fill", "var(--dark)")
    .attr("font-family", "var(--bodyFont)")
    .attr("font-size", fontSize)
    .attr("pointer-events", "none")
    .attr("opacity", focused ? 1 : 0)
  labels.each(function (node) {
    const lines = labelLines(node.text, Math.max(12, Math.floor(Math.min(160, width / 2 - 24) / 7)))
    const first =
      -Math.max(focused ? 10 : 4, options.radius(node)) - 8 - (lines.length - 1) * fontSize
    select(this)
      .selectAll("tspan")
      .data(lines)
      .join("tspan")
      .attr("x", 0)
      .attr("y", (_, index) => first + index * fontSize)
      .text((line) => line)
  })
  anchors
    .on("mouseenter focus", function () {
      select(this).select("text").attr("opacity", 1)
    })
    .on("mouseleave blur", function () {
      if (!focused) select(this).select("text").attr("opacity", 0)
    })
  const update = () => {
    anchors.attr("transform", (node) => `translate(${node.x ?? 0},${node.y ?? 0})`)
    edges
      .attr("x1", (link) => link.source.x ?? 0)
      .attr("y1", (link) => link.source.y ?? 0)
      .attr("x2", (link) => link.target.x ?? 0)
      .attr("y2", (link) => link.target.y ?? 0)
  }
  const simulation = forceSimulation(nodes)
    .force("charge", forceManyBody().strength(-100 * options.repelForce))
    .force("center", forceCenter().strength(options.centerForce))
    .force("link", forceLink<SvgNode, SvgLink>(links).distance(options.linkDistance))
    .force(
      "collide",
      forceCollide<SvgNode>((node) => Math.max(10, options.radius(node))).iterations(3),
    )
    .on("tick", update)
  if (focused || large) {
    simulation.stop()
    if (large && !focused) simulation.tick(20)
  }
  if (options.drag) {
    anchors.call(
      drag<SVGAElement, SvgNode>()
        .container(() => world.node()!)
        .on("start", (event, node) => {
          if (event.sourceEvent?.type === "mousedown") dragView = event.sourceEvent.view
          if (!focused && !large && !event.active) simulation.alphaTarget(0.3).restart()
          node.fx = node.x
          node.fy = node.y
        })
        .on("drag", (event, node) => {
          node.fx = event.x
          node.fy = event.y
          if (focused || large) {
            node.x = event.x
            node.y = event.y
            update()
          }
        })
        .on("end", (event, node) => {
          dragView = undefined
          if (!focused && !event.active) simulation.alphaTarget(0)
          node.fx = null
          node.fy = null
        }),
    )
  }
  if (options.zoom) {
    let labelScale = 1
    const behavior = zoom<SVGSVGElement, unknown>()
      .extent([
        [0, 0],
        [width, height],
      ])
      .scaleExtent([large ? 0.05 : 0.25, 4])
      .on("start", (event) => {
        if (event.sourceEvent?.type === "mousedown") zoomView = event.sourceEvent.view
      })
      .on("end", () => {
        zoomView = undefined
      })
      .on("zoom", (event) => {
        viewport.attr("transform", event.transform.toString())
        if (large && labelScale !== event.transform.k) {
          labelScale = event.transform.k
          anchors
            .select("circle")
            .attr("r", (node) => Math.max(options.radius(node), 2 / labelScale))
          labels.attr("transform", `scale(${1 / labelScale})`)
        }
      })
    svg.call(behavior)
    const spanX =
      Math.max(...nodes.map((node) => node.x ?? 0)) -
      Math.min(...nodes.map((node) => node.x ?? 0)) +
      60
    const spanY =
      Math.max(...nodes.map((node) => node.y ?? 0)) -
      Math.min(...nodes.map((node) => node.y ?? 0)) +
      60
    const initial = large
      ? Math.min(options.scale || 1, width / spanX, height / spanY)
      : options.scale || 1
    svg.call(
      behavior.transform,
      zoomIdentity
        .translate((width * (1 - initial)) / 2, (height * (1 - initial)) / 2)
        .scale(initial),
    )
  }
  update()
  return () => {
    simulation.stop()
    if (dragView) {
      select(dragView).on("mousemove.drag mouseup.drag", null)
      dragEnable(dragView)
    }
    if (zoomView) {
      select(zoomView).on("mousemove.zoom mouseup.zoom", null)
      dragEnable(zoomView)
    }
    svg.interrupt()
    anchors.interrupt()
    svg.on(".zoom", null)
    anchors.on(".drag", null)
    svg.remove()
  }
}
