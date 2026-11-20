"""Field lanes. Edit the account lists to change who each lane follows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Lane:
    id: str
    title: str
    accent: str
    summary: str
    accounts: tuple[tuple[str, str], ...]
    terms: tuple[str, ...]
    boost: tuple[str, ...]
    window_days: int
    news_query: str
    search_query: str

    def public(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "accent": self.accent,
            "summary": self.summary,
            "accounts": [
                {"handle": handle, "name": name, "url": f"https://x.com/{handle}"}
                for handle, name in self.accounts
            ],
        }


LANES: tuple[Lane, ...] = (
    Lane(
        id="neuroscience",
        title="Neuroscience",
        accent="#bb9af7",
        summary="Journals and institutes. Posts are ranked by how hard people are engaging with them.",
        accounts=(
            ("NatureNeuro", "Nature Neuroscience"),
            ("AllenInstitute", "Allen Institute"),
            ("SfNtweets", "Society for Neuroscience"),
            ("TheTransmitter", "The Transmitter"),
        ),
        terms=("neuroscience", "neuralink", "synapse", "connectome", "optogenetic", "fmri", "bci", "hippocampus", "brain"),
        boost=("preprint", "published", "we found", "study"),
        window_days=21,
        news_query="neuroscience",
        search_query='(neuroscience OR "brain-computer" OR optogenetics OR connectome OR "neural circuit" OR synapse) lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="cybersecurity",
        title="Cybersecurity",
        accent="#f7768e",
        summary="Incident reporters and the official cyber agencies.",
        accounts=(
            ("TheHackersNews", "The Hacker News"),
            ("BleepinComputer", "BleepingComputer"),
            ("CISAgov", "CISA"),
            ("vxunderground", "vx-underground"),
        ),
        terms=("ransomware", "malware", "cybersecurity", "infosec", "breach", "vulnerability", "cisa", "cve", "zeroday", "zero-day"),
        boost=("cve-", "zero-day", "ransomware", "breach", "exploited"),
        window_days=7,
        news_query="cybersecurity",
        search_query='(ransomware OR "zero-day" OR "zero day" OR malware OR "data breach" OR "threat actor" OR CVE) lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="chemistry",
        title="Chemistry",
        accent="#e0af68",
        summary="Chemistry journals and the society press.",
        accounts=(
            ("NatureChemistry", "Nature Chemistry"),
            ("ChemistryWorld", "Chemistry World"),
            ("cenmag", "C&EN"),
            ("ACSPublications", "ACS Publications"),
        ),
        terms=("chemistry", "catalysis", "molecule", "perovskite", "polymer", "electrochemistry", "synthesis"),
        boost=("published", "synthesis", "catalyst"),
        window_days=21,
        news_query="chemistry research",
        search_query='(catalysis OR "chemical synthesis" OR "materials chemistry" OR perovskite OR electrochemistry OR "organic chemistry") lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="biology",
        title="Biology",
        accent="#9ece6a",
        summary="Life-science journals plus the bioRxiv feed.",
        accounts=(
            ("NatureBiotech", "Nature Biotechnology"),
            ("CellCellPress", "Cell"),
            ("biorxivpreprint", "bioRxiv"),
            ("eLife", "eLife"),
        ),
        terms=("crispr", "genomics", "proteomics", "microbiome", "mrna", "biotech", "dna", "gene", "genome"),
        boost=("crispr", "preprint", "published"),
        window_days=21,
        news_query="genomics CRISPR",
        search_query='(CRISPR OR genomics OR proteomics OR "synthetic biology" OR microbiome OR "gene therapy") lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="drug-development",
        title="Drug development",
        accent="#ff9e64",
        summary="FDA, trial reporters, and the biotech trade press.",
        accounts=(
            ("US_FDA", "FDA"),
            ("statnews", "STAT"),
            ("endpts", "Endpoints News"),
            ("FierceBiotech", "FierceBiotech"),
        ),
        terms=("fda", "pharma", "vaccine", "biotech", "clinical trial", "drug discovery", "phase 3", "approval"),
        boost=("phase 3", "phase iii", "approved", "clinical trial", "fda"),
        window_days=14,
        news_query="clinical trial",
        search_query='("clinical trial" OR "FDA approval" OR "drug discovery" OR "phase 3" OR "phase III" OR "new drug") lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="physics",
        title="Physics",
        accent="#7dcfff",
        summary="Physics journals, CERN, and LIGO.",
        accounts=(
            ("NaturePhysics", "Nature Physics"),
            ("APSphysics", "American Physical Society"),
            ("CERN", "CERN"),
            ("LIGO", "LIGO"),
        ),
        terms=("quantum", "fusion", "cern", "ligo", "neutrino", "superconduct", "dark matter", "gravitational wave", "physics"),
        boost=("observed", "detected", "published", "result"),
        window_days=21,
        news_query="quantum physics fusion",
        search_query='(quantum OR "fusion energy" OR "dark matter" OR "gravitational wave" OR superconduct OR "particle physics") lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="app-development",
        title="App development",
        accent="#7aa2f7",
        summary="App Store, Google Play, Product Hunt, and GitHub. Launch language ranks higher.",
        accounts=(
            ("ProductHunt", "Product Hunt"),
            ("AppStore", "App Store"),
            ("AndroidDev", "Android Developers"),
            ("github", "GitHub"),
        ),
        terms=("app store", "product hunt", "google play", "ios", "android"),
        boost=("just launched", "now available", "we shipped", "introducing", "on the app store", "product hunt", "new app"),
        window_days=10,
        news_query="app launch",
        search_query='(("just launched" OR "now available" OR "on the App Store" OR "Product Hunt" OR "we just shipped") (app OR iOS OR Android)) lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="robotics",
        title="Robotics",
        accent="#73daca",
        summary="Humanoid builders, Unitree, Boston Dynamics, and the robotics press.",
        accounts=(
            ("BostonDynamics", "Boston Dynamics"),
            ("Figure_robot", "Figure"),
            ("UnitreeRobotics", "Unitree"),
            ("IEEESpectrum", "IEEE Spectrum"),
        ),
        terms=("robotics", "humanoid", "robot", "robots", "unitree", "embodied"),
        boost=("humanoid", "demo", "unveiled", "shipped"),
        window_days=14,
        news_query="robotics humanoid",
        search_query='(humanoid OR robotics OR "robot arm" OR "embodied AI" OR "autonomous robot") lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="ai",
        title="AI",
        accent="#bb9af7",
        summary="Model labs and Hugging Face.",
        accounts=(
            ("OpenAI", "OpenAI"),
            ("AnthropicAI", "Anthropic"),
            ("GoogleDeepMind", "Google DeepMind"),
            ("huggingface", "Hugging Face"),
        ),
        terms=("llm", "gpt", "openai", "anthropic", "claude", "gemini", "foundation model", "ai agent", "ai"),
        boost=("model", "release", "agent", "open-weight", "weights"),
        window_days=7,
        news_query="artificial intelligence model",
        search_query='("foundation model" OR "open-weight" OR "AI agent" OR LLM OR "language model" OR "model release") lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="startups",
        title="Startups",
        accent="#e0af68",
        summary="TechCrunch, Y Combinator, a16z, and Sequoia.",
        accounts=(
            ("TechCrunch", "TechCrunch"),
            ("ycombinator", "Y Combinator"),
            ("a16z", "a16z"),
            ("sequoia", "Sequoia Capital"),
        ),
        terms=("startup", "startups", "ycombinator", "series a", "seed round", "venture", "funding"),
        boost=("raised", "series a", "series b", "seed", "funding"),
        window_days=10,
        news_query="startup funding",
        search_query='(("series a" OR "series b" OR "seed round" OR "funding round") (startup OR founded OR venture)) lang:en -is:retweet -is:reply',
    ),
    Lane(
        id="new-startups",
        title="New startups",
        accent="#9ece6a",
        summary="Launches and first announcements. Launch language ranks above general startup news.",
        accounts=(
            ("ProductHunt", "Product Hunt"),
            ("ycombinator", "Y Combinator"),
            ("IndieHackers", "Indie Hackers"),
            ("TechCrunch", "TechCrunch"),
        ),
        terms=("pre-seed", "out of stealth", "just launched", "startup", "yc"),
        boost=("just launched", "we're launching", "introducing", "pre-seed", "out of stealth", "we built", "now live", "first"),
        window_days=14,
        news_query="startup launch",
        search_query='(("just launched" OR "we\'re launching" OR "out of stealth" OR "pre-seed" OR introducing) (startup OR founded OR "we built")) lang:en -is:retweet -is:reply',
    ),
)

LANES_BY_ID = {lane.id: lane for lane in LANES}
