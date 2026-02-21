import os
import re
from flask import *
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import fitz  # PyMuPDF
import google.generativeai as genai
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Initialize Gemini model
model = genai.GenerativeModel("gemini-2.5-flash-preview-09-2025")

# Flask app setup
app = Flask(__name__)

# Email verification configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///papergen.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Login Manager Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize Flask-Mail and Serializer
mail = Mail(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# --- Database Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    contents = db.relationship('GeneratedContent', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class GeneratedContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content_type = db.Column(db.String(50), nullable=False)
    generated_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# File upload configuration
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# --- Helper Function ---
def extract_text_from_file(file_path):
    if file_path.endswith(".pdf"):
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# --- Routes ---
@app.route("/")
def home():
    if current_user.is_authenticated:
        history = GeneratedContent.query.filter_by(author=current_user).order_by(GeneratedContent.created_at.desc()).all()
        return render_template("index.html", history=history)
    else:
        return render_template("landing.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    # ... (registration logic remains unchanged)
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash('This username is already taken. Please choose another.', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('This email is already registered. Please try to log in.', 'danger')
            return redirect(url_for('register'))

        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        token = s.dumps(email, salt='email-confirm-salt')
        confirm_url = url_for('confirm_email', token=token, _external=True)
        html = render_template('email/activate.html', confirm_url=confirm_url)
        msg = Message('Confirm Your Email - PaperGen',
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[email],
                      html=html)
        mail.send(msg)

        flash('Registration successful! Please check your email to verify your account.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/confirm_email/<token>')
def confirm_email(token):
    # ... (email confirmation logic remains unchanged)
    try:
        email = s.loads(token, salt='email-confirm-salt', max_age=3600)
    except SignatureExpired:
        flash('The confirmation link has expired.', 'danger')
        return redirect(url_for('login'))
    except BadTimeSignature:
        flash('The confirmation link is invalid.', 'danger')
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first_or_404()

    if user.verified:
        flash('Account already confirmed. Please login.', 'info')
    else:
        user.verified = True
        db.session.commit()
        flash('Your account has been verified! You can now log in.', 'success')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (login logic remains unchanged)
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))

        if not user.verified:
            flash('Your account is not verified. Please check your email.', 'warning')
            return redirect(url_for('login'))

        login_user(user)
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # ... (logout logic remains unchanged)
    logout_user()
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    # ... (dashboard logic remains unchanged)
    contents = GeneratedContent.query.filter_by(author=current_user).order_by(GeneratedContent.created_at.desc()).all()
    return render_template('dashboard.html', contents=contents)

@app.route('/delete/<int:content_id>', methods=['POST'])
@login_required
def delete_content(content_id):
    # ... (delete logic remains unchanged)
    content_to_delete = GeneratedContent.query.get_or_404(content_id)
    if content_to_delete.author != current_user:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    db.session.delete(content_to_delete)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/generate_answers', methods=['POST'])
@login_required
def generate_answers():
    data = request.get_json()
    if not data or 'questions' not in data:
        return jsonify({'error': 'Missing questions data'}), 400

    original_questions = data['questions']

    answer_prompt = f"""
Act as an assistant creating a simple answer key document for an educator.
For each question provided below, generate a clear, well-structured model answer suitable for a handwritten answer paper. The answers should be of decent length and directly address the question.

**CRITICAL FORMATTING RULES:**
1.  **Strictly use this format ONLY:**
    Q1. [Full Question Text 1, if available, otherwise just Q1.]
    Answer:
    [Your model answer for the first question, written in plain text paragraphs.]

    Q2. [Full Question Text 2, if available, otherwise just Q2.]
    Answer:
    [Your model answer for the second question, written in plain text paragraphs.]

    ... and so on for all questions.
2.  **A single blank line MUST separate each complete Q/Answer block.** (e.g., between the end of Answer 1 and Q2.)
3.  **ABSOLUTELY DO NOT use tables.** Output MUST be plain text paragraphs.
4.  **DO NOT use markdown formatting** (like ###, ---, | pipes |, lists with *, -, or +). Just plain text paragraphs.
5.  **Use standard paragraph breaks** (a single blank line) within longer answers if needed.
6.  If the original question was a Multiple Choice Question (MCQ), use this format for the answer: `Answer) [Correct Option Letter]) [Correct Option Text]`, for example: `Answer) b) Option B`

**QUESTIONS TO ANSWER:**
{original_questions}

**MODEL ANSWER KEY (PLAIN TEXT ONLY, NO TABLES):**
"""

    try:
        response = model.generate_content(answer_prompt)

        raw_text = ""
        if hasattr(response, 'text'):
             raw_text = response.text
        elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
             raw_text = "".join(part.text for part in response.candidates[0].content.parts)
        else:
             print("Warning: Unexpected Gemini answer response structure in /generate_answers.")
             raw_text = "Could not generate answers properly."

        # --- FINAL REFINED CLEANING LOGIC V4 ---
        text = raw_text.strip()
        text = text.replace("**", "")
        text = text.replace("*", "")

        # Remove markdown table lines first
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if not re.match(r'^\s*\|.*\|?\s*$', line) and not re.match(r'^\s*\|?[:\- ]+\|?\s*$', line)]
        # Filter out completely empty lines resulting from stripping table lines etc.
        cleaned_lines = [line for line in cleaned_lines if line]
        text = '\n'.join(cleaned_lines)

        # Remove markdown headings
        text = re.sub(r'^[#]+\s+', '', text, flags=re.MULTILINE)

        # Ensure newline AFTER labels (handles Answer:, Answer), Description:)
        text = re.sub(r'^(Answer:|Answer\)|Description:)\s*([^\n])', r'\1\n\2', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^(Answer:|Answer\)|Description:)\s*$', r'\1\n', text, flags=re.MULTILINE | re.IGNORECASE)

        # Force a single blank line before any numbered item (Q1., 1., etc.) that isn't at the start of the string
        # Replace "\nQ?<num>." with "\n\nQ?<num>."
        text = re.sub(r'\n(Q?\d+\.)', r'\n\n\1', text)

        # Consolidate any sequence of 3 or more newlines down to exactly 2 (one blank line)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Final trim of leading/trailing whitespace just in case
        answers = text.strip()
        # --- END FINAL REFINED CLEANING LOGIC V4 ---


        return jsonify({'answers': answers})
    except Exception as e:
        print(f"Error generating answers: {e}")
        return jsonify({'error': 'Failed to generate answers'}), 500


