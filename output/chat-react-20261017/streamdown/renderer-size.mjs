// Size of each renderer candidate alone (React included in both): node scripts/renderer-size.mjs
import { readdirSync, readFileSync, statSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { gzipSync } from "node:zlib"
import { fileURLToPath } from "node:url"

import react from "@vitejs/plugin-react"
import { build } from "vite"

const root = fileURLToPath(new URL("..", import.meta.url))
const result = {}
for (const name of ["legacy", "streamdown"]) {
  const outDir = join(tmpdir(), "regulai-chat-redesign", "sizecheck", name)
  await build({
    configFile: false, root, logLevel: "silent", plugins: [react()],
    resolve: { alias: { "@": join(root, "src") } },
    build: { outDir, emptyOutDir: true, sourcemap: false, rollupOptions: { input: join(root, `src/markdown/size-${name}.tsx`) } },
  })
  const files = readdirSync(join(outDir, "assets")).filter((file) => file.endsWith(".js"))
  const bytes = files.reduce((sum, file) => sum + statSync(join(outDir, "assets", file)).size, 0)
  const gzip = files.reduce((sum, file) => sum + gzipSync(readFileSync(join(outDir, "assets", file))).length, 0)
  result[name] = { files: files.length, bytes, gzip }
}
console.log(JSON.stringify(result))
