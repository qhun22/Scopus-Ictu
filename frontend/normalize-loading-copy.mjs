import { readdir, readFile, writeFile } from "node:fs/promises";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const sourceRoot = join(frontendRoot, "src");
const sourceExtensions = new Set([".ts", ".tsx"]);
const loadingTextPattern = /Đang tải[^"'`\r\n<]*/g;
const replacement = "Đang tải dữ liệu...";

async function collectSourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await collectSourceFiles(path)));
    } else if (sourceExtensions.has(extname(entry.name))) {
      files.push(path);
    }
  }

  return files;
}

const files = await collectSourceFiles(sourceRoot);
let changedFiles = 0;
let replacements = 0;

for (const file of files) {
  const source = await readFile(file, "utf8");
  const normalized = source.replace(loadingTextPattern, (match) => {
    if (match === replacement) {
      return match;
    }

    replacements += 1;
    return replacement;
  });

  if (normalized !== source) {
    await writeFile(file, normalized, "utf8");
    changedFiles += 1;
  }
}

console.log(`Normalized ${replacements} loading label(s) in ${changedFiles} file(s).`);
