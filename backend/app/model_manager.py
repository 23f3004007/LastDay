import os
import joblib
import shutil
from sklearn.linear_model import SGDClassifier
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.pipeline import Pipeline

# Directory to store user models
MODEL_DIR = "user_models"
BASE_MODEL_PATH = "base_model.pkl"

# Ensure directory exists
if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

def create_base_model():
    """
    Creates a generic starting model.
    """
    # 1. Define the components
    vect = HashingVectorizer(stop_words='english', n_features=2**20, alternate_sign=False)
    
    # --- FIX: Removed class_weight='balanced' to prevent crash ---
    clf = SGDClassifier(
        loss='log_loss', 
        penalty='l2', 
        alpha=1e-4, 
        random_state=42, 
        max_iter=5, 
        tol=None
        # class_weight parameter removed
    )
    
    # 2. Bundle them in a pipeline for easy saving/loading
    pipeline = Pipeline([
        ('vect', vect),
        ('clf', clf),
    ])
    
    # 3. INITIALIZATION & BALANCING
    # We manually balance the starting brain by giving it 1 strong SPAM and 1 strong RELEVANT example.
    dummy_texts = [
        "limited time offer discount sale buy now cheap price generic spam", # Class 0 (Spam)
        "urgent meeting schedule project deadline internship offer letter application" # Class 1 (Relevant)
    ]
    dummy_labels = [0, 1]
    
    # Transform text to numbers manually
    dummy_X = vect.transform(dummy_texts)
    
    # Teach it both classes immediately
    clf.partial_fit(dummy_X, dummy_labels, classes=[0, 1])
    
    # 4. Save
    joblib.dump(pipeline, BASE_MODEL_PATH)
    print(f"✅ Balanced Base model created at {BASE_MODEL_PATH}")
    return pipeline

def get_user_model(user_email: str):
    """
    Loads a specific user's model. If they don't have one, copies the Base Model.
    """
    user_model_path = os.path.join(MODEL_DIR, f"{user_email}.pkl")
    
    # 1. If user already has a model, load it
    if os.path.exists(user_model_path):
        try:
            return joblib.load(user_model_path)
        except:
            print(f"⚠️ Corrupt model for {user_email}, resetting to base.")
            if os.path.exists(user_model_path):
                os.remove(user_model_path)
    
    # 2. If no base model exists, create it (First run only)
    if not os.path.exists(BASE_MODEL_PATH):
        create_base_model()
        
    # 3. Create a personalized copy for this user
    shutil.copy(BASE_MODEL_PATH, user_model_path)
    return joblib.load(user_model_path)

def update_user_model(user_email: str, text: str, is_important: bool):
    """
    Updates the user's model based on their feedback.
    """
    model = get_user_model(user_email)
    
    # 1. Unpack the pipeline components
    vect = model.named_steps['vect']
    clf = model.named_steps['clf']
    
    # 2. Prepare Data
    label = 1 if is_important else 0
    X = vect.transform([text])
    
    # 3. Learn (Partial Fit)
    clf.partial_fit(X, [label])
    
    # 4. Save the smarter brain back to disk
    user_model_path = os.path.join(MODEL_DIR, f"{user_email}.pkl")
    joblib.dump(model, user_model_path)
    print(f"🧠 Updated brain for {user_email}")