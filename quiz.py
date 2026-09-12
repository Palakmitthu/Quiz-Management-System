from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "online_quiz_secret_key"

DATABASE = "quiz.db"


# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student'
        )
    """)

    # Quizzes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL
        )
    """)

    # Questions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            option1 TEXT NOT NULL,
            option2 TEXT NOT NULL,
            option3 TEXT NOT NULL,
            option4 TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        )
    """)

    # Results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        )
    """)

    # Create default admin
    admin = cursor.execute(
        "SELECT * FROM users WHERE email = ?",
        ("admin@gmail.com",)
    ).fetchone()

    if not admin:
        cursor.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
        """, (
            "Administrator",
            "admin@gmail.com",
            generate_password_hash("admin123"),
            "admin"
        ))

    # Add sample quiz if no quiz exists
    quiz_count = cursor.execute(
        "SELECT COUNT(*) FROM quizzes"
    ).fetchone()[0]

    if quiz_count == 0:
        cursor.execute("""
            INSERT INTO quizzes (title, subject)
            VALUES (?, ?)
        """, ("Python Basics Quiz", "Python"))

        quiz_id = cursor.lastrowid

        sample_questions = [
            (
                quiz_id,
                "Which keyword is used to define a function in Python?",
                "function",
                "def",
                "fun",
                "define",
                "def"
            ),
            (
                quiz_id,
                "Which data type is used to store multiple values in Python?",
                "List",
                "Integer",
                "Boolean",
                "Float",
                "List"
            ),
            (
                quiz_id,
                "Which symbol is used for comments in Python?",
                "#",
                "//",
                "/*",
                "--",
                "#"
            ),
            (
                quiz_id,
                "Which function is used to display output in Python?",
                "display()",
                "show()",
                "print()",
                "output()",
                "print()"
            ),
            (
                quiz_id,
                "Which of these is a Python framework?",
                "Flask",
                "Photoshop",
                "Excel",
                "Oracle",
                "Flask"
            )
        ]

        cursor.executemany("""
            INSERT INTO questions
            (quiz_id, question, option1, option2, option3, option4, correct_answer)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, sample_questions)

    conn.commit()
    conn.close()


# ---------------- LOGIN DECORATORS ----------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            flash("Admin access required.")
            return redirect(url_for("dashboard"))

        return f(*args, **kwargs)

    return decorated_function


# ---------------- HOME ----------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO users (name, email, password)
                VALUES (?, ?, ?)
            """, (name, email, hashed_password))

            conn.commit()
            conn.close()

            flash("Registration successful. Please login.")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            conn.close()
            flash("Email already registered.")

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin"))

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out.")

    return redirect(url_for("index"))


# ---------------- STUDENT DASHBOARD ----------------

@app.route("/dashboard")
@login_required
def dashboard():

    conn = get_db()

    quizzes = conn.execute(
        "SELECT * FROM quizzes"
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        quizzes=quizzes
    )


# ---------------- START QUIZ ----------------

@app.route("/quiz/<int:quiz_id>")
@login_required
def quiz(quiz_id):

    conn = get_db()

    quiz_data = conn.execute(
        "SELECT * FROM quizzes WHERE id = ?",
        (quiz_id,)
    ).fetchone()

    questions = conn.execute(
        "SELECT * FROM questions WHERE quiz_id = ?",
        (quiz_id,)
    ).fetchall()

    conn.close()

    if not quiz_data:
        flash("Quiz not found.")
        return redirect(url_for("dashboard"))

    return render_template(
        "quiz.html",
        quiz=quiz_data,
        questions=questions
    )


# ---------------- SUBMIT QUIZ ----------------

@app.route("/submit_quiz/<int:quiz_id>", methods=["POST"])
@login_required
def submit_quiz(quiz_id):

    conn = get_db()

    questions = conn.execute(
        "SELECT * FROM questions WHERE quiz_id = ?",
        (quiz_id,)
    ).fetchall()

    score = 0

    for question in questions:

        answer = request.form.get(
            "question_" + str(question["id"])
        )

        if answer == question["correct_answer"]:
            score += 1

    total = len(questions)

    conn.execute("""
        INSERT INTO results
        (user_id, quiz_id, score, total)
        VALUES (?, ?, ?, ?)
    """, (
        session["user_id"],
        quiz_id,
        score,
        total
    ))

    conn.commit()

    result_id = conn.execute(
        "SELECT last_insert_rowid()"
    ).fetchone()[0]

    conn.close()

    return redirect(
        url_for("result", result_id=result_id)
    )


# ---------------- RESULT ----------------

@app.route("/result/<int:result_id>")
@login_required
def result(result_id):

    conn = get_db()

    result_data = conn.execute("""
        SELECT results.*, quizzes.title
        FROM results
        JOIN quizzes ON results.quiz_id = quizzes.id
        WHERE results.id = ?
    """, (result_id,)).fetchone()

    conn.close()

    if not result_data:
        flash("Result not found.")
        return redirect(url_for("dashboard"))

    percentage = 0

    if result_data["total"] > 0:
        percentage = (
            result_data["score"] /
            result_data["total"]
        ) * 100

    return render_template(
        "result.html",
        result=result_data,
        percentage=round(percentage, 2)
    )


# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin")
@admin_required
def admin():

    conn = get_db()

    quizzes = conn.execute(
        "SELECT * FROM quizzes"
    ).fetchall()

    results = conn.execute("""
        SELECT
            results.id,
            users.name,
            users.email,
            quizzes.title,
            results.score,
            results.total,
            results.date
        FROM results
        JOIN users ON results.user_id = users.id
        JOIN quizzes ON results.quiz_id = quizzes.id
        ORDER BY results.date DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        quizzes=quizzes,
        results=results
    )


