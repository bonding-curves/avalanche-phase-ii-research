import { JSX } from "preact"

const OverflowList = ({
  children,
  ...props
}: JSX.HTMLAttributes<HTMLUListElement>) => {
  return (
    <ul {...props} class={[props.class, "overflow"].filter(Boolean).join(" ")} id={props.id}>
      {children}
      <li class="overflow-end" />
    </ul>
  )
}

let numLists = 0
export default () => {
  const id = `list-${numLists++}`

  return {
    OverflowList: (props: JSX.HTMLAttributes<HTMLUListElement>) => (
      <OverflowList {...props} data-overflow-id={id} id={props.id ?? id} />
    ),
    overflowListAfterDOMLoaded: `
document.addEventListener("nav", (e) => {
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const parentUl = entry.target.parentElement
      if (!parentUl) return
      if (entry.isIntersecting) {
        parentUl.classList.remove("gradient-active")
      } else {
        parentUl.classList.add("gradient-active")
      }
    }
  })

  const ul = document.querySelector('[data-overflow-id="${id}"]')
  if (!ul) return

  const end = ul.querySelector(".overflow-end")
  if (!end) return

  observer.observe(end)
  window.addCleanup(() => observer.disconnect())
})
`,
  }
}
