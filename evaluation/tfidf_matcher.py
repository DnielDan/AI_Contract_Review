"""The inherited Spring 2024 TF-IDF matcher, kept only as the accuracy baseline for the AI review.

The app no longer uses it: OSP will use the tool only with an approved AI provider, so there is no
fallback to this matcher (see docs/AI_REVIEW.md). The logic is unchanged from what produced
evaluation/results/baseline_*.md, so the baseline can be reproduced. That includes two known matcher
bugs left unfixed on purpose (US-14 c): sk_cosine_sim fits a new vectorizer for every pair of sentences,
and flag_sentences keeps the last match above the threshold for a sentence rather than the best one.
"""
from nltk.tokenize import sent_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Similarity score above which a sentence is flagged
DEFAULT_SIMILARITY_THRESHOLD = 0.20


# Returns the cosine similarity matrix of two sentences' TF-IDF vectors; [0][1] is their similarity
def sk_cosine_sim(sen1, sen2):
    vect = TfidfVectorizer(min_df=1, stop_words="english")
    vectors = vect.fit_transform([sen1, sen2])
    return cosine_similarity(vectors)


# Flags each contract sentence whose similarity to a Common Problem in the Ts&Cs Matrix is above the
# threshold. Returns {sentence: details}, with the same detail names as llm_review._issue_details.
def flag_sentences(tnc_dictionary, contract_text, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    contract_sentences = sent_tokenize(contract_text)
    flagged_sentences = {}

    for sheet_name, sub_dict in tnc_dictionary.items():
        if "Common Problems" in sub_dict:
            preferred_language = sub_dict.get("Auburn's Preferred Language", [])
            why = sub_dict.get("Why", [])
            response = sub_dict.get("1st response to Sponsor", [])
            for sentence in contract_sentences:
                for i, value in enumerate(sub_dict["Common Problems"]):
                    similarity = sk_cosine_sim(value, sentence)
                    if similarity[0][1] > threshold:
                        flagged_sentences[sentence] = {
                            "Problem Category": sheet_name,
                            "Common Problems": value,
                            "Preferred Language": preferred_language,
                            "Why": why[i],
                            "1st response to Sponsor": response[i],
                            "Confidence": similarity[0][1],
                        }

    return flagged_sentences
