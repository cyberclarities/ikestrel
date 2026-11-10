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
