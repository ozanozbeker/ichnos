# Changelog

## [0.0.3](https://github.com/ozanozbeker/ichnos/compare/v0.0.2...v0.0.3) (2026-11-04)


### Documentation

* add CLI reference pages and glossary-based API sections ([#90](https://github.com/ozanozbeker/ichnos/issues/90)) ([b2528e7](https://github.com/ozanozbeker/ichnos/commit/b2528e71cd7337e3b050d945185da251522c444d))

## [0.0.2](https://github.com/ozanozbeker/ichnos/compare/v0.0.1...v0.0.2) (2026-11-03)


### Features

* infer direct column lineage ([#82](https://github.com/ozanozbeker/ichnos/issues/82)) ([fdcdd6e](https://github.com/ozanozbeker/ichnos/commit/fdcdd6eaaf535d244d8bb7842f610d6c4b889147)), closes [#66](https://github.com/ozanozbeker/ichnos/issues/66)
* infer indirect lineage and COUNT(*) ([#83](https://github.com/ozanozbeker/ichnos/issues/83)) ([8c1eaf6](https://github.com/ozanozbeker/ichnos/commit/8c1eaf6e1d63f2b6a05ec1aeb7d5949100e060d5)), closes [#67](https://github.com/ozanozbeker/ichnos/issues/67)
* infer keys ([#79](https://github.com/ozanozbeker/ichnos/issues/79)) ([9b11dc8](https://github.com/ozanozbeker/ichnos/commit/9b11dc826f4f99f9d2b0acb08a2b31e7655230af)), closes [#63](https://github.com/ozanozbeker/ichnos/issues/63)
* infer relationships and their direction ([#80](https://github.com/ozanozbeker/ichnos/issues/80)) ([5abf127](https://github.com/ozanozbeker/ichnos/commit/5abf127b2ef253179a6bb9f70fa69c3f1f64d1f8)), closes [#64](https://github.com/ozanozbeker/ichnos/issues/64)
* infer types, nullable and observed values ([#78](https://github.com/ozanozbeker/ichnos/issues/78)) ([685044f](https://github.com/ozanozbeker/ichnos/commit/685044f9a45c8e6b0511a5e744a1338bfb916fc6)), closes [#62](https://github.com/ozanozbeker/ichnos/issues/62)
* list unparsed queries ([#75](https://github.com/ozanozbeker/ichnos/issues/75)) ([2826504](https://github.com/ozanozbeker/ichnos/commit/2826504d83cf013c24072b84eb2efd9ea4e0b77a)), closes [#59](https://github.com/ozanozbeker/ichnos/issues/59)
* name reports and output columns ([#81](https://github.com/ozanozbeker/ichnos/issues/81)) ([11f1a87](https://github.com/ozanozbeker/ichnos/commit/11f1a87825895b4ff38fae41756bfe271d3f0ff9)), closes [#65](https://github.com/ozanozbeker/ichnos/issues/65)
* read creating queries as declarations ([#77](https://github.com/ozanozbeker/ichnos/issues/77)) ([df46bef](https://github.com/ozanozbeker/ichnos/commit/df46bef2d826f3e28945ae8392293daad2f74e90)), closes [#61](https://github.com/ozanozbeker/ichnos/issues/61)
* record column and owner ambiguities ([#76](https://github.com/ozanozbeker/ichnos/issues/76)) ([88c5d9e](https://github.com/ozanozbeker/ichnos/commit/88c5d9e7602a26b9ab99fd98fd281b35deebbb5d)), closes [#60](https://github.com/ozanozbeker/ichnos/issues/60)
* write neighborhood and join path slices ([#85](https://github.com/ozanozbeker/ichnos/issues/85)) ([2bf6b7c](https://github.com/ozanozbeker/ichnos/commit/2bf6b7cd3504b957d038fd96dfb9fe69f0bba5cb)), closes [#69](https://github.com/ozanozbeker/ichnos/issues/69)
* write tables and columns to DBML from a corpus ([#73](https://github.com/ozanozbeker/ichnos/issues/73)) ([c5dfde5](https://github.com/ozanozbeker/ichnos/commit/c5dfde5f5e94dc9c7b718c1b3daab2ac3f908eaf)), closes [#57](https://github.com/ozanozbeker/ichnos/issues/57)
* write the summary with owner and keyword filters ([#84](https://github.com/ozanozbeker/ichnos/issues/84)) ([fe791e0](https://github.com/ozanozbeker/ichnos/commit/fe791e01c7a33e8a3e076ed26938ce4ff3a46980)), closes [#68](https://github.com/ozanozbeker/ichnos/issues/68)
* write upstream and downstream lineage slices ([#86](https://github.com/ozanozbeker/ichnos/issues/86)) ([6fb4f3d](https://github.com/ozanozbeker/ichnos/commit/6fb4f3d5be42fa74b9fb4380c479dab4f8f684fe)), closes [#70](https://github.com/ozanozbeker/ichnos/issues/70)


### Bug Fixes

* apply the review of the v1 stack ([#88](https://github.com/ozanozbeker/ichnos/issues/88)) ([2db8942](https://github.com/ozanozbeker/ichnos/commit/2db894212f688b9f0bf935dd07242c57522dc685))


### Documentation

* add the domain glossary ([#24](https://github.com/ozanozbeker/ichnos/issues/24)) ([7562bf2](https://github.com/ozanozbeker/ichnos/commit/7562bf212f08ceac8cd9036ab98fbb0482e9e6fd)), closes [#8](https://github.com/ozanozbeker/ichnos/issues/8)
* add the lineage terms to the glossary ([#37](https://github.com/ozanozbeker/ichnos/issues/37)) ([96a0ab4](https://github.com/ozanozbeker/ichnos/commit/96a0ab402480a0756cf7e716d026cdf1249f9502))
* record the CLI surface ([#49](https://github.com/ozanozbeker/ichnos/issues/49)) ([98dada7](https://github.com/ozanozbeker/ichnos/commit/98dada7d095be5ad7c4908018d23bec78f4ec8d2)), closes [#15](https://github.com/ozanozbeker/ichnos/issues/15)
* record the DBML output rules ([#46](https://github.com/ozanozbeker/ichnos/issues/46)) ([d7904a2](https://github.com/ozanozbeker/ichnos/commit/d7904a2fbffe2b1f5588560aa939f191258d5eac)), closes [#12](https://github.com/ozanozbeker/ichnos/issues/12)
* record the declaration rules ([#43](https://github.com/ozanozbeker/ichnos/issues/43)) ([b24b317](https://github.com/ozanozbeker/ichnos/commit/b24b317e13c326c1b23a342750f8c39d5c954e4e)), closes [#33](https://github.com/ozanozbeker/ichnos/issues/33)
* record the dependency policy ([#39](https://github.com/ozanozbeker/ichnos/issues/39)) ([742d53f](https://github.com/ozanozbeker/ichnos/commit/742d53f8d95dd8c46abcf9d5991d6210ca658046)), closes [#16](https://github.com/ozanozbeker/ichnos/issues/16)
* record the evidence model ([#26](https://github.com/ozanozbeker/ichnos/issues/26)) ([ed5c68a](https://github.com/ozanozbeker/ichnos/commit/ed5c68a4ab9dabd59d4f69b12b53950565868cb3)), closes [#9](https://github.com/ozanozbeker/ichnos/issues/9)
* record the inferred type rules ([#41](https://github.com/ozanozbeker/ichnos/issues/41)) ([ce28690](https://github.com/ozanozbeker/ichnos/commit/ce28690273497fa9a08ca55f0eeedbbdfc1de365)), closes [#30](https://github.com/ozanozbeker/ichnos/issues/30)
* record the key inference rules ([#40](https://github.com/ozanozbeker/ichnos/issues/40)) ([ebc9994](https://github.com/ozanozbeker/ichnos/commit/ebc9994a4998242efb5b8465d370c34a573931c1)), closes [#28](https://github.com/ozanozbeker/ichnos/issues/28)
* record the lineage rules ([#45](https://github.com/ozanozbeker/ichnos/issues/45)) ([0be8bcc](https://github.com/ozanozbeker/ichnos/commit/0be8bcc27e75502b86344caadf425867a93e4ffc)), closes [#35](https://github.com/ozanozbeker/ichnos/issues/35)
* record the literal evidence rules ([#29](https://github.com/ozanozbeker/ichnos/issues/29)) ([6ead7a0](https://github.com/ozanozbeker/ichnos/commit/6ead7a0d5d14a28e81d9c04a1b2dfe316d5c1905)), closes [#11](https://github.com/ozanozbeker/ichnos/issues/11)
* record the LLM output rules ([#47](https://github.com/ozanozbeker/ichnos/issues/47)) ([7c66982](https://github.com/ozanozbeker/ichnos/commit/7c66982b560174fb8e5b2e4aaf706f4d3c4c7013)), closes [#13](https://github.com/ozanozbeker/ichnos/issues/13)
* record the parser decision ([#38](https://github.com/ozanozbeker/ichnos/issues/38)) ([d9506df](https://github.com/ozanozbeker/ichnos/commit/d9506df85681ae1788f7fa049e3c78cf19148a9b)), closes [#17](https://github.com/ozanozbeker/ichnos/issues/17)
* record the public API ([#48](https://github.com/ozanozbeker/ichnos/issues/48)) ([2041c32](https://github.com/ozanozbeker/ichnos/commit/2041c329e441a2d50cb0b0f280fc0b343316aeb9)), closes [#14](https://github.com/ozanozbeker/ichnos/issues/14)
* record the relationship inference rules ([#27](https://github.com/ozanozbeker/ichnos/issues/27)) ([8cbab32](https://github.com/ozanozbeker/ichnos/commit/8cbab328149363cec1ee5285c18817407269e8d4)), closes [#10](https://github.com/ozanozbeker/ichnos/issues/10)
* record the report naming rules ([#44](https://github.com/ozanozbeker/ichnos/issues/44)) ([ef474fb](https://github.com/ozanozbeker/ichnos/commit/ef474fb556ef6152d3002677e78aa90fa41fc9f2)), closes [#34](https://github.com/ozanozbeker/ichnos/issues/34)
* record the testing strategy ([#51](https://github.com/ozanozbeker/ichnos/issues/51)) ([f8fa38c](https://github.com/ozanozbeker/ichnos/commit/f8fa38ca24748fa83da74dcb0db63fd02230367d)), closes [#50](https://github.com/ozanozbeker/ichnos/issues/50)

## 0.0.1 (2026-10-30)


### Tests

* add a smoke test and document hello ([#2](https://github.com/ozanozbeker/ichnos/issues/2)) ([14cc15d](https://github.com/ozanozbeker/ichnos/commit/14cc15df533c4890fd0ea1a7c1dd23a086207865))
