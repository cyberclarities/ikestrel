"""dossier.py: for each store, an example of what it can hold and what that gives away.

Every example value here is INVENTED. Names, numbers, networks and places are
made up, but each example has the shape of a real row: the same columns, the
same codes, the same kind of value. They exist so a reader can see what a store
means without this app ever showing a real row.

  example  invented rows, as "field: value" lines
  alone    what someone learns from this store by itself
  worst    the most compromising thing it can contribute, usually in a join
"""

D = {}


def _d(sid, example, alone, worst):
    D[sid] = {"example": example, "alone": alone, "worst": worst}


_d("graph",
   ["person 4410: name = Dana Whitfield; first name = Dana; family name = Whitfield",
    "person 4410: has address -> full street address = 18 Alder Court, Easton; postal code = 27610",
    "person 4410: has contact information -> phone number = +1 555 010 2231, label = Mobile",
    "person 4410: employer -> member of = Northgate Logistics",
    "person 4410: imputed birthday = 1979-03-14; same as = cnContact:<uuid>",
    "app 7781: bundle id = com.example.vpnclient; published by = Example VPN Inc."],
   "Who the owner knows, where those people live, how to reach them, where they work, and roughly when "
   "they were born. Also every installed app with its publisher.",
   "A ready-made address book of third parties with home addresses and employers, plus a software "
   "inventory that names the owner's security tools, VPN and remote-access apps.")

_d("ontology",
   ["predicate PS317 = 'has address'; PS407 = 'phone number'; nm_imputedBirthday = 'imputed birthday'",
    "class nm_walletOrder = 'wallet order'; nm_shippingInfo = 'shipping info'"],
   "Nothing personal. It is the decoder ring for every code in the other stores.",
   "It shows what Apple built the graph to hold, including wallet orders and shipping details, even "
   "where those are empty today.")

_d("aliases",
   ["Q7560 (mother), localization en: 'mom', 'mum', 'mama'",
    "Q17297777 (friend), localization de: 'Freund'"],
   "Nothing personal. Words people use for relationships, in many languages.",
   "None on its own.")

_d("globalKnowledge",
   ["static fact: FC Example United; league name = Example League; image bytes = <logo>",
    "prior belief: source HealthKit, signal mindful, trust 0.87"],
   "Apple-shipped reference data, the same on every Mac.",
   "None about the owner. Its trust weights show which data sources the system was designed to use.")

_d("keyvalue",
   ["VisionSignalsEntityToVision: face cluster 3F2A.../L0/070 -> entity 4410, confidence 1.0",
    "RelationshipAliasKV: 'wifey' -> Q188830 (wife)",
    "Pipeline.Status.full.previous: lastPipelineRunFinishDate = 2026-11-09 23:41"],
   "Which Photos face belongs to which person, the owner's custom words for relationships, and when "
   "the pipeline last ran.",
   "The face-to-person map. With Photos, it puts a name on every recognized face.")

_d("views",
   ["sourceState: biome Siri.Remembers.CallHistory:remotes:<device-uuid>, last update 2026-11-10 08:27",
    "sourceState: biome Device.Wireless.WiFi, last update 2026-11-10 08:27",
    "viewConfigRecord: personEntityRelevanceRanking -> entityRelevance/entityRelevanceInferences.db"],
   "Every data stream the pipeline reads, which other devices feed it, and when each last updated.",
   "Proof that call, message and audio history from named other devices is synced to this Mac, with "
   "timestamps of the last sync.")

_d("state", ["task: sourceName Contacts, entityClass person, stage linking-resolution"],
   "Pipeline progress only.", "None on its own.")

_d("eventLog", ["event: name ingestContacts, timestamp 2026-11-09 23:40, payloadType <type>"],
   "Internal pipeline events, often empty.", "Timing of pipeline work; little else.")

_d("feedbackLog", ["feedback: type suggestionRejected, clientBundle com.apple.siri, eventId 912"],
   "Feedback the system recorded about its own suggestions, often empty.",
   "Which suggestions the owner accepted or dismissed, when present.")

_d("siriRemembers",
   ["interaction: INSendMessageIntent, app org.example.securemessenger, outgoing, 2026-03-02 23:14, from other device 1",
    "  recipients -> person 'Marcus Oyelaran'; recipient handle -> +1 555 010 8842",
    "interaction: INStartCallIntent, app com.apple.InCallService, incoming, 2026-03-03 07:02, duration 312 s",
    "interaction: LocateIntent, app com.apple.findmy, 2026-03-04 18:20"],
   "Who the owner messaged and called, in which app, in which direction, when, for how long, and from "
   "which device. Message text is not stored; only an identifier.",
   "A communication timeline from the owner's phone, sitting on the Mac. It includes apps chosen for "
   "privacy, and joins to names on this Mac through phone numbers and email addresses.")

_d("siriResolver",
   ["event: 2026-03-02 23:13, trigger 4, from other device 1",
    "candidate: contact <uuid>:ABPerson, app org.example.securemessenger",
    "tuple: (contact <uuid>, app com.apple.MobileSMS) chosen 41 times"],
   "Which contact and which app Siri chose each time it resolved a request, and how often each pairing "
   "won.",
   "Ranks the owner's habitual contact-and-app pairs, which shows the preferred channel for each person.")

