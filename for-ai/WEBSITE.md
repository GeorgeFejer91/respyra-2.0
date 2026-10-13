# Website curation during development

Read this for public website edits, release promotion or download changes.
Product pages/assets remain in `companion/`; generators and publication code
remain in `scripts/`. This protocol owns the curation subroutines, not product UI.
Use [HTML-UI.md](./HTML-UI.md) and background gates in [VERIFICATION.md](./VERIFICATION.md).

## Select the promoted installer

`https://georgefejer91.github.io/respyra-2.0/download` is the permanent download
entry point; Pages redirects the directory URL to `/download/`. Keep the current
tested suite first and the three individual apps beneath it. Site download links
go here, with optional `#respyra`, `#polar` or `#vernier` anchors. Preserve the old
home `#download` redirect and its ordinary link fallback without JavaScript.

`companion/download/release.json` is the sole owner of installer choices. It pins
the public tag, qualified root/Mini revisions, exact artifact names, sizes/hashes
and a public qualification receipt. `scripts/prepare-download-page.mjs` generates
static HTML from it; never hand-edit that HTML or duplicate installer URLs on
other pages. Keep the suite's qualification date distinct from `pageUpdatedAt`.
The latter records the actual curation time in UTC; display date/time in
Europe/Berlin using a semantic `<time>`. Update it when the page content changes,
not on visits or unchanged preparation runs.

Keep the newest **qualified and published** suite selected. A newer source
version, successful compile, draft or uploaded binary alone cannot replace it.
Complete [PACKAGING.md](./PACKAGING.md)'s exact-artifact gates first, record the
receipt, publish with the existing authorization, then update the release record.
Do not use GitHub `releases/latest`: it excludes our preview releases and can
select an older installer. Preserve preview/unsigned status and the actual limits.

## Prepare and check the website

1. Inspect Git status and the owning implementation/release receipt. Update only
   affected current pages; keep historical versioned documentation intact.
   Variables remain one source-grouped table; marker definitions come from the
   catalog. Reuse existing styles, fonts and Pretext; avoid duplicate references.
2. Run `node scripts/prepare-web.mjs`; inspect the generated diff for drift.
3. Run `python for-ai/scripts/check-website-release.py` for download/release
   changes. It checks the public tag, exact server digests/sizes and anonymous
   installer access. It reuses the installed receipt; it does not requalify a
   binary or calculate a fresh full-file download hash.
4. Run `node tests/check_project_site.cjs` and inspect changed headless screenshots.
   Check navigation/local anchors, `/download`, legacy routing, no-JS downloads,
   all four exact links/order, visible update time, themes and enlarged text.
   Website-only changes do not require rebuilding unchanged installers.

## Publish and observe

Commit reviewed source/generated assets and push normally under [WORKFLOW.md](./WORKFLOW.md).
Use a clean, current `gh-pages` checkout; preserve unrelated changes. Publish with
`powershell -NoProfile -File scripts/publish-phone.ps1 -PagesDirectory <checkout> -Push`.
Despite its historical filename, that helper publishes the whole allowlisted
website, including `download/`, assets, `.nojekyll` and source provenance. It
rejects source-generation drift and an out-of-date Pages checkout.

Observe the Pages build for the exact commit. Fetch the ordinary `/download`
URL, verify its `/download/` redirect and exact public HTML/CSS/JS/release record
against Pages Git blobs, then inspect the real hosted page headlessly. Check all
four links and displayed update time, and the old `#download` redirect. A source
push alone is not deployment. Retain logs/hashes/screenshots in `.for-ai-local/`
and update [VERIFIED.md](./VERIFIED.md) with source/deployment SHAs, tests, reused
artifact evidence and scope limits. Report any pending alignment explicitly.