@app.route('/generate_description', methods=['POST'])
@login_required
def generate_description():
    data = request.get_json()
    if not data or 'topics' not in data:
        return jsonify({'error': 'Missing topics data'}), 400

    original_topics = data['topics']

    description_prompt = f"""
You are an expert academic assistant. Your task is to provide a VERY CONCISE 2-3 sentence description (a "blurb") for each of the following presentation topics or project ideas.
This is for an educator to quickly understand the scope.

IMPORTANT: You MUST follow this exact format:
1. [Original Topic Title 1]
   Description: [Your 2-3 sentence description in plain text]

2. [Original Topic Title 2]
   Description: [Your 2-3 sentence description in plain text]

...and so on.

**CRITICAL FORMATTING RULES:**
- **A single blank line MUST separate each numbered topic.**
- **ABSOLUTELY NO tables.** Output MUST be plain text.
- **NO markdown formatting** (like ###, *, -, etc.). Just plain text.

Here are the topics/projects:
{original_topics}
"""
    try:
        response = model.generate_content(description_prompt)

        raw_text = ""
        if hasattr(response, 'text'):
             raw_text = response.text
        elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
             raw_text = "".join(part.text for part in response.candidates[0].content.parts)
        else:
             print("Warning: Unexpected Gemini answer response structure in /generate_description.")
             raw_text = "Could not generate descriptions properly."

        # --- FINAL REFINED CLEANING LOGIC V4 ---
        text = raw_text.strip()
        text = text.replace("**", "")
        text = text.replace("*", "")

        # Remove markdown table lines first
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if not re.match(r'^\s*\|.*\|?\s*$', line) and not re.match(r'^\s*\|?[:\- ]+\|?\s*$', line)]
        cleaned_lines = [line for line in cleaned_lines if line]
        text = '\n'.join(cleaned_lines)

        # Remove markdown headings
        text = re.sub(r'^[#]+\s+', '', text, flags=re.MULTILINE)

        # Ensure newline AFTER labels (handles Answer:, Answer), Description:)
        text = re.sub(r'^(Answer:|Answer\)|Description:)\s*([^\n])', r'\1\n\2', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^(Answer:|Answer\)|Description:)\s*$', r'\1\n', text, flags=re.MULTILINE | re.IGNORECASE)

        # Force a single blank line before any numbered item (Q1., 1., etc.) that isn't at the start of the string
        text = re.sub(r'\n(Q?\d+\.)', r'\n\n\1', text)

        # Consolidate any sequence of 3 or more newlines down to exactly 2 (one blank line)
        text = re.sub(r'\n{3,}', '\n\n', text)

        description = text.strip()
        # --- END FINAL REFINED CLEANING LOGIC V4 ---


        return jsonify({'description': description})
    except Exception as e:
        print(f"Error generating description: {e}")
        return jsonify({'error': 'Failed to generate description'}), 500


# --- DATA DICTIONARIES FOR PROMPTS ---