_d("internalViews",
   ["handle_id: +1 555 010 2231 -> person 4410; dana.w@example.org -> person 4410",
    "wifiContextEvents: Connect:Lakeside Oncology Guest, 2026-10-15 18:43; Disconnect, 20:11",
    "photosObservedAges: person 4410, observed age 46, 2026-09-01",
    "bidirectionalPersonInteractionMechanisms: person 4410, 2026-10-30, mechanism 0, com.apple.mobilephone"],
   "Every phone number and email mapped to a person, a timestamped list of Wi-Fi networks joined, ages "
   "read from faces, and recent two-way contact with specific people.",
   "Network names can name places, so the Wi-Fi history alone can disclose a clinic, an employer or a "
   "home. The handle map is the bridge that names everyone in the phone's history.")

_d("ecr",
   ["entity_summary: person 4410, primary name Dana Whitfield; neighbor signals {people:[...], locations:[...], events:[...]}",
    "asr_entity_alias: person 4410, alias 'dana', signal first_provided_alias, contact <uuid>",
    "asr_entity_alias: person 4410, alias 'whitfield', signal family_provided_alias"],
   "A summary per person of the people, places and events linked to them, and the spoken forms of each "
   "name Siri listens for.",
   "Apple's own one-row dossier per contact, prepared for Siri.")

_d("euclid",
   ["document: 'Dana Whitfield' -> vector 7, partition 3",
    "observation: embedding <float vector> for entity 4410"],
   "Name embeddings for fuzzy matching.",
   "The names are recoverable from the documents, so it is another copy of the contact list.")

_d("entityTagging",
   ["person 4410: friend 0.38, family 0.09, coworker 0.00",
    "person 5120: mother 0.13, sibling 0.54, family 0.27, partner 0.27",
    "person 6031: partner 0.71"],
   "A score for how each person is related to the owner: parent, sibling, partner, child, friend, "
   "coworker.",
   "An inferred family tree and probable partner, for people the owner never labeled.")

_d("features",
   ["personEntityTaggingFacts: person 5120, sameLastName = true",
    "personEntityTaggingFacts: person 6031, sharesHomeAddress = true",
    "personEntityTaggingFacts: person 4410, hasSameWorkEmailDomain = true; personAge = 46"],
   "The evidence behind the relationship scores: shared surname, shared home address, shared email "
   "domain, ages.",
   "Shared home address and surname flags point straight at household members.")

_d("importance",
   ["person 6031: isFavorite = 1, isEmergencyContact = 1, isICloudFamily = 1, relationshipLabel = Spouse"],
   "Favorites, emergency contacts, iCloud family, and the relationship labels the owner set.",
   "Names the people an attacker would impersonate or target first.")

_d("relevance",
   ["person_entity_longterm: person 6031, relevance 0.93, explanation {'topSignals': ['messages', 'calls', 'photos']}"],
   "How important each person is to the owner, with the system's own explanation.",
   "A ranked list of the owner's closest people, with the reasons.")

_d("clients",
   ["siriPerson: person 4410, name Dana Whitfield, employer Northgate Logistics, identifier CNContact <uuid>"],
   "The person view handed to Siri: names and employers.",
   "Employer per contact makes the owner's professional network easy to map.")

_d("people", ["people: person 4410, name Dana Whitfield"], "A people view, often empty.", "Same as the graph when filled.")

_d("visualIdentifier",
   ["person 4410: has visual identifier -> 3F2A.../L0/070, association reason contactMatch",
    "person 4410: has contact information -> phone number +1 555 010 2231"],
   "Which face cluster belongs to which named person, next to that person's contact details.",
   "Face, name and phone number in one place.")

_d("photosAutonaming",
   ["unnamed face cluster 9C1B.../L0/070 -> proposed person 5120, confidence 0.82"],
   "Names the system proposes for faces the owner never named.",
   "Identifies people in photos the owner chose not to label.")

_d("lifeEvent",
   ["subgraph: person 6031, imputed birthday 1983-07-02",
    "subgraph: entity 4410, same as cnContact <uuid>"],
   "The material used to detect life events: birthdays, relationships, identities.",
   "Feeds anniversaries, moves and births once detected.")

_d("futureLifeEvent",
   ["place 811: has address -> 18 Alder Court, Easton 27610; has latitude/longitude 35.79, -78.64"],
   "Addresses and coordinates the system watches for upcoming life events.",
   "Geocoded home addresses for the owner and contacts.")

_d("appleMusicEvent", ["appleMusicEvent_map: event 22, start 2026-05-01 19:00, end 22:00"],
   "Apple Music events tied to the graph, often empty.", "Concert attendance and timing, when present.")

_d("donation", ["donationSubgraph: intent donated by com.example.travel -> event 'Flight to Denver'"],
   "Facts apps donated to the system, often empty.", "Travel and bookings from third-party apps, when present.")

_d("topicsShort", ["topic 1184 (Pregnancy), score 0.71, most recent document <id>"],
   "Short-term interest topics, often empty.", "Health, money or life-stage interests inferred from activity.")

_d("topicsLong", ["topic 402 (Mortgages), score 0.55"],
   "Long-term interest topics, often empty.", "Same as above, over a longer window.")

_d("sourceConfidence",
   ["priorBelief: source HealthKit, signal mindful, 0.87",
    "priorBelief: source HMHome, signal home, 0.90; source PassKit, signal pass, 0.80"],
   "How far each data source is trusted.",
   "The list of sources the system is built to ingest: Health, Home, Wallet, routine visits, contacts "
   "mined from mail. A map of what may appear here later.")

_d("inferredTriples",
   ["language: en, locale US, confidence 0.0; language: es, locale MX"],
   "Languages the owner is inferred to use.", "Hints at background or location.")


def get(sid):
    return D.get(sid)


def missing(store_ids):
    return [s for s in store_ids if s not in D]
