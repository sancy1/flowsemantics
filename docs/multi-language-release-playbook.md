# Multi-Language Release Playbook

The complete discipline used to take FlowSemantics from five language
implementations to published packages on five registries with auto-generated
API docs on GitHub Pages — **v0.1.5, all green**.

Use this verbatim for the next library. Every section exists because we hit
the problem it prevents. The "Pitfalls" sections are the hot water — read
them before you need them.

---

## 1. Repository layout

```
repo/
├── SPEC.md                  # single normative spec (all languages conform)
├── conformance/vectors/     # shared JSON vectors — every language must pass 100%
├── docs/                    # language-neutral guides (features, cookbook, ADRs)
├── cdc/<lang>/              # consumer-driven contract tests (public API only)
├── python/  typescript/  go/  java/  csharp/
│   ├── README.md            # package-facing README (see §5)
│   └── ...implementation + tests...
├── .github/workflows/
│   ├── ci.yml               # Python lint/type/test + packaging audit
│   ├── ci-langs.yml         # unit + conformance for the other 4 languages
│   ├── audit.yml            # zero-third-party-runtime-deps audit
│   ├── docs-consumer.yml    # install-from-wheel consumer test
│   ├── pack.yml             # wheel+sdist+SBOM on tags
│   ├── pages.yml            # docs site → GitHub Pages
│   └── publish-<reg>.yml    # one per registry, tag-triggered
└── VERSION                  # root version; per-language VERSION files mirror it
```

Rules that saved us:

- **One conformance suite, five runners.** Normative semantics live in
  `conformance/vectors/*.json`; each language has a thin runner. Never
  duplicate expected outputs per language.
- **Zero third-party runtime deps** in every implementation, enforced by
  `audit.py` in CI. Build/dev deps are allowed but must be justified in
  `CONTRIBUTING.md`.
- **Every phase ships tests with the code** — unit tests per language AND
  integration/conformance vectors AND CDC tests. Never deferred.

---

## 2. Testing discipline (per language)

| Layer | What | Where |
|---|---|---|
| Unit | Feature-level tests, edge cases, adversarial inputs | `<lang>/tests/` or equivalent |
| Conformance | Shared vectors from `conformance/vectors/` — must be 100% | runner per language |
| Integration | End-to-end flows, error paths, finalization | `<lang>/tests/integration/` |
| CDC | Tests written from public docs only, run against the packed artifact | `cdc/<lang>/` |

Pitfalls:

- **Type-strict CI will find what you won't.** Python `mypy --strict` flagged
  missing return annotations in test helpers. Write annotations from the
  start; don't plan a "fix types later" pass.
- **PowerShell `>` corrupts text files** (writes UTF-16). It once inserted a
  literal `\n` into a Python file and broke imports. Use the `edit` tool or
  `[System.IO.File]::WriteAllText`, never `Set-Content`/`>` for code.
- **Test fixtures must match the spec version.** When vectors change, all
  five runners change in the same commit.

---

## 3. Documentation discipline

Two layers, both required:

### 3a. Human docs (`docs/`)

- `docs/README.md` indexes everything — keep it updated when adding pages.
- Feature guides are **language-neutral**; per-language READMEs link to them
  with absolute GitHub URLs (relative `../docs/` links break on registry pages).
- `SPEC.md` is the single normative source — implementations conform to it,
  docs explain it, nothing contradicts it.

### 3b. Package-facing READMEs (one per language)

Each registry shows its own README. Requirements learned the hard way:

- **Self-contained**: intro, what-it-does, quick-start code, install
  instructions, links to docs. Never "see the repo README".
- **Absolute URLs only** — registry pages have no relative context.
- **Prominent docs link near the top** — registry visitors decide in 5 seconds.
- **Registry metadata in the package manifest** (see §6) — README alone is
  not enough; npm/PyPI/NuGet/Maven all render manifest fields.

### 3c. Auto-generated API docs — per language

