import os
import joblib
import shutil
from sklearn.linear_model import SGDClassifier
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.pipeline import Pipeline

MODEL_DIR = "user_models"
BASE_MODEL_PATH = "base_model.pkl"

if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

def create_base_model():
    vect = HashingVectorizer(stop_words='english', n_features=2**20, alternate_sign=False)
    clf = SGDClassifier(
        loss='log_loss', 
        penalty='l2', 
        alpha=1e-4, 
        random_state=42, 
        max_iter=5, 
        tol=None
    )
    
    pipeline = Pipeline([
        ('vect', vect),
        ('clf', clf),
    ])
    
    dummy_texts = [
        "limited time offer discount sale buy now cheap price generic spam",
        "urgent meeting schedule project deadline internship offer letter application"
    ]
    dummy_labels = [0, 1]
    dummy_X = vect.transform(dummy_texts)
    clf.partial_fit(dummy_X, dummy_labels, classes=[0, 1])
    joblib.dump(pipeline, BASE_MODEL_PATH)
    print(f"✅ Balanced Base model created at {BASE_MODEL_PATH}")
    return pipeline

def get_user_model(user_email: str):
    user_model_path = os.path.join(MODEL_DIR, f"{user_email}.pkl")
    if os.path.exists(user_model_path):
        try:
            return joblib.load(user_model_path)
        except:
            print(f"⚠️ Corrupt model for {user_email}, resetting to base.")
            if os.path.exists(user_model_path):
                os.remove(user_model_path)
    if not os.path.exists(BASE_MODEL_PATH):
        create_base_model()
    shutil.copy(BASE_MODEL_PATH, user_model_path)
    return joblib.load(user_model_path)

def update_user_model(user_email: str, text: str, is_important: bool):
    model = get_user_model(user_email)
    vect = model.named_steps['vect']
    clf = model.named_steps['clf']
    label = 1 if is_important else 0
    X = vect.transform([text])
    clf.partial_fit(X, [label])
    user_model_path = os.path.join(MODEL_DIR, f"{user_email}.pkl")
    joblib.dump(model, user_model_path)
    print(f"🧠 Updated brain for {user_email}")