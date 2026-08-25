import { Extension, Plugin } from "django-prose-editor/editor"

const csrfToken = () => {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ""
}

const validEndpoint = (url) => Boolean(url && url !== "null" && url !== "undefined")

async function jsonResponse(response) {
  const contentType = response.headers.get("content-type") || ""
  if (!contentType.toLowerCase().includes("application/json")) {
    if (response.redirected || response.status === 401 || response.status === 403) {
      throw new Error("Your admin session may have expired. Refresh the page and sign in again.")
    }
    throw new Error("The image service returned an unexpected response. Refresh the page and try again.")
  }
  try {
    return await response.json()
  } catch (_error) {
    throw new Error("The image service returned an unexpected response. Refresh the page and try again.")
  }
}

const figureNode = (asset) => ({
  type: "figure",
  content: [
    { type: "image", attrs: { src: asset.url, alt: asset.alt_text } },
    ...(asset.caption ? [{ type: "caption", content: [{ type: "text", text: asset.caption }] }] : []),
  ],
})

async function uploadFile(file, options) {
  if (!options.allowedTypes.includes(file.type)) throw new Error("Only JPEG, PNG and WebP images are supported.")
  if (file.size > options.maxFileSize) throw new Error("The image exceeds the editorial upload size limit.")
  const altText = window.prompt("Describe this image for readers who cannot see it:", "")
  if (altText === null) return null
  if (!altText.trim()) throw new Error("Alternative text is required.")
  const form = new FormData()
  form.append("image", file)
  form.append("alt_text", altText.trim())
  if (!validEndpoint(options.uploadUrl)) throw new Error("Image uploading is not configured. Refresh the page and try again.")
  const response = await fetch(options.uploadUrl, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrfToken() }, body: form })
  const payload = await jsonResponse(response)
  if (!response.ok) throw new Error(payload.error || "The image could not be uploaded.")
  return payload
}

function openMediaManager(editor, options, asset = null, position = null) {
  if (!window.OEFMediaManager) { window.alert("The OEF media library is not available. Reload the page and try again."); return }
  window.OEFMediaManager.open({ mode: asset ? "details" : "library", asset, usage: "inline", uploadUrl: options.uploadUrl, libraryUrl: options.libraryUrl, onSelect: (selected) => { const chain = editor.chain().focus(); if (position === null) chain.insertContent(figureNode(selected)).run(); else chain.insertContentAt(position, figureNode(selected)).run() } })
}

async function insertFiles(editor, files, options, position = null) {
  for (const file of files) {
    const asset = await uploadFile(file, options)
    if (!asset) continue
    openMediaManager(editor, options, asset, position)
  }
}

export const InlineImageUpload = Extension.create({
  name: "InlineImageUpload",
  addOptions() { return { uploadUrl: null, libraryUrl: null, maxFileSize: 8 * 1024 * 1024, allowedTypes: ["image/jpeg", "image/png", "image/webp"] } },
  addMenuItems({ buttons, menu }) {
    const editor = this.editor
    menu.defineItem({ name: "addImage", groups: "nodes", priority: 115, command: () => openMediaManager(editor, this.options), button: buttons.material("add_photo_alternate", "Add image"), enabled: () => Boolean(this.options.libraryUrl) })
  },
  addProseMirrorPlugins() {
    const editor = this.editor
    const options = this.options
    const imageFiles = (files) => [...files].filter((file) => options.allowedTypes.includes(file.type))
    return [new Plugin({ props: {
      handlePaste(_view, event) { const files = imageFiles(event.clipboardData?.files || []); if (!files.length) return false; event.preventDefault(); insertFiles(editor, files, options).catch((error) => window.alert(error.message)); return true },
      handleDrop(view, event, _slice, moved) { if (moved) return false; const files = imageFiles(event.dataTransfer?.files || []); if (!files.length) return false; event.preventDefault(); insertFiles(editor, files, options, view.posAtCoords({ left: event.clientX, top: event.clientY })?.pos ?? null).catch((error) => window.alert(error.message)); return true },
    } })]
  },
})