| Language | Tool | Output | Registry-native docs? |
|---|---|---|---|
| Python | Sphinx + `sphinx.ext.apidoc` | `site/python/` | No — link from PyPI README |
| TypeScript | TypeDoc | `site/typescript/` | No — link from npm README |
| Go | godoc comments | — | **Yes — pkg.go.dev renders automatically** |
| Java | `javadoc` | `site/java/` | Partial — javadoc.io indexes later |
| C# | DocFX | `site/csharp/` | No — link from NuGet README |

---

## 4. GitHub Pages docs site (`pages.yml`)

One workflow builds all doc generators and assembles `site/`:

```
site/
├── index.html          # hand-written landing page with links to everything
├── python/             # Sphinx HTML
├── typescript/         # TypeDoc HTML
├── java/               # Javadoc HTML
├── csharp/             # DocFX HTML
└── (go → links to pkg.go.dev, no local build)
```

### Pitfalls that cost us hours — DO NOT SKIP

1. **Path filter must include EVERY doc source.** Our filter listed
   `docs/**`, `python/**` but not `csharp/**` or `docfx.json` — DocFX fixes
   never triggered a redeploy and the site stayed stale for hours. When you
   add a doc generator, add its source paths to the filter in the same commit.
2. **Empty commits do NOT trigger path-filtered workflows.** To force a
   redeploy: touch a watched file, or use Actions → Run workflow
   (`workflow_dispatch`).
3. **DocFX needs TWO commands** — `docfx metadata` generates the API `.yml`
   files; `docfx build` only renders what exists. CI ran build-only → zero
   API pages. Always:
   ```
   docfx metadata docfx.json
   docfx build docfx.json
   ```
4. **DocFX `api/` has no `index.html`.** Link to the namespace root page
   (`api/<Namespace>.html`), never the bare `api/` directory.
5. **DocFX toc**: include the generated API tree via `href: api/toc.yml` in
   your root `toc.yml` — gives the full sidebar tree.
6. **DocFX markdown links must target `.yml` sources** (`api/Foo.yml`), not
   `.html` — DocFX resolves them and warns on `.html` links.
7. **Javadoc**: `-Xdoclint:none` avoids doclint failures on imperfect
   comments; `-encoding UTF-8` for non-ASCII.
8. **TypeDoc**: `npm ci` first (needs devDeps); `--excludePrivate` keeps
   internals out.
9. **After deploy, pages look "broken" for ~10 min** — GitHub Pages CDN
   cache + browser cache. Hard-refresh (`Ctrl+Shift+R`) or Incognito before
   concluding anything is wrong. A "canceled" check on a commit is benign —
   it means a newer push superseded it, not a failure.

---

## 5. Versioning discipline

- Single `VERSION` file at root + per-language `VERSION`/manifest bumps —
  **all five move together**. Mixed versions confuse consumers and docs.
- Tag `v<version>` on the release commit; all publish workflows trigger on
  `v*` tags.
- **Registry READMEs are immutable per version.** npm/PyPI/NuGet bake the
  README into the artifact at publish time. A README fix requires a NEW
  version — there is no "edit the published page". Batch all README/metadata
  changes BEFORE tagging.
- Keep a `CHANGELOG.md` (Keep a Changelog format) — update it in the release
  commit, not after.

---

## 6. Publishing — per registry

### 6a. PyPI (`publish-pypi.yml`)

- **Trusted publishing (OIDC)** — no API token. Configure the publisher on
  PyPI.org → package settings → GitHub repo + workflow filename.
- `pyproject.toml` needs: name, version (or dynamic from VERSION), description,
  readme, license, project URLs (Repository, Documentation, Issues),
  `requires-python`, `[build-system]`.
- Workflow: `pypa/gh-action-pypi-publish` on `v*` tags.
- PyPI page = README + metadata. Rich README = rich page.

### 6b. npm (`publish-npm.yml`)