bloom_data = {
    "Remember": {
        "skill": "Ability to recall information like facts, conventions, definitions, jargon, etc. Ability to recall methodology and procedures, abstractions, principles, etc. Knowledge of dates, events, places. Mastery of subject matter.",
        "verbs": "list, define, tell, describe, recite, recall, identify, show, label, tabulate, quote, name, who, when, where"
    },
    "Understand": {
        "skill": "Understanding information. Grasp meaning. Translate knowledge into new context. Interpret facts, compare, contrast. Order, group, infer causes. Predict consequences.",
        "verbs": "describe, explain, paraphrase, restate, associate, contrast, summarize, differentiate, interpret, discuss"
    },
    "Apply": {
        "skill": "Use information. Use methods, concepts, laws, theories in new situations. Solve problems using required skills or knowledge. Demonstrating correct usage of a method or procedure.",
        "verbs": "calculate, predict, apply, solve, illustrate, use, demonstrate, determine, model, experiment, show, examine, modify"
    },
    "Analyse": {
        "skill": "Break down a complex problem into parts. Identify relationships between parts. Identify missing, redundant, or contradictory information.",
        "verbs": "classify, outline, break down, categorize, analyze, diagram, illustrate, infer, select"
    },
    "Evaluate": {
        "skill": "Compare and discriminate between ideas. Assess value of theories, presentations. Make choices based on reasoned argument. Verify value of evidence. Recognize subjectivity. Use definite criteria for judgments.",
        "verbs": "assess, decide, choose, rank, grade, test, measure, defend, recommend, convince, select, judge, support, conclude, argue, justify, compare, summarize, evaluate"
    },
    "Create": {
        "skill": "Use old ideas to create new ones. Combine parts to make a new whole. Generalize from given facts. Relate knowledge from several areas. Predict, draw conclusions.",
        "verbs": "design, formulate, build, invent, create, compose, generate, derive, modify, develop, integrate"
    }
}

difficulty_data = {
    "Easy": "Target a foundational level. Questions should be straightforward, covering core concepts directly. Avoid complex scenarios or multi-step reasoning.",
    "Moderate": "Target an intermediate level. Questions should require some interpretation, combining concepts, or applying knowledge to simple, new situations.",
    "Challenging": "Target an advanced level. Questions should be complex, requiring synthesis, critical analysis, or solving problems with non-obvious steps.",
    "Expert": "Target a specialist level. Questions should require deep, nuanced understanding, evaluation of competing approaches, or justification of complex decisions."
}

