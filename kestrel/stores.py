"""stores.py: every IntelligencePlatform store this app knows, and what it holds.

Paths are relative to ~/Library/IntelligencePlatform. "fullRebuild" twins exist
for most Artifacts stores; they are staging copies used during a rebuild and are
inventoried but not measured.

Sensitivity is a judgment, stated so it can be argued with:
  High   - describes people other than the owner, or reconstructs behavior
  Medium - describes the owner's own setup or routines
  Low    - pipeline state, Apple-shipped reference data
"""

STORES = [
    # id, path, group, holds, sensitivity
    ("graph", "graph.db", "Knowledge graph",
     "The personal knowledge graph: people, organizations, places, apps and calendar events as triples, each tagged with the source it came from.", "High"),
    ("ontology", "ontology.db", "Knowledge graph",
     "Apple's dictionary of the class and predicate codes the graph uses.", "Low"),
    ("aliases", "aliases.db", "Knowledge graph",
     "Multilingual words for relationships (mother, friend), keyed to Wikidata ids.", "Low"),
    ("globalKnowledge", "globalKnowledge.db", "Apple-shipped",
     "Reference data Apple ships: sports teams, holidays, media, and prior beliefs about how far to trust each source.", "Low"),
    ("keyvalue", "keyvalue.db", "Pipeline",
     "Resolver maps, Photos face-to-entity links, relationship words, pipeline run times.", "Medium"),
    ("views", "views.db", "Pipeline",
     "Recipes for every derived view, and the log of each data stream the pipeline reads, including streams synced from other devices.", "Medium"),
    ("state", "state.db", "Pipeline", "Task progress for pipeline stages.", "Low"),
    ("eventLog", "eventLog.db", "Pipeline", "Internal pipeline event log.", "Low"),
    ("feedbackLog", "feedbackLog.db", "Pipeline", "Feedback the system recorded about its own outputs.", "Low"),
    ("siriRemembers", "Artifacts/siri/remembers/view.db", "Communications",
     "Siri's interaction history: messages, calls and app intents, who was on each side, when, and from which device.", "High"),
    ("siriResolver", "Artifacts/siri/defaultResolverInteractions/view.db", "Communications",
     "Which contact and app Siri resolved each request to, with timestamps and device of origin.", "High"),
    ("internalViews", "Artifacts/internal/views.db", "Identity and context",
     "Handle-to-person map, Photos person map, Wi-Fi network connect history, interaction histograms, subgraphs.", "High"),
    ("ecr", "Artifacts/ecr/views.db", "Identity and context",
     "Entity summaries and the aliases Siri listens for, including speech-recognition variants.", "High"),
    ("euclid", "Artifacts/ecr/euclid/index.sql", "Identity and context",
     "A vector index of entity names for fuzzy matching.", "Medium"),
    ("entityTagging", "Artifacts/entityTagging/entityTagging.db", "Relationships",
     "A scored guess, per person, at how each one is related to the owner.", "High"),
    ("features", "Artifacts/feature/features.db", "Relationships",
     "Features behind relationship and relevance scores: shared surname, shared email domain, shared address, birthdays, family membership.", "High"),
    ("importance", "Artifacts/entityRelevance/entityImportanceSignals.db", "Relationships",
     "Favorites, emergency contacts, family membership and relationship labels per person.", "High"),
    ("relevance", "Artifacts/entityRelevance/entityRelevanceInferences.db", "Relationships",
     "Ranked relevance of people and places of interest.", "High"),
    ("clients", "Artifacts/entityRelevance/clients.db", "Relationships",
     "The person view handed to Siri.", "High"),
    ("visualIdentifier", "Artifacts/visualIdentifier/visualIdentifier.db", "Photos",
     "Face clusters from Photos linked to people in the graph.", "High"),
    ("photosAutonaming", "Artifacts/photosAutonaming/photosAutonaming.db", "Photos",
     "Proposed names for unnamed faces in Photos.", "High"),
    ("lifeEvent", "Artifacts/lifeEvent/lifeEventView.db", "Life events",
     "Subgraph used to detect life events.", "Medium"),
    ("futureLifeEvent", "Artifacts/futureLifeEvent/futureLifeEventView.db", "Life events",
     "Subgraph used to anticipate upcoming life events, centered on addresses.", "Medium"),
    ("appleMusicEvent", "Artifacts/appleMusicEvent/appleMusicEventView.db", "Life events",
     "Apple Music events tied to the graph.", "Low"),
    ("donation", "Artifacts/donation/donation.db", "Life events", "Intent donations from apps.", "Medium"),
    ("topicsShort", "Artifacts/firstPartyTopics/scoredTopicsFirstPartyShortTerm.db", "Topics",
     "Short-term interest topics.", "Medium"),
    ("topicsLong", "Artifacts/firstPartyTopics/scoredTopicsFirstPartyLongTerm.db", "Topics",
     "Long-term interest topics.", "Medium"),
    ("sourceConfidence", "Artifacts/confidenceService/sourceConfidence.db", "Pipeline",
     "How far each data source is trusted.", "Low"),
    ("inferredTriples", "Artifacts/internal/inferred_triples.db", "Identity and context",
     "Inferred facts, such as the languages the owner uses.", "Medium"),
    ("people", "Artifacts/people/people.db", "Relationships", "People view.", "High"),
]

BY_ID = {s[0]: s for s in STORES}


def as_dicts():
    return [{"id": i, "path": p, "group": g, "holds": h, "sensitivity": s}
            for i, p, g, h, s in STORES]