- `package.json` needs: name, version, description, `repository`
  (`type: git, url`), `homepage`, `bugs`, `license`, `files`, `types`/`main`.
- Auth: `NPM_TOKEN` secret (granular access token, bypass 2FA for CI or use
  automation token).
- Workflow: `npm publish` (or `npm ci && npm publish`) on `v*` tags.
- **Put the docs-site link at the TOP of the README** — npm renders README
  natively; it's the only docs surface npm gives you.

### 6c. Go (`pkg.go.dev`)

- No publish workflow needed — **pkg.go.dev auto-indexes** the module when
  the tag is pushed. Just ensure `go.mod` module path matches the repo URL
  (`github.com/<user>/<repo>/<subdir>` for subdirectory modules).
- Doc comments on exported symbols ARE the documentation — write them well;
  pkg.go.dev renders them natively.
- Indexing lag: minutes to hours after tag push.

### 6d. NuGet (`publish-nuget.yml`)

- **Trusted publishing (OIDC)** via `NuGet/login@v1` — needs `id-token: write`
  permission and `user` = nuget.org profile name (NOT email).
- `FlowSemantics.csproj` needs: `PackageId`, `Version`, `Authors`,
  `Description`, `PackageLicenseExpression` (SPDX, e.g. `Apache-2.0`),
  `PackageReadmeFile`, `PackageProjectUrl`, `RepositoryUrl` +
  `RepositoryType`, `GenerateDocumentationFile` (ships XML doc for IDE
  tooltips).
- `<PackageReference>`-style README: set `<PackageReadmeFile>README.md</PackageReadmeFile>`
  and include it as `None`/`Content` with `Pack="true"`.
- Workflow: `dotnet pack` → `nuget push` or `NuGet/login` + push on `v*` tags.
- NuGet page = README + metadata. Same immutability rule as npm.

### 6e. Maven Central / Central Portal (`publish-maven.yml`) — the hardest

Central Portal (`central.sonatype.com`) replaced the old Sonatype OSSRH flow.
Namespace `io.github.<user>` is verified by linking your GitHub account —
**no DNS TXT record needed** (use this; `com.<domain>` requires DNS proof
you may not control).

Requirements, in order:

