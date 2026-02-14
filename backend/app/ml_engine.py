import spacy
import dateparser # Tip: install this to handle "next Friday"

nlp = spacy.load("en_core_web_sm")

def extract_deadline_dates(text: str):
    doc = nlp(text)
    results = []
    for ent in doc.ents:
        if ent.label_ in ["DATE", "TIME"]:
            # Convert text like "Friday" to a real datetime object
            clean_date = dateparser.parse(ent.text)
            if clean_date:
                results.append(clean_date)
    return results