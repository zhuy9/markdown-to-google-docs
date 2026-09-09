# Google delivery

Discover capabilities rather than assuming a Drive connector can edit Docs.
Native requests require document creation, batchUpdate, and get with
`includeTabsContent=true`. The converter supports text blocks on this path;
unsupported structure is rejected before any remote creation.

For DOCX import, check Drive `about.importFormats` for the DOCX MIME type
`application/vnd.openxmlformats-officedocument.wordprocessingml.document`.
Upload the binary media with metadata MIME type
`application/vnd.google-apps.document`, then read back with Docs get.
See [Drive import](https://developers.google.com/workspace/drive/api/guides/manage-uploads#import_to_google_docs_types)
and [Docs requests](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request).

Standalone upload uses the user's own Google OAuth desktop client, with Drive
and Docs APIs enabled in their Cloud project. Install the repository/package
with its `google` extra, or install `google-api-python-client>=2,<3` and
`google-auth-oauthlib>=1,<2` alongside the extracted skill's requirements.

```bash
md2gdoc input.md -o output/document.docx --upload --credentials /private/client.json
```

For the extracted skill, use `python <skill-directory>/scripts/convert.py`
instead of `md2gdoc`. Initial sign-in opens a browser. The token defaults to
`~/.config/md2gdoc/token.json`; `--token` overrides it. Subsequent calls can omit
`--credentials`. Keep client files and tokens outside the repository. Never
embed shared keys in a public skill or ask users to paste secrets into chat.

Read-back checks cover text, structural counts, links, and code formatting.
Google import can change layout; these checks do not establish pixel-perfect
appearance. Report the Google URL and any failed checks. No automatic retries
or edits to existing documents are performed.
