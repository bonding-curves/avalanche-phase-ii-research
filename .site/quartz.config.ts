import { QuartzConfig } from "./quartz/cfg"
import * as Plugin from "./quartz/plugins"

/**
 * Quartz 4 Configuration
 *
 * See https://quartz.jzhao.xyz/configuration for more information.
 */
const config: QuartzConfig = {
  configuration: {
    pageTitle: "Avalanche Phase II",
    pageTitleSuffix: "",
    enableSPA: true,
    enablePopovers: false,
    analytics: null,
    locale: "en-US",
    baseUrl: process.env.QUARTZ_BASE_URL ?? "localhost:8844",
    ignorePatterns: ["private", "templates", ".obsidian"],
    defaultDateType: "modified",
    theme: {
      fontOrigin: "local",
      cdnCaching: false,
      typography: {
        header: "Arial",
        body: "Arial",
        code: "monospace",
      },
      colors: {
        lightMode: {
          light: "#fafafa",
          lightgray: "#dedede",
          gray: "#767676",
          darkgray: "#404044",
          dark: "#151517",
          secondary: "#c62430",
          tertiary: "#a91f29",
          highlight: "rgba(232, 65, 66, 0.08)",
          textHighlight: "#e8414230",
        },
        darkMode: {
          light: "#0c0c0e",
          lightgray: "#29292d",
          gray: "#929299",
          darkgray: "#bdbdc4",
          dark: "#f4f4f5",
          secondary: "#ff6269",
          tertiary: "#f4f4f5",
          highlight: "rgba(232, 65, 66, 0.10)",
          textHighlight: "#e8414240",
        },
      },
    },
  },
  plugins: {
    transformers: [
      Plugin.FrontMatter(),
      Plugin.CreatedModifiedDate({
        priority: ["frontmatter", "git", "filesystem"],
      }),
      Plugin.SyntaxHighlighting({
        theme: {
          light: "github-light",
          dark: "github-dark",
        },
        keepBackground: false,
      }),
      Plugin.ObsidianFlavoredMarkdown({ enableInHtmlEmbed: false }),
      Plugin.GitHubFlavoredMarkdown(),
      Plugin.TableOfContents(),
      Plugin.CrawlLinks({ markdownLinkResolution: "absolute" }),
      Plugin.Description(),
      Plugin.Latex({ renderEngine: "mathjax" }),
    ],
    filters: [Plugin.RemoveDrafts()],
    emitters: [
      Plugin.AliasRedirects(),
      Plugin.ComponentResources(),
      Plugin.ContentPage(),
      Plugin.TagPage(),
      Plugin.ContentIndex({
        enableSiteMap: false,
        enableRSS: false,
      }),
      Plugin.Assets(),
      Plugin.Static(),
      Plugin.Favicon(),
      Plugin.NotFoundPage(),
      // Comment out CustomOgImages to speed up build time
    ],
  },
}

export default config
