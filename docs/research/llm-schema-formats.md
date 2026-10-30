# Which text format for a database schema works best for LLMs

Answers [issue 21](https://github.com/ozanozbeker/ichnos/issues/21).

## Recommendation

Use DBML with inline `ref:` settings as the slice format.
Keep each pasted slice under 8,000 characters until a paste test in the target Copilot Chat shows a higher limit.
No published study tests DBML, so this choice rests on measured cost and on the structure of the format, not on measured accuracy.

The reasons, in order of weight:

- Content matters more than syntax.
  Foreign keys raise execution accuracy (EX) by 0.6 to 2.9 points for the OpenAI models in [DAIL-SQL](https://arxiv.org/abs/2308.15363), by 1.3 to 2.1 points in [Chang and Fosler-Lussier](https://arxiv.org/abs/2305.11853), and by 2.6 points in [C3](https://arxiv.org/abs/2307.07306).
  Across five layouts, DAIL-SQL's zero-shot EX spans 2.0 points for GPT-4 and 6.0 to 8.1 points for weaker models.
- DBML with inline refs is the cheapest of the four requested formats.
  It uses 23% fewer characters and 14% fewer tokens than indented DDL.
  Indented JSON uses 3.2 times the characters and 2.8 times the tokens of indented DDL.
- The Learn pages that I read document no maximum for typed or pasted text in Copilot Chat, and no context window.
  The only documented prompt size is 8,000 characters, for prompts that an admin publishes.
  In the sample schemas, 8,000 characters hold about 235 columns in DBML with inline refs (34 characters per column) and about 55 in indented JSON (141 characters per column).
- A slice holds the tables on the foreign key path between the tables in question, with their join columns.
  Rules that add the foreign key columns and junction tables of linked tables raised schema linking recall by 26 points in an [IBM study](https://openproceedings.org/2026/conf/edbt/paper-24.pdf).
  A path-based slice raised BIRD accuracy for Gemini 2.5 Flash from 51.50 to 62.91 in [SchemaGraphSQL](https://arxiv.org/abs/2505.18363).
- If a paste test shows that Copilot reads DBML worse than SQL, fall back to DDL with one line per table.
  It costs 2% more tokens and 21% more characters than DBML with inline refs.

## Method and confidence

All reads and runs happened on 2026-10-30.
Study figures come from the text of each paper's PDF.
The exception is CHESS, whose PDF exceeded the fetch size limit; its figures come from the arXiv abstract and HTML pages.
Microsoft, Uber, LinkedIn, LangChain and LlamaIndex figures come from page text on the owner's own site.
Token counts are my own measurements (see Token cost).
A figure marked (unverified) comes from a source that I could not trace to its owner.
Microsoft Q&A answers that carry an "AI answer" label are not sources here.

## Published evidence on schema format

Eight studies compare schema formats for text-to-SQL or schema linking.
The table lists them oldest first.
All are preprints; I did not confirm a peer-reviewed venue for any of them.

| Study | Models | Formats compared | Result |
| --- | --- | --- | --- |
| [Rajkumar et al. 2022](https://arxiv.org/abs/2204.00498) | Codex davinci | A comment-style list ("API Docs"), 1 to 10 sample rows with column headers, `CREATE TABLE` with types and foreign keys, and `CREATE TABLE` plus 1 to 10 sample rows | Spider dev execution accuracy (EX): list 56.8, rows alone 60.3 to 60.9, `CREATE TABLE` 59.9, `CREATE TABLE` plus 3 rows 67.0. More rows lowered EX: 63.3 at 10 rows. |
| [Nan et al. 2023](https://arxiv.org/abs/2305.12586) | Codex, ChatGPT | Schema as a text sequence, schema as `CREATE` statements, column descriptions added as comments | `CREATE` statements improved zero-shot accuracy, and column descriptions helped zero-shot. The paper reports the numbers in figures only. |
| [Chang and Fosler-Lussier 2023](https://arxiv.org/abs/2305.11853) | Codex, ChatGPT | `Table(Columns)`, `Columns=[]`, `Columns=[]` plus foreign keys, `CreateTable`, each with or without sample values | Zero-shot EX with normalized prompts, Codex / ChatGPT: `Columns=[]` 71.8 / 69.1, plus foreign keys 73.1 / 71.2, `CreateTable` 73.1 / 71.7. Foreign keys add 1.3 / 2.1 points. `CreateTable` adds 0.0 / 0.5 points over the compact list with foreign keys. |
| [DAIL-SQL (D. Gao et al. 2023)](https://arxiv.org/abs/2308.15363) | GPT-4, GPT-3.5-turbo, text-davinci-003, Vicuna-33B | Five layouts: `Table` and `Columns` lines with `Q:`/`A:` markers, plain table lists, `#`-commented lists, `CREATE TABLE` with keys, Alpaca-style Markdown sections | Zero-shot EX spread by model: 2.0 points for GPT-4, 6.0 for GPT-3.5-turbo, 8.1 for text-davinci-003. Adding foreign keys to the list layouts raised EX by 0.6 to 2.9 points for the OpenAI models (two exceptions: -0.2 and -0.4). A `#`-commented list plus foreign keys scored 78.4 with GPT-3.5-turbo; `CREATE TABLE` scored 74.4. |
| [SQLBench (Zhang et al. 2024)](https://arxiv.org/abs/2403.02951) | SQLCoder-34B, Codellama-34B, InternLM-70B, Llama2-Chat-70B | Full DDL in Markdown, HTML or code-comment wrappers; names only (`stadium(Stadium_ID, Location)`) in Markdown wrappers | Names only with Markdown headings beat DDL with the same wrapper on all four models: 65.0 vs 63.2, 71.6 vs 68.4, 67.4 vs 66.3, 54.7 vs 48.7 (Spider dev EX). |
| [XiYan-SQL (Y. Gao et al. 2025)](https://arxiv.org/abs/2411.08599) | GPT-4o, DeepSeek, Claude 3.5 Sonnet, Gemini 1.5 Pro | DDL, MAC-SQL schema, M-Schema | BIRD dev EX: M-Schema beat DDL on all four models, by 1.30 to 2.93 points (mean 2.03). M-Schema adds descriptions and example values that the DDL lacks, so the gain mixes content and syntax. |
| [Dönder et al. 2025](https://arxiv.org/abs/2505.14174) (under review) | GPT-4o | Six formats, including DDL, raw JSON and Python SQLAlchemy | Column F1 in schema linking on BIRD dev: DDL 82.5, MAC-SQL 82.4, M-Schema 80.9, JSON 80.6, DIN-SQL style 80.4, SQLAlchemy 78.1. Table F1 spans 92.0 to 93.0. |
| [McMillan 2026](https://arxiv.org/abs/2602.05447) | 11 models | YAML, Markdown, JSON, TOON; an agent reads the schema files with grep and read tools | Mean SQL accuracy: YAML 75.4%, Markdown 74.9%, JSON 72.3%, TOON 72.3%. The aggregate format effect is not significant (p = 0.484). Spread across formats: 1.6 to 5.4 points for frontier models, 9.8 to 20.1 points for open-source models. |

Three more studies test formats for table data, not schema.
Their results do not transfer directly, and none finds a format that wins everywhere:

- [Sui et al.](https://arxiv.org/abs/2305.13062) (WSDM 2024, Microsoft Research Asia) test seven tasks on GPT-3.5 and GPT-4.
  For GPT-3.5, column retrieval accuracy is 35.33% with Markdown, 54.33% with JSON and 63.33% with HTML.
- [He et al.](https://arxiv.org/abs/2411.10541) (Microsoft) compare plain text, Markdown, JSON and YAML prompt templates.
  GPT-3.5-turbo varies by up to 40% on a code translation task, and GPT-4 varies less.
  The paper finds no format that is best for every GPT model.
- [TQA-Bench](https://arxiv.org/abs/2411.19504) tests multi-table question answering over 8K to 64K tokens of rows.
  Markdown scores highest for most models and JSON lowest for almost all.
  At the 8K scale the same rows take 5,400 tokens in Markdown, 3,730 in CSV, 5,750 in JSON and 10,500 in HTML.

The studies support four statements:

- No study tests DBML, and none tests Markdown tables as the schema format.
- Foreign keys raised accuracy in the three studies that vary them (DAIL-SQL, Chang and Fosler-Lussier, C3), with two small exceptions in DAIL-SQL (-0.2 and -0.4 points).
  Sample values or descriptions add more.
  Three distinct values per column add 2.6 and 1.9 points in Chang and Fosler-Lussier (Table 1), and three sample rows add 7.1 points in Rajkumar et al.
- Syntax matters less for strong models.
  The gap between layouts is 2.0 points for GPT-4 in DAIL-SQL and 1.6 to 5.4 points for frontier models in McMillan.
- No layout is consistently ahead.
  Compact lists score within 0.5 points of `CREATE TABLE`, or higher, in Chang and Fosler-Lussier (with foreign keys), DAIL-SQL (with foreign keys) and SQLBench (names only).
  DDL leads by 0.1 to 4.4 column F1 points in Dönder et al., and the only JSON layout there scores 1.9 points below DDL.

Copilot Chat routes each prompt to a fast model or a reasoning model, so the model that receives a slice varies.
A format that holds up on weaker models is the safer choice.

## Token cost of each format

A script renders two schemas in ten layouts and counts the tokens.
The schemas are modeled on Oracle's HR sample schema (7 tables, 35 columns) and on TPC-H (8 tables, 61 columns).
Together they have 96 columns and 18 foreign keys.
Every layout carries the same facts: table names, column names, types, primary keys and foreign keys.

The run used Python 3.13.12 on macOS arm64, tiktoken 0.14.0 and PyYAML 6.0.3.
In tiktoken, `gpt-4o`, `gpt-4.1` and `gpt-5` map to `o200k_base`, and `gpt-4` maps to `cl100k_base`.
The Microsoft pages that I read do not name the tokenizer of Copilot Chat.
The counts below use `o200k_base`; `cl100k_base` counts differ by 5% or less for every layout.
The experiment script is not committed.

The layouts:

- DDL, indented: one `CREATE TABLE` per table, one column per line, then `PRIMARY KEY` and `FOREIGN KEY ... REFERENCES` lines.
- DDL, one line per table: the same text with single spaces and no line breaks inside a statement.
- DBML, separate `Ref:` lines: `Table` blocks with `[pk]`, then one `Ref:` line per foreign key.
- DBML, inline refs: single-column foreign keys as `[ref: > table.column]`, composite foreign keys as `Ref:` lines.
- Markdown tables: one table per database table, with the columns Column, Type, Key and References.
- Markdown tables, padded: the same tables with every cell padded to the width of the widest cell.
- JSON: one object per table with `columns`, `primary_key` and `foreign_keys`, written with `indent=2` or minified.
- YAML: the same object, written with `yaml.safe_dump`.
- Compact lines: `table(column TYPE PK, ...)` per table, then one `a.b -> c.d` line per foreign key.

DBML with inline refs, for two of the tables:

```dbml
Table regions {
  region_id NUMBER [pk]
  region_name VARCHAR2(25)
}

Table countries {
  country_id CHAR(2) [pk]
  country_name VARCHAR2(40)
  region_id NUMBER [ref: > regions.region_id]
}
```

Measured on both schemas together:

| Layout | Characters | Tokens | Tokens per column | Tokens vs indented DDL | Columns per 8,000 characters | Tokens with notes |
| --- | --- | --- | --- | --- | --- | --- |
| Compact lines | 3,118 | 856 | 8.9 | 0.72 | 245 | 1,107 |
| DBML, inline refs | 3,272 | 1,026 | 10.7 | 0.86 | 235 | 1,385 |
| DDL, one line per table | 3,970 | 1,046 | 10.9 | 0.88 | 195 | 1,312 |
| DBML, separate `Ref:` lines | 3,595 | 1,085 | 11.3 | 0.91 | 215 | 1,453 |
| DDL, indented | 4,272 | 1,190 | 12.4 | 1.00 | 180 | 1,447 |
| Markdown tables | 4,627 | 1,647 | 17.2 | 1.38 | 165 | 2,103 |
| JSON, minified | 6,596 | 1,856 | 19.3 | 1.56 | 115 | 2,166 |
| Markdown tables, padded | 8,085 | 1,889 | 19.7 | 1.59 | 95 | 2,370 |
| YAML | 6,715 | 2,211 | 23.0 | 1.86 | 115 | 2,536 |
| JSON, indent 2 | 13,577 | 3,385 | 35.3 | 2.84 | 55 | 3,778 |

"Tokens with notes" adds a summary line to each of the 15 tables and a note on each of the 19 foreign key columns.
Each note is a short sentence, for example `Seen in 4 queries`.
The ratios to indented DDL differ by less than 0.25 between the two schemas, for every layout.

What the counts show:

- The layout changes the cost by up to four times.
  Indented JSON costs 2.84 times indented DDL in tokens and 3.18 times in characters.
- Characters and tokens rank the layouts differently.
  DBML with inline refs is 18% smaller than one-line DDL in characters and 2% smaller in tokens.
  Padding Markdown tables adds 15% to the tokens and 75% to the characters.
- Indentation costs 12% of the DDL tokens (1,190 against 1,046).
  Chang and Fosler-Lussier measured 25% on Codex (474 against 356 tokens) after they removed line breaks and extra spaces and lowercased the text.
  Tokenizers count whitespace differently, so the saving depends on the model.
- Notes cost 250 to 480 tokens for 34 notes.
  A Markdown table pays for the extra column in every row, even when the cell is empty: +456 tokens.
  DBML pays more for `note:` settings than DDL pays for comments: +359 against +257.
  With notes, the DBML lead over DDL disappears: 1,385 tokens for DBML with inline refs against 1,312 for one-line DDL.

Two published studies report token counts for schema text.
[Chang and Fosler-Lussier](https://arxiv.org/abs/2305.11853) (Table 1) give the average prompt size and accuracy of four layouts on Spider dev, with whitespace and case normalized:

| Layout | Codex tokens | ChatGPT tokens | Codex EX | ChatGPT EX |
| --- | --- | --- | --- | --- |
| `Table(Columns)` | 147 | 115 | 71.9 | 70.5 |
| `Columns=[]` | 167 | 135 | 71.8 | 69.1 |
| `Columns=[]` plus foreign keys | 223 | 174 | 73.1 | 71.2 |
| `CreateTable` | 356 | 254 | 73.1 | 71.7 |

The compact list with foreign keys matches `CreateTable` for Codex, and it is 0.5 points lower for ChatGPT.
It takes 63% to 69% of the tokens.

[Trummer](https://www.vldb.org/pvldb/vol17/p3511-trummer.pdf) (PVLDB 2024) rewrites a five-column `CREATE TABLE` from 93 tokens to 54 and then 39 by grouping columns that share a type and by abbreviating a common name prefix.
He reports that the rewritten schemas halve the reading fees on average and do not lower text-to-SQL accuracy on Spider.

## Copilot Chat limits

The target is a work Copilot Chat (Microsoft Entra sign-in).
I read "locked-down Copilot chat where data is allowed" as that product.

| Item | Finding | Source | Status |
| --- | --- | --- | --- |
| Admin-published prompt text | Up to 8,000 characters | [Organizational prompts](https://learn.microsoft.com/en-us/microsoft-365/copilot/organizational-prompts), updated 2026-09-21 | Verified. A user selects the prompt and its text enters the message box, so the box accepts at least 8,000 characters on the surfaces that show these prompts (inference). |
| Typed or pasted prompt, maximum | Not documented | [Copilot Chat FAQ](https://learn.microsoft.com/en-us/copilot/faq), 2026-10-19; [overview](https://learn.microsoft.com/en-us/copilot/overview), 2026-09-09; [2025 release notes](https://learn.microsoft.com/en-us/microsoft-365/copilot/previous-year-release-notes) | Not found. The release notes of 2025-04-16 list "Support for longer prompts" for Windows and web, with no number. Forum posts report 2,000, 4,000, 8,000 and 16,000 characters, varying by app and date (unverified). |
| Context window | Not documented | The same two pages | Not found. |
| Model | GPT-5 by default; Copilot routes each prompt to a fast model or a reasoning model | [2025 release notes](https://learn.microsoft.com/en-us/microsoft-365/copilot/previous-year-release-notes), entry of 2025-12-23 | Verified for that date. The pages that I read do not name the tokenizer. |
| Pasting | Listed as a way to give Copilot Chat content from the organization | [Overview](https://learn.microsoft.com/en-us/copilot/overview) | Verified. |
| File upload | 20 files per conversation, 50 MB per file. The page lists TXT, MD, JSON, CSV, PDF, DOCX, XLSX and PPTX; `.sql` and `.dbml` are not on it. | [File upload in Microsoft Copilot](https://support.microsoft.com/en-us/microsoft-365-copilot/file-upload-in-microsoft-copilot), undated | Verified on that page. It links to a longer format list that I did not open. |
| Upload control | On by default. An admin can turn it off for Copilot Chat by contacting Microsoft Support. | [Controls to manage file uploads](https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-file-upload-control), 2026-03-31 | Verified. A locked-down tenant may have it off, so pasting is the safe path. |
| Standard access | Capacity-based; the page gives no numbers | [Standard versus priority access](https://support.microsoft.com/topic/standard-versus-priority-access-in-microsoft-365-copilot-chat-12c8d9f8-db32-4f99-8ebe-d8d85879137f) | Verified: no numeric limit. |

8,000 characters are about 2,500 tokens of DBML with inline refs (3.2 characters per token).
For pasted text, the character limit is the one to design for, because it is the only one documented.

## How published systems slice a large schema

Benchmark databases are small: 27.1 columns per database in Spider 1.0 and 54.2 in BIRD.
Spider 2.0-snow has 812.1 ([Spider 2.0](https://arxiv.org/abs/2411.07763), ICLR 2025).
One of Microsoft's internal warehouses has 632 tables and more than 4,000 columns ([Floratou et al.](https://www.cidrdb.org/cidr2024/papers/p74-floratou.pdf), CIDR 2024).

Systems with a reported effect:

| System | Slicing method | Reported effect |
| --- | --- | --- |
| [RESDSQL](https://arxiv.org/abs/2302.05965) (AAAI 2023) | A cross-encoder scores every table and column. The input keeps the top 4 tables and the top 5 columns of each. | The authors set the two cut-offs from dataset statistics. A cut-off that is too small drops required items. |
| [DIN-SQL](https://arxiv.org/abs/2304.11015) (NeurIPS 2023) | A few-shot prompt lists, for each mention in the question, the matching columns and tables. | Removing the module lowers Spider dev EX with CodeX Davinci to 65.9, from 68.7 to 69.9. |
| [C3](https://arxiv.org/abs/2307.07306) | ChatGPT ranks tables (10 samples of the top 4, majority vote), then columns (the 5 most frequent per table), then the foreign keys of the kept tables are added. | Without table and column recall: 79.5 against 81.8 on Spider dev. About 1,000 tokens per query, against more than 10,000 for DIN-SQL. |
| [MAC-SQL](https://arxiv.org/abs/2312.11242) (COLING 2025) | A Selector agent runs only when the schema prompt exceeds a threshold: 25,000 tokens for GPT-4-32k, which is 0.8 of the model limit. It keeps at least 6 columns per table. | Without the Selector, BIRD dev EX is 57.28 against 59.39. The loss is on challenging questions: 35.14 against 40.28. |
| [CHESS](https://arxiv.org/abs/2405.16755) | Agents filter columns, select tables, then select columns. Primary and foreign keys always stay. | The abstract reports about 2% higher accuracy and about 5 times fewer tokens. A worked example shrinks 96 columns in 13 tables to 5 columns in 2 tables. |
| [XiYan-SQL](https://arxiv.org/abs/2411.08599) | Keyword similarity retrieves columns and hashing retrieves values; an LLM then keeps the columns it needs. | GPT-4o on BIRD dev: precision 10.14 to 74.74, recall 100 to 95.47, EX 57.95 to 60.10. |
| [Floratou et al.](https://www.cidrdb.org/cidr2024/papers/p74-floratou.pdf) (Microsoft) | KaggleDBQA (17 tables, 246 columns) with GPT-3.5. Hand-picked tables and columns, hand-picked tables with all columns, embedding retrieval over names, and an LLM call. | Full schema: 22.7 EX. Hand-picked tables and columns: +7. Hand-picked tables with all columns: +2. Both automatic selectors scored below the full schema. |
| [Maamari et al.](https://arxiv.org/abs/2408.07702) (Distyl AI) | Four LLM-based linkers against the full schema. | Linking helps weaker models and lowers accuracy for stronger ones when the schema fits the context window. Fine-tuned GPT-4o in the full pipeline: BIRD dev EX 67.35 with the full schema, 62.58 with table-then-column linking. |
| [SchemaGraphSQL](https://arxiv.org/abs/2505.18363) (preprint) | A graph of tables joined by foreign keys. One LLM call names the source and destination tables, and the union of the shortest join paths between them is the slice. | BIRD dev, Gemini 2.5 Flash: full schema 51.50, embedding retrieval 58.41, path union 62.91, perfect linking 64.41. The high-recall variant beat the high-precision variant by 2 to 7 points. |
| [IBM, EDBT 2026](https://openproceedings.org/2026/conf/edbt/paper-24.pdf) | LLM schema linking, then rules that add the junction tables on a foreign key path and the foreign key columns of linked tables. | Recall rose from 43.07 to 69.40 on average, and the foreign key columns step added the most. Perfect linking was not always the best input: adding representative columns raised EX for two of three models. |
| [DBCopilot](https://arxiv.org/abs/2312.03463) (EDBT 2025) | A graph of tables with primary-foreign, foreign-foreign and joinable edges. A router generates a connected set of tables with graph-constrained decoding. | Up to 19.88% more recall than retrieval baselines, and 4.43% to 11.22% more EX (figures as stated in the introduction). |
| [Deng et al.](https://arxiv.org/abs/2502.00675) (Spider 2.0 agent) | Tables with similar name prefixes or suffixes merge into one full table plus a list of names. Above 50,000 tokens, an LLM keeps or drops each table. | One database's DDL shrinks from more than 50 MB to under 2 MB. Removing the compression costs 3.65 EX on Spider 2.0-snow. |

Production systems and product documentation, none with a measured effect:

| System | Slicing method |
| --- | --- |
| [Uber QueryGPT](https://www.uber.com/en-us/blog/query-gpt/) (2024-09-19) | An intent agent picks a business domain, a table agent picks tables, and a column prune agent removes columns. Large tables used 40 to 60 thousand tokens each, and three of them broke a 32K-token model. |
| [LinkedIn SQL Bot](https://www.linkedin.com/blog/engineering/ai/practical-text-to-sql-for-data-analytics) (2024-12-09) | Embedding retrieval returns the top 20 tables, an LLM re-ranker keeps 7, and a second re-ranker selects fields. |
| Pinterest text-to-SQL (unverified) | An LLM writes a summary of each table, and a vector index of the summaries finds candidate tables. The primary post returned HTTP 403, so this comes from secondary write-ups. |
| [LangChain SQL agent](https://docs.langchain.com/oss/python/langchain/sql-agent) | Two tools: list the tables, then fetch the schema and sample rows of chosen tables. The prompt tells the agent to list the tables first. |
| [LlamaIndex](https://github.com/run-llama/llama_index/blob/main/docs/examples/index_structs/struct_indices/SQLIndexDemo.ipynb) | Each table schema, with an optional description, is an object in a vector index. A retriever returns the top k tables for a question. |
| [Power BI AI data schema](https://learn.microsoft.com/en-us/power-bi/create-reports/copilot-prepare-data-ai-data-schema) | The model author selects the fields that Copilot uses. Relationships still apply to fields outside the selection. |
| [Fabric data agent](https://learn.microsoft.com/en-us/fabric/data-science/data-agent-configuration-best-practices) | The author selects tables and columns, and writes join paths as one direct sentence per join. The page advises descriptive names. |

Two studies ask questions about the schema itself:

- [DW-Bench](https://arxiv.org/abs/2604.18964) (under review) has 1,046 questions on five warehouse schemas with 262 tables.
  Micro exact match across three models is 63.2% to 76.6% for the whole schema as flat text, 75.4% to 80.9% for a 3-hop neighborhood around the tables in the question, and 87.5% to 90.4% when the model calls path tools.
  Renaming tables to random names lowers the scores of the static methods (flat text, vector retrieval, graph neighborhood) by 9 to 32 points.
- [SchemaScope](https://aclanthology.org/2026.surgellm-1.17/) (ACL workshop paper, 2026) groups 410 questions by the number of foreign key edges a query crosses.
  Accuracy of five LLMs is above 80% at one hop, below 40% at four hops and below 25% at six.

The slicing evidence supports five statements:

- Slicing pays for weak models and for schemas beyond the context window.
  It can lower accuracy for strong models that hold the schema (Maamari et al.), and simple automatic selectors can fall below the full schema (Floratou et al.).
- Recall matters more than precision.
  A missed table or join column makes the SQL wrong, and the high-recall variant of SchemaGraphSQL beat the high-precision variant by 2 to 7 points.
  Extra items still cost accuracy: in Floratou et al., hand-picked columns beat whole hand-picked tables by 5 points.
- Foreign key paths and join columns belong in the slice (SchemaGraphSQL, IBM, DBCopilot, C3, CHESS).
  Accuracy falls as the number of joins grows (SchemaScope), and path tools beat flat schema text (DW-Bench), so a slice should state the path.
- Descriptions and descriptive names help.
  Models rely on table names (DW-Bench), and LLM-written descriptions retrieve the right database better than DDL text ([Kreitlow and Oliveira](https://aclanthology.org/2026.propor-1.15/), PROPOR 2026: Hit@1 0.55 to 0.62 against 0.36 to 0.39 on a Portuguese Spider dev set, at database level).
- Repeated table families compress well (Deng et al.).
  Partitioned Oracle tables with a shared prefix are a candidate.

## Gaps

- No study tests DBML or Markdown tables as a schema format.
  A paste test in the target tenant settles it: paste the same slice as DBML and as DDL, ask 20 questions about joins and columns, and compare the answers.
- The prompt maximum of Copilot Chat is unknown.
  Paste 4,000, 8,000, 12,000 and 16,000 characters, each ending in a numbered marker, and ask for the last marker that Copilot received.
- I found no source on whether a long paste is truncated, rejected or turned into an attachment.
- Most format studies use Spider or BIRD, whose databases have 27 and 54 columns on average, and they ask for SQL.
  Oracle schemas inferred from queries have more columns, and the readers of a slice may ask schema questions instead.
- The token counts use two small schemas that I modeled from memory, so the types may differ from the specifications.
  The ratios between layouts are stable across them; the absolute counts are not a forecast for a real schema.
- The Pinterest design is unverified.
  The CHESS token saving comes from its abstract and was not re-derived.

## Not covered

- MMQA (ICLR 2025) and "Same Data, Different Schemas" (arXiv 2605.25838) appeared in searches, and I did not read them.
- Other Copilot products (Copilot Studio, Copilot for Power BI) are out of scope.
- The tokenizer and the context window of the model behind Copilot Chat: no page that I read states them.
