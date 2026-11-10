"""catalog.py: which bundle ids belong to which kind of app. Add to it freely.

Only bundle ids that match a prefix here, or Apple's own (com.apple.), are shown
by name in any report. Anything else is counted as "unlisted app", because an
unknown identifier can name an organization or a custom tool.
"""

CATEGORIES = [
    ("Private messenger", ["ph.telegra.", "org.whispersystems.", "com.wire.", "ch.threema.",
                           "com.viber.", "net.whatsapp.", "com.sessionmessenger.", "im.vector.",
                           "com.facebook.Messenger"]),
    ("Social", ["com.facebook.", "com.burbn.instagram", "com.atebits.Tweetie2", "com.linkedin.",
                "com.zhiliaoapp.musically", "com.reddit."]),
    ("Work tools", ["com.microsoft.", "com.tinyspeck.", "us.zoom.", "com.google.", "com.slack",
                    "com.cisco.webex", "com.atlassian."]),
    ("Apple communication", ["com.apple.MobileSMS", "com.apple.InCallService", "com.apple.facetime",
                             "com.apple.mobilephone", "com.apple.mobilemail", "com.apple.mail"]),
    ("Apple", ["com.apple."]),
]


def classify(bundle):
    b = bundle or ""
    for name, prefixes in CATEGORIES:
        for p in prefixes:
            if b.startswith(p):
                return name
    return "Unlisted"


def display(bundle):
    """A bundle id safe to print, or a placeholder. Fails closed."""
    try:
        return bundle if classify(bundle) != "Unlisted" else "unlisted app"
    except Exception:
        return "withheld"
