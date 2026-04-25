# Binge Consulting — Brand Fonts

Place your font files in this directory. The CSS expects the following files:

## Galderglynn Titling (Headings)

| Weight | Expected filename |
| ------ | ---------------------------------------- |
| Light  | `galderglynn-titling-light.woff2` / `.woff` |
| Regular| `galderglynn-titling-regular.woff2` / `.woff` |
| Bold   | `galderglynn-titling-bold.woff2` / `.woff` |

## MADE Outer Sans (Subtitles / UI)

| Weight | Expected filename |
| ------ | ---------------------------------------- |
| Light  | `made-outer-sans-light.woff2` / `.woff` |
| Regular| `made-outer-sans-regular.woff2` / `.woff` |
| Bold   | `made-outer-sans-bold.woff2` / `.woff` |

## Arimo (Body Text)

Arimo is loaded automatically from Google Fonts via `next/font` — no files needed here.

---

### How to convert .otf / .ttf to .woff2

Use [Font Squirrel Webfont Generator](https://www.fontsquirrel.com/tools/webfont-generator)
or install `woff2_compress` locally:

```bash
# macOS with Homebrew
brew install woff2
woff2_compress YourFont.ttf
```
