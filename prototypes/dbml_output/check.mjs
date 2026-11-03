// Parse DBML files as one project with @dbml/core 11.0.1 and print every diagnostic.
// Usage: node check.mjs entry.dbml [imported.dbml ...]
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { Parser } from "@dbml/core";
import { DBMLDiagnosticsProvider, Filepath } from "@dbml/parse";

const paths = process.argv.slice(2).map((p) => resolve(p));
const p = new Parser();
for (const path of paths) p.setDbmlSource(path, readFileSync(path, "utf8"));
let summary;
try {
  const db = p.parseDbmlProject(paths[0]);
  const tables = db.schemas.flatMap((s) => s.tables).length;
  const refs = db.schemas.flatMap((s) => s.refs).length;
  summary = `parsed: ${tables} tables, ${refs} refs, ${db.schemas.flatMap((s) => s.deps ?? []).length} deps`;
} catch (e) {
  summary = "PARSE FAILED";
}
const diags = new DBMLDiagnosticsProvider(p.DBMLCompiler).provideDiagnostics();
console.log(`${paths[0].split("/").pop()}: ${summary}; ${diags.length} diagnostics`);
for (const d of diags) {
  console.log(`  ${d.type} ${d.filepath?.basename ?? ""}:${d.startRow + 1}:${d.startColumn + 1} ${d.text.split("\n")[0]}`);
}
