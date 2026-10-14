// @ts-ignore
import imageZoomScript from "./scripts/imagezoom.inline"
import styles from "./styles/imagezoom.scss"
import { QuartzComponent, QuartzComponentConstructor } from "./types"

// Renders nothing. Its script makes every image in a page open full screen on click, with zoom and pan.
const ImageZoom: QuartzComponent = () => null

ImageZoom.afterDOMLoaded = imageZoomScript
ImageZoom.css = styles

export default (() => ImageZoom) satisfies QuartzComponentConstructor
