LastDay 📅AI-Powered Deadline Manager & Email OrganizerNever miss a deadline again. LastDay connects to your Gmail, uses Machine Learning to filter spam, and intelligently extracts hidden due dates from email bodies (e.g., "Project submission is due next Friday at 5 PM").📸 ScreenshotsSmart DashboardCalendar ViewSecure LoginPrioritized deadline listMonthly overviewGoogle OAuth 2.0(Note: Replace the placeholder links above with actual screenshots of your app once uploaded to your repo)🚀 Key Features🧠 Intelligent ParsingNatural Language Processing: Extracts dates from complex sentences like "Test scheduled for tomorrow at 10 AM" or "Assignment due on or before 16th Feb".Context Awareness: Distinguishes between the "Sent Date" and the actual "Due Date."Heuristic Fallback: Automatically selects the most logical deadline if multiple dates are mentioned in an email thread.🛡️ Smart Spam FilterCustom ML Model: Uses a Scikit-learn classifier to distinguish between important academic/work emails and newsletters/promotions.Safety First: "Fail-safe" architecture ensures that if the AI is unsure, the email is marked as relevant so you never miss important info.🔒 Privacy & SecurityIn-Memory Processing: Emails are processed in RAM and are never stored in a database.OAuth 2.0: Uses secure Google Sign-In; the app never sees your password.Direct Sync: The backend acts as a pass-through processor between Gmail and your phone.🛠️ Tech StackFrontend (Mobile App)Framework: Flutter (Dart)State Management: setState (Optimized for performance)Networking: http package with custom interceptorsUI: Material Design 3Backend (API)Framework: FastAPI (Python)Server: Uvicorn (ASGI)ML Libraries: scikit-learn, joblib, numpyText Processing: BeautifulSoup4 (HTML parsing), dateparser (Date extraction)Google Integration: google-auth, google-api-python-clientInfrastructureHosting: Render (Cloud deployment)Version Control: Git & GitHub📂 Project StructureBashLastDay/
├── backend/                 # Python FastAPI Server
│   ├── app/
│   │   ├── main.py          # API Entry Point
│   │   ├── gservices.py     # Gmail API Logic
│   │   ├── ml_engine.py     # Spam Classification Logic
│   │   ├── model_manager.py # Per-user model handling
│   │   └── schemas.py       # Pydantic Data Models
│   ├── requirements.txt     # Python Dependencies
│   └── Procfile             # Render Deployment Config
│
├── glassify/                # Flutter App (Frontend)
│   ├── lib/
│   │   ├── screens/         # UI Screens (Home, Login)
│   │   ├── services/        # API & Auth Services
│   │   ├── models/          # Dart Data Models
│   │   └── main.dart        # App Entry Point
│   ├── assets/              # Images & Icons
│   └── pubspec.yaml         # Flutter Dependencies
⚙️ Installation & Local SetupIf you want to run the code yourself or contribute, follow these steps.PrerequisitesFlutter SDK installed.Python 3.10+ installed.A Google Cloud Project with Gmail API enabled.1. Backend SetupBash# Clone the repo
git clone https://github.com/YOUR_USERNAME/LastDay.git
cd LastDay/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up Environment Variables
# Create a .env file in backend/app/ with:
# GOOGLE_CLIENT_ID=your_id
# GOOGLE_CLIENT_SECRET=your_secret

# Run the server
uvicorn app.main:app --reload
2. Frontend SetupBashcd ../glassify

# Get dependencies
flutter pub get

# Setup Secrets
# Create lib/secrets.dart and add:
# const String kGoogleClientId = "YOUR_CLIENT_ID";

# Run the app
flutter run
☁️ DeploymentBackend (Render)The backend is deployed on Render using the free tier.Build Command: pip install -r requirements.txtStart Command: uvicorn app.main:app --host 0.0.0.0 --port 10000Frontend (Android)The APK is built using GitHub Actions (or manually) and released via GitHub Releases.Go to the Releases section.Download app-release.apk.Install on your Android device.🛡️ Privacy PolicyLastDay is a student project designed with privacy in mind.Data Usage: The app only accesses emails to extract deadlines and classify importance.Data Storage: No email content is stored on our servers. All processing happens in real-time (in-memory).Third Parties: Data is not shared with any third parties other than Google (for fetching the emails).🤝 ContributingContributions are welcome!Fork the ProjectCreate your Feature Branch (git checkout -b feature/AmazingFeature)Commit your Changes (git commit -m 'Add some AmazingFeature')Push to the Branch (git push origin feature/AmazingFeature)Open a Pull Request📞 ContactVedit - GitHub ProfileProject Link: https://github.com/YOUR_USERNAME/LastDay