@app.route("/process", methods=["POST"])
@login_required
def process():
    query = request.form.get("query", "").strip()
    content_type = request.form.get("content_type", "Quiz")
    bloom_level = request.form.get("bloom_level", "Remember")
    difficulty_level = request.form.get("difficulty_level", "Moderate")
    file = request.files.get("file")
    extracted_text = ""

    if file and file.filename != "":
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        extracted_text = extract_text_from_file(filepath)

    if not extracted_text and not query:
        return jsonify({"result": "Please provide input or upload a file."})

    level_data = bloom_data.get(bloom_level, bloom_data["Remember"])
    skill_instruction = level_data["skill"]
    verb_examples = level_data["verbs"]

    bloom_prompt_injection = f"""
Your generation must target the '{bloom_level}' level of Bloom's Taxonomy.
This means you should focus on the following skills: {skill_instruction}
When creating questions or topics, try to use verbs such as: {verb_examples}.
"""

    diff_data = difficulty_data.get(difficulty_level, difficulty_data["Moderate"])
    difficulty_prompt_injection = f"""
The overall difficulty must be '{difficulty_level}'.
This means: {diff_data}
"""

    # --- UPDATED Prompts to include blank line instruction & no table emphasis ---
    if content_type.lower() == "quiz":
        prompt = f"""
You are an expert quiz generator. Generate exactly 15 multiple choice questions (MCQs).
{bloom_prompt_injection}
{difficulty_prompt_injection}
Do not repeat questions or copy text directly—create unique questions based on concepts. Avoid markdown formatting like ### or * or tables (|---|) in the output. Output MUST be plain text only.

Format (A single blank line MUST separate each question):
1. Question?
a) Option A
b) Option B
c) Option C
d) Option D

2. Question?
a) Option A
b) Option B
c) Option C
d) Option D

... and so on.

Content:
{extracted_text or query}
"""
    elif content_type.lower() == "scenario":
        prompt = f"""
You are an academic question paper generator. Create 10 descriptive scenario-based questions (5-10 marks each).
{bloom_prompt_injection}
{difficulty_prompt_injection}
Each question should present a short scenario or case study, followed by a question that requires analysis, application, or evaluation. Avoid markdown formatting like ### or * or tables (|---|) in the output. Output MUST be plain text only.

Format (A single blank line MUST separate each question):
"Heading Related to Topic"
1. [Scenario Description] ... Question based on the scenario?

2. [Scenario Description] ... Question based on the scenario?

... and so on.

Content:
{extracted_text or query}
"""
    elif content_type.lower() == "assignment":
        prompt = f"""
You are an academic question paper generator. Create 15 descriptive questions (5 marks each).
{bloom_prompt_injection}
{difficulty_prompt_injection}
Each question should test understanding and originality. Avoid markdown formatting like ### or * or tables (|---|) in the output. Output MUST be plain text only.

Format (A single blank line MUST separate each question):
"Heading Related to Topic"
1. Question one?

2. Question two?

... and so on.

Content:
{extracted_text or query}
"""
    elif content_type.lower() == "presentation":
        prompt = f"""
You are an academic assistant. Generate 15 unique presentation topics.
{bloom_prompt_injection}
{difficulty_prompt_injection}
Each topic must follow the exact format below. A single blank line MUST separate each topic. Output MUST be plain text only.

Example Format:
1. Title
   Subtitle (optional)

2. Another Title
   Another Subtitle (optional)

... and so on.

Rules:
- No bold text
- No markdown formatting like ### or * or tables (|---|)
- No extra explanation
- Exactly 15 topics

Content:
{extracted_text or query}
"""
    elif content_type.lower() == "mini project":
        prompt = f"""
You are an academic assistant. Generate exactly 15 mini project ideas.
{bloom_prompt_injection}
{difficulty_prompt_injection}
Each project idea must follow the exact format below. A single blank line MUST separate each project idea. Output MUST be plain text only.

Example Format:
1. Project title
   A short 4–5 line problem statement explaining purpose and objectives.

2. Another Project title
   A different short 4–5 line problem statement explaining purpose and objectives.

... and so on.

Rules:
- No bold text
- No markdown formatting like ### or * or tables (|---|)
- No extra explanation
- Exactly 15 items

Content:
{extracted_text or query}
"""
    elif content_type.lower() == "group discussion":
        prompt = f"""
You are an academic assistant. Generate 15 unique topics for a group discussion.
{bloom_prompt_injection}
{difficulty_prompt_injection}
Each topic should be debatable, open-ended, and relevant. Output MUST be plain text only.

Format (A single blank line MUST separate each topic):
1. Topic Title (e.g., "The Ethics of AI in Healthcare")

2. Topic Title

... and so on.

Rules:
- No bold text
- No markdown formatting like ### or * or tables (|---|)
- No extra explanation
- Exactly 15 topics

Content:
{extracted_text or query}
"""
    else:
        prompt = f"""
Generate structured {content_type.lower()} content based on the following input. Avoid markdown formatting like ### or * or tables (|---|). Output MUST be plain text only.
{bloom_prompt_injection}
{difficulty_prompt_injection}
Content:
{extracted_text or query}
"""
    # --- END UPDATED Prompts ---

    try:
        response = model.generate_content(prompt)

        raw_text = ""
        if hasattr(response, 'text'):
            raw_text = response.text
        elif response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            raw_text = "".join(part.text for part in response.candidates[0].content.parts)
        else:
            print("Warning: Unexpected Gemini response structure in /process")
            raw_text = "Could not generate content properly."

        # --- FINAL REFINED CLEANING LOGIC V4 ---
        text = raw_text.strip()
        text = text.replace("**", "")
        text = text.replace("*", "")

        # Remove markdown table lines first
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if not re.match(r'^\s*\|.*\|?\s*$', line) and not re.match(r'^\s*\|?[:\- ]+\|?\s*$', line)]
        cleaned_lines = [line for line in cleaned_lines if line]
        text = '\n'.join(cleaned_lines)

        # Remove markdown headings
        text = re.sub(r'^[#]+\s+', '', text, flags=re.MULTILINE)

        # Ensure newline AFTER labels (handles Answer:, Answer), Description:)
        text = re.sub(r'^(Answer:|Answer\)|Description:)\s*([^\n])', r'\1\n\2', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^(Answer:|Answer\)|Description:)\s*$', r'\1\n', text, flags=re.MULTILINE | re.IGNORECASE)

        # Force a single blank line before any numbered item (Q1., 1., etc.) that isn't at the start of the string
        text = re.sub(r'\n(Q?\d+\.)', r'\n\n\1', text)

        # Consolidate any sequence of 3 or more newlines down to exactly 2 (one blank line)
        text = re.sub(r'\n{3,}', '\n\n', text)

        cleaned_text = text.strip()
        # --- END FINAL REFINED CLEANING LOGIC V4 ---


        new_content = GeneratedContent(
            content_type=content_type,
            generated_text=cleaned_text,
            author=current_user
        )
        db.session.add(new_content)
        db.session.commit()

        return jsonify({"result": cleaned_text})
    except Exception as e:
        print("Error from Gemini:", e)
        return jsonify({"result": "Error from model: Please check your input or API key."})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