1. **pom.xml metadata**: `groupId=io.github.<user>`, `artifactId`, `version`,
   `packaging=jar`, `<name>`, `<description>`, `<url>`, `<licenses>`,
   `<developers>`, `<scm>` (connection/developerConnection/url/**tag** —
   keep tag in sync with releases), `<properties>` with
   `maven.compiler.release`, `<build>` with sourceDirectory.
2. **Attach sources + javadoc jars** — `maven-source-plugin` (`jar-no-fork`)
   and `maven-javadoc-plugin` (`jar`). Central requires both.
3. **PGP sign EVERYTHING** — Central Portal rejects unsigned files:
   - `maven-gpg-plugin` bound to `verify` phase, goal `sign`, with
     `<arg>--pinentry-mode</arg><arg>loopback</arg>`.
   - CI imports the key via `crazy-max/ghaction-import-gpg@v6` with secrets
     `GPG_PRIVATE_KEY` + `GPG_PASSPHRASE`.
4. **Generate the GPG key locally** (Git Bash has `gpg`):
   ```
   gpg --full-generate-key        # RSA+RSA, 4096 bits, no expiry
   gpg --list-secret-keys --keyid-format LONG
   ```
5. **Export keys — ASCII armor, NO PowerShell redirect** (it writes UTF-16
   and corrupts the armor → "Misformed armored text" in CI):
   ```
   gpg --armor --export-secret-keys <KEYID> > key.asc   # in Git Bash, or:
   cmd /c '"C:\...\gpg.exe" --armor --export-secret-keys <KEYID> > key.asc'
   ```
   Verify: file starts `-----BEGIN PGP PRIVATE KEY BLOCK-----`, zero null
   bytes. Copy the ENTIRE file including BEGIN/END lines into the secret.
6. **Publish the PUBLIC key** so Central can verify signatures:
   - `gpg --keyserver hkps://keys.openpgp.org --send-keys <KEYID>` — often
     blocked by corporate/firewall networks.
   - **Fallback that always works**: web upload at
     `https://keys.openpgp.org/upload` (file upload, not paste).
   - **Then verify the email** — keys.openpgp.org will NOT serve the key
     until you click the verification link. Central's "Could not find a
     public key by fingerprint" error means this step is incomplete.
   - Verify it's live:
     `https://keys.openpgp.org/vks/v1/by-fingerprint/<FINGERPRINT>`
7. **Central Portal credentials**: create a token at central.sonatype.com →
   set GitHub secrets `CENTRAL_USERNAME` + `CENTRAL_PASSWORD`.
8. **Workflow**: generate `settings.xml` from secrets, `mvn -B deploy`.
   `central-publishing-maven-plugin` with `<autoPublish>true</autoPublish>`
   publishes automatically after validation. Add `workflow_dispatch` so you
   can re-run without re-tagging (versions are immutable once published).
9. **Javadoc appears on Central** once the `-javadoc.jar` is published;
   javadoc.io indexes it within ~a day.

---

## 7. GitHub Actions secrets inventory

Set once per repo (Settings → Secrets → Actions):

| Secret | Registry | Notes |
|---|---|---|
| `NPM_TOKEN` | npm | granular automation token |
| `NUGET_USER` | NuGet | profile name, not email (OIDC) |
| `CENTRAL_USERNAME` | Maven | Central Portal token username |
| `CENTRAL_PASSWORD` | Maven | Central Portal token password |
| `GPG_PRIVATE_KEY` | Maven | ASCII-armored private key, full file |
| `GPG_PASSPHRASE` | Maven | the passphrase YOU chose (irrecoverable) |
| PyPI | — | none needed (OIDC trusted publishing) |
| Go | — | none needed (auto-index) |

---

## 8. Release checklist (run in order)

```
[ ] 1. All tests green locally: unit + conformance (100%) + CDC per language
[ ] 2. audit.py passes (zero runtime deps)
[ ] 3. docs/ updated; every language README is package-facing with absolute links
[ ] 4. All five versions bumped together (VERSION files + manifests)
[ ] 5. CHANGELOG.md entry written
[ ] 6. Commit "release vX.Y.Z" → tag vX.Y.Z → push commit AND tag
[ ] 7. Watch all publish workflows go green (PyPI, npm, NuGet, Maven, Pages)
[ ] 8. Maven only: confirm Central Portal shows "Published" (autoPublish)
[ ] 9. Verify live pages: PyPI, npm, pkg.go.dev, NuGet, central.sonatype.com
[ ] 10. Verify docs site: all 4 API doc sections render (hard-refresh!)
[ ] 11. Repo README package table links all resolve
[ ] 12. Note indexing lag: search.maven.org, javadoc.io, pkg.go.dev take hours
```

---

## 9. Timeline expectations (set expectations early)

| Event | Latency |
|---|---|
| Publish workflow green | ~1–3 min per registry |
| PyPI/npm/NuGet page live | immediate |
| pkg.go.dev indexed | minutes–hours |
| search.maven.org indexed | hours–1 day |
| javadoc.io indexed | hours–1 day |
| GitHub Pages CDN refresh | ~10 min after deploy |
| keys.openpgp.org email verify | instant–15 min (check spam) |

---

## 10. The one-paragraph summary

Conformance vectors keep five languages honest; package-facing READMEs with
absolute doc links make registry pages useful; manifest metadata (not just
READMEs) makes registries render rich pages; Maven Central is the only
registry that fights back (GPG + keyserver + immutable versions); DocFX is
the only doc generator with a two-step build; and every "it's broken" report
in the final hour was cache, path filters, or a missing workflow step —
verify server-side before touching code.
