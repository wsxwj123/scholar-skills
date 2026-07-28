# Zotero 首次设置指南

Note: PyZotero uses **Zotero Web API** (cloud). Desktop app does NOT need to run during API operations — but install it for local sync of created items.

**Step-by-step guide (show this to user if they haven't done it before):**

```
① Register / log in
   → https://www.zotero.org/user/register  (if no account)
   → https://www.zotero.org/user/login

② Get your Library ID (numeric user ID)
   → https://www.zotero.org/settings
   → Scroll to the bottom of the page
   → Look for: "Your user ID for use in API calls is: [NUMBER]"
   → Copy that number — this is your lib_id

③ Create an API key
   → https://www.zotero.org/settings/keys
   → Click "Create new private key"
   → Key Description: e.g. "review-writing-skill"
   → Permissions — check ALL of the following:
       ✅ Allow library access
       ✅ Allow write access           ← required for creating items/collections
       ✅ Allow notes access           ← required for abstract child notes
       ✅ Allow file access            ← required for PDF attachments
   → Click "Save Key"
   → Copy the generated key immediately (shown only once)

④ Save credentials once (reused automatically afterwards)
   python3 scripts/zotero_manager.py save-credentials --lib-id [NUMBER] --api-key [KEY]
   → stored in ~/.config/academic-skills/zotero.json (chmod 600, never in git)

⑤ Test connection (no credentials needed after step ④)
   python3 scripts/zotero_manager.py --status
   Expected output: ✅ Connected to Zotero library ...

⑥ Security rules
   - Credentials live only in ~/.config/academic-skills/zotero.json (600, outside the skill repo)
   - NEVER write api_key to outline.md or any repo file; the CLI never echoes it in full (last 4 chars only)
   - If 403 Forbidden error: re-run save-credentials with a fresh key; re-run --status before continuing
```

If `--status` lists multiple libraries (personal + group), show the list and ask user which to use, then re-run `save-credentials` with the chosen `lib_id`.
