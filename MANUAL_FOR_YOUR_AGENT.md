# iKestrel guide for AI agents

This guide is for an AI agent with a shell on a Mac whose owner wants to know what the
IntelligencePlatform stores hold. Read section 1 and do what it says before anything else.

## 1. Get consent before you read anything

What you read lands in your context, and your context goes to whoever runs your model.
These stores describe the owner's relationships, contacts, communication patterns, Wi-Fi
history and photos, and they hold scored guesses about other people, none of whom agreed
to any of it.

Before your first read, tell the owner which model and provider you are (or that you
don't know), that what you read goes to that provider, and what their question will make
you read. Then ask, and wait:

> Do you trust the provider running me with the contents of your Mac's IntelligencePlatform stores? (yes / no)

Only a plain yes counts. On a no, stop, and point the owner to iKestrel in the browser,
which sends nothing off the Mac.

## 2. Ground rules

1. Never write to a store. Open read-only: `sqlite3 "file:$HOME/Library/IntelligencePlatform/graph.db?mode=ro"`.
   No INSERT, UPDATE, DELETE, VACUUM, `PRAGMA wal_checkpoint` or `PRAGMA journal_mode`.
2. Prefer iKestrel's counts (`/api/summary`) to raw rows. Read rows only when the owner asks
   a question the counts can't answer.
3. Don't touch FTS virtual tables. They need Apple's private tokenizer and will error.
4. Timestamps are seconds since 2001-01-01 UTC. Add 978307200 for Unix time.
5. `sources` in graph.db is a bitmask: 1 Contacts, 32 Photos, 256 Calendar, 8192 Family
   Sharing, 32768 installed apps. Test bits; don't group by the raw value.
6. A store you can't read is not measured. Say so. Don't report it as empty.
7. Don't read Siri's `direction` code as Apple documents it. On real data, rows naming a sender
   are messages received and rows with only recipients are messages sent.
8. iKestrel's `/api/reveal/*` endpoints return real names, numbers and message history. They
   need the token and an `X-Kestrel-Reveal: 1` header. Section 1 applies to them in full: no
   call without the owner's yes.
