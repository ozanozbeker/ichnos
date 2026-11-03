// Parse each DBML text that arrives on stdin with the pinned @dbml/core, and answer with one JSON line.
// Each request is one JSON line holding a string. One process serves a whole pytest session (ADR 0015).
import { createInterface } from "node:readline";
import { Parser } from "@dbml/core";
import { DBMLDiagnosticsProvider } from "@dbml/parse";

function properties(metadata) {
  return Object.fromEntries(Object.entries(metadata ?? {}).map(([key, { value }]) => [key, value]));
}

function check(text) {
  const parser = new Parser();
  parser.setDbmlSource("/main.dbml", text);
  let database = null;
  let error = null;
  try {
    database = parser.parseDbmlProject("/main.dbml");
  } catch (e) {
    error = e.diags?.map((d) => d.message).join("; ") ?? String(e);
  }
  const diagnostics = new DBMLDiagnosticsProvider(parser.DBMLCompiler)
    .provideDiagnostics()
    .map((d) => `${d.type} ${d.startRow + 1}:${d.startColumn + 1} ${d.text}`);
  const tables = (database?.schemas ?? []).flatMap((schema) =>
    schema.tables.map((table) => ({
      schema: schema.name,
      name: table.name,
      properties: properties(table.metadata),
      columns: table.fields.map((field) => ({
        name: field.name,
        type: field.type.type_name,
        null: field.not_null === false,
        properties: properties(field.metadata),
      })),
    })),
  );
  return { error, diagnostics, tables };
}

const lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of lines) {
  process.stdout.write(`${JSON.stringify(check(JSON.parse(line)))}\n`);
}