# ---------------- ADD QUIZ ----------------

@app.route("/admin/add_quiz", methods=["GET", "POST"])
@admin_required
def add_quiz():

    if request.method == "POST":

        title = request.form["title"]
        subject = request.form["subject"]

        conn = get_db()

        cursor = conn.execute("""
            INSERT INTO quizzes (title, subject)
            VALUES (?, ?)
        """, (title, subject))

        quiz_id = cursor.lastrowid

        conn.commit()
        conn.close()

        flash("Quiz created successfully.")

        return redirect(
            url_for("add_questions", quiz_id=quiz_id)
        )

    return render_template("add_quiz.html")


# ---------------- ADD QUESTIONS ----------------

@app.route("/admin/add_questions/<int:quiz_id>", methods=["GET", "POST"])
@admin_required
def add_questions(quiz_id):

    conn = get_db()

    quiz_data = conn.execute(
        "SELECT * FROM quizzes WHERE id = ?",
        (quiz_id,)
    ).fetchone()

    if not quiz_data:
        conn.close()
        flash("Quiz not found.")
        return redirect(url_for("admin"))

    if request.method == "POST":

        question = request.form["question"]
        option1 = request.form["option1"]
        option2 = request.form["option2"]
        option3 = request.form["option3"]
        option4 = request.form["option4"]
        correct_answer = request.form["correct_answer"]

        conn.execute("""
            INSERT INTO questions
            (
                quiz_id,
                question,
                option1,
                option2,
                option3,
                option4,
                correct_answer
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            quiz_id,
            question,
            option1,
            option2,
            option3,
            option4,
            correct_answer
        ))

        conn.commit()

        flash("Question added successfully.")

    questions = conn.execute("""
        SELECT * FROM questions
        WHERE quiz_id = ?
    """, (quiz_id,)).fetchall()

    conn.close()

    return render_template(
        "add_questions.html",
        quiz=quiz_data,
        questions=questions
    )


# ---------------- DELETE QUIZ ----------------

@app.route("/admin/delete_quiz/<int:quiz_id>")
@admin_required
def delete_quiz(quiz_id):

    conn = get_db()

    conn.execute(
        "DELETE FROM questions WHERE quiz_id = ?",
        (quiz_id,)
    )

    conn.execute(
        "DELETE FROM quizzes WHERE id = ?",
        (quiz_id,)
    )

    conn.commit()
    conn.close()

    flash("Quiz deleted.")

    return redirect(url_for("admin"))


# ---------------- DELETE QUESTION ----------------

@app.route("/admin/delete_question/<int:question_id>/<int:quiz_id>")
@admin_required
def delete_question(question_id, quiz_id):

    conn = get_db()

    conn.execute(
        "DELETE FROM questions WHERE id = ?",
        (question_id,)
    )

    conn.commit()
    conn.close()

    flash("Question deleted.")

    return redirect(
        url_for("add_questions", quiz_id=quiz_id)
    )


# ---------------- RUN APP ----------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True)