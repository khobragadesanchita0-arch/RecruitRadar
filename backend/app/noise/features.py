import re
from typing import Any, Dict, List, Set

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd",
    "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those",
    "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll",
    "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's",
    "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't",
    "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}

TECH_RELEASE_YEARS = {
    "kubernetes": 2014,
    "k8s": 2014,
    "docker": 2013,
    "react": 2013,
    "vue": 2014,
    "angular": 2016,
    "rust": 2015,
    "golang": 2009,
    "go": 2009,
    "swift": 2014,
    "kotlin": 2011,
    "typescript": 2012,
    "fastapi": 2018,
    "next.js": 2016,
    "nextjs": 2016,
    "graphql": 2015,
    "kafka": 2011,
    "pytorch": 2016,
    "tensorflow": 2015,
}

def tokenize(text: str) -> List[str]:
    return re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())

def compute_term_frequencies(text: str) -> Dict[str, int]:
    tokens = tokenize(text)
    freqs: Dict[str, int] = {}
    for tok in tokens:
        if tok not in STOPWORDS and len(tok) > 2:
            freqs[tok] = freqs.get(tok, 0) + 1
    return freqs

def compute_type_token_ratio(text: str) -> float:
    tokens = tokenize(text)
    if not tokens:
        return 1.0
    unique = set(tokens)
    return len(unique) / len(tokens)

def compute_jaccard_similarity(s1: str, s2: str) -> float:
    set1 = set(tokenize(s1)) - STOPWORDS
    set2 = set(tokenize(s2)) - STOPWORDS
    if not set1 or not set2:
        return 0.0
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union)

def split_sentences(text: str) -> List[str]:
    # Split by periods, exclamation marks, question marks, and newlines
    raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    cleaned = []
    for s in raw_sentences:
        st = s.strip().rstrip(":")
        # Sentence must have at least 4 words
        words = [w for w in tokenize(st) if w not in STOPWORDS]
        if len(words) >= 4:
            cleaned.append(st)
    return cleaned
