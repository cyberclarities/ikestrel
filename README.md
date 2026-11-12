# iKestrel

See every store your Mac's IntelligencePlatform keeps, measured and reported. Counts only.

macOS builds a personal knowledge graph under `~/Library/IntelligencePlatform`, and then
builds about thirty more stores on top of it. Most tools look at the graph. The graph is
the *who*. The other stores are the *what you do, with whom, when, and where*: Siri's
interaction history synced from your phone, a scored guess at how each person is related
to you, the Wi-Fi networks you joined and when, faces in Photos tied to names.

iKestrel measures all of them, turns the measurements into findings, and writes two
reports a security team can hand to someone else. It never shows a name, a number, an
address, a network, or a message. It shows how many.

## What it covers

Thirty catalogued stores in eight groups, with 57 measurements:

| Group | Stores |
|---|---|
| Knowledge graph | graph, ontology, aliases |
| Communications | Siri remembers, Siri default resolver |
| Identity and context | internal views (handles, Wi-Fi), ECR, Euclid vector index, inferred triples |
| Relationships | entity tagging, features, importance signals, relevance, clients, people |
| Photos | visual identifier, Photos auto-naming |
| Life events and topics | life events, future life events, Apple Music events, donations, topics |
| Pipeline | views, keyvalue, state, event and feedback logs, source confidence |
| Apple-shipped | global knowledge |

A store on disk that this version doesn't catalogue yet is listed in the technical
report, so a new macOS release can't hide a store by adding it.

## Run it

```sh
cd ikestrel
python3 server.py                       # this Mac, live
python3 server.py --copy ~/IP-snapshot  # a copied IntelligencePlatform folder
```

Open the link it prints. Reports open in their own tabs with a print button.

It needs the Python 3 that ships with macOS (3.9 or later). No packages, no build step.

### Full Disk Access

The live folder sits behind macOS privacy controls. Give the app you start the server
from (Terminal, iTerm) Full Disk Access in System Settings › Privacy & Security, then quit
it fully and reopen it. Turn it back off when you're done. The grant covers everything
you run from that app, not just iKestrel.

### Reading a copy

```sh
mkdir -p ~/IP-snapshot
ditto ~/Library/IntelligencePlatform ~/IP-snapshot/IntelligencePlatform
python3 server.py --copy ~/IP-snapshot
```

`ditto` keeps each database with its `-wal` and `-shm`. That matters. The WAL holds the
newest writes, and a reader that skips it reads stale data. On a copy, FileVault is
reported as not measured, because a copy says nothing about the Mac it came from.

## The connection map

Open **Connection map** from the main page. It shows how the stores join, measured as overlaps
between identifier sets. The identifiers stay on the server for the length of one request; the
page gets store names and counts, nothing else.

Five keys tie the stores together:

| Key | What it is | What it tells you |
|---|---|---|
| Entity id | The graph's own id for a person, place, app or organization | About seventeen stores key on it, so it's drawn as a hub on `graph.db` |
| Contact UUID | The Contacts record id | It differs between devices, so phone history matches poorly here |
| Phone or email | Normalized handles | The bridge. Phone history joins to people on this Mac through it |
| Face cluster | A Photos face-cluster id | Ties Photos to the graph |
| Device id | Another device synced to this Mac | Ties the Siri stores to the pipeline's stream log |

Click a store for what it holds and every join it has. Click a line for the overlap and the share
of each side. Drag stores to rearrange them. Toggle keys to see one join at a time. The same data
is in a table under the map, and in section 3a of the technical report with its SQL.

## The spider map

Open **Spider map** for the view iOwl opens with: you in the middle, and everyone your Mac links to
you around you. It is built from all the stores, not just the graph, so the lines say why each
person is there:

| Line | What it means |
|---|---|
| Blue | They're in your message and call history, synced from your phone. Darker means more. |
| Wide orange dashed band | The Mac scored a relationship: family, partner, friend, coworker. You didn't enter it. |
| Wide red band | iCloud Family Sharing |
| Wide green band | The Mac flags a shared home address |
| Pink dotted | You marked them a favorite, an emergency contact, or gave them a label |
| Yellow | Works at, per the graph, out to an employer circle |

Circle colour says what they are to you, by the same rules; circle size is how many stores on
this Mac hold that person. Click anyone and the panel says in plain words what the Mac holds:
how many messages you sent and received and in which apps, what it scored them as, whether it
holds an address, an employer, a birthday or a face, and which stores hold them.

It works in both modes. With real values off, people are "Person 1", "Person 2" in order of how
much the Mac holds on them, employers are "Employer A", and nothing personal leaves the server,
so it is safe to walk someone through on a shared screen. Turn real values on and the same map
fills in names, addresses, employers and the names Siri listens for, with a link to each
person's full profile.

The drawing is iOwl's `force.js`, used unchanged under the Apache License 2.0. See NOTICE.

## Real values

Everything above is counts only. Turn on **Show real values** in the bar at the top of any page
and four views open up, in your browser only:

- **People.** Pick anyone and see every fact this Mac links to them across every store: name,
  phones and emails, graph facts with places resolved to street addresses, relationship scores,
  the features behind them, importance flags, Siri's summary and spoken aliases, ages read from
  faces, and their communication history from the synced Siri store, with each message marked as
  sent to them, received from them, or a group message they were in.
- **Chain drill-down.** On the map, each step of a chain becomes clickable and lists the people
  still in view at that step, each linking to their profile.
