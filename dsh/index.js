// Refresh the vendored runtime with the claude-plugins-dsh sync command.
import { createPlugin, rootFrom } from './claude-compat.js'

const plugin = createPlugin({ root: rootFrom(import.meta.url) })
export const { name, apply } = plugin
export default plugin
