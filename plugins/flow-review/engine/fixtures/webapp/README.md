# Fixture App

A tiny static app used only by flow-review's own engine tests. It exists to exercise
every measurement rule and the explorer's docs pass.

## Features

- **Sign in** — a username/password form (`#login-form`). Submitting with both fields
  filled shows "Signed in."
- **Continue** (`#cta-button`) — a primary action button.
- **Save** / **Cancel** (`#save-button`, `#cancel-button`) — two buttons that sit in the
  same spot.
- **Help** (`#help-button`) — present in the UI, does nothing when clicked.
- **Load data** (`#load-button`) — fetches `/api/fail`, which always returns HTTP 500.
- **Export** — download your data as JSON. Not linked from the app UI; see `docs.html`.