- **Browse stores.** Page through any store's real rows, with ontology codes and Apple dates
  decoded and archived values unpacked.
- **Timeline.** Siri history, Wi-Fi joins, calendar events, two-way contact and Photos
  observations on one timeline, newest first, with phone numbers resolved to names.

How it is fenced:

- The toggle is off by default and lives in the tab's session storage, which is tied to the
  server's port, so every restart turns it off again. A red bar stays up while it's on.
- Real values come only from `/api/reveal/*`, which needs the session token **and** a header the
  app's own pages send. A link or an embedded request can't fetch them.
- Reports and the CSV never include real values, whatever the toggle says. The tests check it.
- Everything is still read-only and nothing is written to disk.

One thing to know before you read the communication history: Siri's `direction` column does not
match Apple's documented enum on real data. iKestrel reads direction from who is listed on each
row instead. A row that names a sender is a message received; a row with only recipients is a
message sent.

Turn the toggle off before you share your screen.

## The store sheet

Open **Store sheet** from the main page for every store in one table: group, sensitivity, a
headline count, how many identifiers of each key it holds, how many stores it joins, which chains
it sits in, and its measurement status. Sort by any column, filter by group or sensitivity, search
any text. **Show risk text** adds what each store gives away and its worst case; **Show example
rows** adds the invented examples.

**Download CSV** saves the same rows, built by the same code, so the file and the page can't
disagree. Cells that begin with `=`, `+`, `-` or `@` are prefixed with an apostrophe so a
spreadsheet opens them as text, never as formulas. The file starts with a byte-order mark so
Excel reads it as UTF-8.

### Going deeper

- **Click a store** for what it gives away on its own, the worst case it contributes to, and a few
  example rows. The examples are invented, in the exact shape of real rows, so a reader can see what
  a store means without the app showing anything real. Every email is `example.org` and every phone
  number is in the reserved 555-01xx range; the tests check that.
- **Click a line** for what that join lets someone learn.
- **What can be ascertained** lists five chains. Each walks from store to store and counts how many
  people are still in view at each step: from the phone's contacts to names, places and relationship
  scores here; from inferred family to contact details; from faces to names and numbers; from the
  people the owner flagged as important to the phone's history; from the people the owner messages
  to their employers. **Show path on map** highlights the stores and the exact keys the chain uses.

The chains, the per-store dossiers and the join notes are also in the technical report (sections
3b and Appendix B), and the brief carries one line per chain.

The map is also where finding K-13 comes from. Contact ids don't line up between a phone and a
Mac. Phone numbers and email addresses do, so a phone's synced history attaches to names, faces
and relationship scores on the Mac anyway.

## Findings

| Id | Finding | Severity |
|---|---|---|
| K-01 | This Mac holds communication history from other devices | High |
| K-02 | Metadata from private messengers is logged by the operating system | High |
| K-03 | Message text is or is not stored in Siri's history | Note or High |
| K-04 | One counterpart dominates the communication log | Medium |
| K-05 | The Mac scores how each person is related to the owner | Medium |
| K-06 | Wi-Fi network names are kept with timestamps | Medium |
| K-07 | Faces in Photos are linked to people in the graph | Medium |
| K-08 | Phone numbers and email addresses resolve to people | Low |
| K-09 | Much of graph.db is free pages left by earlier builds | Note |
| K-10 | HealthKit is a trusted source in the pipeline | Note |
| K-11 | Organization terms appear among people's handles | Medium |
| K-12 | FileVault is off | High |
| K-13 | Phone history joins to named people on this Mac | High |

Severity is a judgment, and it's written down in `kestrel/findings.py` so it can be argued
with. K-03 exists on purpose. Siri keeps who and when, not what was said, and a brief that
doesn't say so will overstate the exposure.

## The rules stay readable

- `kestrel/stores.py` lists every store, what it holds, and how sensitive it is.
- `kestrel/measure.py` holds every measurement and the SQL behind it.
- `kestrel/findings.py` holds every rule.
- `kestrel/catalog.py` decides which apps can be named. Anything outside it prints as
  "unlisted app", because an unknown bundle id can name an organization.
- `kestrel/report.py` renders both reports from the same measurements.

## How it stays local and honest

- One Python process, standard library only, bound to 127.0.0.1.
- A fresh token at every start. No token, no answer. A foreign Host header is refused.
- Every store opens with SQLite `mode=ro`. Nothing is written to disk.
- Full-text virtual tables are never touched. Apple builds them with a private tokenizer
  (`unicode61wrapper`) that stock SQLite doesn't have, and even a count against one fails.
  Their content tables carry the same rows.
- A store or query that can't run is reported as not measured, with the reason. Not
  measured is not zero.
- The technical report hashes every database and WAL in scope. A full run against a copy
  leaves those bytes unchanged; the tests check it.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

`tests/make_fixture.py` builds a small, made-up IntelligencePlatform folder with known
answers, including an FTS table with Apple's private tokenizer. The tests check every
count, check that no invented name, number, address, network or device id reaches the
reports or the API, check that reading leaves the stores unchanged, and start the server
to confirm it refuses requests without its token.

## Limits

- Apple changes these stores between releases. This version was built against one Mac on
  macOS 27. Expect columns to move.
- Many feature values are archived property lists that this version counts but does not
  decode.
- One Mac is one Mac. The phone and other devices hold their own copies.
- Settings that might reduce what's synced are reported as candidates, not fixes, until
  they're tested on a real device.

## License

Apache 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
