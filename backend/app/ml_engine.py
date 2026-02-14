import spacy
import dateparser

nlp = spacy.load("en_core_web_sm")

def extract_deadline_dates(text: str):
    doc = nlp(text)
    results = []
    for ent in doc.ents:
        if ent.label_ in ["DATE", "TIME"]:
            clean_date = dateparser.parse(ent.text)
            if clean_date:
                results.append(clean_date)
    return results