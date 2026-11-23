# CDCT — TypeScript consumer

Verifies that a developer using **only the published `flow-semantics-ts`
package and the public docs** can exercise all 62 SPEC features.

## Pre-publish (local tarball)

```bash
# from repo root
cd typescript && npm pack        # produces flow-semantics-ts-0.0.0.tgz
cd ../cdc/typescript
npm install                      # installs the tarball + @types/node
node --test tests/consumer.test.ts
```

## Post-publish (npm)

Change the dependency in `package.json` to the registry version:

```json
"flow-semantics-ts": "^0.1.0"
```

then `npm install && node --test tests/consumer.test.ts`.

## Coverage

`tests/consumer.test.ts` — node:test suite mapping to all 62 features in
`docs/feature-audit.md`.
