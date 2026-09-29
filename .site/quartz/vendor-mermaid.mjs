// Copy the pinned Mermaid renderer from node_modules into quartz/static/mermaid, where the diagram script loads it.
// Runs after `npm ci` and before every build, so the site draws diagrams without contacting a CDN.
import { cpSync, existsSync, mkdirSync } from "node:fs"
const source = "node_modules/mermaid/dist"
const target = "quartz/static/mermaid"
if (!existsSync(`${source}/mermaid.esm.min.mjs`)) {
  console.error("mermaid is not installed; run npm ci")
  process.exit(1)
}
mkdirSync(target, { recursive: true })
cpSync(`${source}/mermaid.esm.min.mjs`, `${target}/mermaid.esm.min.mjs`)
cpSync(`${source}/chunks/mermaid.esm.min`, `${target}/chunks/mermaid.esm.min`, { recursive: true })
